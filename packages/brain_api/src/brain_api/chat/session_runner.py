"""Bridge a ``brain_core.chat.ChatSession`` to the ``brain_api`` WS events.

Plan 05 Task 19. One runner per WS connection — never reused across
connections. A single ``ChatSession`` instance is lazy-built on the first
turn and reused for subsequent turns on the same WS (so in-memory turn
history and read-note context survive across turns, which the context
compiler relies on).

Plan sketch vs. reality: the plan's ``SessionRunner`` assumed
``ChatSession.run_turn(...) -> AsyncIterator`` and separate per-kind
event classes (``DeltaChatEvent`` et al.). Plan 03 actually shipped:

* ``ChatSession.turn(user_message) -> AsyncIterator[ChatEvent]`` — the
  method name is ``turn``, not ``run_turn``.
* A **single** ``ChatEvent`` Pydantic model with ``kind: ChatEventKind``
  and ``data: dict[str, Any]``. There are no per-kind classes, so we
  dispatch on ``event.kind`` and pull fields out of ``event.data`` by
  string key.
* Constructor takes ``config: ChatSessionConfig`` (carrying ``mode``,
  ``domains``, ``open_doc_path``) plus a pre-built
  ``ContextCompiler`` and a populated ``ToolRegistry`` — not the flat
  kwargs the plan's sketch listed (``allowed_domains=``, ``mode=``,
  ``writer=``, etc.).
* No ``cost_ledger`` on ``ChatSession`` in Task 17/18 — the session
  emits ``COST_UPDATE`` events with ``turn_cost_usd=0.0`` placeholders.
* No ``.title`` attribute; auto-titling mutates ``thread_id`` instead,
  via a vault-side rename. Task 19 passes ``title=None`` on
  ``turn_end`` and defers surfacing the renamed thread_id to Task 21.

The adapter below mirrors the real API. Case B (callback) was
irrelevant; Plan 03 is cleanly Case A.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from brain_core.chat.context import ContextCompiler
from brain_core.chat.modes import MODES
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.edit_open_doc import EditOpenDocTool
from brain_core.chat.tools.list_chats import ListChatsTool
from brain_core.chat.tools.list_index import ListIndexTool
from brain_core.chat.tools.propose_note import ProposeNoteTool
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import (
    ChatEvent,
    ChatEventKind,
    ChatMode,
    ChatSessionConfig,
)

from brain_api.chat.events import (
    CostUpdateEvent,
    DeltaEvent,
    ErrorEvent,
    PatchProposedEvent,
    ServerEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEndEvent,
    TurnStartEvent,
    serialize_server_event,
)

if TYPE_CHECKING:
    from fastapi import WebSocket

    from brain_api.context import AppContext

logger = logging.getLogger("brain_api.chat.session_runner")


def _build_registry() -> ToolRegistry:
    """Build a ToolRegistry with the six Plan 03 chat tools registered.

    ``ChatSession`` filters this down per-mode internally via
    ``_build_effective_registry`` — e.g., Ask mode drops the writer
    tools. We always register all six; the session applies the mode
    allowlist.
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


