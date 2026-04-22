"""Tests for ``brain_cli.runtime.migrator`` — Plan 08 Task 5."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from brain_cli.runtime.migrator import (
    MigrationError,
    list_pending_migrations,
    run_migrations,
)


def _write_sql(path: Path, body: str) -> None:
    """Write a migration file with LF line endings."""
    path.write_text(body, encoding="utf-8", newline="\n")


def _bootstrap_migration(migrations_dir: Path) -> None:
    """Drop 0001 — creates the schema_version + a sample table."""
    migrations_dir.mkdir(parents=True, exist_ok=True)
    _write_sql(
        migrations_dir / "0001_init.sql",
        """-- 0001: bootstrap schema_version + widgets
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
""",
    )


def test_list_pending_only_includes_new_files(tmp_path: Path) -> None:
    """0001 already applied → only 0002 shows up as pending."""
    migrations = tmp_path / "migrations"
    _bootstrap_migration(migrations)
    _write_sql(
        migrations / "0002_add_color.sql",
        "ALTER TABLE widgets ADD COLUMN color TEXT;",
    )
    # Stray non-migration files should be ignored.
    (migrations / "README.md").write_text("not a migration\n", encoding="utf-8")

    state_db = tmp_path / "state.sqlite"
    report = run_migrations(state_db, migrations)
    assert report.ending_version == 2

    # Now add a third, only it should be pending.
    _write_sql(
        migrations / "0003_add_size.sql",
        "ALTER TABLE widgets ADD COLUMN size INTEGER;",
    )

    pending = list_pending_migrations(state_db, migrations)
    assert [p.name for p in pending] == ["0003_add_size.sql"]


def test_run_migrations_applies_in_version_order(tmp_path: Path) -> None:
    """Files apply in numeric order regardless of alphabetical listing."""
    migrations = tmp_path / "migrations"
    _bootstrap_migration(migrations)
    # Intentionally name them to defeat naive alpha sort (0010 < 2 alphabetically).
    _write_sql(migrations / "0002_add_color.sql", "ALTER TABLE widgets ADD COLUMN color TEXT;")
    _write_sql(
        migrations / "0010_add_size.sql",
        "ALTER TABLE widgets ADD COLUMN size INTEGER;",
    )

    state_db = tmp_path / "state.sqlite"
    report = run_migrations(state_db, migrations)

    assert report.starting_version == 0
    assert report.ending_version == 10
    assert [p.name for p in report.applied] == [
        "0001_init.sql",
        "0002_add_color.sql",
        "0010_add_size.sql",
    ]

    conn = sqlite3.connect(str(state_db))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(widgets)")}
    finally:
        conn.close()
    assert {"id", "name", "color", "size"} <= cols


def test_run_migrations_rolls_back_on_failure(tmp_path: Path) -> None:
    """Bad SQL in 0002 → only 0001 committed + MigrationError raised."""
    migrations = tmp_path / "migrations"
    _bootstrap_migration(migrations)
    # Intentionally broken — references a nonexistent column.
    _write_sql(
        migrations / "0002_break.sql",
        "ALTER TABLE nope ADD COLUMN bad INTEGER;",
    )

    state_db = tmp_path / "state.sqlite"
    with pytest.raises(MigrationError, match=r"0002_break\.sql"):
        run_migrations(state_db, migrations)

    # 0001 should have stuck; 0002 should not appear in schema_version.
    conn = sqlite3.connect(str(state_db))
    try:
        versions = {row[0] for row in conn.execute("SELECT version FROM schema_version")}
    finally:
        conn.close()
    assert versions == {1}
