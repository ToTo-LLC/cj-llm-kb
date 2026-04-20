"""Health check endpoint — always 200 unless app failed to boot."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe. No auth required."""
    return {"status": "ok"}
