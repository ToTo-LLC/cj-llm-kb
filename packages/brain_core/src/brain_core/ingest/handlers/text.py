"""Plain text / Markdown handler. Copies the file into archive and reads UTF-8."""

from __future__ import annotations

import shutil
from pathlib import Path

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType

_EXTS = {".txt", ".md", ".markdown"}


class TextHandler:
    source_type: SourceType = SourceType.TEXT

    def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, Path):
            return False
        return spec.suffix.lower() in _EXTS and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"text handler cannot read {spec!r}")
        try:
            body = spec.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise HandlerError(
                f"File {spec.name!r} is not valid UTF-8. Re-save it as UTF-8 text and try again."
            ) from exc
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)
        return ExtractedSource(
            title=spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.TEXT,
            body_text=body,
            archive_path=archive_path,
        )
