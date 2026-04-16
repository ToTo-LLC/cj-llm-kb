"""brain_read_note — read a note by vault-relative path via MCP."""

from __future__ import annotations

from typing import Any

import mcp.types as types
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter

from brain_mcp.tools.base import ToolContext, scope_guard_path, text_result

NAME = "brain_read_note"
DESCRIPTION = "Read a note by vault-relative path. Returns frontmatter + body."
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Vault-relative path like 'research/notes/karpathy.md'",
        },
    },
    "required": ["path"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    raw = str(arguments["path"])
    full = scope_guard_path(raw, ctx)
    if not full.exists():
        raise FileNotFoundError(f"note {raw!r} not found in vault")
    text = full.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except FrontmatterError:
        fm, body = {}, text
    return text_result(body, data={"frontmatter": fm, "body": body, "path": raw})
