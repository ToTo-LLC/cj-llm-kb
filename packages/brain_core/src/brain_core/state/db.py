"""StateDB — thin SQLite wrapper with additive migrations.

Cross-platform: uses pathlib for all paths, WAL journal mode, no POSIX-only syscalls.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class StateDB:
    """Thin SQLite wrapper. Use StateDB.open(path) as the entry point."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def open(cls, path: Path) -> Self:
        """Open (or create) a state database at `path` and apply pending migrations."""
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), isolation_level=None)  # autocommit
        conn.execute("PRAGMA journal_mode=WAL")
        # NORMAL is the idiomatic WAL pairing: ~2x faster writes, still crash-safe.
        # State DB is a rebuildable cache (see CLAUDE.md principle #6), so the
        # last-committed-txn-on-power-loss risk is acceptable.
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        db = cls(conn)
        try:
            db._apply_migrations()
        except Exception:
            conn.close()
            raise
        return db

    def _apply_migrations(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        current = self.schema_version()
        for sql_file in sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
            version = int(sql_file.name[:4])
            if version <= current:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            self._apply_one_migration(version, sql)

    def _apply_one_migration(self, version: int, sql: str) -> None:
        """Apply a single migration file atomically.

        We cannot use ``sqlite3.Connection.executescript`` because it issues an
        implicit COMMIT before running, which defeats the explicit BEGIN below
        and lets partial migrations commit mid-file. Instead, we split on
        semicolons and run each statement inside a single transaction, rolling
        back on any failure so ``schema_version`` never ends up out-of-sync
        with the actual schema.

        Constraint: migration files must not contain semicolons inside string
        literals or trigger bodies (naive split would break them). Today's
        migrations are plain DDL — if a future migration needs triggers or
        string-literal semicolons, upgrade this splitter accordingly.
        """
        # Strip `--` line comments before splitting so a leading comment block
        # doesn't get glued onto the first real statement.
        cleaned = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        try:
            self._conn.execute("BEGIN")
            for stmt in statements:
                self._conn.execute(stmt)
            self._conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def schema_version(self) -> int:
        """Return the highest applied migration version, or 0 if none."""
        try:
            cur = self._conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        except sqlite3.OperationalError:
            return 0
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def exec(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement and return the cursor."""
        return self._conn.execute(sql, params)

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
