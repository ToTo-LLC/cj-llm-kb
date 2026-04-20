"""Tests for AppContext + get_ctx dependency.

Task 2 verifies:
  1. The lifespan populates app.state.ctx with an AppContext whose embedded
     ToolContext agrees on vault_root and allowed_domains.
  2. Lifespan teardown does not destroy the on-disk vault/state artifacts.
  3. The get_ctx FastAPI dependency returns the SAME AppContext instance
     that the lifespan stashed on app.state.ctx (identity, not just equality).
"""

from __future__ import annotations

from pathlib import Path

from brain_api.context import AppContext, get_ctx
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


def test_ctx_populated_during_lifespan(app: FastAPI) -> None:
    """Entering the app's lifespan populates app.state.ctx."""
    with TestClient(app):
        ctx = app.state.ctx
        assert ctx is not None
        assert isinstance(ctx, AppContext)
        assert ctx.vault_root.exists()
        assert ctx.allowed_domains == ("research",)
        # Token defaults to None until Task 7 populates it.
        assert ctx.token is None
        # ToolContext embedded inside — single source of truth for the 10 primitives.
        assert ctx.tool_ctx.vault_root == ctx.vault_root
        assert ctx.tool_ctx.allowed_domains == ctx.allowed_domains


def test_ctx_teardown_preserves_vault(app: FastAPI, seeded_vault: Path) -> None:
    """Exiting the lifespan does not destroy vault artifacts."""
    state_db_path = seeded_vault / ".brain" / "state.sqlite"
    with TestClient(app):
        assert state_db_path.exists()  # DB opened at lifespan start
    # After lifespan exit, the vault and state db file both still exist —
    # teardown is non-destructive. True close semantics verified by Group 6.
    assert seeded_vault.exists()
    assert state_db_path.exists()


def test_get_ctx_dependency_resolves(app: FastAPI) -> None:
    """get_ctx returns the same AppContext instance stashed on app.state.ctx."""

    @app.get("/_ctx_echo")
    async def echo(
        ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI resolves Depends at call time
    ) -> dict[str, object]:
        return {"vault_root": str(ctx.vault_root), "id": id(ctx)}

    with TestClient(app) as c:
        state_id = id(app.state.ctx)
        expected_root = str(app.state.ctx.vault_root)
        response = c.get("/_ctx_echo")

    assert response.status_code == 200
    body = response.json()
    # Identity check — the dependency must return the lifespan-stashed instance,
    # not a fresh build_app_context() call.
    assert body["id"] == state_id
    assert body["vault_root"] == expected_root
