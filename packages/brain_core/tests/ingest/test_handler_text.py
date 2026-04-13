"""Tests for the text/markdown source handler."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_text_handler_reads_plain_text_file(tmp_path: Path, fixtures_dir: Path) -> None:
    h = TextHandler()
    assert await h.can_handle(fixtures_dir / "hello.txt")
    extracted = await h.extract(fixtures_dir / "hello.txt", archive_root=tmp_path)
    assert extracted.source_type is SourceType.TEXT
    assert "Hello, brain." in extracted.body_text
    assert extracted.archive_path.exists()
    assert extracted.title == "hello"


@pytest.mark.asyncio
async def test_text_handler_rejects_non_text(tmp_path: Path) -> None:
    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    assert await TextHandler().can_handle(f) is False
