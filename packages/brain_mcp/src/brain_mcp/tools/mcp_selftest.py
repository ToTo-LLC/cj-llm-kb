"""MCP transport shim for brain_mcp_selftest.

Real handler in brain_core.tools.mcp_selftest.
"""

from __future__ import annotations

from typing import Any

import mcp.types as types
from brain_core.tools.base import ToolContext
from brain_core.tools.mcp_selftest import DESCRIPTION, INPUT_SCHEMA, NAME
from brain_core.tools.mcp_selftest import handle as _core_handle

from brain_mcp.tools.base import text_result

__all__ = ["DESCRIPTION", "INPUT_SCHEMA", "NAME", "handle"]


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    result = await _core_handle(arguments, ctx)
    return text_result(result)
