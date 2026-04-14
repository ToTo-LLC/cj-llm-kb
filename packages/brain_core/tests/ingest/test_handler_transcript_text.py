from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.handlers.transcript_text import TranscriptTextHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_plain_transcript(fixtures_dir: Path, tmp_path: Path) -> None:
    h = TranscriptTextHandler()
    es = await h.extract(fixtures_dir / "transcript.txt", archive_root=tmp_path)
    assert es.source_type is SourceType.TRANSCRIPT
    assert "Alice" in es.body_text


@pytest.mark.asyncio
async def test_transcript_text_raises_handler_error_on_non_utf8(tmp_path: Path) -> None:
    """A file with Latin-1 bytes (not valid UTF-8) must raise HandlerError mentioning UTF-8."""
    bad_file = tmp_path / "bad_transcript.txt"
    bad_file.write_bytes(b"caf\xe9")  # Latin-1, not valid UTF-8
    with pytest.raises(HandlerError, match="UTF-8"):
        await TranscriptTextHandler().extract(bad_file, archive_root=tmp_path / "archive")
