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

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, cast

from brain_core.chat.context import ContextCompiler
from brain_core.chat.modes import MODES
from brain_core.chat.persistence import ThreadPersistence
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

    @property
    def turn_count(self) -> int:
        """Count of USER turns in the underlying ``ChatSession``.

        Surfaced in the WS ``thread_loaded`` handshake frame so a
        reconnecting client knows how many user messages already live in
        the thread. ``0`` when the session hasn't been built yet (the
        route handler calls ``_ensure_session`` eagerly so the count is
        accurate before the frame goes out).
        """
        if self._session is None:
            return 0
        return self._session.turn_count

    def _ensure_session(self) -> ChatSession:
        """Build the ``ChatSession`` on first use; return the cached one after.

        Plan 05 Task 21: on first construction, we check whether the
        thread's canonical markdown file exists in the vault
        (``<domain>/chats/<thread_id>.md``). If it does, we rehydrate
        turns via ``ThreadPersistence.read(path)`` and pass them into
        ``ChatSession(initial_turns=...)`` so the compiled context
        preserves history across reconnects.

        ``ThreadPersistence`` is also injected so ``ChatSession.turn``
        persists after each successful turn (belt-and-braces; the WS
        ``finally`` block also calls ``runner.persist()`` to cover
        mid-turn unclean disconnects).

        Uses ``ChatMode(self.mode)`` to coerce the string mode (which
        arrives from the wire as ``"ask" | "brainstorm" | "draft"``)
        into the ``StrEnum``. Invalid values raise ``ValueError`` here,
        which ``run_turn`` catches and surfaces as an ``ErrorEvent``.

        If the stored thread's mode differs from ``self.mode`` (e.g.,
        the file says ``brainstorm`` but the client connected with
        ``ask``), the CONFIG mode wins — the client-supplied mode is
        treated as an implicit switch-on-reconnect. That matches
        Plan 03's philosophy (mode lives on the thread; the client is
        just asserting it). A future Plan 07 UX refinement can surface
        the drift before accepting a turn, but Plan 05 backend takes
        the client at its word.
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

        # Build ThreadPersistence so ChatSession.turn persists each turn.
        # state_db is required by ThreadPersistence for chat_threads
        # upserts; writer is required for the atomic VaultWriter patch.
        persistence: ThreadPersistence | None = None
        initial_turns = None
        if self.ctx.tool_ctx.state_db is not None and self.ctx.tool_ctx.writer is not None:
            persistence = ThreadPersistence(
                vault_root=self.ctx.vault_root,
                writer=self.ctx.tool_ctx.writer,
                db=self.ctx.tool_ctx.state_db,
            )
            thread_path = self.ctx.vault_root / persistence.thread_path(self.thread_id, config)
            if thread_path.exists():
                try:
                    loaded = persistence.read(thread_path)
                    initial_turns = loaded.turns
                except Exception:
                    # A malformed on-disk thread must not block a new
                    # connection — log and fall through to fresh session.
                    # Plan 07 UX can surface a "thread file damaged"
                    # warning via a separate channel.
                    logger.exception(
                        "failed to load thread_id=%s; starting fresh",
                        self.thread_id,
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
            persistence=persistence,
            initial_turns=initial_turns,
            # autotitler / vault_writer: deferred — autotitle is a
            # draft-mode concern that Plan 07 wires end-to-end (requires
            # a rename + WS thread_id update protocol).
        )
        return self._session

    async def persist(self) -> None:
        """Flush the current session to vault + state.sqlite.

        Belt-and-braces for unclean disconnect: ``ChatSession.turn``
        already persists at the end of every successful turn. This path
        covers the case where the WS closes BETWEEN turns — no-op —
        and documents the contract so the WS ``finally`` block can call
        it unconditionally.

        Never raises. A failure here must not propagate into the WS
        close path (which is already closing). Logged and swallowed.

        No-op when:
        - the session was never built (``_ensure_session`` not called),
        - there are no turns to persist (fresh thread + no messages),
        - ``ThreadPersistence`` is missing (no state_db or writer).
        """
        if self._session is None:
            return
        if not self._session._turns:
            # No turns to write — would create an empty thread file
            # otherwise, which is semantically wrong (a thread with no
            # content shouldn't appear in the list_chats tool output).
            return
        persistence = self._session.persistence
        if persistence is None:
            return
        try:
            persistence.write(
                thread_id=self._session.thread_id,
                config=self._session.config,
                turns=self._session._turns,
            )
        except Exception:
            logger.exception("persist failed for thread_id=%s", self.thread_id)

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

        session = self._ensure_session()
        # Plan 05 Task 21: hold the async generator explicitly so we can
        # ``aclose()`` it deterministically in the ``finally`` below.
        # Without this, a client crash mid-stream (send_json raises,
        # ``async for`` exits without ever calling ``athrow`` on the
        # generator) leaves ``ChatSession.turn``'s ``finally`` block
        # unexecuted until asyncio's async-gen-finalize hook eventually
        # schedules it — which can be AFTER ``runner.persist()`` runs in
        # the route's ``finally``, so ``_turns`` is still empty at
        # persist time. Explicit aclose forces the finally to run before
        # this function returns, guaranteeing ``_turns`` is populated
        # by the time persist() is called.
        # ``session.turn`` is declared ``AsyncIterator[ChatEvent]`` for
        # consumer ergonomics (``async for ev in session.turn(...)``),
        # but at runtime it's always an ``AsyncGenerator`` (async-def
        # with yield). We need ``.aclose`` here, which only the richer
        # protocol exposes — the cast is safe because ``ChatSession``
        # never returns anything else.
        turn_gen = cast(AsyncGenerator[ChatEvent, None], session.turn(content))
        try:
            async for chat_event in turn_gen:
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
            # best-effort notify — if the socket is gone (the usual
            # trigger for Exception here is a closed socket), the inner
            # send_json raises too; swallow it so we fall through to
            # aclose+persist rather than escaping with a double fault.
            with contextlib.suppress(Exception):
                await websocket.send_json(
                    serialize_server_event(
                        ErrorEvent(code="internal", message=str(exc), recoverable=True)
                    )
                )
        finally:
            # Deterministically flush ``ChatSession.turn``'s finally
            # block. ``aclose()`` throws ``GeneratorExit`` at the suspended
            # yield inside the generator, which triggers the try/finally
            # that appends USER + ASSISTANT turns to ``_turns``. Without
            # this explicit aclose, asyncio's async-gen finalizer may
            # run AFTER the route's finally-block persist(), in which
            # case ``_turns`` is still empty when we write.
            #
            # We wrap in ``asyncio.shield`` because ``run_turn`` may be
            # running under a ``CancelledError`` unwind (the route's
            # ``finally`` cancels the turn_task on WS disconnect). A
            # plain ``await turn_gen.aclose()`` under active cancellation
            # can be interrupted before the generator's finally executes,
            # leaving ``_turns`` empty. ``shield`` detaches aclose from
            # the outer cancellation so it runs to completion.
            # ``aclose`` is idempotent — calling it on an already-closed
            # generator is a no-op.
            try:
                await asyncio.shield(turn_gen.aclose())
            except asyncio.CancelledError:
                # Re-raise the outer cancel AFTER aclose completed.
                # The shield propagates CancelledError to the outer
                # awaiter without cancelling the shielded task. We let
                # the cancel continue to unwind the runner normally.
                raise
            except Exception:
                # A misbehaving finally inside ChatSession.turn should
                # not escape the runner; log + swallow.
                logger.exception("turn_gen.aclose raised")


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
