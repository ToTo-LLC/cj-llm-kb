"""brain_get_brain_md — read the vault-root BRAIN.md system prompt."""

from __future__ import annotations

from typing import Any

import mcp.types as types

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_get_brain_md"
DESCRIPTION = (
    "Read BRAIN.md at the vault root — the user's system prompt / persona / working rules."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    brain_md = ctx.vault_root / "BRAIN.md"
    if not brain_md.exists():
        return text_result(
            "(no BRAIN.md yet — run `brain setup` to seed one)",
            data={"exists": False, "body": ""},
        )
    body = brain_md.read_text(encoding="utf-8")
    return text_result(body, data={"exists": True, "body": body})
