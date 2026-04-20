"""MCP-transport helpers for brain_mcp tools.

``ToolContext``, ``ToolResult``, and ``scope_guard_path`` are re-exported
verbatim from ``brain_core.tools.base`` — identity preserved, no subclass or
alias wrapping, so any test that compares classes sees the same object.

``text_result`` lives here because it is MCP-SDK-specific: it returns
``list[mcp.types.TextContent]``. The overloaded signature keeps Plan 04 call
sites working while letting Task 5/6 shims wrap a ``ToolResult`` directly.
``ToolModule`` re-exports the ``ModuleType`` alias from ``brain_core.tools``
so ``brain_mcp.server`` stays on the current import path.
"""

from __future__ import annotations

import json
from typing import Any

import mcp.types as types
from brain_core.tools import ToolModule
from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path

__all__ = [
    "ToolContext",
    "ToolModule",
    "ToolResult",
    "scope_guard_path",
    "text_result",
]


def text_result(
    text_or_result: str | ToolResult,
    *,
    data: dict[str, Any] | None = None,
) -> list[types.TextContent]:
    """Wrap a tool's output into the MCP SDK's TextContent list shape.

    Two call forms for backwards compat with Plan 04 handlers:

    - ``text_result("summary text", data={"k": "v"})`` — Plan 04 form, preserved.
    - ``text_result(ToolResult(text="summary", data={...}))`` — Task 5/6 shim form.

    If structured ``data`` is present, a second ``TextContent`` containing the
    JSON encoding is appended. Clients (Claude Desktop) render both.
    """
    if isinstance(text_or_result, ToolResult):
        text = text_or_result.text
        data = text_or_result.data
    else:
        text = text_or_result

    out: list[types.TextContent] = [types.TextContent(type="text", text=text)]
    if data is not None:
        out.append(types.TextContent(type="text", text=json.dumps(data, indent=2, default=str)))
    return out
