"""list_index tool — read a domain's index.md."""

from __future__ import annotations

from typing import Any

from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter
from brain_core.vault.paths import ScopeError, scope_guard


class ListIndexTool:
    name = "list_index"
    description = "Read the <domain>/index.md file. Defaults to the first allowed domain."
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {"domain": {"type": "string"}},
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        domain = str(args.get("domain") or ctx.allowed_domains[0])
        if domain not in ctx.allowed_domains:
            raise ScopeError(f"domain {domain!r} not in allowed {ctx.allowed_domains}")
        index_path = scope_guard(
            ctx.vault_root / domain / "index.md",
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        if not index_path.exists():
            return ToolResult(
                text="(no index yet)",
                data={"domain": domain, "frontmatter": {}, "body": ""},
            )
        raw = index_path.read_text(encoding="utf-8")
        try:
            fm, body = parse_frontmatter(raw)
        except FrontmatterError:
            fm, body = {}, raw
        return ToolResult(
            text=body,
            data={"domain": domain, "frontmatter": fm, "body": body},
        )
