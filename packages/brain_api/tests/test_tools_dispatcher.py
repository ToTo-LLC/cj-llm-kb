"""Tests for POST /api/tools/<name> dispatcher — Task 10 (validation follows in Task 11).

The Task 10 dispatcher is deliberately a bare passthrough: request body is a
``dict[str, Any]`` handed straight to ``module.handle(body, ctx.tool_ctx)``.
Task 11 wraps this with Pydantic validation against each tool's INPUT_SCHEMA;
these tests pin the current shape (200 on happy path, 404 on unknown tool, 403
on missing token or wrong Origin).

The TestClient re-entry pattern (``with TestClient(app) as fresh``) is needed
wherever the test reads ``app.state.ctx.token`` — the token is populated by
the lifespan at startup, so the context manager must be active when we read it.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_dispatches_to_list_domains(app: FastAPI) -> None:
    """Happy path: valid token + loopback Origin routes to brain_list_domains."""
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "text" in body
    assert "data" in body
    assert isinstance(body["data"]["domains"], list)


def test_unknown_tool_returns_404(app: FastAPI) -> None:
    """A tool name not in the registry surfaces a structured 404."""
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/nonexistent_tool",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 404
    body = response.json()
    # Task 15 flattens the double-wrapped detail envelope; until then the shape
    # is {"detail": {"error": "not_found", "message": ...}}.
    assert body["detail"]["error"] == "not_found"
    assert "nonexistent_tool" in body["detail"]["message"]


def test_missing_token_rejected_before_dispatch(app: FastAPI) -> None:
    """No X-Brain-Token header → 403 from require_token, dispatcher never runs.

    Uses ``with TestClient(app)`` so the lifespan is active and ``require_token``
    can look up ``ctx.token`` — otherwise the dep short-circuits with
    ``RuntimeError: AppContext not initialized``.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={"Origin": "http://localhost:4317"},
        )
    assert response.status_code == 403


def test_wrong_origin_rejected_before_dispatch(app: FastAPI) -> None:
    """A cross-origin Origin → 403 from OriginHostMiddleware even with a valid token."""
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={
                "Origin": "https://evil.example",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 403
