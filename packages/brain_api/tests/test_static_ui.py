"""Tests for SPAStaticFiles + out-dir resolution — Plan 08 Task 1.

brain_api serves the Next.js static export (``apps/brain_web/out/``) under
``/`` with SPA-style fallback so client-side routes (``/chat``, ``/chat/<id>``,
``/browse/foo/bar``) all resolve to ``index.html`` and let React Router take
over post-hydration. API and WebSocket paths must NEVER get the SPA fallback —
a typo at ``/api/nonexistent`` must 404, not hand the browser a stale HTML
response that parses as JSON-garbage.

Five slices:
1. ``GET /`` → 200 + index.html contents.
2. ``GET /_next/static/chunk.js`` → 200 + asset contents.
3. ``GET /chat`` → 200 + index.html (SPA fallback, no physical file).
4. ``GET /chat/abc-123`` → 200 + index.html (dynamic segment).
5. ``GET /api/nonexistent`` → 404 (NEVER SPA fallback).

The fixture builds a tiny ``out/`` directory at ``tmp_path`` with a placeholder
``index.html`` + one ``_next/static`` asset, points ``BRAIN_WEB_OUT_DIR`` at
it via monkeypatch, and spins up a fresh FastAPI app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_api import create_app
from fastapi.testclient import TestClient

_ORIGIN = "http://localhost:4317"

_INDEX_HTML = (
    "<!doctype html>\n"
    "<html><head><title>brain</title></head>"
    '<body><div id="__next">BRAIN_ROOT</div></body></html>\n'
)
_CHUNK_JS = "console.log('chunk loaded');\n"


@pytest.fixture
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a miniature Next.js ``out/`` + point the resolver at it."""
    root = tmp_path / "out"
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(_INDEX_HTML, encoding="utf-8", newline="\n")

    nxt = root / "_next" / "static"
    nxt.mkdir(parents=True, exist_ok=True)
    (nxt / "chunk.js").write_text(_CHUNK_JS, encoding="utf-8", newline="\n")

    monkeypatch.setenv("BRAIN_WEB_OUT_DIR", str(root))
    return root


@pytest.fixture
def static_client(out_dir: Path, tmp_path: Path) -> TestClient:
    """App + TestClient with a resolved static mount."""
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    app = create_app(vault_root=vault, allowed_domains=("research",))
    return TestClient(app, base_url="http://localhost")


def test_root_returns_index_html(static_client: TestClient) -> None:
    """``GET /`` resolves to ``index.html`` (StaticFiles html=True behavior)."""
    with static_client as client:
        r = client.get("/", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        assert "BRAIN_ROOT" in r.text


def test_next_static_asset_is_served_verbatim(static_client: TestClient) -> None:
    """``GET /_next/static/chunk.js`` returns the raw asset bytes."""
    with static_client as client:
        r = client.get("/_next/static/chunk.js", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        assert "chunk loaded" in r.text


def test_spa_fallback_for_unknown_route_returns_index(static_client: TestClient) -> None:
    """``GET /chat`` (no physical file) falls back to ``index.html``."""
    with static_client as client:
        r = client.get("/chat", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        assert "BRAIN_ROOT" in r.text


def test_spa_fallback_for_dynamic_segment(static_client: TestClient) -> None:
    """``GET /chat/abc-123`` (dynamic segment) also falls back to index.html."""
    with static_client as client:
        r = client.get("/chat/abc-123", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        assert "BRAIN_ROOT" in r.text


def test_api_nonexistent_is_404_not_spa_fallback(static_client: TestClient) -> None:
    """``GET /api/nonexistent`` returns 404; the SPA fallback MUST NOT swallow it.

    A misconfigured static mount (e.g. mounted BEFORE the API routers) would
    return index.html here and the browser would choke when its ``fetch`` call
    tried to ``await res.json()`` on HTML bytes. Pin the negative contract:
    unknown ``/api/*`` paths stay 404 regardless of how much static content we
    add.
    """
    with static_client as client:
        r = client.get("/api/nonexistent", headers={"Origin": _ORIGIN})
        assert r.status_code == 404, r.text
