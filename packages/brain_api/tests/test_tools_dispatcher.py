"""Tests for POST /api/tools/<name> dispatcher.

Task 10 landed the dispatcher; Task 11 added Pydantic validation against each
tool's INPUT_SCHEMA; Task 12 pinned the response envelope; Task 15 wired the
project-wide exception handlers that turn every 4xx into the flat
``{"error", "message", "detail"}`` shape (no double-nested ``detail`` wrap).
These tests pin all four contracts: 200 on happy path, 400 on validation
failure, 403 on missing token / wrong Origin, 404 on unknown tool, 406 on
narrow Accept header.

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
    # Task 15 flattened the envelope: top-level "error" / "message"; no
    # ``detail`` wrap. Shape is {"error": "not_found", "message": ..., "detail": None}.
    assert body["error"] == "not_found"
    assert "nonexistent_tool" in body["message"]


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
    # Task 15 flattened the envelope: top-level "error" / "message"; the
    # Pydantic errors() list stays nested under "detail.errors" (structured
    # payload, not a prose message).
    assert body["error"] == "invalid_input"
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
    assert body["error"] == "invalid_input"


def test_response_shape_is_envelope(app: FastAPI) -> None:
    """Task 12: successful response is exactly ``{"text", "data"}`` — no extras.

    FastAPI serializes against ``response_model=ToolResponse``, so any keys the
    handler returns beyond ``text`` / ``data`` are dropped. Pin the contract
    so future additions (e.g. rate-limit hints) can't silently leak through.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
                "Accept": "application/json",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"text", "data"}
    assert isinstance(body["text"], str)


def test_nonjson_accept_rejected(app: FastAPI) -> None:
    """Task 12: ``Accept: text/html`` → 406, dispatcher never runs.

    ``enforce_json_accept`` runs BEFORE ``require_token`` so clients get a
    useful content-negotiation error even when the token is present — the
    tighter error code helps callers debug faster.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
                "Accept": "text/html",
            },
        )
    assert response.status_code == 406


def test_wildcard_accept_allowed(app: FastAPI) -> None:
    """Task 12: ``Accept: */*`` is the browser default — must pass."""
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
                "Accept": "*/*",
            },
        )
    assert response.status_code == 200


def test_missing_accept_allowed(app: FastAPI) -> None:
    """Task 12: clients without Accept (curl default) are accepted.

    A missing Accept header is conventionally treated as ``*/*``; refusing
    would break every curl invocation that doesn't explicitly opt in.
    """
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
