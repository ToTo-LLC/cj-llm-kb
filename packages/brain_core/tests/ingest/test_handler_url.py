from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from brain_core.ingest.handlers.url import URLHandler
from brain_core.ingest.types import SourceType

_HTML = """
<!doctype html>
<html><head><title>Example article</title></head>
<body>
  <article>
    <h1>Example article</h1>
    <p>This is the main body content that trafilatura should pick up.</p>
    <p>It has two paragraphs to prove multi-paragraph extraction works.</p>
  </article>
  <footer>nav junk</footer>
</body></html>
"""


@pytest.mark.asyncio
async def test_url_handler_fetches_and_extracts(tmp_path: Path) -> None:
    async with respx.mock(base_url="https://example.com") as mock:
        mock.get("/a").mock(return_value=httpx.Response(200, text=_HTML))
        h = URLHandler()
        assert await h.can_handle("https://example.com/a")
        es = await h.extract("https://example.com/a", archive_root=tmp_path)
    assert es.source_type is SourceType.URL
    assert "main body content" in es.body_text
    assert es.title == "Example article"
    assert es.source_url == "https://example.com/a"
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_url_handler_rejects_non_http() -> None:
    h = URLHandler()
    assert await h.can_handle("file:///etc/passwd") is False
    assert await h.can_handle(Path("/tmp/x")) is False
