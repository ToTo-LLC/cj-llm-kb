"""brain_lint — STUB. Plan 09 will land the real lint engine.

Registered at the MCP tool surface now so Claude Desktop discovery is stable
across releases; clients can see the tool and will get a structured
"not_implemented" response until Plan 09 delivers wikilink checking, orphan
detection, and frontmatter validation.
"""

from __future__ import annotations

from typing import Any

import mcp.types as types

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_lint"
DESCRIPTION = (
    "[Stub] Vault lint — checks for broken wikilinks, orphan notes, "
    "missing frontmatter. Not yet implemented (scheduled for Plan 09)."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "description": "Optional domain to lint"},
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    return text_result(
        "brain_lint is not yet implemented — scheduled for Plan 09.",
        data={
            "status": "not_implemented",
            "message": "Plan 09 will land the real lint engine.",
        },
    )
