from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.transcript_text import TranscriptTextHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_plain_transcript(fixtures_dir: Path, tmp_path: Path) -> None:
    h = TranscriptTextHandler()
    es = await h.extract(fixtures_dir / "transcript.txt", archive_root=tmp_path)
    assert es.source_type is SourceType.TRANSCRIPT
    assert "Alice" in es.body_text
