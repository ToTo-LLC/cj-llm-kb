"""MCP transport shim for brain_read_note. Real handler in brain_core.tools.read_note."""

from __future__ import annotations

from typing import Any

import mcp.types as types
from brain_core.tools.read_note import DESCRIPTION, INPUT_SCHEMA, NAME
from brain_core.tools.read_note import handle as _core_handle

from brain_mcp.tools.base import ToolContext, text_result

__all__ = ["DESCRIPTION", "INPUT_SCHEMA", "NAME", "handle"]


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    """Delegate to brain_core; wrap ToolResult into MCP TextContent list."""
    result = await _core_handle(arguments, ctx)
    return text_result(result)
