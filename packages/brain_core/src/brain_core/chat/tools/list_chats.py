"""list_chats tool — query state.sqlite for chat thread metadata.

The chat_threads table is populated by ThreadPersistence (Task 13) after
every turn write. This tool is a read-only view into that metadata; it does
not touch the vault or the thread markdown files themselves.
"""

from __future__ import annotations

from typing import Any

from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.vault.paths import ScopeError

_LIMIT = 20


class ListChatsTool:
    name = "list_chats"
    description = "List recent chat threads in scope, optionally filtered by a path substring."
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "query": {"type": "string"},
        },
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if ctx.state_db is None:
            raise RuntimeError("list_chats requires state_db in ToolContext")
        domain_arg = args.get("domain")
        if domain_arg is not None and domain_arg not in ctx.allowed_domains:
            raise ScopeError(f"domain {domain_arg!r} not in allowed {ctx.allowed_domains}")
        domains: tuple[str, ...] = (domain_arg,) if domain_arg else ctx.allowed_domains
        placeholders = ",".join("?" for _ in domains)
        sql = (
            f"SELECT thread_id, path, domain, mode, turns, cost_usd, updated_at "
            f"FROM chat_threads WHERE domain IN ({placeholders})"
        )
        params: tuple[Any, ...] = tuple(domains)
        if args.get("query"):
            sql += " AND path LIKE ?"
            params = (*params, f"%{args['query']}%")
        sql += f" ORDER BY updated_at DESC LIMIT {_LIMIT}"
        cur = ctx.state_db.exec(sql, params)
        rows = [
            {
                "thread_id": r[0],
                "path": r[1],
                "domain": r[2],
                "mode": r[3],
                "turns": r[4],
                "cost_usd": r[5],
                "updated_at": r[6],
            }
            for r in cur.fetchall()
        ]
        if rows:
            text = "\n".join(f"- {r['path']} ({r['turns']} turns)" for r in rows)
        else:
            text = "(no chats yet)"
        return ToolResult(text=text, data={"threads": rows})
