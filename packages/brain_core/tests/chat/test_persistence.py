"""Tests for brain_core.chat.persistence.ThreadPersistence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


@pytest.fixture
def env(
    tmp_path: Path,
) -> Iterator[tuple[Path, VaultWriter, StateDB, ThreadPersistence]]:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    (vault / "research" / "chats").mkdir()
    writer = VaultWriter(vault_root=vault)
    db = StateDB.open(tmp_path / "state.sqlite")
    persistence = ThreadPersistence(vault_root=vault, writer=writer, db=db)
    try:
        yield vault, writer, db, persistence
    finally:
        db.close()


def _turn(role: TurnRole, content: str, *, cost: float = 0.0) -> ChatTurn:
    return ChatTurn(
        role=role,
        content=content,
        created_at=datetime(2026, 4, 14, tzinfo=UTC),
        cost_usd=cost,
    )


def test_first_write_creates_file_via_vault_writer(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[_turn(TurnRole.USER, "hi")])
    path = vault / "research" / "chats" / f"{tid}.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "mode: ask" in content
    assert "## User" in content
    assert "hi" in content


def test_second_write_updates_same_file(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[_turn(TurnRole.USER, "first")])
    persistence.write(
        thread_id=tid,
        config=cfg,
        turns=[_turn(TurnRole.USER, "first"), _turn(TurnRole.ASSISTANT, "second")],
    )
    content = (vault / "research" / "chats" / f"{tid}.md").read_text(encoding="utf-8")
    assert content.count("## User") == 1
    assert content.count("## Assistant") == 1
    assert "first" in content and "second" in content


def test_state_db_row_upserted(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    _, _, db, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.BRAINSTORM, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(
        thread_id=tid,
        config=cfg,
        turns=[
            _turn(TurnRole.USER, "q"),
            _turn(TurnRole.ASSISTANT, "a", cost=0.02),
        ],
    )
    row = db.exec(
        "SELECT mode, turns, cost_usd FROM chat_threads WHERE thread_id = ?",
        (tid,),
    ).fetchone()
    assert row == ("brainstorm", 2, 0.02)


def test_tool_calls_rendered_as_fenced_blocks(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    turn = ChatTurn(
        role=TurnRole.ASSISTANT,
        content="I found it.",
        created_at=datetime(2026, 4, 14, tzinfo=UTC),
        tool_calls=[
            {
                "name": "search_vault",
                "args": {"query": "x"},
                "result_preview": "- r/a.md",
            }
        ],
        cost_usd=0.01,
    )
    persistence.write(thread_id=tid, config=cfg, turns=[turn])
    content = (vault / "research" / "chats" / f"{tid}.md").read_text(encoding="utf-8")
    assert "```tool:search_vault" in content
    assert "```tool-result:search_vault" in content


def test_system_turn_rendered(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(
        thread_id=tid,
        config=cfg,
        turns=[_turn(TurnRole.SYSTEM, "mode changed: ask -> brainstorm")],
    )
    content = (vault / "research" / "chats" / f"{tid}.md").read_text(encoding="utf-8")
    assert "## System" in content
    assert "mode changed" in content


def test_read_round_trip(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    turns_in = [_turn(TurnRole.USER, "hi"), _turn(TurnRole.ASSISTANT, "hello")]
    persistence.write(thread_id=tid, config=cfg, turns=turns_in)
    loaded = persistence.read(vault / "research" / "chats" / f"{tid}.md")
    assert [t.role for t in loaded.turns] == [TurnRole.USER, TurnRole.ASSISTANT]
    assert loaded.turns[0].content.strip() == "hi"
    assert loaded.turns[1].content.strip() == "hello"
    assert loaded.config.mode == ChatMode.ASK


def test_path_uses_first_domain(
    env: tuple[Path, VaultWriter, StateDB, ThreadPersistence],
) -> None:
    vault, _, _, persistence = env
    (vault / "work").mkdir()
    (vault / "work" / "chats").mkdir()
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research", "work"))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[_turn(TurnRole.USER, "x")])
    assert (vault / "research" / "chats" / f"{tid}.md").exists()
    assert not (vault / "work" / "chats" / f"{tid}.md").exists()
