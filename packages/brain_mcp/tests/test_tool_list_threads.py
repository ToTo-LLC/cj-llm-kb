"""Tests for the brain_list_threads MCP tool (issue #18).

Most behavior is covered by ``packages/brain_core/tests/tools/test_list_threads.py``;
this module pins the MCP transport surface (NAME, JSON envelope shape).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.state.db import StateDB
from brain_core.tools.base import ToolContext
from brain_mcp.tools.list_threads import NAME, handle


def _seed_one(db: StateDB) -> None:
    db.exec(
        "CREATE TABLE IF NOT EXISTS chat_threads ("
        " thread_id TEXT PRIMARY KEY, path TEXT, domain TEXT, mode TEXT,"
        " turns INTEGER, cost_usd REAL, updated_at TEXT)"
    )
    db.exec(
        "INSERT OR REPLACE INTO chat_threads"
        "(thread_id, path, domain, mode, turns, cost_usd, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "t-smoke",
            "research/chats/t-smoke.md",
            "research",
            "ask",
            3,
            0.01,
            "2026-04-26T12:00:00+00:00",
        ),
    )


def test_name() -> None:
    assert NAME == "brain_list_threads"


async def test_returns_text_content_envelope(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """The shim returns the standard 2-element TextContent list — first
    element a human-readable summary, second the JSON payload."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    assert ctx.state_db is not None
    _seed_one(ctx.state_db)

    out = await handle({}, ctx)
    assert len(out) == 2
    summary = out[0].text
    payload = json.loads(out[1].text)
    assert "research/chats/t-smoke.md" in summary
    assert payload["threads"][0]["thread_id"] == "t-smoke"
    assert payload["threads"][0]["mode"] == "ask"


async def test_empty_summary_when_no_threads(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    assert "no chats yet" in out[0].text.lower()
    payload = json.loads(out[1].text)
    assert payload["threads"] == []
