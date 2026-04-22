"""Tests for GET /api/token — Plan 08 Task 1.

The token endpoint serves the per-run secret to same-origin browser code so
the SPA can attach it as ``X-Brain-Token`` on subsequent writes. Three slices:

1. Same-origin + token present → 200 with ``{token}`` + ``Cache-Control: no-store``.
2. Cross-origin → 403 (endpoint-level Origin check).
3. No token file on disk → 503 ``setup_required`` (fresh install not done).

The shared :class:`OriginHostMiddleware` only enforces Origin on state-changing
methods (POST/PUT/DELETE) + WebSocket handshakes. GET is exempt at the
middleware layer because safe methods don't cause CSRF damage. These three
new endpoints carry sensitive information (setup state + app secret) that a
same-origin policy-evading page should not be able to read — so we layer an
explicit endpoint-level Origin check on top of the middleware to enforce
same-origin for every ``/api/setup-status``, ``/api/token``, ``/api/upload``
request, closing the gap.
"""

from __future__ import annotations

from pathlib import Path

from brain_api import create_app
from fastapi.testclient import TestClient

_LOOPBACK_ORIGIN = "http://localhost:4317"
_EVIL_ORIGIN = "http://evil.example"


def test_same_origin_with_token_returns_200_and_no_store(tmp_path: Path) -> None:
    """Loopback Origin + token file present → 200 with raw token + no-store."""
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    app = create_app(vault_root=vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        r = client.get("/api/token", headers={"Origin": _LOOPBACK_ORIGIN})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body
        assert isinstance(body["token"], str) and body["token"]
        # Matches what the lifespan minted + wrote to disk.
        assert body["token"] == app.state.ctx.token
        # Caching the token in browser / proxy intermediaries would defeat
        # rotation on ``brain start`` — pin the header explicitly.
        assert r.headers.get("Cache-Control") == "no-store"


def test_cross_origin_is_rejected(tmp_path: Path) -> None:
    """Non-loopback Origin → 403 from endpoint-level Origin check."""
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    app = create_app(vault_root=vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        r = client.get("/api/token", headers={"Origin": _EVIL_ORIGIN})
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["error"] == "refused"


def test_no_token_file_returns_503_setup_required(tmp_path: Path) -> None:
    """Token file missing on disk → 503 ``setup_required``.

    The lifespan always mints + writes a token, so we delete the file after
    startup (before the first request) to simulate the pre-setup state where
    a human has started brain but the file somehow got removed — or more
    realistically, an install-wizard boot that predates the very first token
    generation.
    """
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    app = create_app(vault_root=vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        token_file = vault / ".brain" / "run" / "api-secret.txt"
        assert token_file.exists(), "lifespan should have written the token"
        token_file.unlink()

        r = client.get("/api/token", headers={"Origin": _LOOPBACK_ORIGIN})
        assert r.status_code == 503, r.text
        body = r.json()
        assert body["error"] == "setup_required"
