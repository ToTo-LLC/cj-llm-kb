from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from brain_core.cost.ledger import CostEntry, CostLedger


def test_write_and_aggregate(tmp_path: Path) -> None:
    db = tmp_path / "costs.sqlite"
    ledger = CostLedger(db_path=db)
    now = datetime(2026, 4, 13, 12, 0, tzinfo=UTC)
    ledger.record(
        CostEntry(
            timestamp=now,
            operation="ingest",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.01,
            domain="research",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=now,
            operation="chat",
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=400,
            cost_usd=0.008,
            domain="work",
        )
    )
    assert round(ledger.total_for_day(now.date()), 4) == 0.018
    by_domain = ledger.total_by_domain(now.date())
    assert round(by_domain["research"], 4) == 0.01
    assert round(by_domain["work"], 4) == 0.008


def test_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "costs.sqlite"
    l1 = CostLedger(db_path=db)
    now = datetime(2026, 4, 13, tzinfo=UTC)
    l1.record(
        CostEntry(
            timestamp=now,
            operation="x",
            model="claude-sonnet-4-6",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.001,
            domain="research",
        )
    )
    assert CostLedger(db_path=db).total_for_day(now.date()) == 0.001


def test_summary_returns_typed_record(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    today = date(2026, 4, 15)
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
            operation="summarize",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
            domain="research",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 15, 11, 0, tzinfo=UTC),
            operation="integrate",
            model="claude-sonnet-4-6",
            input_tokens=2000,
            output_tokens=800,
            cost_usd=0.12,
            domain="work",
        )
    )
    summary = ledger.summary(today=today, month=(2026, 4))
    assert summary.today_usd == pytest.approx(0.17)
    assert summary.month_usd == pytest.approx(0.17)
    assert summary.by_domain == {
        "research": pytest.approx(0.05),
        "work": pytest.approx(0.12),
    }


def test_summary_empty_ledger(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    summary = ledger.summary(today=date(2026, 4, 15), month=(2026, 4))
    assert summary.today_usd == 0.0
    assert summary.month_usd == 0.0
    assert summary.by_domain == {}
