"""Budget enforcement + pre-call cost estimation.

Model pricing table is hard-coded here as the baseline. When Anthropic pricing
changes, update this table. It is also surfaced in the Settings UI so users
know the numbers they see are current. Adding a new model requires a row here.

Rates verified against https://claude.com/pricing (April 2026).
"""

from __future__ import annotations

from datetime import datetime, timezone

from brain_core.cost.ledger import CostLedger


class BudgetExceededError(RuntimeError):
    """Raised when a projected spend would exceed a configured budget ceiling."""


# USD per million tokens. Update when provider pricing changes.
# (input_per_Mtok, output_per_Mtok)
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


class BudgetEnforcer:
    def __init__(
        self,
        *,
        ledger: CostLedger | None,
        daily_usd: float,
        monthly_usd: float,
    ) -> None:
        self._ledger = ledger
        self._daily = daily_usd
        self._monthly = monthly_usd

    @staticmethod
    def estimate_cost(*, model: str, input_tokens: int, output_tokens: int) -> float:
        if model not in _PRICING:
            raise KeyError(f"no pricing entry for model {model!r}")
        in_rate, out_rate = _PRICING[model]
        return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate

    def check_can_spend(self, projected_usd: float) -> None:
        if self._ledger is None:
            return
        now = datetime.now(tz=timezone.utc)
        day_total = self._ledger.total_for_day(now.date()) + projected_usd
        if day_total > self._daily:
            raise BudgetExceededError(
                f"daily budget exceeded: projected {day_total:.4f} > limit {self._daily:.2f}"
            )
        month_total = self._ledger.total_for_month(now.year, now.month) + projected_usd
        if month_total > self._monthly:
            raise BudgetExceededError(
                f"monthly budget exceeded: projected {month_total:.4f} > limit {self._monthly:.2f}"
            )
