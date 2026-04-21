"""Tests for Plan 05 Task 20 — cancel_turn / switch_mode / set_open_doc.

Task 20 converts the WS receive loop from a synchronous "await run_turn
inline" dispatch to a concurrent ``asyncio.wait({recv_task, turn_task})``
orchestration, which lets the server interleave inbound client messages
(``cancel_turn`` in particular) with an in-flight turn.

Four invariants covered here:

1. ``cancel_turn`` sent mid-stream produces a ``cancelled`` event with
   the in-flight turn's ``turn_number``. No more ``delta`` frames may
   arrive for that turn after ``cancelled``.
2. ``cancel_turn`` with no active turn produces an ``error`` with
   ``code="invalid_state"``.
3. ``switch_mode`` between turns succeeds silently (no ack, no error).
4. ``switch_mode`` sent DURING a turn produces an ``error`` with
   ``code="invalid_state"``. This races the turn's own completion —
   either the error fires OR the turn finished first; what's NEVER
   allowed is a silent mid-turn mode change.

Mid-turn cancellation mechanics: ``FakeLLMProvider`` has no "slow"
mode (see ``brain_core/llm/fake.py`` — the stream loop yields chars
as fast as the event loop drains them). To reliably get the WS into
a state where a ``cancel_turn`` can arrive BEFORE ``turn_end``, test 1
monkeypatches ``ChatSession.turn`` with an async generator that yields
one ``DELTA`` event and then awaits a long ``asyncio.sleep``. The
``task.cancel()`` raises ``CancelledError`` into the sleep, unwinds
the generator, and the route handler emits ``CancelledEvent`` once the
awaited task resolves.

The ``Host: localhost`` header override mirrors the other WS test files
(``OriginHostMiddleware`` would otherwise reject ``Host: testserver``
on the upgrade).
"""

from __future__ import annotations

import asyncio

from _ws_helpers import get_app_ctx, get_app_token
from fastapi import FastAPI
from fastapi.testclient import TestClient

_LOOPBACK_HEADERS = {"Host": "localhost"}


