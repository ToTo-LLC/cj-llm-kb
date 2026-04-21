"""Plan 07 Task 5 — ``fork_from`` branches a thread from turn N into a new thread.

Three carry modes (D3a):

* ``full`` — copy turns 0..turn_index verbatim into the new thread.
* ``none`` — start empty; new thread only inherits mode + scope.
* ``summary`` — Haiku-cheap prose summary of prior turns, prepended as
  a single ``SYSTEM`` turn.

The source thread is read via ``ThreadPersistence.read``; the new
session is constructed with ``initial_turns=...`` (Plan 05 Task 21a).
A fresh ``thread_id`` is generated; the new session is returned
unpersisted so the caller can choose when to flush (typically after
the first turn runs).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from brain_core.chat.context import ContextCompiler
from brain_core.chat.fork import fork_from, summarize_turns
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.llm.fake import FakeLLMProvider
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


@dataclass
class ForkEnv:
    vault: Path
    fake: FakeLLMProvider
    persistence: ThreadPersistence
    db: StateDB
    compiler: ContextCompiler
    registry: ToolRegistry
    retrieval: BM25VaultIndex
    pending: PendingPatchStore


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ForkEnv]:
    vault = tmp_path / "vault"
    (vault / "research" / "chats").mkdir(parents=True)
    (vault / "research" / "notes").mkdir(parents=True)
    (vault / "research" / "index.md").write_text("# research\n", encoding="utf-8")

    fake = FakeLLMProvider()
    db = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    writer = VaultWriter(vault_root=vault)
    persistence = ThreadPersistence(vault_root=vault, writer=writer, db=db)
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE")
    registry = ToolRegistry()
    registry.register(SearchVaultTool())
    registry.register(ReadNoteTool())
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(("research",))
    pending = PendingPatchStore(tmp_path / ".brain" / "pending")
    try:
        yield ForkEnv(
            vault=vault,
            fake=fake,
            persistence=persistence,
            db=db,
            compiler=compiler,
            registry=registry,
            retrieval=retrieval,
            pending=pending,
        )
    finally:
        db.close()


def _seed_source_thread(
    *,
    persistence: ThreadPersistence,
    n_turns: int,
    thread_id: str = "2026-04-16-source-thread",
    mode: ChatMode = ChatMode.ASK,
) -> tuple[str, ChatSessionConfig]:
    """Persist a thread with ``n_turns`` user+assistant turn pairs."""
    from datetime import UTC, datetime

    config = ChatSessionConfig(mode=mode, domains=("research",))
    turns: list[ChatTurn] = []
    now = datetime.now(UTC)
    for i in range(n_turns):
        turns.append(
            ChatTurn(role=TurnRole.USER, content=f"user msg {i}", created_at=now)
        )
        turns.append(
            ChatTurn(
                role=TurnRole.ASSISTANT,
                content=f"assistant reply {i}",
                created_at=now,
            )
        )
    persistence.write(thread_id=thread_id, config=config, turns=turns)
    return thread_id, config


async def _do_fork(
    env: ForkEnv,
    *,
    source_thread_id: str,
    turn_index: int,
    carry: str,
    mode: ChatMode | None = None,
) -> ChatSession:
    """Invoke ``fork_from`` with the env's wiring."""
    from typing import Literal, cast

    return await fork_from(
        source_thread_id=source_thread_id,
        turn_index=turn_index,
        vault_root=env.vault,
        llm=env.fake,
        compiler=env.compiler,
        registry=env.registry,
        persistence=env.persistence,
        retrieval=env.retrieval,
        pending_store=env.pending,
        state_db=env.db,
        carry=cast(Literal["full", "none", "summary"], carry),
        mode=mode,
    )


async def test_fork_full_carry_copies_turns(env: ForkEnv) -> None:
    """``carry='full'`` copies turns 0..turn_index (inclusive) verbatim."""
    source_id, _ = _seed_source_thread(persistence=env.persistence, n_turns=3)
    # Source has 6 turns (3 user + 3 assistant). Forking at index 3
    # means turns 0..3 inclusive — i.e., 4 turns copied.
    forked = await _do_fork(
        env, source_thread_id=source_id, turn_index=3, carry="full"
    )
    assert isinstance(forked, ChatSession)
    assert len(forked._turns) == 4
    assert forked._turns[0].content == "user msg 0"
    assert forked._turns[3].content == "assistant reply 1"
    # Scope and mode inherited from source.
    assert forked.config.mode == ChatMode.ASK
    assert forked.config.domains == ("research",)
    # Fresh thread_id, not the source.
    assert forked.thread_id != source_id


async def test_fork_none_carry_empty(env: ForkEnv) -> None:
    """``carry='none'`` inherits mode + scope but starts with zero turns."""
    source_id, _ = _seed_source_thread(
        persistence=env.persistence, n_turns=3, mode=ChatMode.BRAINSTORM
    )
    forked = await _do_fork(
        env, source_thread_id=source_id, turn_index=2, carry="none"
    )
    assert forked._turns == []
    # Mode inherited from source thread.
    assert forked.config.mode == ChatMode.BRAINSTORM


async def test_fork_summary_carry_runs_llm(env: ForkEnv) -> None:
    """``carry='summary'`` compresses prior turns into one SYSTEM entry."""
    source_id, _ = _seed_source_thread(persistence=env.persistence, n_turns=2)
    env.fake.queue("This is a 4-sentence summary of prior conversation.")
    forked = await _do_fork(
        env, source_thread_id=source_id, turn_index=3, carry="summary"
    )
    assert len(forked._turns) == 1
    assert forked._turns[0].role == TurnRole.SYSTEM
    assert "summary" in forked._turns[0].content.lower()


async def test_fork_invalid_turn_index_raises(env: ForkEnv) -> None:
    """Out-of-range ``turn_index`` raises ``IndexError`` before any LLM call."""
    source_id, _ = _seed_source_thread(persistence=env.persistence, n_turns=2)
    # Source has 4 turns (0..3); index 99 is out of range.
    with pytest.raises(IndexError):
        await _do_fork(
            env, source_thread_id=source_id, turn_index=99, carry="full"
        )


async def test_fork_mode_override_wins(env: ForkEnv) -> None:
    """Explicit ``mode=...`` overrides the source thread's mode."""
    source_id, _ = _seed_source_thread(
        persistence=env.persistence, n_turns=1, mode=ChatMode.ASK
    )
    forked = await _do_fork(
        env,
        source_thread_id=source_id,
        turn_index=0,
        carry="full",
        mode=ChatMode.DRAFT,
    )
    assert forked.config.mode == ChatMode.DRAFT


async def test_summarize_turns_uses_haiku_model(env: ForkEnv) -> None:
    """``summarize_turns`` defaults to the Haiku model for cost efficiency."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="what is x?", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="x is y.", created_at=now),
    ]
    env.fake.queue("Summary text.")
    result = await summarize_turns(turns, env.fake)
    assert result == "Summary text."
    # Confirm the LLM saw the Haiku model.
    assert env.fake.requests[0].model.startswith("claude-haiku")
