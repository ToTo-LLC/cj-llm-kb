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


_HTML_JS_ONLY = "<html><body><script>var x=1;</script></body></html>"


@pytest.mark.asyncio
async def test_url_handler_raises_on_empty_extraction(tmp_path: Path) -> None:
    from brain_core.ingest.handlers.base import HandlerError

    async with respx.mock(base_url="https://example.com") as mock:
        mock.get("/js-only").mock(return_value=httpx.Response(200, text=_HTML_JS_ONLY))
        h = URLHandler()
        with pytest.raises(HandlerError, match="No readable content"):
            await h.extract("https://example.com/js-only", archive_root=tmp_path)


@pytest.mark.asyncio
async def test_url_handler_raises_handler_error_on_http_404(tmp_path: Path) -> None:
    """A 404 response must raise HandlerError mentioning 'HTTP 404'."""
    from brain_core.ingest.handlers.base import HandlerError

    async with respx.mock(base_url="https://example.com") as mock:
        mock.get("/missing").mock(return_value=httpx.Response(404, text="Not Found"))
        h = URLHandler()
        with pytest.raises(HandlerError, match="HTTP 404"):
            await h.extract("https://example.com/missing", archive_root=tmp_path)
