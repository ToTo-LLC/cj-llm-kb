"""Build a ChatSession from CLI options. Test-injection point for FakeLLMProvider.

Task 20 uses this as the single place where a real ChatSession is stood up for
CLI use. Tests override `llm` to inject a FakeLLMProvider; production passes
None so an AnthropicProvider is built from environment config.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
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
from brain_core.chat.types import ChatMode, ChatSessionConfig
from brain_core.llm.provider import LLMProvider
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


def _new_draft_thread_id() -> str:
    """Generate a fresh draft thread id of the form ``YYYY-MM-DD-draft-<6hex>``."""
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    suffix = uuid.uuid4().hex[:6]
    return f"{date}-draft-{suffix}"


def _register_all_tools(registry: ToolRegistry) -> None:
    """Register every production tool. Mode filtering happens inside ChatSession."""
    registry.register(SearchVaultTool())
    registry.register(ReadNoteTool())
    registry.register(ListIndexTool())
    registry.register(ListChatsTool())
    registry.register(ProposeNoteTool())
    registry.register(EditOpenDocTool())


def _build_anthropic_provider() -> LLMProvider:
    """Build a real AnthropicProvider from the ANTHROPIC_API_KEY env var."""
    from brain_core.llm.providers.anthropic import AnthropicProvider

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Set it in your shell or .env file before running `brain chat`."
        )
    return AnthropicProvider(api_key=api_key)


def build_session(
    *,
    mode: ChatMode,
    domains: tuple[str, ...],
    open_doc: Path | None,
    model: str,
    vault_root: Path,
    llm: LLMProvider | None = None,
    thread_id: str | None = None,
) -> ChatSession:
    """Stand up a fully-wired ChatSession. ``llm=None`` builds an AnthropicProvider."""
    (vault_root / ".brain").mkdir(parents=True, exist_ok=True)
    state_db = StateDB.open(vault_root / ".brain" / "state.sqlite")
    writer = VaultWriter(vault_root=vault_root)
    pending = PendingPatchStore(vault_root / ".brain" / "pending")
    retrieval = BM25VaultIndex(vault_root, state_db)
    retrieval.build(domains)

    mode_prompt_text = MODES[mode].prompt_text
    compiler = ContextCompiler(vault_root, mode_prompt_text)
    persistence = ThreadPersistence(vault_root, writer, state_db)

    registry = ToolRegistry()
    _register_all_tools(registry)

    llm_provider: LLMProvider = llm if llm is not None else _build_anthropic_provider()

    config = ChatSessionConfig(
        mode=mode,
        domains=domains,
        open_doc_path=open_doc,
        model=model,
    )

    autotitler = AutoTitler(llm_provider)

    return ChatSession(
        config=config,
        llm=llm_provider,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=state_db,
        vault_root=vault_root,
        thread_id=thread_id or _new_draft_thread_id(),
        persistence=persistence,
        autotitler=autotitler,
        vault_writer=writer,
    )
