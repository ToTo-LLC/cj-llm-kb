"""Regression-pin tests for the flat error envelope shape — Plan 13 Task 5.

Plan 05 Batch A established the flat ``{"error", "message", "detail"}``
envelope as the single 4xx/5xx body shape brain_api emits across the
middleware layer (Origin/Host rejections), the dependency layer (token
auth rejections), and the route layer (every domain exception caught by
:mod:`brain_api.errors`). Plan 11/12 closure cycles let the brain_api
unit suite drift such that 13 tests asserting against this shape silently
returned HTTP 200 + ``index.html`` whenever ``apps/brain_web/out/`` had
been built — masking the contract instead of pinning it (Plan 13 Task 4
findings).

These tests pin the shape at every distinct rejection layer so the
regression that Plan 13 Task 5 fixed can never re-emerge as a soft
"green" the way it did across Plans 09-12. Each case asserts:

    set(body.keys()) == {"error", "message", "detail"}

against a real ``create_app()``-built FastAPI instance — NO mocks at the
middleware layer (per Plan 13 D7 / Plan 11 lesson 343 / Plan 12 D6:
production-shape integration tests are the regression guard).

Five layers covered:

1. ``OriginHostMiddleware`` 403 (bad Origin header).
2. Route 400 (``ValueError`` mapped by :mod:`brain_api.errors`).
3. Route 500 (catch-all path; no traceback leakage).
4. WebSocket 1008 close (handshake rejection close-code parity).
5. Token-auth 403 (``require_token`` dependency, missing token).

The conftest's ``app`` fixture passes ``mount_static_ui=False`` per Plan 13
Task 5 so synthetic ``/_boom`` / ``/_protected`` routes resolve as
intended; THIS test file inherits that shape directly.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from brain_api.auth import require_token
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

_ENVELOPE_KEYS = {"error", "message", "detail"}
_LOOPBACK_HEADERS = {"Host": "localhost"}


def _attach_failing_route(app: FastAPI, exc_factory: Callable[[], BaseException]) -> None:
    """Mirror ``test_errors.py``'s synthetic-route pattern."""

    @app.get("/_boom")
    async def boom() -> dict[str, str]:
        raise exc_factory()


def test_origin_host_middleware_403_envelope_shape(app: FastAPI) -> None:
    """Bad ``Origin`` on a state-changing method → 403 with the flat envelope.

    Pins the middleware-layer rejection shape. ``OriginHostMiddleware``
    short-circuits BEFORE any route handler runs, so this proves the
    envelope shape is owned by the middleware itself (not the route's
    error handler). A synthetic POST route on the live ``app`` fixture
    keeps the test independent of production route surface — what we're
    pinning is the middleware's refusal envelope, not any specific
    endpoint.
    """

    @app.post("/_origin_test")
    async def origin_test() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app, base_url="http://localhost") as c:
        response = c.post(
            "/_origin_test",
            json={},
            headers={"Origin": "https://evil.example"},
        )
    assert response.status_code == 403
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["error"] == "refused"
    assert body["message"]


def test_route_400_envelope_shape(app: FastAPI) -> None:
    """A route raising :class:`ValueError` → 400 with the flat envelope.

    Pins the route-layer 400 path through the global
    :class:`ValueError` handler in :mod:`brain_api.errors`.
    """
    _attach_failing_route(app, lambda: ValueError("path must be vault-relative"))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 400
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["error"] == "invalid_input"


def test_route_500_envelope_shape(app: FastAPI) -> None:
    """A route raising bare :class:`Exception` → 500 with the flat envelope.

    Pins the catch-all 500 path. Per CLAUDE.md principle #10, the body
    must NOT leak the exception type or args — only the static
    ``{"error": "internal", "message": "unexpected error", "detail": ...}``
    shape. The ``detail`` slot is permitted to carry ``request_id`` from
    :class:`RequestIDMiddleware`; we assert the top-level keys, not the
    inner shape of ``detail``.
    """
    _attach_failing_route(app, lambda: RuntimeError("internal wiring blew up"))
    with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as c:
        response = c.get("/_boom")
    assert response.status_code == 500
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["error"] == "internal"
    assert body["message"] == "unexpected error"
    # No exception-type / arg leakage in the rendered body.
    rendered = response.text
    assert "RuntimeError" not in rendered
    assert "internal wiring" not in rendered


def test_ws_handshake_close_code_parity(app: FastAPI) -> None:
    """Bad ``thread_id`` (slash in path) → WS close, ``WebSocketDisconnect`` raised.

    Pins the WS rejection close-code parity. Plan 05 Task 17 chose
    1008 (Policy Violation) for every refusal path the WS handshake can
    fire (Host check, Origin check, token check, thread-id regex). The
    rejection here happens in the router (path doesn't match the regex),
    so the framework returns a 404 close-shape — what matters for the
    parity pin is that the connection is REJECTED (TestClient raises
    ``WebSocketDisconnect``) and never produces an HTTP 200 with
    ``index.html`` body, which is what the pre-Task-5 regression did.
    """
    with (
        TestClient(app, base_url="http://localhost") as fresh,
        pytest.raises(WebSocketDisconnect),
        fresh.websocket_connect(
            "/ws/chat/bad/slash?token=anything",
            headers=_LOOPBACK_HEADERS,
        ),
    ):
        pass


def test_auth_403_envelope_shape(app: FastAPI) -> None:
    """Missing ``X-Brain-Token`` on a protected route → 403 with the flat envelope.

    Pins the dependency-layer rejection shape. ``require_token`` raises
    :class:`PermissionError`; the global :class:`PermissionError` handler
    wraps it in the flat envelope.
    """

    @app.post("/_protected", dependencies=[Depends(require_token)])
    async def protected() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app, base_url="http://localhost") as c:
        response = c.post(
            "/_protected",
            json={},
            headers={"Origin": "http://localhost:4317"},
        )
    assert response.status_code == 403
    body = response.json()
    assert set(body.keys()) == _ENVELOPE_KEYS
    assert body["error"] == "refused"
    assert "X-Brain-Token" in body["message"]
