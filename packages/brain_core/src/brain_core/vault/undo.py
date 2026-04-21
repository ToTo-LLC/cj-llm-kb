"""Undo log replay — reverts a previously applied PatchSet.

Plan 07 Task 4 extends the on-disk format with a ``RENAME_DOMAIN`` kind.
The original Plan 01 ``PATH``/``NEW``/``PREV_LEN``/``END_PREV`` per-file
record format is unchanged; the new kind sits alongside as a discrete
record with a different first line (``KIND\trename_domain``). When
``revert`` reads a file, it routes by the leading marker:

* ``KIND\trename_domain`` — handled by ``_revert_rename_domain``.
* anything else — replayed by the legacy per-file replay loop.

This shape keeps `brain_undo_last` blind to the kind: a single undo_id
fully reverses whatever was logged.
"""

from __future__ import annotations

import os
from pathlib import Path


class UndoLog:
    def __init__(self, *, vault_root: Path) -> None:
        self.vault_root = vault_root.resolve()
        self._dir = self.vault_root / ".brain" / "undo"

    def revert(self, undo_id: str) -> None:
        record = (self._dir / f"{undo_id}.txt").read_text(encoding="utf-8")
        lines = record.split("\n")
        if lines and lines[0] == "KIND\trename_domain":
            self._revert_rename_domain(lines[1:])
            return
        self._revert_per_file(lines)

    @staticmethod
    def _revert_per_file(lines: list[str]) -> None:
        i = 0
        while i < len(lines):
            if not lines[i].startswith("PATH\t"):
                i += 1
                continue
            path = Path(lines[i].split("\t", 1)[1])
            i += 1
            if i < len(lines) and lines[i] == "NEW":
                if path.exists():
                    path.unlink()
                i += 1
            elif i < len(lines) and lines[i].startswith("PREV_LEN\t"):
                i += 1
                prev_lines: list[str] = []
                while i < len(lines) and lines[i] != "END_PREV":
                    prev_lines.append(lines[i])
                    i += 1
                i += 1  # skip END_PREV
                path.write_text("\n".join(prev_lines), encoding="utf-8")

    def _revert_rename_domain(self, lines: list[str]) -> None:
        """Reverse a ``brain_rename_domain`` operation.

        Record shape (after the leading ``KIND`` line):

            FROM\t<from-slug>
            TO\t<to-slug>
            PATH\t<absolute-path-of-edited-file>
            PREV_LEN\t<n>
            <prev-content>
            END_PREV
            ... repeated per file ...

        Order matters: the folder rename is the last thing that happened
        on apply, so it is the first thing we undo on revert (so the
        per-file rewrites land back in the original ``<from>/`` tree).
        """
        from_slug: str | None = None
        to_slug: str | None = None
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("FROM\t"):
                from_slug = line.split("\t", 1)[1]
            elif line.startswith("TO\t"):
                to_slug = line.split("\t", 1)[1]
            elif line.startswith("PATH\t"):
                break
            i += 1

        if from_slug is None or to_slug is None:
            raise ValueError("rename_domain undo record missing FROM / TO header")

        from_dir = self.vault_root / from_slug
        to_dir = self.vault_root / to_slug
        # Reverse the folder rename first so subsequent per-file paths
        # written via the FROM-rooted absolute path resolve again.
        if to_dir.exists() and not from_dir.exists():
            os.rename(to_dir, from_dir)

        # Now replay the per-file edits. The absolute paths in the record
        # already point under <from>/ (we wrote the records BEFORE the
        # folder rename in the apply path).
        self._revert_per_file(lines[i:])