class SessionRunner:
    """One ``ChatSession`` bound to one WS connection.

    Not thread-safe. Not reused across WS connections — each WS
    ``accept()`` constructs a fresh runner. The underlying
    ``ChatSession`` is built lazily on the first turn (Task 21 will
    swap this for a ``load_or_create`` path that reads prior turns from
    the vault transcript).
    """

    def __init__(self, ctx: AppContext, thread_id: str, mode: str = "ask") -> None:
        self.ctx = ctx
        self.thread_id = thread_id
        self.mode = mode
        # Task 20: ``open_doc`` is stashed on the runner when the client
        # sends a ``set_open_doc`` frame. It's purely metadata for now —
        # Task 21+ will thread it into ``ChatSessionConfig.open_doc_path``
        # so the context compiler can inject the focused note's contents
        # into the prompt. Stored here (not on the ChatSession) because
        # the session is lazy-built; the open-doc path can be set before
        # the first turn, so the stash must live on the runner.
        self.open_doc: str | None = None
        self._turn_number = 0
        self._session: ChatSession | None = None

    @property
    def turn_number(self) -> int:
        """Read-only access to the current 1-indexed turn counter.

        The route-handler cancel path emits ``CancelledEvent(turn_number=
        runner.turn_number)`` after awaiting the cancelled task — the
        event carries the turn the cancel landed in, which is the same
        turn ``run_turn`` incremented on entry. Exposed as a property
        (not a public field) because mutation is strictly internal to
        ``run_turn``.
        """
        return self._turn_number

    def _ensure_session(self) -> ChatSession:
        """Build the ``ChatSession`` on first use; return the cached one after.

        Uses ``ChatMode(self.mode)`` to coerce the string mode (which
        arrives from the wire as ``"ask" | "brainstorm" | "draft"``)
        into the ``StrEnum``. Invalid values raise ``ValueError`` here,
        which ``run_turn`` catches and surfaces as an ``ErrorEvent``.
        """
        if self._session is not None:
            return self._session

        mode_enum = ChatMode(self.mode)
        compiler = ContextCompiler(
            vault_root=self.ctx.vault_root,
            mode_prompt=MODES[mode_enum].prompt_text,
        )
        config = ChatSessionConfig(
            mode=mode_enum,
            domains=self.ctx.allowed_domains,
        )
        self._session = ChatSession(
            config=config,
            llm=self.ctx.tool_ctx.llm,
            compiler=compiler,
            registry=_build_registry(),
            retrieval=self.ctx.tool_ctx.retrieval,
            pending_store=self.ctx.tool_ctx.pending_store,
            state_db=self.ctx.tool_ctx.state_db,
            vault_root=self.ctx.vault_root,
            thread_id=self.thread_id,
            # persistence / autotitler / vault_writer: deferred to
            # Task 21, which wires persistence end-to-end.
        )
        return self._session

    async def run_turn(self, content: str, websocket: WebSocket) -> None:
        """Run one turn; stream events to the websocket.

        Emits, in order:

        * ``turn_start`` — always first, carries the 1-indexed
          ``turn_number`` (used by the client to correlate subsequent
          deltas / tool_result / turn_end frames).
        * ``delta`` / ``tool_call`` / ``tool_result`` / ``cost_update``
          / ``patch_proposed`` — as ``ChatSession.turn`` yields them.
        * ``turn_end`` on success, OR ``error`` on any exception.

        The ``turn_end`` + ``error`` branches BOTH keep the socket open
        (per CLAUDE.md principle #9 "plain English with a next action"
        and Plan 05 Group 6's "errors are recoverable by default"
        contract). A terminal close is the caller's job, not the
        runner's.
        """
        self._turn_number += 1
        await websocket.send_json(
            serialize_server_event(TurnStartEvent(turn_number=self._turn_number))
        )

        try:
            session = self._ensure_session()
            async for chat_event in session.turn(content):
                ws_event = _convert_chat_event(chat_event)
                if ws_event is not None:
                    await websocket.send_json(serialize_server_event(ws_event))
                # ChatSession's own internal TURN_END event is consumed
                # here (converted to None by _convert_chat_event) — the
                # WS turn_end frame is emitted once, below, after the
                # iterator drains. This keeps the WS turn_end frame the
                # single authoritative "turn is over" signal even if
                # ChatSession grows more post-turn events later.

            await websocket.send_json(
                serialize_server_event(TurnEndEvent(turn_number=self._turn_number, title=None))
            )
        except Exception as exc:
            # logger.exception emits a full traceback to the log for
            # debugging; the WS frame stays plain-English per Principle
            # #9. Note: we do NOT log the user's message content (that
            # would be a prompt-body log, which CLAUDE.md forbids by
            # default).
            logger.exception(
                "Chat turn failed: thread=%s turn=%d",
                self.thread_id,
                self._turn_number,
            )
            await websocket.send_json(
                serialize_server_event(
                    ErrorEvent(code="internal", message=str(exc), recoverable=True)
                )
            )


