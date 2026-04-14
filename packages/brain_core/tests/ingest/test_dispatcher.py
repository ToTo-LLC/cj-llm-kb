from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.dispatcher import DispatchError, dispatch
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.handlers.url import URLHandler


@pytest.mark.asyncio
async def test_dispatch_url_picks_url_handler() -> None:
    h = await dispatch("https://example.com/a")
    assert isinstance(h, URLHandler)


@pytest.mark.asyncio
async def test_dispatch_tweet_url_picks_tweet_handler_before_url_handler() -> None:
    h = await dispatch("https://x.com/karpathy/status/123")
    assert isinstance(h, TweetHandler)


@pytest.mark.asyncio
async def test_dispatch_pdf_path(fixtures_dir: Path) -> None:
    h = await dispatch(fixtures_dir / "sample.pdf")
    assert isinstance(h, PDFHandler)


@pytest.mark.asyncio
async def test_dispatch_text_path(fixtures_dir: Path) -> None:
    h = await dispatch(fixtures_dir / "hello.txt")
    assert isinstance(h, TextHandler)


@pytest.mark.asyncio
async def test_dispatch_unknown_raises() -> None:
    with pytest.raises(DispatchError, match=r"nope\.xyz"):
        await dispatch(Path("/nope/nope.xyz"))
