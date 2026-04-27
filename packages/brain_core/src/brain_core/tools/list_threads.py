"""brain_list_threads — list recent chat threads visible to the current scope.

Wraps a read-only query against ``state.sqlite``'s ``chat_threads`` table.
The table is upserted by :class:`brain_core.chat.persistence.ThreadPersistence`
on every chat-turn write, so every thread the user has held in scope is
listed. ``personal``-domain threads only appear when ``personal`` is in
``ctx.allowed_domains`` (scope-guarded).

Why a separate MCP tool when the chat session has its own ``ListChatsTool``?

The chat-session tool runs inside an in-progress chat (search the vault for
prior threads to cite). This tool is the API the SPA calls to populate the
left-nav recent-chats panel — fired from outside any chat session, so it
doesn't fit the ``ChatTool`` Protocol shape.

Issue #18 in ``docs/v0.1.0-known-issues.md``.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_list_threads"
DESCRIPTION = (
    "List recent chat threads visible in the current scope. Returns "
    "{thread_id, path, domain, mode, turns, cost_usd, updated_at} per "
    "thread. Threads in domains outside ``ctx.allowed_domains`` are "
    "filtered out server-side. Default limit 50; pass ``limit`` to override."
)

# Hard ceiling so a misbehaving caller can't fetch every thread in a
# multi-thousand-thread vault. The frontend's left-nav recent-chats
# panel only shows ~20 anyway.
_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {
            "type": "string",
            "description": (
                "Optional single-domain filter. Must be in "
                "``ctx.allowed_domains`` or the call is refused with "
                "ScopeError."
            ),
        },
        "query": {
            "type": "string",
            "description": (
                "Optional substring to match against the thread file path "
                "(SQL LIKE wildcard)."
            ),
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": _MAX_LIMIT,
            "default": _DEFAULT_LIMIT,
        },
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    if ctx.state_db is None:
        # The state DB is wired by every realistic ToolContext build path
        # (brain_api / brain_mcp / brain_cli) so this is a defensive
        # check rather than a real exit. Emit an empty list instead of
        # raising — the frontend renders an empty state cleanly.
        return ToolResult(text="(no chats yet)", data={"threads": []})

    domain_arg = arguments.get("domain")
    if domain_arg is not None:
        if not isinstance(domain_arg, str) or not domain_arg:
            raise ValueError("domain must be a non-empty string")
        if domain_arg not in ctx.allowed_domains:
            from brain_core.vault.paths import ScopeError

            raise ScopeError(
                f"domain {domain_arg!r} not in allowed {ctx.allowed_domains}"
            )
        domains: tuple[str, ...] = (domain_arg,)
    else:
        domains = ctx.allowed_domains

    query_arg = arguments.get("query")
    query: str | None = None
    if query_arg is not None:
        if not isinstance(query_arg, str):
            raise ValueError("query must be a string")
        query = query_arg

    limit_arg = arguments.get("limit", _DEFAULT_LIMIT)
    if not isinstance(limit_arg, int) or limit_arg < 1:
        raise ValueError("limit must be a positive integer")
    limit = min(limit_arg, _MAX_LIMIT)

    placeholders = ",".join("?" for _ in domains)
    sql = (
        "SELECT thread_id, path, domain, mode, turns, cost_usd, updated_at "
        f"FROM chat_threads WHERE domain IN ({placeholders})"
    )
    params: tuple[Any, ...] = tuple(domains)
    if query:
        sql += " AND path LIKE ?"
        params = (*params, f"%{query}%")
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params = (*params, limit)

    try:
        cur = ctx.state_db.exec(sql, params)
        rows = cur.fetchall()
    except Exception:
        # ``chat_threads`` table is created lazily by the chat persistence
        # path on first turn write. A vault that has never held a chat
        # session will not have the table — return empty rather than
        # erroring so the left-nav renders the empty state.
        rows = []

    threads = [
        {
            "thread_id": r[0],
            "path": r[1],
            "domain": r[2],
            "mode": r[3],
            "turns": r[4],
            "cost_usd": r[5],
            "updated_at": r[6],
        }
        for r in rows
    ]
    text = (
        "\n".join(
            f"- {t['path']} ({t['turns']} turns, {t['mode']})" for t in threads
        )
        if threads
        else "(no chats yet)"
    )
    return ToolResult(text=text, data={"threads": threads})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
