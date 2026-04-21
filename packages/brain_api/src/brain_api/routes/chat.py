"""WS /ws/chat/<thread_id> — chat endpoint.

Plan 05 Task 17 landed the bare handshake; Task 18 added typed events +
parsed client messages; Task 19 wired ``SessionRunner`` to dispatch
``turn_start`` synchronously. Task 20 converts the receive loop to
concurrent ``asyncio.wait`` orchestration so the server can process a
``cancel_turn`` message while a turn is actively streaming events.

The endpoint does five things today:

1. Validates ``thread_id`` against a kebab-case regex BEFORE accepting
   the upgrade. Any slash / uppercase / invalid char closes the socket
   with code 1008 (Policy Violation) — the bad input never touches any
   vault I/O or chat state.
2. Authenticates via ``?token=<hex>`` query param (browsers cannot set
   custom headers on the ``WebSocket`` constructor). ``check_ws_token``
   closes with 1008 on mismatch; we return immediately.
3. After accept, emits two typed framing events —
   ``SchemaVersionEvent`` and ``ThreadLoadedEvent`` — then enters a
   concurrent receive/turn loop.
4. The loop awaits two tasks at once: ``recv_task`` (next client frame)
   and ``turn_task`` (an in-flight ``SessionRunner.run_turn``). Whichever
   completes first drives the next state transition. This is what
   lets ``cancel_turn`` arrive mid-turn — under Task 19's inline
   ``await runner.run_turn(...)`` there was no opportunity to read from
   the socket until the turn finished.
5. Dispatches every parsed ``ClientMessage`` per Task 20's state
   machine (see table below). Unknown or malformed messages get a
   typed ``ErrorEvent`` back; the socket stays open so a confused
   client can retry without reconnecting.

Message dispatch (state = idle means turn_task is None or done):

    TurnStartMessage  + idle       -> spawn turn_task; optional mode override
    TurnStartMessage  + active     -> error(invalid_state, "already active")
    CancelTurnMessage + active     -> cancel + await + emit cancelled
    CancelTurnMessage + idle       -> error(invalid_state, "no active turn")
    SwitchModeMessage + idle       -> mutate runner.mode (silent success)
    SwitchModeMessage + active     -> error(invalid_state, "mid-turn switch")
    SetOpenDocMessage + any        -> stash runner.open_doc (silent)

Cancellation mechanics: ``turn_task.cancel()`` injects ``CancelledError``
into the running task. We ``await`` it (catching both ``CancelledError``
and any other exception — ``run_turn`` catches ``Exception`` internally
but ``CancelledError`` bypasses that) to guarantee no further event
frames slip through before we emit ``CancelledEvent``. The cancelled
frame is the single authoritative "turn is over" signal after a cancel.

Middleware (``OriginHostMiddleware``) catches non-loopback Origin on
the upgrade handshake before we even enter this function, so the
endpoint doesn't re-check Origin itself.

Concurrent-connection semantics (Plan 05 Task 25 note for Plan 07):
nothing here prevents TWO WebSockets from opening on the same
``thread_id`` — the route handler is stateless across calls and the
``SessionRunner`` is constructed fresh per connection. Each runner
loads the on-disk thread independently; each writes independently on
disconnect. Interleaved turns from two tabs therefore exhibit
last-writer-wins semantics: the second disconnect's ``persist`` call
overwrites whatever the first disconnect just wrote. Plan 07's UI is
expected to enforce single-tab-per-thread (either by disabling the
"open another tab" affordance or by closing the old WS on new-tab
focus); a backend-side lock would require a global coordination layer
this project has not needed yet.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from brain_api.auth import check_ws_token
from brain_api.chat.events import (
    SCHEMA_VERSION,
    CancelledEvent,
    CancelTurnMessage,
    ErrorEvent,
    SchemaVersionEvent,
    SetOpenDocMessage,
    SwitchModeMessage,
    ThreadLoadedEvent,
    TurnStartMessage,
    parse_client_message,
    serialize_server_event,
)
from brain_api.chat.session_runner import SessionRunner
from brain_api.context import AppContext

router = APIRouter(tags=["chat"])
logger = logging.getLogger("brain_api.chat")

# Kebab-case, digits, 1-64 chars, must start with an alphanumeric. No
# slashes (prevents ``../`` path traversal into the vault); no uppercase
# (Windows filesystems are case-insensitive, keep thread_id collision-
# free); no leading dash (reserved for future namespacing). Task 25 may
# promote this to ``brain_core.ids`` if another subsystem grows a
# thread_id concept.
_THREAD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# Windows reserves these device names as file aliases regardless of
# extension — ``con.md`` / ``prn.md`` / ``com1.md`` all fail to create
# on NTFS. The regex above accepts them (they are valid kebab-case),
# so we filter them explicitly here. The persistence layer writes
# ``<vault>/<domain>/chats/<thread_id>.md`` (see
# ``brain_core.chat.persistence.ThreadPersistence.thread_path``); an
# unfiltered reserved name would pass the handshake but raise
# ``OSError`` at turn-commit time on Windows — silent persist failure,
# no user-visible feedback.
# Reference: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


@router.websocket("/ws/chat/{thread_id}")
async def chat_ws(websocket: WebSocket, thread_id: str) -> None:
    """WebSocket endpoint for chat streaming.

    Task 20: concurrent receive/turn orchestration. The receive loop is
    no longer "await receive_json -> dispatch -> await run_turn"; it's
    "await whichever of {receive_json, turn_task} fires first -> handle
    that completion -> loop".
    """
    # 1. Validate thread_id shape BEFORE accept. Closing without accepting
    # is the cleanest rejection — no leaked state, no half-open socket.
    # Second check rejects Windows reserved device names that slip past
    # the regex — see ``_WINDOWS_RESERVED_NAMES`` for the rationale.
    if not _THREAD_ID_RE.match(thread_id) or thread_id in _WINDOWS_RESERVED_NAMES:
        await websocket.close(code=1008, reason=f"invalid thread_id {thread_id!r}")
        return

    # 2. Resolve AppContext from the mounted app. FastAPI's ``Depends``
    # injection is more limited on WebSocket endpoints than on HTTP, so
    # we reach directly through ``app.state`` — the same stash the HTTP
    # routes read via ``Depends(get_ctx)`` under the hood.
    ctx: AppContext = websocket.app.state.ctx

    # 3. Token check via query param. ``check_ws_token`` closes with
    # 1008 on mismatch and returns False; we bail without further work.
    ok = await check_ws_token(websocket, ctx)
    if not ok:
        return

    # 4. Accept the upgrade.
    await websocket.accept()

    # 5. Build the SessionRunner and eagerly load any existing thread
    # from the vault BEFORE sending the ``thread_loaded`` frame, so the
    # reported ``turn_count`` reflects the actual on-disk state. Task 17
    # shipped with a hardcoded ``turn_count = 0``; Task 21 swaps that for
    # a real load-from-vault + state.sqlite. A fresh thread still reports
    # ``0``; a reconnected thread reports the number of user turns
    # already persisted.
    mode = "ask"
    runner = SessionRunner(ctx=ctx, thread_id=thread_id, mode=mode)
    runner._ensure_session()

    # 6. Send handshake events. Two frames, in order: schema version
    # first (so a pinned client can disconnect before processing any
    # content if the major version has changed), then thread metadata.
    # Both go through ``serialize_server_event`` so the wire shape is
    # driven by the Pydantic model — there's no hand-maintained JSON
    # shape that can drift from the typed contract.
    await websocket.send_json(serialize_server_event(SchemaVersionEvent(version=SCHEMA_VERSION)))

    await websocket.send_json(
        serialize_server_event(
            ThreadLoadedEvent(
                thread_id=thread_id,
                mode=mode,
                turn_count=runner.turn_count,
            )
        )
    )

    # 7. Concurrent receive/turn loop. Two asyncio tasks coexist:
    #   - ``recv_task``: re-created every loop iteration; awaits the
    #     next inbound frame.
    #   - ``turn_task``: created on ``turn_start``, lives until the turn
    #     completes naturally OR is cancelled by ``cancel_turn`` / WS
    #     disconnect.
    # ``asyncio.wait(..., return_when=FIRST_COMPLETED)`` returns as soon
    # as either fires. Handling order matters: we process turn_task
    # completion BEFORE recv dispatch (so "already active" checks see
    # the just-cleared handle), but inside the same iteration.
    # "Both completed in the same tick" is legal — two independent
    # ``in done`` branches cover it.
    turn_task: asyncio.Task[None] | None = None

    try:
        while True:
            recv_task: asyncio.Task[Any] = asyncio.create_task(websocket.receive_json())
            wait_set: set[asyncio.Task[Any]] = {recv_task}
            if turn_task is not None and not turn_task.done():
                wait_set.add(turn_task)

            done, _pending = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)

            # --- Handle turn_task completion FIRST so the dispatch
            # below sees ``turn_task = None`` if the turn ended in the
            # same tick as an inbound frame. ``run_turn`` catches
            # ``Exception`` internally and emits ``error``; we just
            # need to null the handle and consume any unretrieved
            # exception to silence asyncio warnings.
            if turn_task is not None and turn_task in done:
                exc = turn_task.exception()
                if exc is not None and not isinstance(exc, asyncio.CancelledError):
                    logger.exception("turn_task escaped run_turn's Exception handler: %r", exc)
                turn_task = None

            # --- Handle inbound frame dispatch.
            if recv_task in done:
                try:
                    raw = recv_task.result()
                except WebSocketDisconnect:
                    # Bubble up to the outer handler — the WS is gone.
                    raise
                turn_task = await _dispatch_client_frame(
                    raw=raw,
                    websocket=websocket,
                    runner=runner,
                    turn_task=turn_task,
                )
            else:
                # recv_task did not fire (turn_task finished first). We
                # MUST cancel it to avoid a "Task was destroyed but it is
                # pending!" warning at WS close. ``receive_json`` parks
                # on the underlying stream; cancelling unparks cleanly.
                # ``contextlib.suppress`` covers both CancelledError (the
                # expected unwind path) and any rarely-surfaced WS-side
                # exception so cleanup never raises.
                recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await recv_task

    except WebSocketDisconnect:
        logger.info("chat WS disconnected: thread_id=%s", thread_id)
    finally:
        # Task 21 — belt-and-braces flush. ORDER MATTERS:
        # 1. Cancel the in-flight turn_task first. ``ChatSession.turn``
        #    has a ``finally`` block that appends the USER + ASSISTANT
        #    turns to ``_turns`` even on ``CancelledError``, so after
        #    awaiting the cancelled task the session's turn list is
        #    consistent (the partial assistant reply is captured).
        # 2. THEN call persist(). The ``ChatSession.turn`` code path
        #    that ran ``persistence.write`` lived AFTER the yield of
        #    ``turn_end`` — cancelled or exception-interrupted turns
        #    never reach it. persist() writes the session state we
        #    just assembled.
        # On a clean between-turn disconnect the turn_task is already
        # None and persist() either writes identical bytes (harmless,
        # atomic) or is a no-op if _turns is empty. persist() never
        # raises (see its docstring), so it cannot mask an interesting
        # exception escaping the receive loop.
        if turn_task is not None and not turn_task.done():
            turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await turn_task
        await runner.persist()


async def _dispatch_client_frame(
    *,
    raw: Any,
    websocket: WebSocket,
    runner: SessionRunner,
    turn_task: asyncio.Task[None] | None,
) -> asyncio.Task[None] | None:
    """Parse + dispatch one inbound client frame.

    Returns the new value of ``turn_task`` (possibly unchanged). Each
    branch either:

    - starts a new turn (TurnStartMessage + idle),
    - cancels + awaits the active turn (CancelTurnMessage + active),
    - emits a single error frame (invalid state or parse failure),
    - silently mutates runner state (SwitchModeMessage idle / SetOpenDoc).

    Factored out of the receive loop to keep the state-machine branches
    readable — inlining would bury the dispatch inside a 120-line while
    body.
    """
    # Parse — malformed frames surface as a structured error so clients
    # get a uniform response regardless of which validator tripped.
    # The broad ``Exception`` catch is intentional: Pydantic raises
    # ``ValidationError`` but any other deserialization slip (e.g.,
    # ``raw`` is not a dict at all) should map to the same wire-level
    # error shape so clients don't need per-validator dispatch.
    try:
        msg = parse_client_message(raw)
    except Exception as exc:
        await websocket.send_json(
            serialize_server_event(
                ErrorEvent(code="invalid_message", message=str(exc), recoverable=True)
            )
        )
        return turn_task

    if isinstance(msg, TurnStartMessage):
        if turn_task is not None and not turn_task.done():
            await websocket.send_json(
                serialize_server_event(
                    ErrorEvent(
                        code="invalid_state",
                        message="cannot start new turn while one is active",
                        recoverable=True,
                    )
                )
            )
            return turn_task
        if msg.mode:
            runner.mode = msg.mode
        return asyncio.create_task(runner.run_turn(msg.content, websocket))

    if isinstance(msg, CancelTurnMessage):
        if turn_task is None or turn_task.done():
            await websocket.send_json(
                serialize_server_event(
                    ErrorEvent(
                        code="invalid_state",
                        message="no active turn to cancel",
                        recoverable=True,
                    )
                )
            )
            return turn_task
        # Cancel and await — awaiting is essential so no further event
        # frames can be emitted between here and the CancelledEvent we
        # send next. ``run_turn`` catches ``Exception`` internally but
        # NOT ``CancelledError`` (asyncio treats CancelledError specially
        # — a bare except-Exception doesn't catch it). We catch both
        # here explicitly.
        turn_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await turn_task
        await websocket.send_json(
            serialize_server_event(CancelledEvent(turn_number=runner.turn_number))
        )
        return None

    if isinstance(msg, SwitchModeMessage):
        if turn_task is not None and not turn_task.done():
            await websocket.send_json(
                serialize_server_event(
                    ErrorEvent(
                        code="invalid_state",
                        message="cannot switch mode during active turn",
                        recoverable=True,
                    )
                )
            )
            return turn_task
        # Silent success — the wire contract has no ack frame.
        runner.mode = msg.mode
        return turn_task

    if isinstance(msg, SetOpenDocMessage):
        # ALWAYS accepted (idle or mid-turn). Task 20 treats this as
        # pure metadata — runner.open_doc is stashed but not threaded
        # into the active session's context (Task 21+ wires that).
        runner.open_doc = msg.path
        return turn_task

    # Unknown variant — parse_client_message should have raised, but
    # belt-and-braces for a future ClientMessage addition without a
    # dispatch branch.
    return turn_task
