"""GET /api/token — Plan 08 Task 1.

Hand the per-run app secret to same-origin browser code so the SPA can attach
it as ``X-Brain-Token`` on every subsequent write. Reads the token directly
from the disk (``<vault>/.brain/run/api-secret.txt``) rather than from
``AppContext.token`` so that if a ``brain start`` cycle rotates the token and
the file gets rewritten, the next ``/api/token`` fetch picks up the new value
even within the same Python process (not something we rely on today, but a
useful property for future in-place reload).

Response::

    {"token": "<hex>"}          (200)
    {"error": "setup_required"} (503 — token file missing)

The response always carries ``Cache-Control: no-store`` so browser + proxy
intermediaries can't serve a stale secret after rotation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from brain_api.auth import read_token_file
from brain_api.context import AppContext, get_ctx
from brain_api.endpoints._origin import require_loopback_origin
from brain_api.errors import ApiError

router = APIRouter(tags=["setup"])


class TokenResponse(BaseModel):
    """Typed response body for the token endpoint."""

    token: str


@router.get(
    "/api/token",
    response_model=TokenResponse,
    dependencies=[Depends(require_loopback_origin)],
    summary="Return the per-run app secret to same-origin callers.",
)
async def get_token(
    response: Response,
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI Depends idiom
) -> TokenResponse:
    """Return ``{token}`` to a loopback caller or 503 if no token on disk."""
    token = read_token_file(ctx.vault_root)
    if token is None:
        raise ApiError(
            status=503,
            code="setup_required",
            message="brain is not yet set up; token file missing",
        )
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(token=token)
