"""brain_recent_ingests — list recent ingest_history rows.

Powers the Inbox UI tabs (Recent / In progress / Needs attention). Reads
the ``ingest_history`` table seeded by ``IngestPipeline.ingest`` (Plan 07
migration 0002). Metadata-only; no vault IO, no LLM.

If the table does not exist (e.g. the caller's StateDB is on an older
schema or no ingest has ever run on this vault), the handler returns an
empty list rather than raising — the UI surface should degrade
gracefully on a fresh vault.
"""

from __future__ import annotations

import sqlite3
import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_recent_ingests"
DESCRIPTION = (
    "List the most recent ingest runs (success / quarantined / failed / duplicate) "
    "from ingest_history. Powers the Inbox UI tabs."
)
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": _MAX_LIMIT,
            "default": _DEFAULT_LIMIT,
        },
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    raw_limit = int(arguments.get("limit", _DEFAULT_LIMIT))
    limit = max(1, min(raw_limit, _MAX_LIMIT))

    if ctx.state_db is None:
        return ToolResult(
            text="(no state_db available)",
            data={"ingests": []},
        )

    try:
        rows = ctx.state_db.exec(
            "SELECT source, source_type, domain, status, patch_id, classified_at, "
            "cost_usd, error FROM ingest_history "
            "ORDER BY classified_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError:
        # Table missing — fresh vault on a pre-Plan-07 StateDB. Degrade gracefully.
        return ToolResult(
            text="(no ingest history)",
            data={"ingests": []},
        )

    ingests: list[dict[str, Any]] = []
    for source, source_type, domain, status, patch_id, classified_at, cost_usd, error in rows:
        entry: dict[str, Any] = {
            "source": source,
            "source_type": source_type,
            "domain": domain,
            "status": status,
            "classified_at": classified_at,
            "cost_usd": float(cost_usd) if cost_usd is not None else 0.0,
        }
        if patch_id is not None:
            entry["patch_id"] = patch_id
        if error is not None:
            entry["error"] = error
        ingests.append(entry)

    if not ingests:
        text = "(no ingest history)"
    else:
        text = "\n".join(
            f"- [{e['status']}] {e['source']}"
            f"{' → ' + e['domain'] if e.get('domain') else ''}"
            f" ({e['classified_at']})"
            for e in ingests
        )
    return ToolResult(text=text, data={"ingests": ingests})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
