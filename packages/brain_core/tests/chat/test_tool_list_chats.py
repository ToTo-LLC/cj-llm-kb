"""Tests for the list_chats tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.tools.base import ToolContext
from brain_core.chat.tools.list_chats import ListChatsTool
from brain_core.state.db import StateDB
from brain_core.vault.paths import ScopeError


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[ToolContext]:
    db = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    # Seed three threads directly — ThreadPersistence (Task 13) isn't built yet.
    rows = [
        (
            "t1",
            "research/chats/2026-04-10-foo.md",
            "research",
            "ask",
            3,
            0.01,
            "2026-04-10T10:00:00Z",
        ),
        (
            "t2",
            "research/chats/2026-04-12-rag.md",
            "research",
            "brainstorm",
            5,
            0.03,
            "2026-04-12T10:00:00Z",
        ),
        (
            "t3",
            "personal/chats/2026-04-11-bar.md",
            "personal",
            "ask",
            1,
            0.00,
            "2026-04-11T10:00:00Z",
        ),
    ]
    for r in rows:
        db.exec(
            "INSERT INTO chat_threads(thread_id, path, domain, mode, turns, cost_usd, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            r,
        )
    ctx = ToolContext(
        vault_root=tmp_path / "vault",
        allowed_domains=("research",),
        open_doc_path=None,
        retrieval=None,
        pending_store=None,
        state_db=db,
        source_thread="t.md",
        mode_name="ask",
    )
    yield ctx
    db.close()


def test_lists_in_scope_threads_only(ctx: ToolContext) -> None:
    result = ListChatsTool().run({}, ctx)
    assert result.data is not None
    ids = [t["thread_id"] for t in result.data["threads"]]
    assert set(ids) == {"t1", "t2"}
    # personal t3 must be excluded
    assert "t3" not in ids


def test_ordered_by_updated_desc(ctx: ToolContext) -> None:
    result = ListChatsTool().run({}, ctx)
    assert result.data is not None
    ids = [t["thread_id"] for t in result.data["threads"]]
    # t2 (2026-04-12) is newer than t1 (2026-04-10)
    assert ids == ["t2", "t1"]


def test_query_substring_filter(ctx: ToolContext) -> None:
    result = ListChatsTool().run({"query": "rag"}, ctx)
    assert result.data is not None
    ids = [t["thread_id"] for t in result.data["threads"]]
    assert ids == ["t2"]


def test_out_of_scope_domain_arg_raises(ctx: ToolContext) -> None:
    with pytest.raises(ScopeError):
        ListChatsTool().run({"domain": "personal"}, ctx)