def _convert_chat_event(e: ChatEvent) -> ServerEvent | None:
    """Map ``brain_core.chat.types.ChatEvent`` → ``brain_api`` ``ServerEvent``.

    Returns ``None`` for kinds that have no WS counterpart in the Task
    18 wire contract (``TURN_END`` is emitted by the session loop but
    the WS layer owns the authoritative ``turn_end`` frame with
    ``turn_number``; ``ERROR`` is surfaced via the ``run_turn``
    exception path, not forwarded from the session).

    The ``ChatEvent`` shape is a single Pydantic model with ``kind``
    (a ``ChatEventKind`` enum) and ``data`` (an untyped ``dict``).
    Per the Plan 03 session loop (``brain_core/chat/session.py``),
    every kind populates ``data`` with a known set of keys:

    * ``DELTA``: ``{"text": str}``
    * ``TOOL_CALL``: ``{"id": str, "name": str, "args": dict}``
    * ``TOOL_RESULT``: ``{"id": str, "name": str, "text": str, "error"?: bool}``
    * ``COST_UPDATE``: ``{"turn_cost_usd": float, "session_cost_usd": float}``
    * ``PATCH_PROPOSED``: ``{"patch_id": str, "target_path": str, "tool": str}``

    Field-name adaptations below (the WS contract and the core session
    chose different names for the same concept):

    * TOOL_CALL: core ``name`` / ``args`` → WS ``tool`` / ``arguments``
    * TOOL_RESULT: core emits ``text`` (the already-stringified tool
      output); WS contract carries ``data: dict``. We wrap the text in
      ``{"text": ...}`` (and forward ``error`` if present) to satisfy
      the typed schema without losing the tool's actual output.
    * COST_UPDATE: core doesn't emit token counts in Task 17/18 (no
      cost ledger plumbing yet), so we pass ``tokens_in=0``,
      ``tokens_out=0``, ``cost_usd=turn_cost_usd``,
      ``cumulative_usd=session_cost_usd``. Task 21+ plugs real numbers.
    * PATCH_PROPOSED: core emits ``tool`` (the tool that proposed the
      patch); WS contract carries a human-readable ``reason``. We pass
      ``reason=f"proposed by {tool_name}"`` as a stopgap until Plan 03
      teaches tools to emit a structured reason.
    """
    kind = e.kind
    data = e.data

    if kind is ChatEventKind.DELTA:
        return DeltaEvent(text=str(data.get("text", "")))

    if kind is ChatEventKind.TOOL_CALL:
        return ToolCallEvent(
            id=str(data["id"]),
            tool=str(data["name"]),
            arguments=dict(data.get("args", {})),
        )

    if kind is ChatEventKind.TOOL_RESULT:
        wrapped: dict[str, object] = {"text": str(data.get("text", ""))}
        if data.get("error"):
            wrapped["error"] = True
        return ToolResultEvent(id=str(data["id"]), data=wrapped)

    if kind is ChatEventKind.COST_UPDATE:
        return CostUpdateEvent(
            tokens_in=0,
            tokens_out=0,
            cost_usd=float(data.get("turn_cost_usd", 0.0)),
            cumulative_usd=float(data.get("session_cost_usd", 0.0)),
        )

    if kind is ChatEventKind.PATCH_PROPOSED:
        tool_name = str(data.get("tool", "unknown"))
        return PatchProposedEvent(
            patch_id=str(data["patch_id"]),
            target_path=str(data["target_path"]),
            reason=f"proposed by {tool_name}",
        )

    # TURN_END and ERROR: WS layer owns these frames (turn_end with
    # the WS-side turn_number, error from the exception path), so we
    # drop the core-side versions to avoid double-emitting.
    return None
