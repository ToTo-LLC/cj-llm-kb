"""Health check endpoint — always 200 unless app failed to boot."""

from __future__ import annotations

from fastapi import APIRouter

from brain_api.responses import ErrorResponse

router = APIRouter()


@router.get(
    "/healthz",
    responses={
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
)
async def healthz() -> dict[str, str]:
    """Liveness probe. No auth required.

    Declares a 500 response shape in OpenAPI for symmetry with the rest of
    the API — any unhandled exception bubbles through the catch-all in
    :mod:`brain_api.errors` and renders as the flat error envelope.
    """
    return {"status": "ok"}
