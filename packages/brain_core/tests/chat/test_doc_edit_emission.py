"""Plan 07 Task 2 — Draft-mode ``\\`\\`\\`edits`` fence emits ``DOC_EDIT`` events.

The assistant in Draft mode may append a fenced ``edits`` JSON block to
its reply. After the streaming turn completes, ``ChatSession.turn``
scans the assembled assistant text for those fences and yields one
``ChatEvent(kind=DOC_EDIT)`` per edit entry. The fence text itself is
left in the assistant message — non-Draft surfaces render it as an
ordinary markdown code block, so only Draft-mode WS clients act on the
structured events.

Ask/Brainstorm modes never emit ``DOC_EDIT`` — the fence is just text.
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
from brain_core.chat.types import ChatEventKind, ChatMode, ChatSessionConfig
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
    _write_note(vault, "research/notes/draft.md", title="Draft", body="line one")
    (vault / "research" / "index.md").write_text("# research\n- [[draft]]\n", encoding="utf-8")

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
    open_doc: Path | None = None,
) -> ChatSession:
    vault, fake, registry, retrieval, pending, db = env_tuple
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE PROMPT")
    cfg = ChatSessionConfig(mode=mode, domains=("research",), open_doc_path=open_doc)
    return ChatSession(
        config=cfg,
        llm=fake,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        vault_root=vault,
        thread_id="2026-04-16-draft-etest001",
    )


_FENCED_RESPONSE = (
    "OK here's the edit proposal.\n"
    "\n"
    "```edits\n"
    '{"edits": [{"op": "insert", "anchor": {"kind": "line", "value": 3},'
    ' "text": "new line"}]}\n'
    "```\n"
    "\n"
    "Let me know."
)


async def test_draft_mode_emits_doc_edit_event(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue(_FENCED_RESPONSE)
    session = _make_session(
        env,
        mode=ChatMode.DRAFT,
        open_doc=Path("research/notes/draft.md"),
    )
    events = [e async for e in session.turn("propose an edit")]
    doc_edits = [e for e in events if e.kind == ChatEventKind.DOC_EDIT]
    assert len(doc_edits) == 1
    data = doc_edits[0].data
    assert data["op"] == "insert"
    assert data["anchor"]["kind"] == "line"
    assert data["anchor"]["value"] == 3
    assert data["text"] == "new line"
    # The assistant message text must retain the fence — non-Draft
    # surfaces render it as a normal markdown block. Non-mutation is
    # part of the Task 2 contract (no filtering before other listeners).
    assistant_turns = [t for t in session._turns if t.role.value == "assistant"]
    assert "```edits" in assistant_turns[-1].content


async def test_ask_mode_does_not_emit_doc_edit(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue(_FENCED_RESPONSE)
    session = _make_session(env, mode=ChatMode.ASK)
    events = [e async for e in session.turn("reply")]
    assert not any(e.kind == ChatEventKind.DOC_EDIT for e in events)
