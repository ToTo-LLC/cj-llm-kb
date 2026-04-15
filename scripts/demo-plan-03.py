"""Plan 03 end-to-end demo.

Runs in a temp directory, scaffolds a tiny vault, drives ChatSession against
FakeLLMProvider through the 7 Plan 03 demo gates, and prints PLAN 03 DEMO OK
on success.

Gates:
  1. Ask mode with tool call (search_vault)
  2. Brainstorm mode with propose_note (patch staged, not written)
  3. Draft mode with edit_open_doc (patch staged, open doc unchanged)
  4. Thread persistence (frontmatter + User/Assistant sections)
  5. Auto-title after turn 2 (draft thread renamed)
  6. Idempotency (re-opening StateDB yields identical state)
  7. Scope guard rejects personal/ in research-scoped session
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from brain_core.chat.autotitle import AutoTitler
from brain_core.chat.context import ContextCompiler
from brain_core.chat.modes import MODES
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.edit_open_doc import EditOpenDocTool
from brain_core.chat.tools.list_chats import ListChatsTool
from brain_core.chat.tools.list_index import ListIndexTool
from brain_core.chat.tools.propose_note import ProposeNoteTool
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import ChatEvent, ChatEventKind, ChatMode, ChatSessionConfig
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import ToolUse
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


def _scaffold_vault(root: Path) -> None:
    """Build a minimal vault: research + personal domains, a few notes, an open doc."""
    root.mkdir(parents=True)
    (root / ".brain").mkdir()
    for domain in ("research", "personal"):
        d = root / domain
        for sub in ("sources", "entities", "concepts", "synthesis", "chats"):
            (d / sub).mkdir(parents=True)
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")

    (root / "research" / "sources" / "karpathy.md").write_text(
        "---\ntitle: Karpathy\ndomain: research\n---\n"
        "Andrej Karpathy wrote about the LLM wiki pattern.\n",
        encoding="utf-8",
    )
    (root / "research" / "sources" / "rag.md").write_text(
        "---\ntitle: RAG\ndomain: research\n---\n"
        "Retrieval-augmented generation over raw documents.\n",
        encoding="utf-8",
    )
    (root / "research" / "sources" / "drafting.md").write_text(
        "---\ntitle: Drafting\ndomain: research\n---\n"
        "The original unique sentence about the draft.\n",
        encoding="utf-8",
    )
    (root / "personal" / "sources" / "secret.md").write_text(
        "---\ntitle: Secret\ndomain: personal\n---\nshould never be read.\n",
        encoding="utf-8",
    )


def _build_session(
    vault: Path,
    *,
    fake: FakeLLMProvider,
    mode: ChatMode,
    domains: tuple[str, ...] = ("research",),
    open_doc: Path | None = None,
    thread_id: str,
) -> ChatSession:
    db = StateDB.open(vault / ".brain" / "state.sqlite")
    writer = VaultWriter(vault_root=vault)
    pending = PendingPatchStore(vault / ".brain" / "pending")
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(domains)
    compiler = ContextCompiler(vault_root=vault, mode_prompt=MODES[mode].prompt_text)
    persistence = ThreadPersistence(vault_root=vault, writer=writer, db=db)

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

    autotitler = AutoTitler(fake)
    config = ChatSessionConfig(
        mode=mode,
        domains=domains,
        open_doc_path=open_doc,
        model="claude-sonnet-4-6",
    )
    return ChatSession(
        config=config,
        llm=fake,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        vault_root=vault,
        thread_id=thread_id,
        persistence=persistence,
        autotitler=autotitler,
        vault_writer=writer,
    )


async def _collect(events: AsyncIterator[ChatEvent]) -> list[ChatEvent]:
    out: list[ChatEvent] = []
    async for ev in events:
        out.append(ev)
    return out


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  OK  {msg}")


async def gate_1_ask_mode(vault: Path) -> None:
    print("[gate 1] Ask mode with tool call")
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "karpathy"})]
    )
    fake.queue("The LLM wiki pattern is described in [[karpathy]].")

    session = _build_session(
        vault, fake=fake, mode=ChatMode.ASK, thread_id="2026-04-15-draft-ask001"
    )
    events = await _collect(session.turn("What is the LLM wiki pattern?"))

    kinds = [e.kind for e in events]
    _check(ChatEventKind.TOOL_CALL in kinds, "TOOL_CALL event emitted")
    _check(
        any(
            e.kind == ChatEventKind.TOOL_CALL and e.data.get("name") == "search_vault"
            for e in events
        ),
        "search_vault tool called",
    )
    _check(ChatEventKind.DELTA in kinds, "DELTA events emitted for answer text")
    _check(
        ChatEventKind.PATCH_PROPOSED not in kinds,
        "Ask mode does NOT emit PATCH_PROPOSED",
    )
    assert session.state_db is not None
    session.state_db.close()


async def gate_2_brainstorm_propose_note(vault: Path) -> None:
    print("[gate 2] Brainstorm mode with propose_note")
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="propose_note",
                input={
                    "path": "research/sources/new-idea.md",
                    "content": "# new idea\n\nbody",
                    "reason": "brainstorm captured this",
                },
            )
        ]
    )
    fake.queue("Staged for you.")

    session = _build_session(
        vault, fake=fake, mode=ChatMode.BRAINSTORM, thread_id="2026-04-15-draft-bs0001"
    )
    events = await _collect(session.turn("Let's capture this idea."))

    kinds = [e.kind for e in events]
    _check(ChatEventKind.PATCH_PROPOSED in kinds, "PATCH_PROPOSED event emitted")
    _check(
        not (vault / "research" / "sources" / "new-idea.md").exists(),
        "vault file at proposed path does NOT exist",
    )
    pending = PendingPatchStore(vault / ".brain" / "pending")
    entries = pending.list()
    _check(
        any(e.tool == "propose_note" for e in entries),
        "pending queue has a propose_note entry",
    )
    assert session.state_db is not None
    session.state_db.close()


async def gate_3_draft_edit_open_doc(vault: Path) -> None:
    print("[gate 3] Draft mode with edit_open_doc")
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="edit_open_doc",
                input={
                    "old": "The original unique sentence about the draft.",
                    "new": "The rewritten sentence about the draft.",
                    "reason": "clarify tone",
                },
            )
        ]
    )
    fake.queue("Staged edit.")

    session = _build_session(
        vault,
        fake=fake,
        mode=ChatMode.DRAFT,
        open_doc=Path("research/sources/drafting.md"),
        thread_id="2026-04-15-draft-df0001",
    )
    events = await _collect(session.turn("Tighten the first paragraph."))

    kinds = [e.kind for e in events]
    _check(ChatEventKind.PATCH_PROPOSED in kinds, "PATCH_PROPOSED event emitted")
    drafting_body = (vault / "research" / "sources" / "drafting.md").read_text(encoding="utf-8")
    _check(
        "The original unique sentence about the draft." in drafting_body,
        "open doc still contains ORIGINAL text (no vault write)",
    )
    _check(
        "The rewritten sentence about the draft." not in drafting_body,
        "open doc does NOT contain NEW text",
    )
    assert session.state_db is not None
    session.state_db.close()


async def gate_4_thread_persistence(vault: Path) -> None:
    print("[gate 4] Thread persistence")
    chats_dir = vault / "research" / "chats"
    thread_files = list(chats_dir.glob("*.md"))
    _check(
        len(thread_files) >= 3,
        f"chats/ has at least 3 thread files (found {len(thread_files)})",
    )
    for f in thread_files:
        body = f.read_text(encoding="utf-8")
        _check("---" in body, f"{f.name} has frontmatter")
        _check("mode:" in body, f"{f.name} frontmatter has mode")
        _check("scope:" in body, f"{f.name} frontmatter has scope")
        _check("## User" in body, f"{f.name} has User section")
        _check("## Assistant" in body, f"{f.name} has Assistant section")


async def gate_5_auto_title(vault: Path) -> None:
    print("[gate 5] Auto-title after turn 2")
    fake = FakeLLMProvider()
    fake.queue("first answer")
    fake.queue("second answer")
    # AutoTitler call — derives slug deterministically from title via regex.
    fake.queue('{"title": "karpathy llm wiki"}')

    session = _build_session(
        vault, fake=fake, mode=ChatMode.ASK, thread_id="2026-04-15-draft-at0001"
    )
    await _collect(session.turn("q1"))
    old_thread_id = session.thread_id
    old_path = vault / "research" / "chats" / f"{old_thread_id}.md"
    _check(old_path.exists(), "draft thread file exists after turn 1")

    await _collect(session.turn("q2"))
    _check(session.thread_id != old_thread_id, "thread_id changed after turn 2")
    _check(
        "karpathy-llm-wiki" in session.thread_id,
        "new thread_id contains auto-title slug",
    )
    _check("draft" not in session.thread_id, "new thread_id does NOT contain 'draft'")
    _check(not old_path.exists(), "old thread file was renamed away")
    new_path = vault / "research" / "chats" / f"{session.thread_id}.md"
    _check(new_path.exists(), "new thread file exists at renamed path")

    assert session.state_db is not None
    rows = session.state_db.exec("SELECT thread_id FROM chat_threads").fetchall()
    ids = [r[0] for r in rows]
    _check(session.thread_id in ids, "state.sqlite chat_threads has new thread_id row")
    _check(old_thread_id not in ids, "state.sqlite no longer has draft thread row")
    session.state_db.close()


async def gate_6_idempotency(vault: Path) -> None:
    print("[gate 6] Idempotency")
    chats_before = sorted((vault / "research" / "chats").glob("*.md"))

    db1 = StateDB.open(vault / ".brain" / "state.sqlite")
    rows_before = db1.exec("SELECT thread_id FROM chat_threads").fetchall()
    db1.close()

    db2 = StateDB.open(vault / ".brain" / "state.sqlite")
    rows_after = db2.exec("SELECT thread_id FROM chat_threads").fetchall()
    db2.close()
    _check(
        rows_before == rows_after,
        "re-opening StateDB yields identical chat_threads rows",
    )

    chats_after = sorted((vault / "research" / "chats").glob("*.md"))
    _check(chats_before == chats_after, "no thread files added or removed on re-open")


async def gate_7_scope_guard(vault: Path) -> None:
    print("[gate 7] Scope guard rejects personal/ in research session")
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[
            ToolUse(
                id="tu_1",
                name="read_note",
                input={"path": "personal/sources/secret.md"},
            )
        ]
    )
    fake.queue("handled")

    session = _build_session(
        vault, fake=fake, mode=ChatMode.ASK, thread_id="2026-04-15-draft-sg0001"
    )
    events = await _collect(session.turn("Try to read a secret note."))

    tool_results = [e for e in events if e.kind == ChatEventKind.TOOL_RESULT]
    _check(len(tool_results) == 1, "one TOOL_RESULT event emitted")
    _check(tool_results[0].data.get("error") is True, "TOOL_RESULT flagged as error")
    text_lc = str(tool_results[0].data.get("text", "")).lower()
    _check(
        "personal" in text_lc or "scope" in text_lc,
        "error message mentions personal/scope",
    )
    assert session.state_db is not None
    session.state_db.close()


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "brain"
        _scaffold_vault(vault)

        await gate_1_ask_mode(vault)
        await gate_2_brainstorm_propose_note(vault)
        await gate_3_draft_edit_open_doc(vault)
        await gate_4_thread_persistence(vault)
        await gate_5_auto_title(vault)
        await gate_6_idempotency(vault)
        await gate_7_scope_guard(vault)

        print()
        print("PLAN 03 DEMO OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
