"""Tests for the text/markdown source handler."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_text_handler_reads_plain_text_file(tmp_path: Path, fixtures_dir: Path) -> None:
    h = TextHandler()
    assert h.can_handle(fixtures_dir / "hello.txt")
    extracted = await h.extract(fixtures_dir / "hello.txt", archive_root=tmp_path)
    assert extracted.source_type is SourceType.TEXT
    assert "Hello, brain." in extracted.body_text
    assert extracted.archive_path.exists()
    assert extracted.title == "hello"


def test_text_handler_rejects_non_text(tmp_path: Path) -> None:
    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    assert TextHandler().can_handle(f) is False


@pytest.mark.asyncio
async def test_text_handler_raises_handler_error_on_non_utf8(tmp_path: Path) -> None:
    """A file with Latin-1 bytes (not valid UTF-8) must raise HandlerError mentioning UTF-8."""
    bad_file = tmp_path / "bad.txt"
    bad_file.write_bytes(b"caf\xe9")  # Latin-1, not valid UTF-8
    with pytest.raises(HandlerError, match="UTF-8"):
        await TextHandler().extract(bad_file, archive_root=tmp_path / "archive")
