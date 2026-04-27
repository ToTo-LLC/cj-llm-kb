"""brain_budget_override — set an ephemeral budget override.

Raises the effective daily cap by ``amount_usd`` for ``duration_hours``
hours. Plan 11 Task 4 wires :func:`persist_config_or_revert` so the
override fields (``budget.override_until`` + ``budget.override_delta_usd``)
round-trip to ``<vault>/.brain/config.json`` via :func:`save_config`. Both
fields are in the persisted-field whitelist (Plan 11 D4) so a restart
respects the override until it expires.

The ``CostLedger.is_over_budget(config, today)`` consult is what actually
gates spending — see ``brain_core/cost/ledger.py``.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from brain_core.config.writer import persist_config_or_revert
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_budget_override"
DESCRIPTION = (
    "Temporarily raise the daily budget cap by amount_usd for duration_hours. "
    "Returns the override window. Persists override_until + override_delta_usd "
    "to <vault>/.brain/config.json via save_config()."
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
        raise ValueError(f"amount_usd {amount_usd} out of range [{_MIN_AMOUNT}, {_MAX_AMOUNT}]")
    if not (_MIN_DURATION <= duration_hours <= _MAX_DURATION):
        raise ValueError(
            f"duration_hours {duration_hours} out of range [{_MIN_DURATION}, {_MAX_DURATION}]"
        )

    override_until = datetime.now(tz=UTC) + timedelta(hours=duration_hours)

    # Plan 07 Task 4 + Plan 11 Task 4: mutate ``BudgetConfig`` in-place
    # then persist to ``<vault>/.brain/config.json`` via
    # ``persist_config_or_revert``. The helper snapshots first and
    # reverts both override fields if the disk write fails so the
    # in-memory override never drifts from disk. Persistence is skipped
    # when ``ctx.config`` is ``None`` (low-level test contexts) — the
    # response payload still carries the intended window so the caller
    # (frontend) can mirror locally.
    config = getattr(ctx, "config", None)
    if config is not None and hasattr(config, "budget"):
        with persist_config_or_revert(config, ctx.vault_root):
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
                "Override window persisted to <vault>/.brain/config.json "
                "via save_config(). Restart respects the override until it expires."
            ),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
