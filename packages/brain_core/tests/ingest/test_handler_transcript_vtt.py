from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.transcript_vtt import TranscriptVTTHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_vtt_transcript_strips_timestamps(fixtures_dir: Path, tmp_path: Path) -> None:
    h = TranscriptVTTHandler()
    assert await h.can_handle(fixtures_dir / "meeting.vtt")
    es = await h.extract(fixtures_dir / "meeting.vtt", archive_root=tmp_path)
    assert es.source_type is SourceType.TRANSCRIPT
    assert "Alice: Welcome to the meeting." in es.body_text
    assert "-->" not in es.body_text
    assert "00:00:00" not in es.body_text
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_srt_transcript_strips_timestamps(fixtures_dir: Path, tmp_path: Path) -> None:
    h = TranscriptVTTHandler()
    es = await h.extract(fixtures_dir / "meeting.srt", archive_root=tmp_path)
    assert "Alice: Welcome to the meeting." in es.body_text
    assert "Bob: Thanks for setting this up." in es.body_text
    assert "-->" not in es.body_text


@pytest.mark.asyncio
async def test_vtt_handler_rejects_txt(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("nope", encoding="utf-8")
    assert await TranscriptVTTHandler().can_handle(f) is False
