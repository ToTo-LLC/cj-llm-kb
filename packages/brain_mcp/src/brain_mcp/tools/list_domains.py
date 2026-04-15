"""brain_list_domains — list top-level domain directories in the vault."""

from __future__ import annotations

from typing import Any

import mcp.types as types

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_list_domains"
DESCRIPTION = (
    "List the top-level domain directories in the vault "
    "(research / work / personal / ...). Metadata-only; returns names sorted alphabetically."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    _ = arguments  # no inputs
    domains: list[str] = []
    if ctx.vault_root.exists():
        for child in sorted(ctx.vault_root.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue  # Skip .brain, .git, etc.
            if (child / "index.md").exists() or any(child.rglob("*.md")):
                domains.append(child.name)
    text = "\n".join(f"- {d}" for d in domains) if domains else "(no domains)"
    return text_result(text, data={"domains": domains})
