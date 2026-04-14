"""Parametrized cross-handler test: extract() raises HandlerError on bad input.

Each handler's extract() has a guard at the top that rejects inputs its
can_handle() would also reject. This test ensures that guard is exercised
for every handler, since individual handler tests typically only test
can_handle() for the rejection case.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.handlers.email import EmailHandler
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.handlers.transcript_docx import TranscriptDOCXHandler
from brain_core.ingest.handlers.transcript_text import TranscriptTextHandler
from brain_core.ingest.handlers.transcript_vtt import TranscriptVTTHandler
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.handlers.url import URLHandler

# Handlers that expect Path inputs. Bad input: a non-existent Path, a str, and an int.
_PATH_HANDLERS: list[Any] = [
    TextHandler(),
    PDFHandler(),
    TranscriptTextHandler(),
    TranscriptVTTHandler(),
    TranscriptDOCXHandler(),
]

# Handlers that expect str (URL / email text) inputs. Bad input: a Path, an int.
_STR_HANDLERS: list[Any] = [
    URLHandler(),
    EmailHandler(),
    TweetHandler(),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", _PATH_HANDLERS, ids=lambda h: type(h).__name__)
async def test_path_handler_extract_rejects_missing_file(handler: Any, tmp_path: Path) -> None:
    bad = tmp_path / "does-not-exist.xyz"
    with pytest.raises(HandlerError):
        await handler.extract(bad, archive_root=tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", _PATH_HANDLERS, ids=lambda h: type(h).__name__)
async def test_path_handler_extract_rejects_str_input(handler: Any, tmp_path: Path) -> None:
    with pytest.raises(HandlerError):
        await handler.extract("a random string", archive_root=tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", _STR_HANDLERS, ids=lambda h: type(h).__name__)
async def test_str_handler_extract_rejects_path_input(handler: Any, tmp_path: Path) -> None:
    with pytest.raises(HandlerError):
        await handler.extract(tmp_path / "x", archive_root=tmp_path)
