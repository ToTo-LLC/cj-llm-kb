"""/api/tools — tool discovery + dispatcher.

Task 3 lands the GET listing. Task 10 adds the POST /api/tools/<name>
dispatcher that actually runs tool handlers.
"""

from __future__ import annotations

from typing import Any

from brain_core import tools as tools_registry
from brain_core.tools.base import ToolResult
from fastapi import APIRouter, Body, Depends
from starlette.requests import Request

from brain_api.auth import enforce_json_accept, require_token
from brain_api.context import AppContext, get_ctx
from brain_api.errors import ApiError
from brain_api.responses import ErrorResponse, ToolResponse

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
    response_model=ToolResponse,
    dependencies=[Depends(enforce_json_accept), Depends(require_token)],
    summary="Call a brain tool by name.",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Request body does not match tool INPUT_SCHEMA",
        },
        403: {"model": ErrorResponse, "description": "Missing or invalid X-Brain-Token"},
        404: {"model": ErrorResponse, "description": "Tool not registered"},
        406: {"model": ErrorResponse, "description": "Accept header excludes application/json"},
    },
)
async def call_tool(
    name: str,
    request: Request,
    body: dict[str, Any] = Body(default_factory=dict),  # noqa: B008 — FastAPI-idiomatic Body default
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI resolves Depends lazily per request
) -> ToolResponse:
    """Dispatch to ``brain_core.tools.<name>.handle(body, ctx.tool_ctx)``.

    Task 11 validates the request body against the tool's ``INPUT_SCHEMA``
    before dispatch: a Pydantic model (built once at lifespan startup and
    stashed on ``app.state.tool_models``) runs ``model_validate(body)`` and
    surfaces ``ValidationError`` as a 400 with Pydantic's canonical
    ``errors()`` list. Handlers receive the validated, None-stripped dict —
    identical in shape to what they received from Task 10's bare passthrough
    for any request that would have succeeded before.

    Task 12 pins the response envelope as :class:`ToolResponse` so FastAPI
    serializes handler output against a typed schema (extra keys dropped at
    the wire) and the ``/docs`` page advertises a concrete 200 body rather
    than a generic ``object``. The same task adds content-negotiation via
    ``enforce_json_accept`` — clients that send ``Accept: text/html`` or
    similar get a 406 *before* the tool is even looked up. The dependency
    order matters: ``enforce_json_accept`` runs first so a wrong Accept
    short-circuits to 406, a clearer signal than 403 for a client-side bug.

    The handler receives ``ctx.tool_ctx`` (the embedded ``ToolContext``), not
    the full ``AppContext`` — tool handlers know nothing about HTTP / FastAPI.

    Task 15 wires the project-wide exception handlers. Both the 404 (unknown
    tool) and the 400 (INPUT_SCHEMA validation) now render as the flat
    ``{"error", "message", "detail"}`` envelope: the 404 via :class:`ApiError`
    raised here, the 400 via a bare :class:`pydantic.ValidationError` that
    bubbles out of ``model_validate`` and is mapped by
    :func:`brain_api.errors.register_error_handlers`.
    """
    module = ctx.tool_by_name.get(name)
    if module is None:
        raise ApiError(
            status=404,
            code="not_found",
            message=f"tool {name!r} is not registered",
        )

    # Validate the body against the tool's INPUT_SCHEMA. Models are built
    # once at lifespan startup (app.state.tool_models); a KeyError here would
    # indicate a registration mismatch between ctx.tool_by_name and the
    # startup builder — fail loud (500) rather than mask as 404.
    #
    # ``ValidationError`` bubbles out by design: the global handler in
    # ``brain_api.errors`` maps it to a 400 with ``detail.errors`` carrying
    # Pydantic's canonical ``errors()`` list, so the flat envelope is
    # consistent with every other 400 the API emits.
    model_cls = request.app.state.tool_models[name]
    validated = model_cls.model_validate(body)

    # ``exclude_none=True`` strips optional fields that defaulted to None so
    # handlers see the same dict shape they did under Task 10's passthrough.
    result: ToolResult = await module.handle(
        validated.model_dump(exclude_none=True),
        ctx.tool_ctx,
    )
    return ToolResponse(text=result.text, data=result.data)
