"""/api/tools — tool discovery + dispatcher.

Task 3 lands the GET listing. Task 10 adds the POST /api/tools/<name>
dispatcher that actually runs tool handlers.
"""

from __future__ import annotations

from typing import Any

from brain_core import tools as tools_registry
from brain_core.tools.base import ToolResult
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError
from starlette.requests import Request

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
        400: {"description": "Request body does not match tool INPUT_SCHEMA"},
        404: {"description": "Tool not registered"},
        403: {"description": "Missing or invalid X-Brain-Token"},
    },
)
async def call_tool(
    name: str,
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 — FastAPI-idiomatic Body default
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI resolves Depends lazily per request
) -> dict[str, Any]:
    """Dispatch to ``brain_core.tools.<name>.handle(body, ctx.tool_ctx)``.

    Task 11 validates the request body against the tool's ``INPUT_SCHEMA``
    before dispatch: a Pydantic model (built once at lifespan startup and
    stashed on ``app.state.tool_models``) runs ``model_validate(body)`` and
    surfaces ``ValidationError`` as a 400 with Pydantic's canonical
    ``errors()`` list. Handlers receive the validated, None-stripped dict —
    identical in shape to what they received from Task 10's bare passthrough
    for any request that would have succeeded before.

    The handler receives ``ctx.tool_ctx`` (the embedded ``ToolContext``), not
    the full ``AppContext`` — tool handlers know nothing about HTTP / FastAPI.

    Note: both the 400 and 404 bodies are currently ``{"detail": {...}}``
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

    # Validate the body against the tool's INPUT_SCHEMA. Models are built
    # once at lifespan startup (app.state.tool_models); a KeyError here would
    # indicate a registration mismatch between ctx.tool_by_name and the
    # startup builder — fail loud (500) rather than mask as 404.
    model_cls = request.app.state.tool_models[name]
    try:
        validated = model_cls.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_input",
                "message": f"request body does not match {name!r} INPUT_SCHEMA",
                "errors": exc.errors(),
            },
        ) from exc

    # ``exclude_none=True`` strips optional fields that defaulted to None so
    # handlers see the same dict shape they did under Task 10's passthrough.
    result: ToolResult = await module.handle(
        validated.model_dump(exclude_none=True),
        ctx.tool_ctx,
    )
    return {"text": result.text, "data": result.data}
