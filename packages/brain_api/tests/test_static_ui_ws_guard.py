"""Pin SPAStaticFiles non-http scope guard — Plan 14 Task 1 (D3).

The parent ``starlette.staticfiles.StaticFiles.__call__`` opens with
``assert scope["type"] == "http"``. Production today never reaches that
assertion because every API + WebSocket router is registered before the
SPA static mount in :func:`brain_api.app.create_app` and Starlette walks
the routing table in insertion order. The latent risk Plan 13 Task 4
findings flagged: a malformed WebSocket path (e.g. ``/ws/chat/bad/slash``
that fails the WS regex) or a future route-ordering change could fall
through to the static mount, hand a ``"websocket"`` scope to the base
class, and surface an ``AssertionError`` instead of a clean 404.

These tests pin the override on :class:`SPAStaticFiles.__call__` that
short-circuits any non-http scope with a 404 ASGI response. They drive
the ASGI three-tuple (``scope``, ``receive``, ``send``) directly so the
production-shape contract — "non-http scope produces a 404, never an
``AssertionError``" — is exercised end-to-end (lesson 343 + Plan 14 Task
1 review checklist).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from brain_api.static_ui import SPAStaticFiles
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Send

_INDEX_HTML = (
    "<!doctype html>\n"
    "<html><head><title>brain</title></head>"
    '<body><div id="__next">BRAIN_ROOT</div></body></html>\n'
)


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    """Build a miniature Next.js ``out/`` so SPAStaticFiles has a directory."""
    root = tmp_path / "out"
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(_INDEX_HTML, encoding="utf-8", newline="\n")
    return root


@pytest.fixture
def static_app(out_dir: Path) -> SPAStaticFiles:
    """A bare ``SPAStaticFiles`` instance pointed at the fake out_dir."""
    return SPAStaticFiles(directory=str(out_dir), html=True)


async def _drive_asgi(
    app: SPAStaticFiles,
    scope: dict[str, Any],
) -> tuple[list[Message], list[Message]]:
    """Drive the ASGI three-tuple manually and capture sent messages.

    Returns ``(start_messages, body_messages)``. Starlette's
    ``Response.__call__`` rewrites ``http.response.start`` to
    ``websocket.http.response.start`` for websocket scopes (the WebSocket
    Denial Response shape from the ASGI spec); accept either form so the
    same helper exercises http, websocket, and lifespan scopes.
    """
    sent: list[Message] = []

    async def receive() -> Message:  # pragma: no cover — never called for static
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    receive_callable: Receive = receive
    send_callable: Send = send
    await app(scope, receive_callable, send_callable)
    starts = [m for m in sent if str(m["type"]).endswith("http.response.start")]
    bodies = [m for m in sent if str(m["type"]).endswith("http.response.body")]
    return starts, bodies


@pytest.mark.asyncio
async def test_ws_scope_returns_404(static_app: SPAStaticFiles) -> None:
    """A WebSocket-shaped scope must produce a 404, not an ``AssertionError``.

    This is the regression-pin: the parent class's
    ``assert scope["type"] == "http"`` would fire here without the
    override Plan 14 Task 1 added.
    """
    scope: dict[str, Any] = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": "/anywhere",
        "raw_path": b"/anywhere",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 4317),
    }
    starts, _ = await _drive_asgi(static_app, scope)
    assert len(starts) == 1
    assert starts[0]["status"] == 404


@pytest.mark.asyncio
async def test_lifespan_scope_returns_404(static_app: SPAStaticFiles) -> None:
    """Lifespan scopes are per-app, not per-mount, so they never reach a
    StaticFiles mount in normal Starlette routing — but the override
    treats them conservatively (anything that isn't ``"http"`` produces a
    404). Pin the conservative behavior so a future routing-edge case
    can't quietly bubble an AssertionError.
    """
    scope: dict[str, Any] = {
        "type": "lifespan",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
    }
    starts, _ = await _drive_asgi(static_app, scope)
    assert len(starts) == 1
    assert starts[0]["status"] == 404


@pytest.mark.asyncio
async def test_ws_scope_does_not_raise_assertion_error(
    static_app: SPAStaticFiles,
) -> None:
    """Explicit shape pin: the WS path must NOT raise ``AssertionError``.

    Without the override, the parent ``StaticFiles.__call__`` would hit
    ``assert scope["type"] == "http"`` and bubble out. Proving the
    override actually intercepts (rather than coincidentally hiding the
    bug behind some other mechanism) is the load-bearing assertion.
    """
    scope: dict[str, Any] = {
        "type": "websocket",
        "path": "/ws/chat/bad/slash",
        "raw_path": b"/ws/chat/bad/slash",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 4317),
    }

    # If the override regresses, this raises AssertionError from the
    # parent's ``assert scope["type"] == "http"``. The clean 404 path is
    # the only acceptable outcome.
    try:
        starts, _ = await _drive_asgi(static_app, scope)
    except AssertionError as exc:  # pragma: no cover — regression signal
        pytest.fail(
            "SPAStaticFiles.__call__ leaked an AssertionError on a "
            f"WebSocket scope; the non-http guard regressed: {exc!r}"
        )

    assert len(starts) == 1
    assert starts[0]["status"] == 404


def test_http_scope_unchanged(out_dir: Path, tmp_path: Path) -> None:
    """Real http requests still reach SPAStaticFiles' SPA fallback unchanged.

    Anti-regression for the override: only non-http scopes short-circuit;
    http scopes flow into the existing ``__call__`` → ``get_response`` →
    ``_spa_fallback`` chain. We use the full FastAPI app here (rather
    than the bare ``SPAStaticFiles`` instance) so the assertion exercises
    the production-shape stack.
    """
    import os

    from brain_api import create_app

    os.environ["BRAIN_WEB_OUT_DIR"] = str(out_dir)
    try:
        vault = tmp_path / "vault"
        vault.mkdir(parents=True, exist_ok=True)
        app = create_app(vault_root=vault, allowed_domains=("research",))
        with TestClient(app, base_url="http://localhost") as client:
            r = client.get("/", headers={"Origin": "http://localhost:4317"})
            assert r.status_code == 200, r.text
            assert "BRAIN_ROOT" in r.text
    finally:
        os.environ.pop("BRAIN_WEB_OUT_DIR", None)
