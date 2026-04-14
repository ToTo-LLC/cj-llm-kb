from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from brain_core.ingest.handlers.tweet import TweetHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_tweet_handler_fetches_and_extracts(fixtures_dir: Path, tmp_path: Path) -> None:
    payload = json.loads((fixtures_dir / "tweet.json").read_text(encoding="utf-8"))
    async with respx.mock(base_url="https://cdn.syndication.twimg.com") as mock:
        mock.get("/tweet-result").mock(return_value=httpx.Response(200, json=payload))
        h = TweetHandler()
        url = "https://x.com/karpathy/status/2039805659525644595"
        assert await h.can_handle(url)
        es = await h.extract(url, archive_root=tmp_path)
    assert es.source_type is SourceType.TWEET
    assert "markdown wikis" in es.body_text
    assert es.author == "karpathy"
    assert es.title and "karpathy" in es.title


@pytest.mark.asyncio
async def test_tweet_handler_rejects_non_tweet_url() -> None:
    h = TweetHandler()
    assert await h.can_handle("https://example.com") is False
    assert await h.can_handle("https://twitter.com/karpathy") is False  # no status ID
