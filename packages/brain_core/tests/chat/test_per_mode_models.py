"""Plan 07 Task 2 — per-mode chat model selection.

``ChatSessionConfig`` gets three optional per-mode model fields:
``ask_model`` / ``brainstorm_model`` / ``draft_model``. When the active
mode's field is set, ``ChatSession.turn`` uses it; otherwise it falls
back to ``config.model`` (preserving Plan 03 default-model semantics).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.context import ContextCompiler
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.edit_open_doc import EditOpenDocTool
from brain_core.chat.tools.list_chats import ListChatsTool
from brain_core.chat.tools.list_index import ListIndexTool
from brain_core.chat.tools.propose_note import ProposeNoteTool
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import ChatMode, ChatSessionConfig
from brain_core.llm.fake import FakeLLMProvider
from brain_core.state.db import StateDB

EnvTuple = tuple[Path, FakeLLMProvider, ToolRegistry, BM25VaultIndex, PendingPatchStore, StateDB]


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def env(tmp_path: Path) -> Iterator[EnvTuple]:
    vault = tmp_path / "vault"
    _write_note(vault, "research/notes/a.md", title="A", body="body A")
    (vault / "research" / "index.md").write_text("# research\n- [[a]]\n", encoding="utf-8")

    fake = FakeLLMProvider()
    db = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(("research",))
    pending = PendingPatchStore(tmp_path / ".brain" / "pending")

    registry = ToolRegistry()
    for tool in (
        SearchVaultTool(),
        ReadNoteTool(),
        ListIndexTool(),
        ListChatsTool(),
        ProposeNoteTool(),
        EditOpenDocTool(),
    ):
        registry.register(tool)

    try:
        yield vault, fake, registry, retrieval, pending, db
    finally:
        db.close()


def _make_session(
    env_tuple: EnvTuple,
    *,
    mode: ChatMode,
    config_overrides: dict[str, object] | None = None,
) -> ChatSession:
    vault, fake, registry, retrieval, pending, db = env_tuple
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE PROMPT")
    base: dict[str, object] = {
        "mode": mode,
        "domains": ("research",),
        "model": "default-m",
    }
    if config_overrides:
        base.update(config_overrides)
    cfg = ChatSessionConfig(**base)  # type: ignore[arg-type]
    return ChatSession(
        config=cfg,
        llm=fake,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        vault_root=vault,
        thread_id="2026-04-16-draft-mtest001",
    )


async def test_ask_mode_uses_ask_model(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue("ok")
    session = _make_session(
        env,
        mode=ChatMode.ASK,
        config_overrides={"ask_model": "ask-m"},
    )
    async for _ in session.turn("hi"):
        pass
    # FakeLLMProvider captures every LLMRequest in ``.requests``; the
    # per-mode override must reach the provider through ``LLMRequest.model``.
    assert fake.requests[-1].model == "ask-m"


async def test_brainstorm_mode_uses_brainstorm_model(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue("ok")
    session = _make_session(
        env,
        mode=ChatMode.BRAINSTORM,
        config_overrides={"brainstorm_model": "brainstorm-m"},
    )
    async for _ in session.turn("hi"):
        pass
    assert fake.requests[-1].model == "brainstorm-m"


async def test_fallback_to_default_when_mode_model_unset(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue("ok")
    # No ask_model override — expect default to be used.
    session = _make_session(env, mode=ChatMode.ASK)
    async for _ in session.turn("hi"):
        pass
    assert fake.requests[-1].model == "default-m"
