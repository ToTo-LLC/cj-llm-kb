"""brain_get_index — read a domain's index.md via MCP."""

from __future__ import annotations

from typing import Any

import mcp.types as types
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter
from brain_core.vault.paths import ScopeError, scope_guard

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_get_index"
DESCRIPTION = "Read the <domain>/index.md file. Defaults to the first allowed domain."
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {
            "type": "string",
            "description": "Domain name. Omit to use the first allowed domain.",
        },
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    domain = str(arguments.get("domain") or ctx.allowed_domains[0])
    if domain not in ctx.allowed_domains:
        raise ScopeError(f"domain {domain!r} not in allowed {ctx.allowed_domains}")
    index_path = scope_guard(
        ctx.vault_root / domain / "index.md",
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
    )
    if not index_path.exists():
        return text_result("(no index yet)", data={"domain": domain, "body": ""})
    raw = index_path.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(raw)
    except FrontmatterError:
        fm, body = {}, raw
    return text_result(body, data={"domain": domain, "frontmatter": fm, "body": body})
