"""brain_cost_report — return today / month / by-domain cost summary.

Thin wrapper over ``CostLedger.summary()`` that hands the caller a typed
snapshot of spend. Takes no arguments; the session's ``ctx.cost_ledger``
carries the ledger handle. Stays privacy-safe — reports USD totals only, no
prompt bodies or per-call detail.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_cost_report"
DESCRIPTION = (
    "Return the cost ledger summary: today's total USD, this month's total USD, "
    "and today's by-domain breakdown."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = arguments  # no inputs
    now = datetime.now(UTC)
    today = now.date()
    summary = ctx.cost_ledger.summary(today=today, month=(now.year, now.month))
    by_domain_text = ", ".join(f"{d}=${c:.4f}" for d, c in summary.by_domain.items()) or "(empty)"
    text = (
        f"today: ${summary.today_usd:.4f}\n"
        f"month: ${summary.month_usd:.4f}\n"
        f"by domain today: {by_domain_text}"
    )
    return ToolResult(
        text=text,
        data={
            "today_usd": summary.today_usd,
            "month_usd": summary.month_usd,
            "by_domain": summary.by_domain,
            # Plan 07 Task 3: by-mode breakdown for the cost-chart UI.
            # NULL-mode rows (ingest / legacy) land in the empty-string
            # key; the frontend renders that as ``Other``.
            "by_mode": summary.by_mode,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
