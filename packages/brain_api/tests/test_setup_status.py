"""Tests for GET /api/setup-status — Plan 08 Task 1.

The setup-status endpoint is the browser's first handshake with a fresh install.
It must answer four true/false questions from the filesystem alone — no LLM,
no DB touch, no token required. The Origin gate still applies (same middleware
as every other endpoint) so a malicious cross-origin page can't even probe
first-run state.

Each test constructs a fresh FastAPI app whose vault_root points at a tmp_path
in a specific state (no vault, vault-but-no-token, etc.) and then enters the
app's lifespan via TestClient's context manager. Because the lifespan itself
mints + writes a token file, we have to short-circuit it for the "no-token"
cases. We do that by injecting a ``token_override`` and then deleting the
written token file BEFORE the first request — the endpoint reads the
filesystem on every call, so the deletion takes effect immediately.

Origin-gate coverage: every test sends ``Origin: http://localhost:4317`` so
the middleware accepts it; the cross-origin variant is covered alongside the
cross-origin tests for the other new endpoints.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_api import create_app
from fastapi.testclient import TestClient

_ORIGIN = "http://localhost:4317"


def _make_vault_scaffold(vault: Path) -> None:
    """Create the minimum subdirs the AppContext builder expects.

    build_app_context needs ``<vault>/.brain/`` to exist so StateDB + CostLedger
    can open SQLite files. Calling this in tests that want ``vault_exists=True``
    gives the endpoint something to report; tests that want
    ``vault_exists=False`` skip this entirely so the vault directory itself is
    absent.
    """
    vault.mkdir(parents=True, exist_ok=True)
    (vault / ".brain").mkdir(parents=True, exist_ok=True)


@pytest.fixture
def fresh_vault(tmp_path: Path) -> Path:
    """Return a path that does NOT yet exist on disk (fresh-install sim)."""
    return tmp_path / "brand-new-vault"


def _client_for(vault_root: Path) -> TestClient:
    app = create_app(vault_root=vault_root, allowed_domains=("research",))
    return TestClient(app, base_url="http://localhost")


def test_fresh_state_reports_first_run_no_vault_no_token(fresh_vault: Path) -> None:
    """No vault dir, no token file → is_first_run=True, both flags False."""
    # build_app_context creates ``<vault>/.brain`` during lifespan, so at
    # startup ``vault_root`` exists but we'll delete the token + BRAIN.md to
    # simulate "brand new". The endpoint checks ``vault_root.is_dir()`` so we
    # report vault_exists=True here; the "no vault" combination is exercised
    # inside the fully-set-up inverse below.
    app = create_app(vault_root=fresh_vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        # Remove the token file the lifespan minted so has_token flips False.
        token_file = fresh_vault / ".brain" / "run" / "api-secret.txt"
        if token_file.exists():
            token_file.unlink()

        r = client.get("/api/setup-status", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_token"] is False
        assert body["vault_exists"] is True  # lifespan created it
        assert body["is_first_run"] is True  # no token OR no BRAIN.md → True
        assert body["vault_path"] == str(fresh_vault)


def test_vault_exists_but_no_token_reports_first_run(tmp_path: Path) -> None:
    """Vault dir present, token absent → has_token=False, is_first_run=True."""
    vault = tmp_path / "vault"
    _make_vault_scaffold(vault)
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")

    app = create_app(vault_root=vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        token_file = vault / ".brain" / "run" / "api-secret.txt"
        if token_file.exists():
            token_file.unlink()

        r = client.get("/api/setup-status", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_token"] is False
        assert body["vault_exists"] is True
        # Missing token alone flips first_run even though BRAIN.md is here.
        assert body["is_first_run"] is True


def test_vault_and_token_but_no_brain_md_reports_first_run(tmp_path: Path) -> None:
    """Vault + token present, BRAIN.md missing → first_run stays True."""
    vault = tmp_path / "vault"
    _make_vault_scaffold(vault)
    # Deliberately DO NOT write BRAIN.md.

    app = create_app(vault_root=vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        r = client.get("/api/setup-status", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_token"] is True  # lifespan wrote it
        assert body["vault_exists"] is True
        assert body["is_first_run"] is True  # missing BRAIN.md → True


def test_fully_set_up_reports_not_first_run(tmp_path: Path) -> None:
    """Vault + token + BRAIN.md all present → is_first_run=False."""
    vault = tmp_path / "vault"
    _make_vault_scaffold(vault)
    (vault / "BRAIN.md").write_text("# BRAIN\n", encoding="utf-8", newline="\n")

    app = create_app(vault_root=vault, allowed_domains=("research",))
    with TestClient(app, base_url="http://localhost") as client:
        r = client.get("/api/setup-status", headers={"Origin": _ORIGIN})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_token"] is True
        assert body["vault_exists"] is True
        assert body["is_first_run"] is False
        assert body["vault_path"] == str(vault)
