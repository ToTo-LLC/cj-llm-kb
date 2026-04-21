"""Tests for end-to-end chat-turn streaming over WS (Plan 05 Task 19).

``SessionRunner`` bridges ``brain_core.chat.ChatSession.turn(...)`` (an
``AsyncIterator[ChatEvent]``) into the typed WS event stream landed in
Task 18. Two shapes matter here:

1. Happy path — queue a FakeLLM response, send ``turn_start``, verify
   the WS emits ``turn_start`` first, ``delta`` somewhere in the middle,
   and ``turn_end`` last.
2. Failure path — force ``ChatSession.turn`` to raise, verify the WS
   emits an ``error`` event with ``recoverable=True``, and confirm the
   connection STAYS OPEN (sending another ``turn_start`` does not raise
   ``WebSocketDisconnect``).

The ``Host: localhost`` override is required because ``TestClient``
hard-codes ``Host: testserver`` on WS connects, which Task 8's
``OriginHostMiddleware`` would otherwise reject. See
``test_ws_chat_handshake.py`` for the longer comment.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

_LOOPBACK_HEADERS = {"Host": "localhost"}


def test_turn_emits_ordered_events(app: FastAPI) -> None:
    """Happy path — turn_start, at least one delta, turn_end, in order."""
    with TestClient(app, base_url="http://localhost") as fresh:
        # Queue BEFORE opening the WS so the FakeLLM has a response ready
        # when the background turn fires.
        fresh.app.state.ctx.tool_ctx.llm.queue("Hello there.")
        token = fresh.app.state.ctx.token

        with fresh.websocket_connect(f"/ws/chat/t1?token={token}", headers=_LOOPBACK_HEADERS) as ws:
            # Drain the two handshake frames.
            assert ws.receive_json()["type"] == "schema_version"
            assert ws.receive_json()["type"] == "thread_loaded"

            ws.send_json({"type": "turn_start", "content": "hi", "mode": "ask"})

            events: list[dict] = []
            while True:
                frame = ws.receive_json()
                events.append(frame)
                if frame["type"] in {"turn_end", "error"}:
                    break

    types_seen = [e["type"] for e in events]
    assert types_seen[0] == "turn_start", f"expected turn_start first, got {types_seen}"
    assert "delta" in types_seen, f"expected at least one delta, got {types_seen}"
    assert types_seen[-1] == "turn_end", f"expected turn_end last, got {types_seen}"

    # turn_start + turn_end carry the same turn_number (1-indexed, first turn).
    turn_starts = [e for e in events if e["type"] == "turn_start"]
    turn_ends = [e for e in events if e["type"] == "turn_end"]
    assert turn_starts[0]["turn_number"] == 1
    assert turn_ends[0]["turn_number"] == 1


def test_turn_error_emits_error_event_keeps_connection_open(app: FastAPI, monkeypatch) -> None:
    """A ChatSession failure emits ``error`` but does not close the WS.

    Monkeypatches ``ChatSession.turn`` to raise. The SessionRunner catches
    the exception, sends a typed ``ErrorEvent`` with ``recoverable=True``,
    and the receive loop keeps going. Proof-of-life: send a second
    ``turn_start`` and confirm a frame comes back (it'll be another
    ``turn_start`` followed by another ``error``, but the key invariant
    is the socket did not close between turns).
    """
    from brain_core.chat import session as session_mod

    async def boom(self, user_message):
        raise RuntimeError("simulated session failure")
        yield  # pragma: no cover — unreachable, makes this an async-gen

    monkeypatch.setattr(session_mod.ChatSession, "turn", boom)

    with TestClient(app, base_url="http://localhost") as fresh:
        token = fresh.app.state.ctx.token
        with fresh.websocket_connect(f"/ws/chat/t2?token={token}", headers=_LOOPBACK_HEADERS) as ws:
            ws.receive_json()  # schema_version
            ws.receive_json()  # thread_loaded

            ws.send_json({"type": "turn_start", "content": "anything", "mode": "ask"})

            # Drain until the error frame. turn_start is always emitted
            # before the turn body runs, so it arrives before the error.
            frame = ws.receive_json()
            while frame["type"] != "error":
                frame = ws.receive_json()
            assert frame["code"] == "internal"
            assert frame["recoverable"] is True

            # Proof the connection is still alive — another turn_start
            # must be accepted and echoed back (at minimum as a
            # server-side turn_start event).
            ws.send_json({"type": "turn_start", "content": "again", "mode": "ask"})
            next_frame = ws.receive_json()
            assert next_frame["type"] in {"turn_start", "error"}
