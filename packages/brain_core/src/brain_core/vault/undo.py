"""Undo log replay — reverts a previously applied PatchSet."""

from __future__ import annotations

from pathlib import Path


class UndoLog:
    def __init__(self, *, vault_root: Path) -> None:
        self.vault_root = vault_root.resolve()
        self._dir = self.vault_root / ".brain" / "undo"

    def revert(self, undo_id: str) -> None:
        record = (self._dir / f"{undo_id}.txt").read_text(encoding="utf-8")
        lines = record.split("\n")
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
