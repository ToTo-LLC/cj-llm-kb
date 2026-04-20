"""MCP transport shim for brain_search. Real handler in brain_core.tools.search."""

from __future__ import annotations

from typing import Any

import mcp.types as types
from brain_core.rate_limit import RateLimitError
from brain_core.tools.search import DESCRIPTION, INPUT_SCHEMA, NAME
from brain_core.tools.search import handle as _core_handle

from brain_mcp.tools.base import ToolContext, text_result

__all__ = ["DESCRIPTION", "INPUT_SCHEMA", "NAME", "handle"]


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    """Delegate to brain_core; convert RateLimitError to Plan 04 inline-JSON shape.

    The try/except pattern is applied uniformly to every shim — most tools
    never call rate_limiter.check(), but keeping the shim single-shape means
    readers don't have to track which tools rate-limit and future additions
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
