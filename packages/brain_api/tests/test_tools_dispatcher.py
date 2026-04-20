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


def test_missing_required_field_returns_400(app: FastAPI) -> None:
    """Task 11: a missing ``required`` field surfaces a 400 with ``errors`` list.

    ``brain_propose_note`` requires ``path``, ``content``, and ``reason``. Sending
    only ``path`` must be rejected before the handler runs — the handler never
    sees a half-populated dict.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_propose_note",
            json={"path": "research/notes/x.md"},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 400
    body = response.json()
    # Task 15 will flatten the ``{"detail": {...}}`` wrap; until then pin
    # the current shape so callers can parse field-level errors.
    assert body["detail"]["error"] == "invalid_input"
    assert isinstance(body["detail"]["errors"], list)
    assert body["detail"]["errors"], "errors list should not be empty"


def test_wrong_type_returns_400(app: FastAPI) -> None:
    """Task 11: a wrong-typed field surfaces a 400 from Pydantic coercion failure.

    ``brain_search``'s ``top_k`` is ``{"type": "integer"}``. A non-numeric string
    like ``"not-an-int"`` can't coerce and must produce a 400 — the handler's
    own ``int(...)`` coercion is a last line of defense, not a validation layer.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_search",
            json={"query": "x", "top_k": "not-an-int"},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "invalid_input"
