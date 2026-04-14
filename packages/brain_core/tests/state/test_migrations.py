"""Tests for migration discovery and execution."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from brain_core.state import db as db_module
from brain_core.state.db import StateDB


class TestMigrations:
    def test_first_open_records_schema_version_1(self, tmp_path: Path) -> None:
        with StateDB.open(tmp_path / "state.sqlite") as db:
            assert db.schema_version() == 1

    def test_chat_threads_table_exists(self, tmp_path: Path) -> None:
        with StateDB.open(tmp_path / "state.sqlite") as db:
            cur = db.exec(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_threads'"
            )
            assert cur.fetchone() is not None

    def test_bm25_cache_table_exists(self, tmp_path: Path) -> None:
        with StateDB.open(tmp_path / "state.sqlite") as db:
            cur = db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='bm25_cache'")
            assert cur.fetchone() is not None

    def test_reopen_does_not_re_run_migrations(self, tmp_path: Path) -> None:
        path = tmp_path / "state.sqlite"
        with StateDB.open(path) as db:
            db.exec(
                "INSERT INTO bm25_cache(domain, vault_hash, index_blob) VALUES (?, ?, ?)",
                ("research", "deadbeef", b"\x00\x01"),
            )
        with StateDB.open(path) as db:
            cur = db.exec("SELECT vault_hash FROM bm25_cache WHERE domain = ?", ("research",))
            row = cur.fetchone()
            assert row[0] == "deadbeef"

    def test_failed_migration_rolls_back_atomically(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A migration that fails mid-file must not commit partial tables or a
        schema_version row. Exercises the explicit BEGIN/ROLLBACK path in
        ``_apply_one_migration``.
        """
        real_0001 = db_module._MIGRATIONS_DIR / "0001_chat_and_bm25.sql"
        migrations = tmp_path / "migrations"
        migrations.mkdir()
        (migrations / "0001_chat_and_bm25.sql").write_text(
            real_0001.read_text(encoding="utf-8"), encoding="utf-8"
        )
        # 0002: valid first statement, broken second statement. If the
        # transaction wrapper is working, the `partial_good` table must NOT
        # exist after the failure.
        (migrations / "0002_broken.sql").write_text(
            "CREATE TABLE partial_good (x INTEGER);\nCREATE TABLE THIS IS NOT VALID SQL;\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(db_module, "_MIGRATIONS_DIR", migrations)

        db_path = tmp_path / "state.sqlite"
        with pytest.raises(sqlite3.OperationalError):
            StateDB.open(db_path)

        # Reopen with only the valid 0001 migration present.
        (migrations / "0002_broken.sql").unlink()
        with StateDB.open(db_path) as db:
            # partial_good must have been rolled back.
            cur = db.exec(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='partial_good'"
            )
            assert cur.fetchone() is None

            # schema_version should have exactly one row: version=1.
            rows = db.exec("SELECT version FROM schema_version ORDER BY version").fetchall()
            assert rows == [(1,)]
