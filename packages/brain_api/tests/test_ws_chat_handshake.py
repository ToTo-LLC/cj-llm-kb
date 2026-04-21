"""Tests for the WS /ws/chat/<thread_id> handshake - Plan 05 Task 17.

Task 17 lands only the handshake: thread_id validation, token auth, schema
announcement, and an empty receive loop. Tasks 18-21 add typed events,
ChatSession wiring, cancel, and reconnect.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# TestClient.websocket_connect hard-codes a ``ws://testserver`` base URL
# (see ``starlette.testclient.TestClient.websocket_connect``), so every
# WS handshake leaves the client with ``Host: testserver`` regardless of
# the ``TestClient(base_url=...)`` kwarg. Task 8's ``OriginHostMiddleware``
# rejects non-loopback Host values - correct for production, but hostile
# to the TestClient's default. Every handshake test that expects an
# ACCEPT therefore explicitly overrides ``Host: localhost``. Tests that
# expect a REJECT don't need the override: the Host check rejects
# ``testserver`` before token validation runs, so the rejection still
# happens for the reason claimed by the test's name (the middleware is
# doing its job, just via a different loopback guard).
_LOOPBACK_HEADERS = {"Host": "localhost"}


# WS endpoints read ``ctx`` off ``websocket.app.state.ctx``; that stash is
# populated by the FastAPI lifespan, which the default ``client`` fixture
# does NOT enter (it only constructs ``TestClient`` without a context
# manager). Every WS test therefore wraps an explicit
# ``with TestClient(app, ...) as fresh`` so the lifespan fires and
# ``app.state.ctx`` exists. HTTP tests don't hit this because httpx
# trips lifespan on first request for them.


def test_handshake_missing_token_rejected(app: FastAPI) -> None:
    """No ``?token=`` -> close(1008) on upgrade; TestClient raises on failed connect."""
    with (
        TestClient(app, base_url="http://localhost") as fresh,
        pytest.raises(WebSocketDisconnect),
        fresh.websocket_connect("/ws/chat/test-thread", headers=_LOOPBACK_HEADERS),
    ):
        pass


def test_handshake_wrong_token_rejected(app: FastAPI) -> None:
    """Wrong token -> close(1008). check_ws_token runs before accept."""
    with (
        TestClient(app, base_url="http://localhost") as fresh,
        pytest.raises(WebSocketDisconnect),
        fresh.websocket_connect("/ws/chat/test-thread?token=badtoken", headers=_LOOPBACK_HEADERS),
    ):
        pass


def test_handshake_valid_token_accepted(app: FastAPI) -> None:
    """Valid token -> accept + schema_version + thread_loaded frames."""
    with TestClient(app, base_url="http://localhost") as fresh:
        token = fresh.app.state.ctx.token
        with fresh.websocket_connect(
            f"/ws/chat/test-thread?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            # First frame: schema_version.
            first = ws.receive_json()
            assert first["type"] == "schema_version"
            assert first["version"] == "1"

            # Second frame: thread_loaded with defaults.
            second = ws.receive_json()
            assert second["type"] == "thread_loaded"
            assert second["thread_id"] == "test-thread"
            assert second["turn_count"] == 0  # fresh thread
            assert second["mode"] == "ask"


def test_handshake_rejects_bad_thread_id(app: FastAPI) -> None:
    """``/ws/chat/bad/slash`` -> 404 (router never matches two segments).

    The regex ``^[a-z0-9][a-z0-9-]{0,63}$`` doubles as a filesystem-safe
    check inside the endpoint, but the path segment itself never resolves
    past the router when a slash is present.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        token = fresh.app.state.ctx.token
        with (
            pytest.raises(WebSocketDisconnect),
            fresh.websocket_connect(f"/ws/chat/bad/slash?token={token}", headers=_LOOPBACK_HEADERS),
        ):
            pass


def test_handshake_rejects_evil_origin(app: FastAPI) -> None:
    """Middleware blocks WS upgrade from a non-loopback Origin (DNS rebinding / CSRF).

    Sends ``Host: localhost`` (to pass the Host check) and an evil
    ``Origin`` - the middleware must still refuse. Without the explicit
    Host override we'd still see a rejection, but for the wrong reason
    (Host mismatch), which wouldn't prove the Origin check runs on WS.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        token = fresh.app.state.ctx.token
        with (
            pytest.raises(WebSocketDisconnect),
            fresh.websocket_connect(
                f"/ws/chat/test-thread?token={token}",
                headers={**_LOOPBACK_HEADERS, "Origin": "https://evil.example"},
            ),
        ):
            pass
