"""Tests for OriginHostMiddleware — DNS rebinding + cross-origin CSRF defense.

Plan 05 Task 8. The middleware is installed globally on the FastAPI app
(see ``brain_api.app.create_app``); these tests exercise the HTTP layer
via ``TestClient``. WebSocket upgrade semantics are covered indirectly
here (the middleware runs on any HTTP request including the handshake);
real WS routes land in Group 6.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestHostValidation:
    def test_accepts_localhost(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "localhost:4317"})
        assert response.status_code == 200

    def test_accepts_127_0_0_1(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "127.0.0.1:4317"})
        assert response.status_code == 200

    def test_accepts_bare_localhost_no_port(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "localhost"})
        assert response.status_code == 200

    def test_rejects_evil_host(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "evil.example"})
        assert response.status_code == 403
        body = response.json()
        assert body["error"] == "refused"

    def test_rejects_public_ip_host(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "203.0.113.10:4317"})
        assert response.status_code == 403


class TestOriginValidation:
    def test_get_with_no_origin_allowed(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_get_with_evil_origin_allowed(self, client: TestClient) -> None:
        """GET is a safe method — Origin doesn't matter for read-only endpoints."""
        response = client.get("/healthz", headers={"Origin": "https://evil.example"})
        assert response.status_code == 200

    def test_post_with_evil_origin_rejected(self, client: TestClient) -> None:
        """Synthetic POST route for this test — Task 10 adds the real ones.

        Even though the target path does not yet exist, the middleware short-
        circuits at 403 before routing is consulted.
        """
        response = client.post(
            "/api/tools/_synthetic_write",
            json={},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["error"] == "refused"
        assert "origin" in body["message"].lower()

    def test_post_with_localhost_origin_allowed_through_middleware(self, app: FastAPI) -> None:
        """Localhost Origin passes the middleware; downstream handlers take over.

        The POST /api/tools/{name} dispatcher exists, so this hits
        ``enforce_json_accept`` (ok, no Accept) then ``require_token`` (403:
        missing token). Post-Task-15 both middleware and require_token use the
        same flat envelope, so we distinguish by message content: the
        middleware refers to ``host``/``origin`` values, while ``require_token``
        names the missing ``X-Brain-Token`` header. Requires
        ``with TestClient(app)`` so the lifespan populates ``app.state.ctx``.
        """
        with TestClient(app, base_url="http://localhost") as fresh:
            response = fresh.post(
                "/api/tools/_synthetic_write",
                json={},
                headers={"Origin": "http://localhost:4317"},
            )
        # Middleware accepts; any 403 here is from require_token downstream,
        # which names the missing header, not an origin/host value.
        body = response.json()
        message = body.get("message", "").lower()
        assert "origin" not in message
        assert "host" not in message

    def test_post_with_null_origin_allowed(self, app: FastAPI) -> None:
        """Native clients (curl, CLI) send no Origin header — allowed by middleware."""
        with TestClient(app, base_url="http://localhost") as fresh:
            response = fresh.post("/api/tools/_synthetic_write", json={})
        # Middleware accepts; see the comment on the previous test for why we
        # check the message content rather than the error code.
        body = response.json()
        message = body.get("message", "").lower()
        assert "origin" not in message
        assert "host" not in message

    def test_post_with_127_origin_allowed(self, app: FastAPI) -> None:
        """Bonus: 127.0.0.1 origin also passes the middleware."""
        with TestClient(app, base_url="http://localhost") as fresh:
            response = fresh.post(
                "/api/tools/_synthetic_write",
                json={},
                headers={"Origin": "http://127.0.0.1:4317"},
            )
        # Middleware accepts; see the comment on the first test in this block
        # for why we check the message content rather than the error code.
        body = response.json()
        message = body.get("message", "").lower()
        assert "origin" not in message
        assert "host" not in message
