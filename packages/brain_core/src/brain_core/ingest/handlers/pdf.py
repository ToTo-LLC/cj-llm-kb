"""PDF handler — text-only extraction via pymupdf. Scanned PDFs are flagged, not OCR'd."""

from __future__ import annotations

import shutil
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType


class ScannedPDFError(HandlerError):
    """Raised when the PDF appears to be a scan (too little extractable text)."""


class PDFHandler:
    source_type: SourceType = SourceType.PDF

    def __init__(self, *, min_chars: int = 200) -> None:
        self._min_chars = min_chars

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, Path):
            return False
        return spec.suffix.lower() == ".pdf" and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"pdf handler cannot read {spec!r}")
        doc = fitz.open(spec)
        try:
            parts: list[str] = []
            title = None
            try:
                meta = doc.metadata or {}
                title = meta.get("title") or None
            except Exception:
                title = None
            for page in doc:
                parts.append(page.get_text())
        finally:
            doc.close()
        body = "\n\n".join(p.strip() for p in parts if p.strip())
        if len(body) < self._min_chars:
            raise ScannedPDFError(
                f"extracted {len(body)} chars from {spec.name};"
                f" below min={self._min_chars} (likely scanned)"
            )
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)
        return ExtractedSource(
            title=title or spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.PDF,
            body_text=body,
            archive_path=archive_path,
        )