def test_cancel_turn_mid_stream(app: FastAPI, monkeypatch) -> None:
    """A ``cancel_turn`` sent while a turn is running emits ``cancelled``.

    We monkeypatch ``ChatSession.turn`` to yield one ``DELTA`` then park
    on a long sleep — the sleep is what the cancel interrupts. Without
    this, FakeLLM drains synchronously and the turn finishes before the
    ``cancel_turn`` frame lands, making the test racy.

    The ``cancelled`` event's ``turn_number`` must match the one the
    server emitted on ``turn_start`` (1-indexed, first turn => 1).
    """
    from brain_core.chat import session as session_mod
    from brain_core.chat.types import ChatEvent, ChatEventKind

    async def slow_turn(self, user_message):
        # One quick event so the client has proof the turn is actually
        # in flight, then park — the cancel is what unblocks this.
        yield ChatEvent(kind=ChatEventKind.DELTA, data={"text": "hi"})
        await asyncio.sleep(60)  # long enough that the test cancels it
        yield ChatEvent(kind=ChatEventKind.DELTA, data={"text": "never"})

    monkeypatch.setattr(session_mod.ChatSession, "turn", slow_turn)

    with TestClient(app, base_url="http://localhost") as fresh:
        token = get_app_token(fresh)
        with fresh.websocket_connect(
            f"/ws/chat/t-cancel?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            assert ws.receive_json()["type"] == "schema_version"
            assert ws.receive_json()["type"] == "thread_loaded"

            ws.send_json({"type": "turn_start", "content": "slow one", "mode": "ask"})

            # Wait for turn_start server frame — proves run_turn has
            # actually started the async task (the cancel below needs
            # a live turn_task to operate on).
            first = ws.receive_json()
            assert first["type"] == "turn_start"
            assert first["turn_number"] == 1

            # Drain any in-flight frames (the "hi" delta may or may not
            # have landed yet, depending on event-loop scheduling).
            # The strict invariant is simply: after cancel_turn, we
            # eventually see a ``cancelled`` event.
            ws.send_json({"type": "cancel_turn"})

            saw_cancelled = False
            for _ in range(50):
                frame = ws.receive_json()
                if frame["type"] == "cancelled":
                    saw_cancelled = True
                    assert frame["turn_number"] == 1
                    break
                # delta or other pre-cancel frames are acceptable.
                assert frame["type"] in {
                    "delta",
                    "tool_call",
                    "tool_result",
                    "cost_update",
                    "patch_proposed",
                }, f"unexpected frame during cancel drain: {frame}"
            assert saw_cancelled, "expected a cancelled event after cancel_turn"


def test_cancel_without_active_turn_emits_error(app: FastAPI) -> None:
    """``cancel_turn`` with no turn in flight is an ``invalid_state`` error."""
    with TestClient(app, base_url="http://localhost") as fresh:
        token = get_app_token(fresh)
        with fresh.websocket_connect(
            f"/ws/chat/t-nocancel?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            ws.receive_json()  # schema_version
            ws.receive_json()  # thread_loaded

            ws.send_json({"type": "cancel_turn"})
            frame = ws.receive_json()
            assert frame["type"] == "error"
            assert frame["code"] == "invalid_state"
            # Connection stays open — error is recoverable by default.
            assert frame.get("recoverable", True) is True


def test_switch_mode_between_turns(app: FastAPI) -> None:
    """``switch_mode`` while idle is a silent success — no frame back.

    The wire contract (Task 18 + Task 20) doesn't define a ``mode_switched``
    ack. Clients that care about the post-switch mode can re-request
    thread state; most UIs just optimistically reflect the local toggle.

    We prove "silent success" by sending ``switch_mode``, then sending a
    ``turn_start`` and confirming the server responds normally — i.e.,
    the switch didn't break the receive loop or trigger an error frame.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        get_app_ctx(fresh).tool_ctx.llm.queue("ok")
        token = get_app_token(fresh)
        with fresh.websocket_connect(
            f"/ws/chat/t-switch?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            ws.receive_json()  # schema_version
            ws.receive_json()  # thread_loaded

            ws.send_json({"type": "switch_mode", "mode": "brainstorm"})
            # No ack expected — confirm by sending a turn and watching
            # the normal event stream resume.
            ws.send_json({"type": "turn_start", "content": "hi"})

            # First frame must be the server's turn_start — if switch_mode
            # had errored, an error frame would arrive first.
            first = ws.receive_json()
            assert first["type"] == "turn_start", (
                f"switch_mode should be silent, but first frame was {first!r}"
            )

            # Drain to turn_end to keep the runner clean.
            while True:
                frame = ws.receive_json()
                if frame["type"] in {"turn_end", "error"}:
                    break


def test_switch_mode_mid_turn_rejected(app: FastAPI, monkeypatch) -> None:
    """``switch_mode`` during a live turn MUST emit an ``invalid_state`` error.

    We force a slow turn (same mechanic as ``test_cancel_turn_mid_stream``)
    so the ``switch_mode`` message is guaranteed to arrive while the turn
    task is still active. Without the slow-turn monkeypatch this would be
    a genuine race; with it, the invariant is strict.

    Strict assertion: ``switch_mode`` NEVER succeeds silently mid-turn.
    Either we see the ``invalid_state`` error, or (the fallback, defensive
    against event-loop scheduling quirks) we see a ``turn_end`` — but the
    critical property is that no absence-of-error-plus-continued-normal-
    flow path exists.

    After observing the error we send ``cancel_turn`` to unwind the
    parked turn so the WS closes cleanly (otherwise the test client's
    context-manager exit waits for the 60s sleep to resolve).
    """
    from brain_core.chat import session as session_mod
    from brain_core.chat.types import ChatEvent, ChatEventKind

    async def slow_turn(self, user_message):
        yield ChatEvent(kind=ChatEventKind.DELTA, data={"text": "start"})
        await asyncio.sleep(60)
        yield ChatEvent(kind=ChatEventKind.DELTA, data={"text": "never"})

    monkeypatch.setattr(session_mod.ChatSession, "turn", slow_turn)

    with TestClient(app, base_url="http://localhost") as fresh:
        token = get_app_token(fresh)
        with fresh.websocket_connect(
            f"/ws/chat/t-midswitch?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            ws.receive_json()  # schema_version
            ws.receive_json()  # thread_loaded

            ws.send_json({"type": "turn_start", "content": "hi", "mode": "ask"})
            # Wait for turn_start server frame so we know the turn task
            # is live before sending switch_mode.
            assert ws.receive_json()["type"] == "turn_start"

            ws.send_json({"type": "switch_mode", "mode": "brainstorm"})

            saw_error = False
            for _ in range(30):
                frame = ws.receive_json()
                if frame["type"] == "error" and frame.get("code") == "invalid_state":
                    saw_error = True
                    break
                if frame["type"] == "turn_end":
                    # Defensive: if the turn somehow completed first, the
                    # test still passes — the strict invariant (no silent
                    # mid-turn switch) holds in that branch trivially.
                    break
                # delta / tool_call etc. pre-error are fine.
                assert frame["type"] in {
                    "delta",
                    "tool_call",
                    "tool_result",
                    "cost_update",
                    "patch_proposed",
                }, f"unexpected frame during switch_mode race: {frame}"

            assert saw_error, (
                "switch_mode mid-turn must emit invalid_state — got no error "
                "frame within 30 drained events"
            )

            # Unwind the parked turn so the WS closes without waiting on
            # the 60s sleep.
            ws.send_json({"type": "cancel_turn"})
            for _ in range(30):
                frame = ws.receive_json()
                if frame["type"] == "cancelled":
                    break
