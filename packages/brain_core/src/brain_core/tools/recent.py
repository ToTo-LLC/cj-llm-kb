"""brain_recent — recently modified notes via filesystem walk (D6a)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.paths import ScopeError

NAME = "brain_recent"
DESCRIPTION = "List recently modified notes across allowed domains, sorted newest first."
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 50
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": _MAX_LIMIT},
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    limit = min(int(arguments.get("limit", _DEFAULT_LIMIT)), _MAX_LIMIT)
    domain_arg = arguments.get("domain")
    if domain_arg and domain_arg not in ctx.allowed_domains:
        raise ScopeError(f"domain {domain_arg!r} not in allowed {ctx.allowed_domains}")
    domains = (domain_arg,) if domain_arg else ctx.allowed_domains

    entries: list[tuple[int, str, str]] = []
    for domain in domains:
        domain_root = ctx.vault_root / domain
        if not domain_root.exists():
            continue
        for md in domain_root.rglob("*.md"):
            rel = md.relative_to(ctx.vault_root)
            if "chats" in rel.parts:
                continue  # Exclude chat threads per D6a.
            stat = md.stat()
            entries.append(
                (
                    stat.st_mtime_ns,
                    rel.as_posix(),
                    datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                )
            )

    entries.sort(reverse=True)
    top = entries[:limit]
    notes = [{"path": p, "modified_at": t} for (_, p, t) in top]
    lines = [f"- {n['path']} ({n['modified_at']})" for n in notes] or ["(no recent notes)"]
    return ToolResult(text="\n".join(lines), data={"notes": notes, "limit_used": limit})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
