"""VaultWriter - the only path through which the vault is mutated.

Enforces scope_guard on every path, atomic write-and-rename, filelock-based
concurrency, per-operation write ceilings, and an undo log.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock

from brain_core.vault.index import IndexEntry, IndexFile
from brain_core.vault.log import LogEntry, LogFile
from brain_core.vault.paths import ScopeError, scope_guard
from brain_core.vault.types import PatchSet

_INDEX_LINE_RE = re.compile(r"^- \[\[([^\]]+)\]\]\s*—\s*(.*)$")


class PatchTooLargeError(ValueError):
    """Raised when a PatchSet exceeds max_patch_bytes."""


class TooManyFilesError(ValueError):
    """Raised when a PatchSet touches more files than allowed."""


@dataclass
class Receipt:
    applied_files: list[Path] = field(default_factory=list)
    undo_id: str | None = None


class VaultWriter:
    def __init__(
        self,
        *,
        vault_root: Path,
        max_patch_bytes: int = 500 * 1024,
        max_files_per_patch: int = 50,
    ) -> None:
        self.vault_root = vault_root.resolve()
        self.max_patch_bytes = max_patch_bytes
        self.max_files_per_patch = max_files_per_patch
        self._locks_dir = self.vault_root / ".brain" / "locks"
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        self._undo_dir = self.vault_root / ".brain" / "undo"
        self._undo_dir.mkdir(parents=True, exist_ok=True)

    def apply(self, patch: PatchSet, *, allowed_domains: tuple[str, ...]) -> Receipt:
        if patch.total_size() > self.max_patch_bytes:
            raise PatchTooLargeError(
                f"patch total size {patch.total_size()} > limit {self.max_patch_bytes}"
            )
        if patch.file_count() > self.max_files_per_patch:
            raise TooManyFilesError(
                f"patch touches {patch.file_count()} files > limit {self.max_files_per_patch}"
            )

        # Pre-validate every path before any mutation.
        for nf in patch.new_files:
            scope_guard(nf.path, vault_root=self.vault_root, allowed_domains=allowed_domains)
        for e in patch.edits:
            scope_guard(e.path, vault_root=self.vault_root, allowed_domains=allowed_domains)
        for ie in patch.index_entries:
            if ie.domain not in allowed_domains:
                raise PermissionError(
                    f"index entry for domain {ie.domain!r} not in allowed {allowed_domains}"
                )

        receipt = Receipt()
        undo_id = self._new_undo_id()
        # (path, previous_content or None if new)
        undo_records: list[tuple[Path, str | None]] = []

        lock = FileLock(str(self._locks_dir / "global.lock"))
        with lock.acquire(timeout=30):
            try:
                for nf in patch.new_files:
                    undo_records.append((nf.path, None))
                    self._atomic_write(nf.path, nf.content)
                    receipt.applied_files.append(nf.path)
                for e in patch.edits:
                    prev_text = e.path.read_text(encoding="utf-8")
                    if e.old not in prev_text:
                        raise ValueError(f"edit old-text not found in {e.path}")
                    undo_records.append((e.path, prev_text))
                    self._atomic_write(e.path, prev_text.replace(e.old, e.new, 1))
                    receipt.applied_files.append(e.path)
                for ie in patch.index_entries:
                    idx_path = self.vault_root / ie.domain / "index.md"
                    idx = IndexFile.load(idx_path)
                    parsed = _parse_index_line(ie.line)
                    idx.add_entry(ie.section, parsed)
                    idx.save()
                log_entry = patch.log_entry
                if log_entry:
                    domain = allowed_domains[0]
                    log = LogFile(self.vault_root / domain / "log.md")
                    summary = _sanitize_log_summary(log_entry) or patch.reason
                    log.append(
                        LogEntry(
                            timestamp=datetime.now(tz=UTC),
                            op="patch",
                            summary=summary,
                        )
                    )
                self._write_undo_record(undo_id, undo_records)
                receipt.undo_id = undo_id
            except BaseException:
                for path, prev in reversed(undo_records):
                    if prev is None:
                        if path.exists():
                            path.unlink()
                    else:
                        self._atomic_write(path, prev)
                raise
        return receipt

    def rename_file(
        self,
        src: Path,
        dst: Path,
        *,
        allowed_domains: tuple[str, ...],
    ) -> Receipt:
        """Atomically rename a file inside the vault.

        Both paths must be inside the vault and inside allowed domains, and
        must belong to the same top-level domain (cross-domain moves are
        rejected). `dst` must not exist. Writes a rename undo record.
        """
        src_abs = scope_guard(src, vault_root=self.vault_root, allowed_domains=allowed_domains)
        dst_abs = scope_guard(dst, vault_root=self.vault_root, allowed_domains=allowed_domains)
        src_rel = src_abs.relative_to(self.vault_root)
        dst_rel = dst_abs.relative_to(self.vault_root)
        if src_rel.parts[0] != dst_rel.parts[0]:
            raise ScopeError(
                f"rename across domains not allowed: {src_rel.parts[0]} -> {dst_rel.parts[0]}"
            )
        lock = FileLock(str(self._locks_dir / "global.lock"))
        with lock.acquire(timeout=30):
            if not src_abs.exists():
                raise FileNotFoundError(f"source {src} does not exist")
            if dst_abs.exists():
                raise FileExistsError(f"destination {dst} already exists")
            dst_abs.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src_abs, dst_abs)
            undo_id = self._new_undo_id()
            self._write_rename_undo_record(undo_id, src_abs, dst_abs)
        return Receipt(applied_files=[dst_rel], undo_id=undo_id)

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _new_undo_id(self) -> str:
        return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%f")

    def _write_undo_record(self, undo_id: str, records: list[tuple[Path, str | None]]) -> None:
        target = self._undo_dir / f"{undo_id}.txt"
        lines: list[str] = []
        for p, prev in records:
            lines.append(f"PATH\t{p}")
            if prev is None:
                lines.append("NEW")
            else:
                lines.append("PREV_LEN\t" + str(len(prev)))
                lines.append(prev)
                lines.append("END_PREV")
        target.write_text("\n".join(lines), encoding="utf-8")

    def _write_rename_undo_record(self, undo_id: str, src: Path, dst: Path) -> None:
        target = self._undo_dir / f"{undo_id}.txt"
        target.write_text(f"RENAME\nSRC\t{src}\nDST\t{dst}\n", encoding="utf-8", newline="\n")


def _sanitize_log_summary(text: str) -> str:
    """Strip a log_entry down to a safe single-line summary.

    Prevents log-injection: an LLM-produced log_entry containing embedded
    newlines followed by `## [...]` headers could forge historical log entries
    when written into log.md. Collapse all whitespace-including newlines to a
    single space, and strip leading `#` chars used for markdown heading.
    """
    return " ".join(text.lstrip("#").strip().split())


def _parse_index_line(line: str) -> IndexEntry:
    m = _INDEX_LINE_RE.match(line.strip())
    if not m:
        raise ValueError(f"invalid index entry line: {line!r}")
    return IndexEntry(target=m.group(1), summary=m.group(2))
