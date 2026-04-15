"""Tests for brain_core.chat.session.ChatSession — pure event loop.

No persistence wiring (that's Task 18). All tests use FakeLLMProvider to
orchestrate streaming tool_use responses.
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
from brain_core.llm.types import (
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TokenUsage,
    ToolUse,
)
from brain_core.state.db import StateDB

EnvTuple = tuple[Path, FakeLLMProvider, ToolRegistry, BM25VaultIndex, PendingPatchStore, StateDB]


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def env(tmp_path: Path) -> Iterator[EnvTuple]:
    vault = tmp_path / "vault"
    _write_note(
        vault,
        "research/notes/karpathy.md",
        title="Karpathy",
        body="LLM wiki pattern by Karpathy.",
    )
    _write_note(
        vault,
        "research/notes/rag.md",
        title="RAG",
        body="Retrieval augmented generation.",
    )
    _write_note(
        vault,
        "research/notes/filler.md",
        title="Filler",
        body="Cooking recipes and gardening tips.",
    )
    (vault / "research" / "index.md").write_text(
        "# research\n- [[karpathy]]\n- [[rag]]\n", encoding="utf-8"
    )

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
    mode: ChatMode = ChatMode.ASK,
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
        thread_id="2026-04-14-draft-test0001",
    )


async def test_single_turn_no_tool(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue("Hello there.")
    session = _make_session(env)
    events = [e async for e in session.turn("hi")]
    kinds = [e.kind for e in events]
    assert ChatEventKind.DELTA in kinds
    assert kinds[-1] == ChatEventKind.TURN_END
    assert len(session._turns) == 2


async def test_single_tool_call_then_final(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue_tool_use(
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "karpathy"})]
    )
    fake.queue("Found karpathy. Answer.")
    session = _make_session(env)
    events = [e async for e in session.turn("what is karpathy?")]
    kinds = [e.kind for e in events]
    assert ChatEventKind.TOOL_CALL in kinds
    assert ChatEventKind.TOOL_RESULT in kinds
    assert kinds[-1] == ChatEventKind.TURN_END


async def test_tool_error_propagates_as_tool_result_error(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="read_note",
                input={"path": "research/notes/missing.md"},
            )
        ]
    )
    fake.queue("handled")
    session = _make_session(env)
    events = [e async for e in session.turn("read a note")]
    tool_results = [e for e in events if e.kind == ChatEventKind.TOOL_RESULT]
    assert len(tool_results) == 1
    assert tool_results[0].data.get("error") is True
    assert "not found" in tool_results[0].data["text"].lower()


async def test_propose_note_emits_patch_proposed(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="propose_note",
                input={
                    "path": "research/notes/new.md",
                    "content": "# new",
                    "reason": "brainstorm",
                },
            )
        ]
    )
    fake.queue("staged")
    session = _make_session(env, mode=ChatMode.BRAINSTORM)
    events = [e async for e in session.turn("make a note")]
    patch_events = [e for e in events if e.kind == ChatEventKind.PATCH_PROPOSED]
    assert len(patch_events) == 1
    assert patch_events[0].data["target_path"].endswith("research/notes/new.md")
    vault = env[0]
    assert not (vault / "research" / "notes" / "new.md").exists()


async def test_max_tool_rounds_cap(env: EnvTuple) -> None:
    fake = env[1]
    for i in range(11):
        fake.queue_tool_use(
            tool_uses=[ToolUse(id=f"tu_{i}", name="search_vault", input={"query": f"q{i}"})]
        )
    session = _make_session(env)
    events = [e async for e in session.turn("loop forever")]
    assert events[-1].kind == ChatEventKind.TURN_END
    assert events[-1].data.get("error") == "max tool rounds exceeded"


async def test_ask_mode_excludes_propose_note(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="propose_note",
                input={"path": "r/a.md", "content": "x", "reason": "x"},
            )
        ]
    )
    fake.queue("handled")
    session = _make_session(env, mode=ChatMode.ASK)
    events = [e async for e in session.turn("hi")]
    tool_results = [e for e in events if e.kind == ChatEventKind.TOOL_RESULT]
    assert len(tool_results) == 1
    assert tool_results[0].data.get("error") is True
    assert "not available" in tool_results[0].data["text"].lower()


async def test_open_doc_none_excludes_edit_open_doc(env: EnvTuple) -> None:
    fake = env[1]
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="edit_open_doc",
                input={"old": "x", "new": "y", "reason": "z"},
            )
        ]
    )
    fake.queue("handled")
    session = _make_session(env, mode=ChatMode.DRAFT, open_doc=None)
    events = [e async for e in session.turn("edit")]
    tool_results = [e for e in events if e.kind == ChatEventKind.TOOL_RESULT]
    assert len(tool_results) == 1
    assert tool_results[0].data.get("error") is True


async def test_switch_mode_appends_system_turn_and_updates_registry(
    env: EnvTuple,
) -> None:
    session = _make_session(env, mode=ChatMode.ASK)
    session.switch_mode(ChatMode.BRAINSTORM)
    assert session.config.mode == ChatMode.BRAINSTORM
    assert any(t.role.value == "system" and "mode changed" in t.content for t in session._turns)
    assert "propose_note" in [t.name for t in session._effective_registry.all()]


async def test_set_open_doc_appends_system_turn(env: EnvTuple) -> None:
    session = _make_session(env, mode=ChatMode.DRAFT, open_doc=None)
    # Initially no system turn.
    assert not any(t.role.value == "system" for t in session._turns)
    # Setting to a path appends a SYSTEM turn.
    session.set_open_doc(Path("research/notes/drafting.md"))
    system_turns = [t for t in session._turns if t.role.value == "system"]
    assert len(system_turns) == 1
    assert "open doc set" in system_turns[0].content
    assert "research/notes/drafting.md" in system_turns[0].content
    # edit_open_doc should now be in the effective registry.
    assert "edit_open_doc" in [t.name for t in session._effective_registry.all()]
    # Clearing appends another SYSTEM turn.
    session.set_open_doc(None)
    system_turns = [t for t in session._turns if t.role.value == "system"]
    assert len(system_turns) == 2
    assert "open doc cleared" in system_turns[1].content
    # edit_open_doc should be removed from the effective registry.
    assert "edit_open_doc" not in [t.name for t in session._effective_registry.all()]
    # Setting to same None is a no-op.
    session.set_open_doc(None)
    assert len([t for t in session._turns if t.role.value == "system"]) == 2


class _CombinedChunkProvider:
    """Minimal provider that yields a single chunk combining delta + usage.

    Real Anthropic streams deliver delta and usage as separate events, but the
    `LLMStreamChunk` schema permits a combined shape. This provider exercises
    that path so future SDK changes do not silently regress.
    """

    name = "combined-chunk"

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError

    async def stream(self, request: LLMRequest):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        # Single combined chunk: text delta AND usage in the same message.
        # done=False — the stream terminates by iterator exhaustion, not a
        # sentinel, to prove the loop does not depend on `done=True` firing.
        yield LLMStreamChunk(
            delta="hi",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            done=False,
        )


async def test_turn_handles_combined_delta_and_usage_chunk(env: EnvTuple) -> None:
    vault, _fake, registry, retrieval, pending, db = env
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE PROMPT")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    session = ChatSession(
        config=cfg,
        llm=_CombinedChunkProvider(),
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        vault_root=vault,
        thread_id="2026-04-14-draft-combined",
    )
    events = [e async for e in session.turn("hi")]
    deltas = [e for e in events if e.kind == ChatEventKind.DELTA]
    assert len(deltas) == 1
    assert deltas[0].data["text"] == "hi"
    assert events[-1].kind == ChatEventKind.TURN_END
    # Assistant turn captured with the combined text.
    assistant_turns = [t for t in session._turns if t.role.value == "assistant"]
    assert assistant_turns[-1].content == "hi"
