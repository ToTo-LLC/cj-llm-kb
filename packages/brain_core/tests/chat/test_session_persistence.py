"""Tests for Task 18: ChatSession persistence + autotitle wiring."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.autotitle import AutoTitler
from brain_core.chat.context import ContextCompiler
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import ChatEventKind, ChatMode, ChatSessionConfig
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.loader import load_prompt
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


@pytest.fixture
def persistent_env(
    tmp_path: Path,
) -> Iterator[tuple[Path, FakeLLMProvider, ChatSession]]:
    vault = tmp_path / "vault"
    (vault / "research" / "chats").mkdir(parents=True)
    (vault / "research" / "notes").mkdir()
    (vault / "research" / "notes" / "karpathy.md").write_text(
        "---\ntitle: Karpathy\n---\nLLM wiki body.\n", encoding="utf-8"
    )
    (vault / "research" / "notes" / "rag.md").write_text(
        "---\ntitle: RAG\n---\nRAG body.\n", encoding="utf-8"
    )
    (vault / "research" / "notes" / "filler.md").write_text(
        "---\ntitle: Filler\n---\nUnrelated filler content.\n", encoding="utf-8"
    )
    (vault / "research" / "index.md").write_text("# research\n- [[karpathy]]\n", encoding="utf-8")

    fake = FakeLLMProvider()
    db = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    writer = VaultWriter(vault_root=vault)
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(("research",))
    pending = PendingPatchStore(tmp_path / ".brain" / "pending")
    persistence = ThreadPersistence(vault_root=vault, writer=writer, db=db)
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE")

    registry = ToolRegistry()
    registry.register(SearchVaultTool())
    registry.register(ReadNoteTool())

    autotitler = AutoTitler(fake, prompt=load_prompt("chat_autotitle"))

    config = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    session = ChatSession(
        config=config,
        llm=fake,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        vault_root=vault,
        thread_id="2026-04-14-draft-abc123",
        persistence=persistence,
        autotitler=autotitler,
        vault_writer=writer,
    )
    try:
        yield vault, fake, session
    finally:
        db.close()


async def test_turn_persists_thread_markdown(
    persistent_env: tuple[Path, FakeLLMProvider, ChatSession],
) -> None:
    vault, fake, session = persistent_env
    fake.queue("hello")
    async for _ in session.turn("hi"):
        pass
    path = vault / "research" / "chats" / f"{session.thread_id}.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "## User" in text
    assert "## Assistant" in text


async def test_turn_2_triggers_autotitle_and_rename(
    persistent_env: tuple[Path, FakeLLMProvider, ChatSession],
) -> None:
    vault, fake, session = persistent_env
    old_thread_id = session.thread_id
    fake.queue("answer 1")
    async for _ in session.turn("q1"):
        pass
    assert session.thread_id == old_thread_id
    fake.queue("answer 2")
    fake.queue('{"title": "llm wiki basics", "slug": "llm-wiki-basics"}')
    async for _ in session.turn("q2"):
        pass
    assert session.thread_id != old_thread_id
    assert "llm-wiki-basics" in session.thread_id
    assert "draft" not in session.thread_id
    assert not (vault / "research" / "chats" / f"{old_thread_id}.md").exists()
    assert (vault / "research" / "chats" / f"{session.thread_id}.md").exists()


async def test_state_db_row_updated_on_rename(
    persistent_env: tuple[Path, FakeLLMProvider, ChatSession],
) -> None:
    _vault, fake, session = persistent_env
    fake.queue("a1")
    async for _ in session.turn("q1"):
        pass
    fake.queue("a2")
    fake.queue('{"title": "foo bar baz", "slug": "foo-bar-baz"}')
    async for _ in session.turn("q2"):
        pass
    assert session.state_db is not None
    rows = session.state_db.exec("SELECT thread_id FROM chat_threads").fetchall()
    ids = [r[0] for r in rows]
    assert session.thread_id in ids
    assert not any("draft" in i for i in ids)


async def test_autotitle_none_skips_rename(
    persistent_env: tuple[Path, FakeLLMProvider, ChatSession],
) -> None:
    _vault, fake, session = persistent_env
    session.autotitler = None
    original = session.thread_id
    fake.queue("a1")
    async for _ in session.turn("q1"):
        pass
    fake.queue("a2")
    async for _ in session.turn("q2"):
        pass
    assert session.thread_id == original


async def test_autotitle_failure_rolls_back_thread_id(
    persistent_env: tuple[Path, FakeLLMProvider, ChatSession],
) -> None:
    _vault, fake, session = persistent_env
    original = session.thread_id
    fake.queue("a1")
    async for _ in session.turn("q1"):
        pass
    fake.queue("a2")
    fake.queue("not json at all")
    events = [e async for e in session.turn("q2")]
    assert session.thread_id == original
    error_events = [e for e in events if e.kind == ChatEventKind.ERROR]
    assert len(error_events) >= 1
    assert "autotitle" in error_events[0].data["message"].lower()
