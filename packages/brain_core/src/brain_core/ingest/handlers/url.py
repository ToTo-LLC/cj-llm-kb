"""URL handler — fetches with httpx, extracts readable content with trafilatura."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, SourceType


class URLHandler:
    source_type: SourceType = SourceType.URL

    async def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, str):
            return False
        parsed = urlparse(spec)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, str):
            raise HandlerError(f"url handler cannot read {spec!r}")
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(spec)
            resp.raise_for_status()
            html = resp.text
            final_url = str(resp.url)

        extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
        if not extracted or not extracted.strip():
            raise HandlerError(
                f"No readable content extracted from {final_url!r}. "
                "The page may require JavaScript, be login-walled, or contain only navigation chrome."
            )
        meta = trafilatura.extract_metadata(html)
        title: str | None = meta.title if meta and meta.title else None
        author: str | None = meta.author if meta and meta.author else None

        archive_root.mkdir(parents=True, exist_ok=True)
        h = content_hash(html)[:16]
        archive_path = archive_root / f"{h}.html"
        archive_path.write_text(html, encoding="utf-8")

        return ExtractedSource(
            title=title,
            author=author,
            published=None,
            source_url=final_url,
            source_type=SourceType.URL,
            body_text=extracted,
            archive_path=archive_path,
        )
