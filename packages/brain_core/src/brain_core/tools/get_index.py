"""brain_get_index — read a domain's index.md."""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter
from brain_core.vault.paths import ScopeError, scope_guard

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


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    domain = str(arguments.get("domain") or ctx.allowed_domains[0])
    if domain not in ctx.allowed_domains:
        raise ScopeError(f"domain {domain!r} not in allowed {ctx.allowed_domains}")
    index_path = scope_guard(
        ctx.vault_root / domain / "index.md",
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
    )
    if not index_path.exists():
        # Shape parity with the happy path: callers can unconditionally read
        # data["frontmatter"] without a KeyError on the miss branch.
        return ToolResult(
            text="(no index yet)", data={"domain": domain, "frontmatter": {}, "body": ""}
        )
    raw = index_path.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(raw)
    except FrontmatterError:
        fm, body = {}, raw
    return ToolResult(text=body, data={"domain": domain, "frontmatter": fm, "body": body})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
