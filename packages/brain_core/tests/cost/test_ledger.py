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
    assert summary.by_mode == {}


def test_cost_entry_accepts_mode_and_stage() -> None:
    """Plan 07 Task 3: mode and stage are optional tags that default to
    None so Plan 02-05 call sites compile unchanged."""
    entry = CostEntry(
        timestamp=datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
        operation="chat_turn",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
        domain="research",
        mode="ask",
        stage=None,
    )
    assert entry.mode == "ask"
    assert entry.stage is None


def test_summary_returns_by_mode_breakdown(tmp_path: Path) -> None:
    """Plan 07 Task 3: summary now aggregates today's spend by mode.
    NULL mode (ingest and pre-Plan 07 rows) aggregates into the empty
    string so the UI can label it ``Other``."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    today = date(2026, 4, 21)
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 21, 10, 0, tzinfo=UTC),
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
            domain="research",
            mode="ask",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 21, 11, 0, tzinfo=UTC),
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=800,
            output_tokens=400,
            cost_usd=0.03,
            domain="research",
            mode="brainstorm",
        )
    )
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
            operation="ingest",
            model="claude-haiku-4-5",
            input_tokens=500,
            output_tokens=100,
            cost_usd=0.01,
            domain="research",
            mode=None,
            stage="classify",
        )
    )
    summary = ledger.summary(today=today, month=(2026, 4))
    assert summary.by_mode == {
        "ask": pytest.approx(0.05),
        "brainstorm": pytest.approx(0.03),
        "": pytest.approx(0.01),
    }


def test_migration_adds_mode_stage_columns_to_existing_db(tmp_path: Path) -> None:
    """The Plan 07 Task 3 migration must be safe when applied to a DB
    created by an earlier plan — no data loss, columns added in place."""
    import sqlite3

    db = tmp_path / "costs.sqlite"
    # Simulate a Plan 02-era DB by creating the table without the new columns.
    with sqlite3.connect(db) as raw:
        raw.executescript(
            """
            CREATE TABLE costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                day TEXT NOT NULL,
                operation TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                domain TEXT NOT NULL
            );
            """
        )
        raw.execute(
            "INSERT INTO costs (ts_utc, day, operation, model, input_tokens, output_tokens, cost_usd, domain) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-04-20T10:00:00+00:00",
                "2026-04-20",
                "ingest",
                "claude-sonnet-4-6",
                1000,
                500,
                0.02,
                "research",
            ),
        )

    # Open via CostLedger — the migration must fire.
    ledger = CostLedger(db_path=db)
    # Existing row should survive.
    assert ledger.total_for_day(date(2026, 4, 20)) == pytest.approx(0.02)

    # New rows may now use mode/stage.
    ledger.record(
        CostEntry(
            timestamp=datetime(2026, 4, 20, 11, 0, tzinfo=UTC),
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=100,
            cost_usd=0.01,
            domain="research",
            mode="draft",
        )
    )
    summary = ledger.summary(today=date(2026, 4, 20), month=(2026, 4))
    # Pre-migration row has NULL mode → "" key; new row → "draft".
    assert summary.by_mode == {
        "": pytest.approx(0.02),
        "draft": pytest.approx(0.01),
    }

    # Re-opening must be idempotent (no "duplicate column" error).
    CostLedger(db_path=db)
