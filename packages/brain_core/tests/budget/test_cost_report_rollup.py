"""Plan 16 Task 27 — per-domain rollup query pin tests.

Seeds the ledger with 3 entries across 2 domains at known offsets from a
fixed ``now`` and asserts ``CostLedger.domain_spend_within_window`` returns
the correct sum given various ``since`` windows. These pins lock the
contract that Task 28's ``PerDomainBudgetGuard`` depends on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from brain_core.cost.ledger import CostEntry, CostLedger


def _seed(ledger: CostLedger, now: datetime) -> None:
    """Three entries: research $0.50 (-2d), work $0.30 (-1d), research $0.20 (-1h)."""
    ledger.record(
        CostEntry(
            timestamp=now - timedelta(days=2),
            operation="ingest",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.50,
            domain="research",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=now - timedelta(days=1),
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=400,
            cost_usd=0.30,
            domain="work",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=now - timedelta(hours=1),
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=400,
            output_tokens=200,
            cost_usd=0.20,
            domain="research",
        )
    )


def test_research_three_day_window_sums_both_research_entries(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    _seed(ledger, now)

    spent = ledger.domain_spend_within_window("research", since=now - timedelta(days=3))

    assert spent == pytest.approx(0.70)


def test_work_three_day_window_returns_only_work_entry(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    _seed(ledger, now)

    spent = ledger.domain_spend_within_window("work", since=now - timedelta(days=3))

    assert spent == pytest.approx(0.30)


def test_research_one_day_window_excludes_two_day_old_entry(tmp_path: Path) -> None:
    """Window boundary is inclusive on the >= side; the -2d entry must be excluded."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    _seed(ledger, now)

    spent = ledger.domain_spend_within_window("research", since=now - timedelta(days=1))

    assert spent == pytest.approx(0.20)


def test_unknown_domain_returns_zero(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    _seed(ledger, now)

    spent = ledger.domain_spend_within_window("nonexistent", since=now - timedelta(days=30))

    assert spent == 0.0


def test_empty_ledger_returns_zero(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    spent = ledger.domain_spend_within_window("research", since=now - timedelta(days=30))

    assert spent == 0.0
