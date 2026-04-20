"""brain_read_note — read a note by vault-relative path."""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter

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


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    raw = str(arguments["path"])
    full = scope_guard_path(raw, ctx)
    if not full.exists():
        raise FileNotFoundError(f"note {raw!r} not found in vault")
    text = full.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except FrontmatterError:
        fm, body = {}, text
    return ToolResult(text=body, data={"frontmatter": fm, "body": body, "path": raw})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
