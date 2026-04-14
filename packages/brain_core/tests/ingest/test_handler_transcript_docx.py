from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.transcript_docx import TranscriptDOCXHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_docx_transcript_reads_paragraphs(fixtures_dir: Path, tmp_path: Path) -> None:
    h = TranscriptDOCXHandler()
    assert h.can_handle(fixtures_dir / "notes.docx")
    es = await h.extract(fixtures_dir / "notes.docx", archive_root=tmp_path)
    assert es.source_type is SourceType.TRANSCRIPT
    assert "Meeting notes 2026-04-13" in es.body_text
    assert "Alice: Welcome to the meeting." in es.body_text
    assert "Bob: Thanks for setting this up." in es.body_text
    assert es.archive_path.exists()


def test_docx_handler_rejects_txt(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("nope", encoding="utf-8")
    assert TranscriptDOCXHandler().can_handle(f) is False


@pytest.mark.asyncio
async def test_docx_handler_raises_handler_error_on_corrupt_docx(tmp_path: Path) -> None:
    """A file with .docx extension that is not a valid DOCX must raise HandlerError."""
    from brain_core.ingest.handlers.base import HandlerError

    fake = tmp_path / "fake.docx"
    fake.write_bytes(b"not a docx")
    with pytest.raises(HandlerError):
        await TranscriptDOCXHandler().extract(fake, archive_root=tmp_path / "archive")
