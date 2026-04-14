"""DOCX transcript handler — reads paragraphs with python-docx."""

from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType


class TranscriptDOCXHandler:
    source_type: SourceType = SourceType.TRANSCRIPT

    async def can_handle(self, spec: str | Path) -> bool:
        return isinstance(spec, Path) and spec.suffix.lower() == ".docx" and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"transcript_docx cannot read {spec!r}")
        try:
            doc = Document(spec)  # type: ignore[arg-type]  # python-docx stubs say str | IO[bytes], but Path works at runtime
        except Exception as exc:
            raise HandlerError(
                f"Could not open DOCX {spec.name!r}: {exc}. "
                "The file may be corrupt or not a Word document."
            ) from exc
        body = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)
        return ExtractedSource(
            title=spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.TRANSCRIPT,
            body_text=body,
            archive_path=archive_path,
        )
