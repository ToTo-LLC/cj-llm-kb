"""brain_budget_override — set an ephemeral budget override.

Raises the effective daily cap by ``amount_usd`` for ``duration_hours``
hours. Persistence lands in Plan 07 Task 5; this tool currently writes
to ``ctx.config`` if a config object is attached, otherwise returns the
intended values so the caller (frontend) can mirror the change locally.

The ``CostLedger.is_over_budget(config, today)`` consult is what actually
gates spending — see ``brain_core/cost/ledger.py``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_budget_override"
DESCRIPTION = (
    "Temporarily raise the daily budget cap by amount_usd for duration_hours. "
    "Returns the override window. Persistence lands in Plan 07 Task 5."
)
_MIN_AMOUNT = 0.01
_MAX_AMOUNT = 100.0
_MIN_DURATION = 1
_MAX_DURATION = 72
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "amount_usd": {
            "type": "number",
            "minimum": _MIN_AMOUNT,
            "maximum": _MAX_AMOUNT,
        },
        "duration_hours": {
            "type": "integer",
            "minimum": _MIN_DURATION,
            "maximum": _MAX_DURATION,
            "default": 24,
        },
    },
    "required": ["amount_usd"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    amount_usd = float(arguments["amount_usd"])
    duration_hours = int(arguments.get("duration_hours", 24))

    if not (_MIN_AMOUNT <= amount_usd <= _MAX_AMOUNT):
        raise ValueError(
            f"amount_usd {amount_usd} out of range [{_MIN_AMOUNT}, {_MAX_AMOUNT}]"
        )
    if not (_MIN_DURATION <= duration_hours <= _MAX_DURATION):
        raise ValueError(
            f"duration_hours {duration_hours} out of range "
            f"[{_MIN_DURATION}, {_MAX_DURATION}]"
        )

    override_until = datetime.now(tz=UTC) + timedelta(hours=duration_hours)

    # If a config object is wired through ToolContext (Plan 07 Task 5+),
    # update the in-memory BudgetConfig so the next ``is_over_budget`` call
    # respects the override. Today no Plan 04 ToolContext carries config; we
    # use ``getattr`` with a default to stay forward-compatible without
    # forcing a ToolContext-shape change in this task.
    config = getattr(ctx, "config", None)
    if config is not None and hasattr(config, "budget"):
        config.budget.override_until = override_until
        config.budget.override_delta_usd = amount_usd

    return ToolResult(
        text=(
            f"budget override set: +${amount_usd:.2f} for {duration_hours}h "
            f"(until {override_until.isoformat()})"
        ),
        data={
            "status": "override_set",
            "override_until": override_until.isoformat(),
            "override_delta_usd": amount_usd,
            "note": (
                "Plan 07 Task 4: in-memory override. Persistence (writing the "
                "fields back into config.json) lands in Plan 07 Task 5."
            ),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
