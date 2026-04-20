"""brain_lint — STUB. Plan 09 will land the real lint engine.

Registered at the tool surface now so client discovery is stable across
releases; clients can see the tool and will get a structured
"not_implemented" response until Plan 09 delivers wikilink checking, orphan
detection, and frontmatter validation.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

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


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = arguments, ctx  # stub: no inputs consumed until Plan 09
    return ToolResult(
        text="brain_lint is not yet implemented — scheduled for Plan 09.",
        data={
            "status": "not_implemented",
            "message": "Plan 09 will land the real lint engine.",
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
