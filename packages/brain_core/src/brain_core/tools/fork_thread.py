"""brain_fork_thread — fork a chat thread into a new thread.

Thin wrapper around :func:`brain_core.chat.fork.fork_from` (Plan 07 Task 5).
Builds the :class:`ThreadPersistence`, :class:`ContextCompiler`, and
:class:`ToolRegistry` that ``fork_from`` needs from the primitives carried on
``ToolContext`` (state_db, writer, retrieval, llm). Returns the newly-minted
``thread_id`` so the Plan 07 Task 20 Fork dialog can navigate to it.

The returned :class:`ChatSession` is NOT persisted here — ``fork_from``'s
contract is that the caller's first ``session.turn(...)`` writes the thread
to disk. The Fork dialog UX calls ``brain_fork_thread`` (to reserve the id
and stage carry turns in memory), then opens a fresh WS connection to the
new ``thread_id``; the next user turn persists the thread file.

Unlike the ``summary`` carry mode's Haiku LLM call, ``full`` and ``none``
never touch the LLM, so the rate-limit bucket only charges when carry is
``summary`` — matching the actual spend.
"""

from __future__ import annotations

import sys
from typing import Any, Literal, cast

from brain_core.chat.context import ContextCompiler
from brain_core.chat.fork import fork_from
from brain_core.chat.modes import MODES
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.edit_open_doc import EditOpenDocTool
from brain_core.chat.tools.list_chats import ListChatsTool
from brain_core.chat.tools.list_index import ListIndexTool
from brain_core.chat.tools.propose_note import ProposeNoteTool
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import ChatMode
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_fork_thread"
DESCRIPTION = (
    "Fork a chat thread at a given turn index into a new thread. "
    "Carry modes: 'full' (copy turns verbatim), 'none' (empty), "
    "'summary' (Haiku-cheap prose summary). Returns the new thread_id. "
    "Does NOT persist the new thread — the first turn writes it to disk."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source_thread_id": {
            "type": "string",
            "description": "The thread_id of the source thread to fork from.",
        },
        "turn_index": {
            "type": "integer",
            "minimum": 0,
            "description": "Fork after this turn (0-indexed, inclusive).",
        },
        "carry": {
            "type": "string",
            "enum": ["full", "none", "summary"],
            "description": (
                "How prior turns carry into the new thread. "
                "'full' copies verbatim; 'none' starts empty; "
                "'summary' runs a Haiku summary as one SYSTEM entry."
            ),
        },
        "mode": {
            "type": "string",
            "enum": ["ask", "brainstorm", "draft"],
            "description": "Chat mode for the new thread.",
        },
        "title_hint": {
            "type": ["string", "null"],
            "description": "Optional slug hint embedded in the new thread_id.",
        },
    },
    "required": ["source_thread_id", "turn_index", "carry", "mode"],
}

# Only the 'summary' carry mode hits the LLM — 'full' and 'none' are pure
# in-memory copies. Gate the rate-limit spend accordingly so callers aren't
# charged a Haiku-sized budget for a zero-LLM fork.
_SUMMARY_TOKEN_COST = 1000


def _build_registry() -> ToolRegistry:
    """Build the six-tool chat registry ``fork_from`` passes to ``ChatSession``.

    Mirrors ``brain_api.chat.session_runner._build_registry`` 1:1 so the
    forked session sees the same tool surface as a normally-opened thread.
    """
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
    return registry


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    """Fork ``source_thread_id`` at ``turn_index`` into a new thread.

    Raises:
        FileNotFoundError: source thread file is missing in the vault.
            Mapped to 404 by the brain_api error handlers.
        IndexError: ``turn_index`` is out of range for the source thread.
        ValueError: ``mode`` is not a valid :class:`ChatMode` enum value.
        RateLimitError: rate limit drained (summary carry only).
    """
    carry = cast(Literal["full", "none", "summary"], str(arguments["carry"]))
    if carry == "summary":
        ctx.rate_limiter.check("tokens", cost=_SUMMARY_TOKEN_COST)

    # state_db + writer are required to reconstruct the source thread; without
    # them, fork_from can't read the source file or persist the new one.
    if ctx.state_db is None or ctx.writer is None:
        raise RuntimeError(
            "brain_fork_thread requires state_db + writer on ToolContext"
        )

    mode = ChatMode(str(arguments["mode"]))
    compiler = ContextCompiler(
        vault_root=ctx.vault_root,
        mode_prompt=MODES[mode].prompt_text,
    )
    persistence = ThreadPersistence(
        vault_root=ctx.vault_root,
        writer=ctx.writer,
        db=ctx.state_db,
    )

    title_hint = arguments.get("title_hint")
    title_hint_str = str(title_hint) if title_hint else None

    session = await fork_from(
        source_thread_id=str(arguments["source_thread_id"]),
        turn_index=int(arguments["turn_index"]),
        vault_root=ctx.vault_root,
        llm=ctx.llm,
        compiler=compiler,
        registry=_build_registry(),
        persistence=persistence,
        retrieval=ctx.retrieval,
        pending_store=ctx.pending_store,
        state_db=ctx.state_db,
        vault_writer=ctx.writer,
        cost_ledger=ctx.cost_ledger,
        carry=carry,
        mode=mode,
        title_hint=title_hint_str,
    )

    return ToolResult(
        text=f"forked thread {session.thread_id} from {arguments['source_thread_id']} (carry={carry})",
        data={"new_thread_id": session.thread_id},
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
