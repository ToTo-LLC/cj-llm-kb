"""/api/tools — tool discovery endpoint.

Task 3 lands the GET listing. Task 10 adds the POST /api/tools/<name>
dispatcher that actually runs tool handlers.
"""

from __future__ import annotations

from typing import Any

from brain_core import tools as tools_registry
from fastapi import APIRouter

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools() -> dict[str, list[dict[str, Any]]]:
    """Return every registered tool's metadata. No auth required.

    Sorted alphabetically by ``name`` so downstream clients (Plan 07 frontend)
    can rely on stable ordering.
    """
    out: list[dict[str, Any]] = []
    for module in sorted(tools_registry.list_tools(), key=lambda m: m.NAME):
        out.append(
            {
                "name": module.NAME,
                "description": module.DESCRIPTION,
                "input_schema": module.INPUT_SCHEMA,
            }
        )
    return {"tools": out}
