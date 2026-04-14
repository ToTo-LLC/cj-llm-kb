"""Tests for brain_core.state.db — the SQLite primitive."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.state.db import StateDB


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / ".brain" / "state.sqlite"


class TestStateDBBasics:
    def test_connect_creates_parent_dir(self, db_path: Path) -> None:
        assert not db_path.parent.exists()
        db = StateDB.open(db_path)
        try:
            assert db_path.parent.exists()
            assert db_path.exists()
        finally:
            db.close()

    def test_open_is_idempotent(self, db_path: Path) -> None:
        db1 = StateDB.open(db_path)
        db1.close()
        db2 = StateDB.open(db_path)
        try:
            assert db2.schema_version() >= 1
        finally:
            db2.close()

    def test_wal_mode_enabled(self, db_path: Path) -> None:
        db = StateDB.open(db_path)
        try:
            cur = db.exec("PRAGMA journal_mode")
            row = cur.fetchone()
            assert row[0].lower() == "wal"
        finally:
            db.close()

    def test_exec_returns_cursor(self, db_path: Path) -> None:
        db = StateDB.open(db_path)
        try:
            db.exec(
                "INSERT INTO chat_threads(thread_id, path, domain, mode, turns, cost_usd, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("t1", "research/foo.md", "research", "ask", 2, 0.01, "2026-04-14T00:00:00Z"),
            )
            cur = db.exec("SELECT thread_id, mode FROM chat_threads WHERE thread_id = ?", ("t1",))
            row = cur.fetchone()
            assert row == ("t1", "ask")
        finally:
            db.close()

    def test_context_manager(self, db_path: Path) -> None:
        with StateDB.open(db_path) as db:
            assert db.schema_version() >= 1
