"""Tests for the brain_fork_thread MCP shim.

Thin wrapper over ``brain_core.tools.fork_thread.handle``. We verify the MCP
shim returns the expected text+JSON blocks on the happy path; the carry-mode
branching is covered by the brain_core unit tests.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.tools.base import ToolContext
from brain_mcp.tools.fork_thread import INPUT_SCHEMA, NAME, handle


def test_name_and_schema() -> None:
    assert NAME == "brain_fork_thread"
    assert INPUT_SCHEMA["required"] == [
        "source_thread_id",
        "turn_index",
        "carry",
        "mode",
    ]


async def test_fork_thread_returns_new_thread_id(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """MCP shim returns a TextContent block with ``new_thread_id`` in the JSON body."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    # Seed a source thread via the real persistence layer.
    persistence = ThreadPersistence(vault_root=seeded_vault, writer=ctx.writer, db=ctx.state_db)
    source_id = "2026-04-21-mcp-source"
    now = datetime.now(UTC)
    persistence.write(
        thread_id=source_id,
        config=ChatSessionConfig(mode=ChatMode.ASK, domains=("research",)),
        turns=[
            ChatTurn(role=TurnRole.USER, content="hi", created_at=now),
            ChatTurn(role=TurnRole.ASSISTANT, content="hello", created_at=now),
        ],
    )

    out = await handle(
        {
            "source_thread_id": source_id,
            "turn_index": 1,
            "carry": "full",
            "mode": "ask",
        },
        ctx,
    )
    assert len(out) >= 2
    data = json.loads(out[1].text)
    assert "new_thread_id" in data
    assert isinstance(data["new_thread_id"], str)
    assert data["new_thread_id"] != source_id
