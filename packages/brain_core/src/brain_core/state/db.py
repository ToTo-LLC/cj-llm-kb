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
        conn.execute("PRAGMA foreign_keys=ON")
        db = cls(conn)
        db._apply_migrations()
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
            self._conn.executescript(sql)
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )

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
