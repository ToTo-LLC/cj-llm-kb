"""Tests for ``require_token`` dependency — run against a synthetic endpoint.

Plan 05 Task 9. Real write endpoints land in Group 4 (Task 10+); we exercise
the dep in isolation here by attaching it to a test-only POST route.
"""

from __future__ import annotations

from brain_api.auth import require_token
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


def _attach_synthetic_write_route(app: FastAPI) -> None:
    """Add a test-only route that requires the token dep.

    Defined inline per-test so each test gets a fresh registration on the
    shared ``app`` fixture. TestClient re-entry picks up the new route.
    """

    @app.post("/_synthetic_write", dependencies=[Depends(require_token)])
    async def synthetic() -> dict[str, bool]:
        return {"ok": True}


def test_missing_token_rejected(app: FastAPI) -> None:
    _attach_synthetic_write_route(app)
    with TestClient(app, base_url="http://localhost") as fresh:
        response = fresh.post(
            "/_synthetic_write",
            json={},
            headers={"Origin": "http://localhost:4317"},
        )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "refused"
    assert "X-Brain-Token" in body["detail"]["message"]


def test_wrong_token_rejected(app: FastAPI) -> None:
    _attach_synthetic_write_route(app)
    with TestClient(app, base_url="http://localhost") as fresh:
        response = fresh.post(
            "/_synthetic_write",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": "0" * 64,
            },
        )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "refused"


def test_correct_token_accepted(app: FastAPI) -> None:
    _attach_synthetic_write_route(app)
    with TestClient(app, base_url="http://localhost") as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/_synthetic_write",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
