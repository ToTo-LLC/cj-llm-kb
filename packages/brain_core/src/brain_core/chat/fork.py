"""Fork a chat thread from turn N into a new thread.

Plan 07 Task 5 per pre-flight decision D3a. Three carry modes:

* ``full`` — copy turns 0..turn_index verbatim into ``initial_turns``
  (the Plan 05 Task 21a addition to ``ChatSession.__init__``).
* ``none`` — start empty; new thread only inherits mode + scope.
* ``summary`` — Haiku-cheap prose summary of prior turns, prepended
  as a single ``SYSTEM`` entry.

The returned ``ChatSession`` is not auto-persisted: the caller flushes
the new thread when ready (typically after the first turn runs, via
``ChatSession.turn`` which calls ``persistence.write`` internally).

The ``brain_api`` tool wrapper (``brain_fork_thread``) lands in the
Plan 07 Task 25 sweep; this module is the ``brain_core`` primitive.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from brain_core.chat.context import ContextCompiler
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.cost.ledger import CostLedger
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter

# Haiku is the cheapest Anthropic model; the ``summary`` carry mode
# compresses prior turns into a single SYSTEM entry for context. The
# larger turn model is not worth the spend for a one-off prose summary.
_SUMMARY_MODEL = "claude-haiku-4-5-20251001"

_SUMMARY_SYSTEM = (
    "Summarize the chat transcript in ~4 sentences, preserving factual "
    "claims and the open question the user was working on."
)


def _new_thread_id(title_hint: str | None = None) -> str:
    """Generate a fresh kebab-case thread_id.

    Matches the WS route's ``^[a-z0-9][a-z0-9-]{0,63}$`` regex: a
    ``YYYY-MM-DD`` prefix + optional slug + 6-char hex suffix. Non-
    alphanumerics in the hint collapse to a single ``-``; leading /
    trailing / doubled dashes are trimmed so the result passes the
    regex. Falls back to a date + hex-only id when no hint given.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    hex_suffix = uuid.uuid4().hex[:6]
    if title_hint:
        raw = "".join(c.lower() if c.isalnum() else "-" for c in title_hint)
        # Collapse runs of dashes and trim leading / trailing.
        while "--" in raw:
            raw = raw.replace("--", "-")
        slug = raw.strip("-")[:32]
        if slug:
            return f"{today}-{slug}-{hex_suffix}"
    return f"{today}-{hex_suffix}"


async def summarize_turns(
    turns: list[ChatTurn],
    llm: LLMProvider,
    *,
    model: str = _SUMMARY_MODEL,
) -> str:
    """Haiku-cheap prose summary of the given chat turns.

    Returns the raw LLM text (typically ~4 sentences). Caller decides
    how to wrap it — ``fork_from`` prepends it as a single ``SYSTEM``
    turn in the new session's initial history.
    """
    transcript = "\n\n".join(f"{t.role.value}: {t.content}" for t in turns)
    response = await llm.complete(
        LLMRequest(
            model=model,
            system=_SUMMARY_SYSTEM,
            messages=[LLMMessage(role="user", content=transcript)],
            max_tokens=600,
            temperature=0.2,
        )
    )
    return response.content.strip()


async def fork_from(
    source_thread_id: str,
    turn_index: int,
    *,
    vault_root: Path,
    llm: LLMProvider,
    compiler: ContextCompiler,
    registry: ToolRegistry,
    persistence: ThreadPersistence,
    retrieval: BM25VaultIndex | None = None,
    pending_store: PendingPatchStore | None = None,
    state_db: StateDB | None = None,
    vault_writer: VaultWriter | None = None,
    cost_ledger: CostLedger | None = None,
    carry: Literal["full", "none", "summary"] = "full",
    mode: ChatMode | None = None,
    title_hint: str | None = None,
    new_thread_id: str | None = None,
) -> ChatSession:
    """Fork a source thread at ``turn_index`` into a fresh ``ChatSession``.

    The source is loaded from disk via ``ThreadPersistence.read``. The
    new session inherits the source's ``ChatSessionConfig`` (mode,
    domains, model) unless ``mode`` is passed explicitly. Turns 0..
    ``turn_index`` (inclusive) from the source drive the new session's
    ``initial_turns`` per the ``carry`` rule.

    Raises ``IndexError`` when ``turn_index`` is negative or beyond the
    source's last turn. Raises ``FileNotFoundError`` when the source
    thread file is missing.

    The returned ``ChatSession`` is NOT persisted: the caller's first
    ``session.turn(...)`` invocation persists it via the already-wired
    ``ThreadPersistence``.
    """
    source_config = ChatSessionConfig(
        mode=mode or ChatMode.ASK,
        domains=("research",),
    )
    # Try both common domain locations — we don't know the source's
    # domain up-front, so walk each allowed domain's chats/ dir. In
    # practice the source's ``ChatSessionConfig`` was written with its
    # original domain; the file we read carries the real value in its
    # frontmatter, which ``persistence.read`` uses to reconstruct
    # ``ChatSessionConfig.domains``. The path lookup below is solely
    # about finding the file on disk.
    source_path = _find_source_thread_file(
        vault_root=vault_root,
        thread_id=source_thread_id,
        probe_config=source_config,
        persistence=persistence,
    )
    loaded = persistence.read(source_path)

    if turn_index < 0 or turn_index >= len(loaded.turns):
        raise IndexError(
            f"turn_index {turn_index} out of range for thread "
            f"{source_thread_id!r} with {len(loaded.turns)} turns"
        )

    turns_to_carry = list(loaded.turns[: turn_index + 1])

    initial_turns: list[ChatTurn]
    if carry == "none":
        initial_turns = []
    elif carry == "full":
        initial_turns = turns_to_carry
    elif carry == "summary":
        summary_text = await summarize_turns(turns_to_carry, llm)
        initial_turns = [
            ChatTurn(
                role=TurnRole.SYSTEM,
                content=summary_text,
                created_at=datetime.now(UTC),
            )
        ]
    else:
        raise ValueError(f"unknown carry mode: {carry!r}")

    effective_mode = mode if mode is not None else loaded.config.mode
    new_config = loaded.config.model_copy(update={"mode": effective_mode})
    thread_id = new_thread_id or _new_thread_id(title_hint)

    return ChatSession(
        config=new_config,
        llm=llm,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending_store,
        state_db=state_db,
        vault_root=vault_root,
        thread_id=thread_id,
        persistence=persistence,
        vault_writer=vault_writer,
        cost_ledger=cost_ledger,
        initial_turns=initial_turns,
    )


def _find_source_thread_file(
    *,
    vault_root: Path,
    thread_id: str,
    probe_config: ChatSessionConfig,
    persistence: ThreadPersistence,
) -> Path:
    """Locate the source thread's file on disk.

    ``ThreadPersistence.thread_path`` derives the directory from
    ``config.domains[0]``; we probe every domain directory under the
    vault root that contains a ``chats/`` dir. The caller's
    ``probe_config`` is a placeholder for the default domain — we walk
    the filesystem and pick the first match.
    """
    for domain_dir in vault_root.iterdir():
        if not domain_dir.is_dir():
            continue
        candidate = domain_dir / "chats" / f"{thread_id}.md"
        if candidate.exists():
            return candidate
    # Fallback: honour the probe_config path so the FileNotFoundError
    # message points at the canonical location rather than a vague
    # "vault".
    fallback = vault_root / persistence.thread_path(thread_id, probe_config)
    raise FileNotFoundError(f"thread file not found: {fallback}")
