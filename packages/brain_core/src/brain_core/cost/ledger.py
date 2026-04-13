"""costs.sqlite — append-only cost ledger with per-day and per-domain aggregation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class CostEntry:
    timestamp: datetime
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    domain: str


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

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def record(self, entry: CostEntry) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO costs (ts_utc, day, operation, model, input_tokens, output_tokens, cost_usd, domain) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.timestamp.astimezone(timezone.utc).isoformat(),
                    entry.timestamp.astimezone(timezone.utc).date().isoformat(),
                    entry.operation,
                    entry.model,
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.cost_usd,
                    entry.domain,
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

    def total_for_month(self, year: int, month: int) -> float:
        prefix = f"{year:04d}-{month:02d}"
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM costs WHERE day LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
        return float(row[0])
