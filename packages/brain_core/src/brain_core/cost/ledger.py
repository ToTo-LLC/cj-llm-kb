"""costs.sqlite — append-only cost ledger with per-day and per-domain aggregation.

Plan 07 Task 3: entries now carry optional ``mode`` (chat: ``ask`` /
``brainstorm`` / ``draft``) and ``stage`` (ingest: ``classify`` /
``summarize`` / ``integrate``) tags so the frontend can slice spend by
UX surface. Both default ``None`` so every Plan 02-05 call site
compiles unchanged; unrecorded-mode rows aggregate into the empty-
string key in ``CostSummary.by_mode``.

Plan 07 Task 4: ``is_over_budget(config, today)`` consults the
``BudgetConfig.override_until`` / ``override_delta_usd`` fields so a
short-lived override (set via the ``brain_budget_override`` tool)
raises the effective daily cap until the timestamp expires.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain_core.config.schema import BudgetConfig


@dataclass(frozen=True)
class CostEntry:
    timestamp: datetime
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    domain: str
    mode: str | None = None
    """Chat mode tag — ``"ask"`` / ``"brainstorm"`` / ``"draft"`` — or
    ``None`` for non-chat ops (ingest, tooling, etc.)."""
    stage: str | None = None
    """Ingest stage tag — ``"classify"`` / ``"summarize"`` /
    ``"integrate"`` — or ``None`` for non-ingest ops."""


@dataclass(frozen=True)
class CostSummary:
    """Typed snapshot of ledger state used by `brain_cost_report` + Plan 07 UI."""

    today_usd: float
    month_usd: float
    by_domain: dict[str, float]
    by_mode: dict[str, float]
    """Today's spend broken down by chat mode. Entries with ``mode=None``
    aggregate into the empty-string key so the UI can label them
    ``Other`` (typically ingest rows)."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS costs (
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
CREATE INDEX IF NOT EXISTS idx_costs_day ON costs(day);
CREATE INDEX IF NOT EXISTS idx_costs_domain ON costs(domain);
"""


class CostLedger:
    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)
            self._apply_plan07_migration(c)

    def _apply_plan07_migration(self, c: sqlite3.Connection) -> None:
        """Add ``mode`` and ``stage`` columns to ``costs`` in-place.

        Idempotent: checks PRAGMA table_info and only issues ALTER TABLE
        for missing columns. SQLite ALTER TABLE ADD COLUMN preserves
        existing rows and seeds the new column with NULL, which matches
        the ``mode: str | None = None`` / ``stage: str | None = None``
        default on ``CostEntry``.

        No schema-version bump: this is Plan 07 Task 3, not Task 5.
        """
        existing_cols = {row[1] for row in c.execute("PRAGMA table_info(costs)")}
        if "mode" not in existing_cols:
            c.execute("ALTER TABLE costs ADD COLUMN mode TEXT")
        if "stage" not in existing_cols:
            c.execute("ALTER TABLE costs ADD COLUMN stage TEXT")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def record(self, entry: CostEntry) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO costs (ts_utc, day, operation, model, input_tokens, output_tokens, cost_usd, domain, mode, stage) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.timestamp.astimezone(UTC).isoformat(),
                    entry.timestamp.astimezone(UTC).date().isoformat(),
                    entry.operation,
                    entry.model,
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.cost_usd,
                    entry.domain,
                    entry.mode,
                    entry.stage,
                ),
            )

    def total_for_day(self, d: date) -> float:
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day = ?",
                (d.isoformat(),),
            ).fetchone()
        return float(row[0])

    def total_by_domain(self, d: date) -> dict[str, float]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT domain, COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day = ? GROUP BY domain",
                (d.isoformat(),),
            ).fetchall()
        return {domain: float(total) for domain, total in rows}

    def total_by_mode(self, d: date) -> dict[str, float]:
        """Today's spend grouped by ``mode`` tag. ``NULL`` mode aggregates
        into the empty-string key so the dict always has JSON-safe keys.
        """
        with self._conn() as c:
            rows = c.execute(
                "SELECT COALESCE(mode, ''), COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day = ? GROUP BY COALESCE(mode, '')",
                (d.isoformat(),),
            ).fetchall()
        return {mode: float(total) for mode, total in rows}

    def total_for_month(self, year: int, month: int) -> float:
        prefix = f"{year:04d}-{month:02d}"
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
        return float(row[0])

    def is_over_budget(self, config: BudgetConfig, today: date) -> bool:
        """Return True if today's spend exceeds the (override-aware) daily cap.

        Effective cap = ``config.daily_usd`` plus ``config.override_delta_usd``
        IFF ``config.override_until`` is set and lies in the future. An expired
        override is ignored — the caller is expected to clear the fields via
        the next config write (Plan 07 Task 5 lands the persistence layer that
        does this automatically).

        ``today`` is provided by the caller (rather than inferred from
        ``datetime.now``) so callers can drive the check in tests with
        deterministic dates.
        """
        spent = self.total_for_day(today)
        cap = config.daily_usd
        override_until = config.override_until
        if override_until is not None:
            now = datetime.now(tz=UTC)
            if override_until.tzinfo is None:
                override_until = override_until.replace(tzinfo=UTC)
            if now < override_until:
                cap = config.daily_usd + config.override_delta_usd
        return spent > cap

    def summary(self, *, today: date, month: tuple[int, int]) -> CostSummary:
        """Return a typed summary: today's total, this month's total, today's
        breakdown by domain AND by mode. Used by the `brain_cost_report`
        MCP tool and the Plan 07 cost-breakdown UI."""
        return CostSummary(
            today_usd=self.total_for_day(today),
            month_usd=self.total_for_month(month[0], month[1]),
            by_domain=self.total_by_domain(today),
            by_mode=self.total_by_mode(today),
        )
