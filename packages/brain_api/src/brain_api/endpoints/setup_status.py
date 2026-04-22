"""GET /api/setup-status — Plan 08 Task 1.

The browser's first handshake with a fresh brain install. Reports three
booleans plus the vault path so the SPA can decide whether to redirect to the
setup wizard or go straight to chat. Pure filesystem — no LLM, no DB touch,
no token required (a pre-setup install has no token yet).

Contract::

    {
      "has_token":    bool,   # <vault>/.brain/run/api-secret.txt exists
      "is_first_run": bool,   # !has_token OR !vault_exists OR !BRAIN.md
      "vault_exists": bool,   # vault_root is a directory
      "vault_path":   str,    # str(vault_root)
    }

Endpoint-level Origin gate on top of the shared middleware (GET is otherwise
Origin-exempt; see :mod:`brain_api.endpoints._origin`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from brain_api.context import AppContext, get_ctx
from brain_api.endpoints._origin import require_loopback_origin

router = APIRouter(tags=["setup"])


class SetupStatusResponse(BaseModel):
    """Typed response body for the setup-status endpoint."""

    has_token: bool
    is_first_run: bool
    vault_exists: bool
    vault_path: str


@router.get(
    "/api/setup-status",
    response_model=SetupStatusResponse,
    dependencies=[Depends(require_loopback_origin)],
    summary="Report fresh-install state to the browser.",
)
async def get_setup_status(
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI Depends idiom
) -> SetupStatusResponse:
    """Return the three booleans the setup wizard consumes on mount."""
    vault_root = ctx.vault_root
    vault_exists = vault_root.is_dir()
    token_path = vault_root / ".brain" / "run" / "api-secret.txt"
    has_token = token_path.exists()
    brain_md_exists = (vault_root / "BRAIN.md").exists()

    is_first_run = (not has_token) or (not vault_exists) or (not brain_md_exists)

    return SetupStatusResponse(
        has_token=has_token,
        is_first_run=is_first_run,
        vault_exists=vault_exists,
        vault_path=str(vault_root),
    )
