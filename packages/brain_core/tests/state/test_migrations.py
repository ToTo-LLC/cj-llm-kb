"""Tests for migration discovery and execution."""

from __future__ import annotations

from pathlib import Path

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
