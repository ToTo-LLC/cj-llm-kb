"""brain_cost_report — return today / month / by-domain cost summary.

Thin wrapper over `CostLedger.summary()` that hands the MCP client a typed
snapshot of spend. Takes no arguments; the server's `ctx.cost_ledger` carries
the session's ledger handle. Stays privacy-safe — reports USD totals only, no
prompt bodies or per-call detail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import mcp.types as types

from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_cost_report"
DESCRIPTION = (
    "Return the cost ledger summary: today's total USD, this month's total USD, "
    "and today's by-domain breakdown."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    now = datetime.now(UTC)
    today = now.date()
    summary = ctx.cost_ledger.summary(today=today, month=(now.year, now.month))
    by_domain_text = ", ".join(f"{d}=${c:.4f}" for d, c in summary.by_domain.items()) or "(empty)"
    text = (
        f"today: ${summary.today_usd:.4f}\n"
        f"month: ${summary.month_usd:.4f}\n"
        f"by domain today: {by_domain_text}"
    )
    return text_result(
        text,
        data={
            "today_usd": summary.today_usd,
            "month_usd": summary.month_usd,
            "by_domain": summary.by_domain,
        },
    )
