"""brain_search — BM25 search over vault notes in active scope."""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.paths import ScopeError, scope_guard

NAME = "brain_search"
DESCRIPTION = "BM25 search over notes in the allowed domains. Returns ranked hits with snippets."
_MAX_TOP_K = 20
_DEFAULT_TOP_K = 5
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "top_k": {"type": "integer", "minimum": 1, "maximum": _MAX_TOP_K},
        "domains": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["query"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    query = str(arguments.get("query", "")).strip()
    top_k = min(int(arguments.get("top_k", _DEFAULT_TOP_K)), _MAX_TOP_K)
    requested = tuple(arguments.get("domains") or ctx.allowed_domains)
    for d in requested:
        if d not in ctx.allowed_domains:
            raise ScopeError(f"domain {d!r} not in allowed {ctx.allowed_domains}")

    if not query:
        return ToolResult(text="(empty query)", data={"hits": [], "top_k_used": top_k})

    hits = ctx.retrieval.search(query, domains=requested, top_k=top_k)
    verified: list[dict[str, Any]] = []
    for h in hits:
        # Belt-and-braces re-verification per Plan 03 Task 6.
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
    lines = [f"- {h['path']} — {h['title']}" for h in verified] or ["(no hits)"]
    return ToolResult(text="\n".join(lines), data={"hits": verified, "top_k_used": top_k})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
