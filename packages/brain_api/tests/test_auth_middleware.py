"""Tests for OriginHostMiddleware — DNS rebinding + cross-origin CSRF defense.

Plan 05 Task 8. The middleware is installed globally on the FastAPI app
(see ``brain_api.app.create_app``); these tests exercise the HTTP layer
via ``TestClient``. WebSocket upgrade semantics are covered indirectly
here (the middleware runs on any HTTP request including the handshake);
real WS routes land in Group 6.
"""

from __future__ import annotations

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

    def test_post_with_localhost_origin_allowed_through_middleware(
        self, client: TestClient
    ) -> None:
        """Localhost Origin passes the middleware; the 404/405 that follows is
        from the non-existent route, not from the middleware."""
        response = client.post(
            "/api/tools/_synthetic_write",
            json={},
            headers={"Origin": "http://localhost:4317"},
        )
        # Middleware accepts; Task 10-era routing returns 404 for the unknown tool.
        # In Task 8 pre-Task-10, the POST handler doesn't exist → 404 or 405.
        assert response.status_code != 403 or response.json().get("error") != "refused"

    def test_post_with_null_origin_allowed(self, client: TestClient) -> None:
        """Native clients (curl, CLI) send no Origin header — allowed."""
        response = client.post("/api/tools/_synthetic_write", json={})
        # Middleware accepts; route lookup fails → not a 403 from middleware.
        assert response.status_code != 403 or response.json().get("error") != "refused"

    def test_post_with_127_origin_allowed(self, client: TestClient) -> None:
        """Bonus: 127.0.0.1 origin also passes the middleware."""
        response = client.post(
            "/api/tools/_synthetic_write",
            json={},
            headers={"Origin": "http://127.0.0.1:4317"},
        )
        assert response.status_code != 403 or response.json().get("error") != "refused"
