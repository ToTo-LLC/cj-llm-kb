"""/api/tools — tool discovery + dispatcher.

Task 3 lands the GET listing. Task 10 adds the POST /api/tools/<name>
dispatcher that actually runs tool handlers.
"""

from __future__ import annotations

from typing import Any

from brain_core import tools as tools_registry
from brain_core.tools.base import ToolResult
from fastapi import APIRouter, Body, Depends, HTTPException

from brain_api.auth import require_token
from brain_api.context import AppContext, get_ctx

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


@router.post(
    "/{name}",
    dependencies=[Depends(require_token)],
    summary="Call a brain tool by name.",
    responses={
        404: {"description": "Tool not registered"},
        403: {"description": "Missing or invalid X-Brain-Token"},
    },
)
async def call_tool(
    name: str,
    body: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 — FastAPI-idiomatic Body default
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI resolves Depends lazily per request
) -> dict[str, Any]:
    """Dispatch to ``brain_core.tools.<name>.handle(body, ctx.tool_ctx)``.

    Task 10 is a bare passthrough: request body is forwarded to the handler
    as-is. Task 11 adds a Pydantic validator in front of this dispatcher that
    rejects mismatched input with a 400 before the handler runs.

    The handler receives ``ctx.tool_ctx`` (the embedded ``ToolContext``), not
    the full ``AppContext`` — tool handlers know nothing about HTTP / FastAPI.

    Note: the 404 body is currently ``{"detail": {"error": "not_found", ...}}``
    because FastAPI wraps :class:`HTTPException` detail under a top-level
    ``detail`` key. Plan 05 Task 15 flattens this via a project-wide exception
    handler so the envelope matches ``{"error", "message"}`` everywhere.
    """
    module = ctx.tool_by_name.get(name)
    if module is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"tool {name!r} is not registered",
            },
        )
    result: ToolResult = await module.handle(body, ctx.tool_ctx)
    return {"text": result.text, "data": result.data}
