"""Tweet handler — fetches via cdn.syndication.twimg.com (fragile, unauth)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType

_ID_RE = re.compile(r"/status/(\d+)")
_SYNDICATION = "https://cdn.syndication.twimg.com/tweet-result"


class TweetHandler:
    """Fragile unauth handler for single X/Twitter posts."""

    source_type: SourceType = SourceType.TWEET
    fragile: bool = True

    def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, str):
            return False
        parsed = urlparse(spec)
        if parsed.netloc not in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}:
            return False
        return bool(_ID_RE.search(parsed.path))

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, str):
            raise HandlerError(f"tweet handler cannot read {spec!r}")
        m = _ID_RE.search(urlparse(spec).path)
        if not m:
            raise HandlerError(f"no tweet id in {spec}")
        tweet_id = m.group(1)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(_SYNDICATION, params={"id": tweet_id})
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise HandlerError(
                f"Syndication fetch failed for tweet {tweet_id}: HTTP {exc.response.status_code}. "
                "The tweet may be deleted, private, or the syndication endpoint may have changed."
            ) from exc
        except httpx.RequestError as exc:
            raise HandlerError(
                f"Could not reach the tweet syndication endpoint: {type(exc).__name__}. "
                "Check your network connection."
            ) from exc
        except ValueError as exc:  # json.JSONDecodeError is a ValueError subclass
            raise HandlerError(
                f"Syndication endpoint returned non-JSON for tweet {tweet_id}. "
                "The endpoint may have changed — this handler may need an update."
            ) from exc
        author = data.get("user", {}).get("screen_name") or None
        display = data.get("user", {}).get("name") or author
        text = data.get("text") or ""
        if display and author and display != author:
            title = f"Tweet by {display} (@{author})"
        elif author:
            title = f"Tweet by @{author}"
        else:
            title = f"Tweet {tweet_id}"

        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / f"tweet-{tweet_id}.json"
        archive_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ExtractedSource(
            title=title,
            author=author,
            published=None,
            source_url=spec,
            source_type=SourceType.TWEET,
            body_text=text,
            archive_path=archive_path,
        )
