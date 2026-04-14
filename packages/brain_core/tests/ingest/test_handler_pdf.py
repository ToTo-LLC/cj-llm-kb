from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.pdf import PDFHandler, ScannedPDFError
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_pdf_handler_extracts_text(tmp_path: Path, fixtures_dir: Path) -> None:
    h = PDFHandler()
    assert await h.can_handle(fixtures_dir / "sample.pdf")
    es = await h.extract(fixtures_dir / "sample.pdf", archive_root=tmp_path)
    assert es.source_type is SourceType.PDF
    assert "Plan 02 PDF fixture" in es.body_text
    assert "Paragraph one." in es.body_text
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_pdf_handler_flags_probable_scan(tmp_path: Path) -> None:
    """A PDF whose extracted text is below the min-chars threshold must raise ScannedPDFError."""
    import fitz  # type: ignore[import-untyped]

    p = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()  # no text
    doc.save(p)
    doc.close()
    with pytest.raises(ScannedPDFError):
        await PDFHandler(min_chars=50).extract(p, archive_root=tmp_path)


@pytest.mark.asyncio
async def test_pdf_handler_rejects_non_pdf(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("not a pdf", encoding="utf-8")
    assert await PDFHandler().can_handle(f) is False


@pytest.mark.asyncio
async def test_pdf_handler_raises_handler_error_on_corrupt_pdf(tmp_path: Path) -> None:
    """A file with a .pdf extension that is not a valid PDF must raise HandlerError."""
    from brain_core.ingest.handlers.base import HandlerError

    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not a pdf at all")
    with pytest.raises(HandlerError, match="Could not open"):
        await PDFHandler().extract(fake, archive_root=tmp_path / "archive")
