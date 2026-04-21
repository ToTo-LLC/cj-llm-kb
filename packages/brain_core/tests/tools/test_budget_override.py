"""Smoke test for brain_core.tools.budget_override + CostLedger.is_over_budget."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from brain_core.config.schema import BudgetConfig
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.budget_override import NAME, handle


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_budget_override"


async def test_returns_override_window(tmp_path: Path) -> None:
    result = await handle(
        {"amount_usd": 5.0, "duration_hours": 12},
        _mk_ctx(tmp_path),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "override_set"
    assert result.data["override_delta_usd"] == pytest.approx(5.0)
    # ISO-8601 string with timezone.
    parsed = datetime.fromisoformat(result.data["override_until"])
    assert parsed.tzinfo is not None


async def test_rejects_out_of_range_amount(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        await handle({"amount_usd": 500.0}, _mk_ctx(tmp_path))


def test_is_over_budget_respects_active_override(tmp_path: Path) -> None:
    """When an active override is set, the effective cap rises by override_delta_usd."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    today = date(2026, 4, 15)
    # Spend $4.50 today.
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
            operation="ask",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=100,
            cost_usd=4.50,
            domain="research",
        )
    )

    # Without override at $5 cap → not over.
    cfg = BudgetConfig(daily_usd=5.0)
    assert ledger.is_over_budget(cfg, today) is False

    # Lower cap → over.
    tight = BudgetConfig(daily_usd=4.0)
    assert ledger.is_over_budget(tight, today) is True

    # Active override raises cap → not over again.
    override = BudgetConfig(
        daily_usd=4.0,
        override_until=datetime.now(tz=UTC) + timedelta(hours=1),
        override_delta_usd=5.0,
    )
    assert ledger.is_over_budget(override, today) is False

    # Expired override → no relief.
    expired = BudgetConfig(
        daily_usd=4.0,
        override_until=datetime.now(tz=UTC) - timedelta(hours=1),
        override_delta_usd=5.0,
    )
    assert ledger.is_over_budget(expired, today) is True
