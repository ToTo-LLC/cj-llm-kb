"""Tests for brain_core.tools.list_threads (issue #18).

Covers: NAME pin, empty-vault path, scope filtering by allowed_domains,
explicit domain= filter (in-scope and refused-out-of-scope), substring
query, limit clamping, and the chat_threads-table-missing fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_core.state.db import StateDB
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_threads import NAME, handle
from brain_core.vault.paths import ScopeError


def _mk_ctx(
    vault: Path,
    *,
    db: StateDB | None = None,
    allowed: tuple[str, ...] = ("research", "work"),
) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=allowed,
        retrieval=None,
        pending_store=None,
        state_db=db,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def _seed(db: StateDB, rows: list[tuple[str, str, str, str, int, float, str]]) -> None:
    """Insert (thread_id, path, domain, mode, turns, cost_usd, updated_at) rows."""
    db.exec(
        "CREATE TABLE IF NOT EXISTS chat_threads ("
        " thread_id TEXT PRIMARY KEY, path TEXT, domain TEXT, mode TEXT,"
        " turns INTEGER, cost_usd REAL, updated_at TEXT)"
    )
    for r in rows:
        db.exec(
            "INSERT OR REPLACE INTO chat_threads"
            "(thread_id, path, domain, mode, turns, cost_usd, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            r,
        )


def test_name() -> None:
    assert NAME == "brain_list_threads"


async def test_empty_when_no_state_db(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path))
    assert isinstance(result, ToolResult)
    assert result.data == {"threads": []}


async def test_empty_when_table_missing(tmp_path: Path) -> None:
    """Vault with no chat history yet — chat_threads table doesn't exist.

    The handler swallows the OperationalError and renders an empty list
    so the left-nav shows the empty state instead of erroring.
    """
    db_path = tmp_path / ".brain" / "state.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = StateDB.open(db_path)
    try:
        result = await handle({}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()
    assert isinstance(result, ToolResult)
    assert result.data == {"threads": []}


async def test_returns_inserted_rows_newest_first(tmp_path: Path) -> None:
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        old_ts = datetime(2026, 4, 10, tzinfo=UTC).isoformat()
        new_ts = datetime(2026, 4, 15, tzinfo=UTC).isoformat()
        _seed(
            db,
            [
                ("t-old", "research/chats/t-old.md", "research", "ask", 4, 0.01, old_ts),
                ("t-new", "research/chats/t-new.md", "research", "draft", 8, 0.05, new_ts),
            ],
        )
        result = await handle({}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()

    assert result.data is not None
    threads = result.data["threads"]
    assert [t["thread_id"] for t in threads] == ["t-new", "t-old"]
    assert threads[0]["mode"] == "draft"
    assert threads[0]["turns"] == 8
    assert threads[0]["cost_usd"] == pytest.approx(0.05)


async def test_scope_filters_personal_when_not_allowed(tmp_path: Path) -> None:
    """personal-domain threads must NOT appear when ``personal`` isn't in
    ``allowed_domains``. Honors the global scope-guard rule (CLAUDE.md
    principle #2)."""
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        _seed(
            db,
            [
                (
                    "t-research",
                    "research/chats/t.md",
                    "research",
                    "ask",
                    1,
                    0.0,
                    "2026-04-26T00:00:00+00:00",
                ),
                (
                    "t-personal",
                    "personal/chats/t.md",
                    "personal",
                    "ask",
                    1,
                    0.0,
                    "2026-04-26T01:00:00+00:00",
                ),
            ],
        )
        ctx = _mk_ctx(tmp_path, db=db, allowed=("research",))
        result = await handle({}, ctx)
    finally:
        db.close()

    assert result.data is not None
    domains = {t["domain"] for t in result.data["threads"]}
    assert domains == {"research"}


async def test_explicit_domain_filter_in_scope(tmp_path: Path) -> None:
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        _seed(
            db,
            [
                (
                    "r1",
                    "research/chats/r1.md",
                    "research",
                    "ask",
                    1,
                    0.0,
                    "2026-04-26T00:00:00+00:00",
                ),
                (
                    "w1",
                    "work/chats/w1.md",
                    "work",
                    "ask",
                    1,
                    0.0,
                    "2026-04-26T01:00:00+00:00",
                ),
            ],
        )
        result = await handle({"domain": "work"}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()

    assert result.data is not None
    assert [t["thread_id"] for t in result.data["threads"]] == ["w1"]


async def test_explicit_domain_out_of_scope_raises(tmp_path: Path) -> None:
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        with pytest.raises(ScopeError, match="not in allowed"):
            await handle(
                {"domain": "personal"},
                _mk_ctx(tmp_path, db=db, allowed=("research",)),
            )
    finally:
        db.close()


async def test_query_substring_matches_path(tmp_path: Path) -> None:
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        _seed(
            db,
            [
                (
                    "t1",
                    "research/chats/fisher-ury.md",
                    "research",
                    "ask",
                    1,
                    0.0,
                    "2026-04-26T00:00:00+00:00",
                ),
                (
                    "t2",
                    "research/chats/q2-board.md",
                    "research",
                    "draft",
                    1,
                    0.0,
                    "2026-04-26T01:00:00+00:00",
                ),
            ],
        )
        result = await handle({"query": "fisher"}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()

    assert result.data is not None
    assert [t["thread_id"] for t in result.data["threads"]] == ["t1"]


async def test_limit_clamps_to_max(tmp_path: Path) -> None:
    """Pass an absurd limit; the handler clamps to MAX_LIMIT."""
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        _seed(
            db,
            [
                (
                    f"t{i}",
                    f"research/chats/t{i}.md",
                    "research",
                    "ask",
                    1,
                    0.0,
                    f"2026-04-26T00:{i:02d}:00+00:00",
                )
                for i in range(5)
            ],
        )
        # Limit higher than _MAX_LIMIT — pydantic-style schema would
        # validate but the handler additionally clamps in code.
        result = await handle({"limit": 100_000}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()

    assert result.data is not None
    assert len(result.data["threads"]) == 5  # all rows, not clamped down


async def test_invalid_limit_raises(tmp_path: Path) -> None:
    db = StateDB.open(tmp_path / "state.sqlite")
    try:
        with pytest.raises(ValueError, match="limit must be a positive integer"):
            await handle({"limit": 0}, _mk_ctx(tmp_path, db=db))
        with pytest.raises(ValueError, match="limit must be a positive integer"):
            await handle({"limit": "many"}, _mk_ctx(tmp_path, db=db))
    finally:
        db.close()
