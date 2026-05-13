from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.pdf import PDFHandler, ScannedPDFError
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_pdf_handler_extracts_text(tmp_path: Path, fixtures_dir: Path) -> None:
    h = PDFHandler()
    assert h.can_handle(fixtures_dir / "sample.pdf")
    es = await h.extract(fixtures_dir / "sample.pdf", archive_root=tmp_path)
    assert es.source_type is SourceType.PDF
    assert "Plan 02 PDF fixture" in es.body_text
    assert "Paragraph one." in es.body_text
    assert es.archive_path.exists()
    # Text-rich PDF → no image-mode flag, no rendered pages.
    assert es.extras.get("pdf_image_mode") in (None, False)
    assert es.extras.get("images", []) == []


@pytest.mark.asyncio
async def test_pdf_handler_low_text_triggers_image_mode(tmp_path: Path) -> None:
    """Plan 25 T3 D14: low-text PDFs render pages for OCR instead of raising.

    Pre-Plan-25 this raised :class:`ScannedPDFError`. Plan 25 T3 changes
    the path to image-mode: pages are rendered to PNG and returned in
    ``extras["images"]`` for the pipeline OCR pass.
    """
    import fitz  # type: ignore[import-untyped]

    p = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()  # no text
    doc.save(p)
    doc.close()

    es = await PDFHandler(min_chars=50).extract(p, archive_root=tmp_path / "archive")
    assert es.source_type is SourceType.PDF
    assert es.extras.get("pdf_image_mode") is True
    images = es.extras.get("images", [])
    assert len(images) == 1
    assert images[0]["page_index"] == 1
    assert images[0]["content_type"] == "image/png"


def test_scanned_pdf_error_remains_handler_error_subclass() -> None:
    """Plan 25 T3: :class:`ScannedPDFError` is retained as an export for
    backward-compat (no longer raised by the handler, but importers shouldn't
    break)."""
    from brain_core.ingest.handlers.base import HandlerError

    assert issubclass(ScannedPDFError, HandlerError)


def test_pdf_handler_rejects_non_pdf(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("not a pdf", encoding="utf-8")
    assert PDFHandler().can_handle(f) is False


@pytest.mark.asyncio
async def test_pdf_handler_raises_handler_error_on_corrupt_pdf(tmp_path: Path) -> None:
    """A file with a .pdf extension that is not a valid PDF must raise HandlerError."""
    from brain_core.ingest.handlers.base import HandlerError

    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not a pdf at all")
    with pytest.raises(HandlerError, match="Could not open"):
        await PDFHandler().extract(fake, archive_root=tmp_path / "archive")
