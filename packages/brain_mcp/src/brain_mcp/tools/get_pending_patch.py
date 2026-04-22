"""MCP transport shim for brain_get_pending_patch. Real handler in brain_core.tools.get_pending_patch."""

from __future__ import annotations

from typing import Any

import mcp.types as types
from brain_core.rate_limit import RateLimitError
from brain_core.tools.get_pending_patch import DESCRIPTION, INPUT_SCHEMA, NAME
from brain_core.tools.get_pending_patch import handle as _core_handle

from brain_mcp.tools.base import ToolContext, text_result

__all__ = ["DESCRIPTION", "INPUT_SCHEMA", "NAME", "handle"]


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    """Delegate to brain_core; convert RateLimitError to Plan 04 inline-JSON shape.

    Matches the shim pattern of every other tool — single-shape error handling
    so readers don't have to track which tools rate-limit and future additions
    drop in without changing the transport surface.
    """
    try:
        result = await _core_handle(arguments, ctx)
    except RateLimitError as exc:
        return text_result(
            f"rate limited ({exc.bucket}/min)",
            data={
                "status": "rate_limited",
                "bucket": exc.bucket,
                "retry_after_seconds": exc.retry_after_seconds,
            },
        )
    return text_result(result)
