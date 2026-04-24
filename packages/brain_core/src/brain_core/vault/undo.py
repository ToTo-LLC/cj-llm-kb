"""Undo log replay — reverts a previously applied PatchSet.

Plan 07 Task 4 extends the on-disk format with a ``RENAME_DOMAIN`` kind.
The original Plan 01 ``PATH``/``NEW``/``PREV_LEN``/``END_PREV`` per-file
record format is unchanged; the new kind sits alongside as a discrete
record with a different first line (``KIND\trename_domain``). Plan 07
Task 25 sub-task A adds a third kind ``KIND\tdelete_domain`` for the
Manage Domains "Delete" action. When ``revert`` reads a file, it routes
by the leading marker:

* ``KIND\trename_domain`` — handled by ``_revert_rename_domain``.
* ``KIND\tdelete_domain`` — handled by ``_revert_delete_domain``.
* anything else — replayed by the legacy per-file replay loop.

This shape keeps `brain_undo_last` blind to the kind: a single undo_id
fully reverses whatever was logged.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _consume_prev_chars(lines: list[str], start: int, prev_len: int) -> tuple[str, int]:
    """Consume enough list elements (rejoined with ``\\n``) to total exactly
    ``prev_len`` characters, returning ``(prev_content, next_index)``.

    The undo writer joins the per-file record with ``\\n``, so a multi-line
    prev value is split across consecutive ``lines`` entries. The recorded
    ``PREV_LEN`` is the original character count of the un-split string —
    walking by that count is independent of any sentinel that might appear
    inside the content (issue #25).
    """
    consumed_chars = 0
    consumed_parts: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        sep_len = 1 if consumed_parts else 0  # the joining "\n" between parts
        candidate_total = consumed_chars + sep_len + len(line)
        if candidate_total > prev_len:
            # Take only what fits to land on exactly prev_len chars.
            take = prev_len - consumed_chars - sep_len
            if take >= 0:
                consumed_parts.append(line[:take])
            i += 1
            break
        consumed_parts.append(line)
        consumed_chars = candidate_total
        i += 1
        if consumed_chars == prev_len:
            break
    return "\n".join(consumed_parts), i


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
        if lines and lines[0] == "KIND\tdelete_domain":
            self._revert_delete_domain(lines[1:])
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
                prev_len = int(lines[i].split("\t", 1)[1])
                i += 1
                # Slice exactly prev_len characters of content (issue #25).
                # The original parser used the END_PREV sentinel and
                # truncated when the file's prior content contained that
                # exact line. Consuming by recorded byte count is safe.
                prev_content, i = _consume_prev_chars(lines, i, prev_len)
                # Tolerate the optional END_PREV trailer for backward
                # compatibility — older undo records still have it.
                if i < len(lines) and lines[i] == "END_PREV":
                    i += 1
                path.write_text(prev_content, encoding="utf-8")

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

    def _revert_delete_domain(self, lines: list[str]) -> None:
        """Reverse a ``brain_delete_domain`` operation.

        Record shape (after the leading ``KIND`` line):

            SLUG\t<slug>
            TRASH\t<absolute-path-of-trash-dir>
            ORIGINAL\t<absolute-path-of-original-domain-dir>

        We ``shutil.move`` the trashed folder back to its original
        location. If the original path is occupied (e.g. the user
        recreated the domain after deleting it), refuse rather than
        clobber.
        """
        trash: str | None = None
        original: str | None = None
        for line in lines:
            if line.startswith("TRASH\t"):
                trash = line.split("\t", 1)[1]
            elif line.startswith("ORIGINAL\t"):
                original = line.split("\t", 1)[1]
        if trash is None or original is None:
            raise ValueError("delete_domain undo record missing TRASH / ORIGINAL header")
        trash_path = Path(trash)
        original_path = Path(original)
        if not trash_path.exists():
            raise FileNotFoundError(f"trashed domain folder {trash_path} is missing")
        if original_path.exists():
            raise FileExistsError(f"cannot restore {trash_path} — {original_path} already exists")
        shutil.move(str(trash_path), str(original_path))
