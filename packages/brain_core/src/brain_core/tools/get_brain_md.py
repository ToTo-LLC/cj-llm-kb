"""brain_get_brain_md — read the vault-root BRAIN.md system prompt."""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_get_brain_md"
DESCRIPTION = (
    "Read BRAIN.md at the vault root — the user's system prompt / persona / working rules."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    brain_md = ctx.vault_root / "BRAIN.md"
    if not brain_md.exists():
        return ToolResult(
            text="(no BRAIN.md yet — run `brain setup` to seed one)",
            data={"exists": False, "body": ""},
        )
    body = brain_md.read_text(encoding="utf-8")
    return ToolResult(text=body, data={"exists": True, "body": body})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
