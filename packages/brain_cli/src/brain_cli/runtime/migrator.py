"""SQLite migration runner for ``brain upgrade``.

Plan 08 Task 5. brain_core already has an additive SQL migration runner
baked into :class:`brain_core.state.db.StateDB` — it reads
``NNNN_*.sql`` files from ``brain_core/state/migrations/`` and tracks
applied versions in a ``schema_version`` table. The upgrade flow, though,
needs a *standalone* migrator that can point at ANY migrations directory
(the staged install's, not the current install's) against ANY state DB
path. That's this module.

The tracking table is the same ``schema_version(version INT PK,
applied_at TEXT)`` brain_core uses — two rows inserted by the core
migrator are indistinguishable from two rows inserted by this runner, so
upgrading from a running brain install where brain_core already bumped
the schema will simply show zero pending migrations and no-op.

Files must be named ``NNNN_*.sql`` with 4-digit zero-padded version
prefixes. ``list_pending_migrations`` returns them sorted. Each file
runs in a single transaction; on any statement failure the transaction
rolls back and the run aborts, leaving the schema at the last
successfully-applied version.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Same filename convention as brain_core/state/migrations — four-digit
# version prefix, underscore, short descriptor, .sql extension.
_MIGRATION_FILE_RE = re.compile(r"^(\d{4})_[\w.-]+\.sql$")


class MigrationError(RuntimeError):
    """Raised when a migration file fails to apply.

    The message always contains the offending file's version + name so
    the upgrade-command log tells the user exactly which migration
    broke. The underlying ``sqlite3.OperationalError`` is chained via
    ``__cause__`` for debugging.
    """


@dataclass
class MigrationReport:
    """Outcome of a :func:`run_migrations` call.

    ``applied`` lists the files in the order they ran (same order as
    ``list_pending_migrations``). ``starting_version`` / ``ending_version``
    are the highest applied version before + after. If no migrations
    were pending, ``applied == []`` and both versions equal.
    """

    starting_version: int
    ending_version: int
    applied: list[Path] = field(default_factory=list)


def _parse_version(path: Path) -> int | None:
    """Return the 4-digit version prefix from ``path.name``, or None.

    Files that don't match the convention are silently skipped — keeps
    editor junk (``0003_foo.sql.swp``, ``.DS_Store``) from blowing up
    a migration run.
    """
    match = _MIGRATION_FILE_RE.match(path.name)
    if not match:
        return None
    return int(match.group(1))


def _current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied version, or 0 if the table is missing.

    We intentionally do NOT create the table here — that's the job of
    the first real migration (which must include
    ``CREATE TABLE IF NOT EXISTS schema_version (...)`` as its first
    statement, matching brain_core's 0001 convention).
    """
    try:
        cur = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
    except sqlite3.OperationalError:
        return 0
    row = cur.fetchone()
    return int(row[0]) if row else 0


def list_pending_migrations(
    state_db: Path,
    migrations_dir: Path,
) -> list[Path]:
    """List ``.sql`` files in ``migrations_dir`` not yet applied to ``state_db``.

    Returns an empty list if the DB doesn't exist yet (everything
    pending — but we let :func:`run_migrations` actually materialize the
    file) or if the migrations dir is missing. The caller decides
    whether that's an error.
    """
    if not migrations_dir.is_dir():
        return []

    candidates: list[tuple[int, Path]] = []
    for path in migrations_dir.iterdir():
        if not path.is_file():
            continue
        version = _parse_version(path)
        if version is None:
            continue
        candidates.append((version, path))
    candidates.sort(key=lambda pair: pair[0])

    if not state_db.exists():
        # No DB yet — every file is pending.
        return [path for _version, path in candidates]

    # Read-only probe of current version. Using URI mode so we don't
    # create the file if it somehow disappeared between the check above
    # and here (race with ``brain stop`` cleanup, etc.).
    conn = sqlite3.connect(str(state_db))
    try:
        current = _current_schema_version(conn)
    finally:
        conn.close()

    return [path for version, path in candidates if version > current]


def _apply_one(conn: sqlite3.Connection, version: int, sql: str) -> None:
    """Apply one migration atomically.

    Split-on-semicolon approach matches brain_core's runner — we
    explicitly cannot use ``executescript`` because it COMMITs before
    running, which defeats our BEGIN/ROLLBACK guard. Same caveat about
    no semicolons inside string literals or trigger bodies applies.
    """
    # Strip ``--`` line comments so a leading comment block doesn't
    # glue onto the first statement.
    cleaned = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]

    try:
        conn.execute("BEGIN")
        for stmt in statements:
            conn.execute(stmt)
        conn.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def run_migrations(
    state_db: Path,
    migrations_dir: Path,
) -> MigrationReport:
    """Apply every pending migration in order, stopping on first failure.

    Returns a :class:`MigrationReport` listing applied files and the
    before/after versions. Raises :class:`MigrationError` on any
    failure — by that point earlier migrations have already committed
    (that's the point of per-file transactions; one-bad-apple should
    not undo three good ones). The report's ``ending_version`` reflects
    the last successful commit.
    """
    state_db.parent.mkdir(parents=True, exist_ok=True)

    # Autocommit off by default in sqlite3; our per-file BEGIN/COMMIT
    # is explicit.
    conn = sqlite3.connect(str(state_db), isolation_level=None)
    try:
        # Apply the same WAL pragmas brain_core uses so we're not
        # leaving the DB in a surprising journal mode.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")

        starting = _current_schema_version(conn)
        applied: list[Path] = []

        pending: list[tuple[int, Path]] = []
        if migrations_dir.is_dir():
            for path in migrations_dir.iterdir():
                if not path.is_file():
                    continue
                version = _parse_version(path)
                if version is None or version <= starting:
                    continue
                pending.append((version, path))
        pending.sort(key=lambda pair: pair[0])

        ending = starting
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            try:
                _apply_one(conn, version, sql)
            except sqlite3.DatabaseError as exc:
                raise MigrationError(
                    f"Migration {path.name} failed: {exc}. Schema left at version {ending}."
                ) from exc
            applied.append(path)
            ending = version

        return MigrationReport(
            starting_version=starting,
            ending_version=ending,
            applied=applied,
        )
    finally:
        conn.close()
