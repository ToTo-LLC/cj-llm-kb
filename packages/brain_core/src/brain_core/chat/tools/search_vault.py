"""search_vault tool — BM25 retrieval over the session's allowed domains.

Every returned hit's path is re-verified via scope_guard as belt-and-braces
against a retrieval bug leaking cross-domain paths.
"""

from __future__ import annotations

from typing import Any

from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.vault.paths import ScopeError, scope_guard

_MAX_TOP_K = 20
_DEFAULT_TOP_K = 5


class SearchVaultTool:
    name = "search_vault"
    description = "BM25 search over notes in the active scope. Returns paths + snippets."
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": _MAX_TOP_K},
            "domains": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        top_k = min(int(args.get("top_k", _DEFAULT_TOP_K)), _MAX_TOP_K)
        requested = tuple(args.get("domains") or ctx.allowed_domains)
        for d in requested:
            if d not in ctx.allowed_domains:
                raise ScopeError(f"domain {d!r} not in allowed {ctx.allowed_domains}")
        if not query:
            return ToolResult(
                text="(empty query)",
                data={"hits": [], "top_k_used": top_k},
            )

        idx: BM25VaultIndex = ctx.retrieval
        hits = idx.search(query, domains=requested, top_k=top_k)

        verified: list[dict[str, Any]] = []
        for h in hits:
            scope_guard(
                ctx.vault_root / h.path,
                vault_root=ctx.vault_root,
                allowed_domains=ctx.allowed_domains,
            )
            verified.append(
                {
                    "path": h.path.as_posix(),
                    "title": h.title,
                    "snippet": h.snippet,
                    "score": round(h.score, 4),
                }
            )
        lines = [f"- {h['path']} — {h['title']}" for h in verified] if verified else ["(no hits)"]
        return ToolResult(
            text="\n".join(lines),
            data={"hits": verified, "top_k_used": top_k},
        )
