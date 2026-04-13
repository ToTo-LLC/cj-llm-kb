from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from brain_core.cost.budget import BudgetEnforcer, BudgetExceededError
from brain_core.cost.ledger import CostEntry, CostLedger


def _fresh(tmp_path: Path) -> tuple[CostLedger, BudgetEnforcer]:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    be = BudgetEnforcer(ledger=ledger, daily_usd=1.0, monthly_usd=10.0)
    return ledger, be


def test_under_budget_allows(tmp_path: Path) -> None:
    _, be = _fresh(tmp_path)
    be.check_can_spend(0.5)  # should not raise


def test_over_daily_budget_raises(tmp_path: Path) -> None:
    ledger, be = _fresh(tmp_path)
    ledger.record(
        CostEntry(
            timestamp=datetime.now(tz=timezone.utc),
            operation="x",
            model="m",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.9,
            domain="research",
        )
    )
    with pytest.raises(BudgetExceededError, match="daily"):
        be.check_can_spend(0.2)


def test_estimate_cost_for_sonnet() -> None:
    # claude-sonnet-4-6: $3/Mtok in, $15/Mtok out
    # 1000 in + 500 out → $3 × 0.001 + $15 × 0.0005 = 0.003 + 0.0075 = 0.0105
    est = BudgetEnforcer.estimate_cost(
        model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500
    )
    assert round(est, 4) == 0.0105


def test_estimate_cost_for_opus() -> None:
    # claude-opus-4-6: $5/Mtok in, $25/Mtok out
    # 1000 in + 500 out → $5 × 0.001 + $25 × 0.0005 = 0.005 + 0.0125 = 0.0175
    est = BudgetEnforcer.estimate_cost(
        model="claude-opus-4-6", input_tokens=1000, output_tokens=500
    )
    assert round(est, 4) == 0.0175


def test_estimate_cost_for_haiku() -> None:
    # claude-haiku-4-5-20251001: $1/Mtok in, $5/Mtok out
    # 1000 in + 500 out → $1 × 0.001 + $5 × 0.0005 = 0.001 + 0.0025 = 0.0035
    est = BudgetEnforcer.estimate_cost(
        model="claude-haiku-4-5-20251001", input_tokens=1000, output_tokens=500
    )
    assert round(est, 4) == 0.0035


def test_estimate_cost_unknown_model_raises() -> None:
    with pytest.raises(KeyError):
        BudgetEnforcer.estimate_cost(model="mystery-model", input_tokens=1, output_tokens=1)
