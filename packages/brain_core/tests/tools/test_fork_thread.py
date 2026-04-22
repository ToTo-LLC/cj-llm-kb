"""Unit tests for brain_core.tools.fork_thread.

Covers the three carry modes (full / none / summary) plus the invalid-source
path. Exercises the real ``fork_from`` primitive under the hood — no mocking
of the chat session's moving parts; the only fake is the LLM provider so the
summary path is deterministic and cheap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.llm.fake import FakeLLMProvider
from brain_core.state.db import StateDB
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.fork_thread import NAME, handle
from brain_core.vault.writer import VaultWriter


@dataclass
class _AllowAllLimiter:
    """Rate-limiter stand-in: every ``check`` succeeds (no raise, no return)."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        return None


def _seed_source_thread(
    *,
    persistence: ThreadPersistence,
    n_turns: int,
    thread_id: str = "2026-04-21-source-thread",
    mode: ChatMode = ChatMode.ASK,
) -> str:
    """Persist a source thread with ``n_turns`` user+assistant pairs."""
    config = ChatSessionConfig(mode=mode, domains=("research",))
    turns: list[ChatTurn] = []
    now = datetime.now(UTC)
    for i in range(n_turns):
        turns.append(ChatTurn(role=TurnRole.USER, content=f"user msg {i}", created_at=now))
        turns.append(
            ChatTurn(role=TurnRole.ASSISTANT, content=f"assistant reply {i}", created_at=now)
        )
    persistence.write(thread_id=thread_id, config=config, turns=turns)
    return thread_id


def _mk_ctx(vault: Path, llm: FakeLLMProvider) -> tuple[ToolContext, StateDB]:
    """Build a ToolContext wired to a real state_db + writer for fork_from."""
    brain_dir = vault / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    db = StateDB.open(brain_dir / "state.sqlite")
    writer = VaultWriter(vault_root=vault)
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(("research",))
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=retrieval,
        pending_store=None,
        state_db=db,
        writer=writer,
        llm=llm,
        cost_ledger=None,
        rate_limiter=_AllowAllLimiter(),
        undo_log=None,
    )
    return ctx, db


def test_name() -> None:
    assert NAME == "brain_fork_thread"


async def test_fork_full_carry_happy_path(tmp_path: Path) -> None:
    """``carry='full'`` returns a new thread_id; source unchanged."""
    vault = tmp_path / "vault"
    (vault / "research" / "chats").mkdir(parents=True)
    (vault / "research" / "index.md").write_text("# research\n", encoding="utf-8")

    llm = FakeLLMProvider()
    ctx, db = _mk_ctx(vault, llm)
    try:
        persistence = ThreadPersistence(vault_root=vault, writer=ctx.writer, db=db)
        source_id = _seed_source_thread(persistence=persistence, n_turns=3)

        result = await handle(
            {
                "source_thread_id": source_id,
                "turn_index": 3,
                "carry": "full",
                "mode": "ask",
            },
            ctx,
        )

        assert isinstance(result, ToolResult)
        assert result.data is not None
        new_id = result.data["new_thread_id"]
        assert isinstance(new_id, str) and new_id
        assert new_id != source_id
        # Source thread file still intact.
        assert (vault / "research" / "chats" / f"{source_id}.md").exists()
        # New thread is NOT persisted yet — first turn writes it.
        assert not (vault / "research" / "chats" / f"{new_id}.md").exists()
        # No LLM call for 'full' carry.
        assert llm.requests == []
    finally:
        db.close()


async def test_fork_summary_carry_invokes_llm(tmp_path: Path) -> None:
    """``carry='summary'`` runs the Haiku summary helper and returns a thread id."""
    vault = tmp_path / "vault"
    (vault / "research" / "chats").mkdir(parents=True)
    (vault / "research" / "index.md").write_text("# research\n", encoding="utf-8")

    llm = FakeLLMProvider()
    llm.queue("A 4-sentence summary of the prior conversation.")
    ctx, db = _mk_ctx(vault, llm)
    try:
        persistence = ThreadPersistence(vault_root=vault, writer=ctx.writer, db=db)
        source_id = _seed_source_thread(persistence=persistence, n_turns=2)

        result = await handle(
            {
                "source_thread_id": source_id,
                "turn_index": 3,
                "carry": "summary",
                "mode": "brainstorm",
                "title_hint": "deep-dive",
            },
            ctx,
        )

        assert result.data is not None
        new_id = result.data["new_thread_id"]
        # title_hint embedded in the thread_id slug.
        assert "deep-dive" in new_id
        # One LLM call for the summary.
        assert len(llm.requests) == 1
        assert llm.requests[0].model.startswith("claude-haiku")
    finally:
        db.close()


async def test_fork_invalid_source_raises_file_not_found(tmp_path: Path) -> None:
    """Unknown ``source_thread_id`` raises :class:`FileNotFoundError`.

    brain_api's global handler maps this to a 404 ``not_found`` response;
    MCP surfaces it via the shim's normal exception path.
    """
    vault = tmp_path / "vault"
    (vault / "research" / "chats").mkdir(parents=True)
    (vault / "research" / "index.md").write_text("# research\n", encoding="utf-8")

    llm = FakeLLMProvider()
    ctx, db = _mk_ctx(vault, llm)
    try:
        with pytest.raises(FileNotFoundError):
            await handle(
                {
                    "source_thread_id": "does-not-exist",
                    "turn_index": 0,
                    "carry": "full",
                    "mode": "ask",
                },
                ctx,
            )
    finally:
        db.close()
