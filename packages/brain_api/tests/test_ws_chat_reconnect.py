"""Tests for WS disconnect-flush + reconnect-rebuild (Plan 05 Task 21).

Three invariants proved here:

1. **Clean disconnect persists.** Close the WS after a full turn; the
   thread file must exist on disk under ``<vault>/<domain>/chats/``.
   This mostly re-verifies that ``ChatSession.turn`` already persists
   on successful completion — but it also proves the WS ``finally``
   block doesn't double-write in a way that corrupts the file.

2. **Reconnect rebuilds history.** Open a WS, run one turn, close.
   Re-open a NEW WS with the same ``thread_id`` — the ``thread_loaded``
   frame must report ``turn_count >= 1`` (rehydrated from the vault
   transcript via ``ThreadPersistence.read`` + ``ChatSession(initial_turns
   =...)`` ).

3. **Unclean disconnect still persists.** Raise inside the
   ``websocket_connect`` context manager (simulates a client crash /
   browser kill mid-turn). The ``finally`` in the route handler still
   fires and writes the thread file. This is the case
   ``ChatSession.turn`` CANNOT cover on its own — the post-yield
   ``persistence.write`` sits AFTER the event loop's cancellation
   point, so a mid-turn cancel never reaches it. ``runner.persist()``
   is the backstop.

Follows the ``Host: localhost`` override pattern used by every other
WS test in this package; see ``test_ws_chat_handshake.py`` for the
underlying reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _ws_helpers import get_app_ctx, get_app_token
from fastapi import FastAPI
from fastapi.testclient import TestClient

_LOOPBACK_HEADERS = {"Host": "localhost"}


def _drain_until_turn_end(ws) -> list[dict]:
    """Read WS frames until a ``turn_end`` or ``error`` arrives.

    Returns all frames observed (including the terminal one). Useful
    because the exact stream shape is
    ``turn_start, (delta|tool_call|tool_result|cost_update)*, turn_end``
    and tests here only care about the terminal marker.
    """
    frames: list[dict] = []
    while True:
        frame = ws.receive_json()
        frames.append(frame)
        if frame["type"] in {"turn_end", "error"}:
            return frames


def test_thread_persisted_on_clean_disconnect(app: FastAPI, seeded_vault: Path) -> None:
    """A completed turn followed by a clean WS close leaves the thread file on disk.

    The ``FakeLLMProvider.queue`` call arms a single canned assistant
    response. The WS client sends one ``turn_start``, drains to
    ``turn_end``, then exits the context manager (clean close). The
    ``research/chats/<thread_id>.md`` file must exist and contain the
    user's message.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        get_app_ctx(fresh).tool_ctx.llm.queue("assistant response")
        token = get_app_token(fresh)

        with fresh.websocket_connect(
            f"/ws/chat/persist-me?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            assert ws.receive_json()["type"] == "schema_version"
            loaded = ws.receive_json()
            assert loaded["type"] == "thread_loaded"
            assert loaded["turn_count"] == 0  # fresh thread, no prior turns

            ws.send_json({"type": "turn_start", "content": "hello brain", "mode": "ask"})
            _drain_until_turn_end(ws)

        # WS has closed — runner.persist() fired in the ``finally``
        # block (even though ChatSession.turn also already persisted on
        # success; both writes are idempotent because the second sees
        # the file and issues an Edit patch with identical old/new
        # content... unless the timestamp in the frontmatter ``updated``
        # field differs. That's fine — VaultWriter's atomic rename
        # handles either case.
        chats_dir = seeded_vault / "research" / "chats"
        assert chats_dir.exists(), "expected chats directory to exist after first turn"
        thread_files = list(chats_dir.glob("persist-me*.md"))
        assert len(thread_files) == 1, f"expected 1 thread file, got {thread_files}"
        content = thread_files[0].read_text(encoding="utf-8")
        assert "hello brain" in content, f"user message missing from thread file: {content!r}"
        assert "mode: ask" in content


def test_reconnect_reports_real_turn_count(app: FastAPI, seeded_vault: Path) -> None:
    """Reconnecting to an existing thread_id reports the real prior turn count.

    Connection A runs one full turn and closes. Connection B reopens
    the SAME ``thread_id`` — the ``thread_loaded`` frame must carry
    ``turn_count == 1``. This proves:

    * ``ThreadPersistence.read`` parses the on-disk file correctly.
    * ``ChatSession(initial_turns=...)`` rehydrates USER turns.
    * ``ChatSession.turn_count`` counts USER entries (not total).
    * ``SessionRunner.turn_count`` forwards from the loaded session.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        get_app_ctx(fresh).tool_ctx.llm.queue("first reply")
        token = get_app_token(fresh)

        # --- Connection A: run one turn then close cleanly.
        with fresh.websocket_connect(
            f"/ws/chat/rejoin?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            assert ws.receive_json()["type"] == "schema_version"
            loaded = ws.receive_json()
            assert loaded["turn_count"] == 0  # never been opened before

            ws.send_json({"type": "turn_start", "content": "hi", "mode": "ask"})
            _drain_until_turn_end(ws)

        # The on-disk thread now has 1 USER + 1 ASSISTANT turn. Sanity
        # check to fail fast if persistence broke before reconnect.
        thread_file = seeded_vault / "research" / "chats" / "rejoin.md"
        assert thread_file.exists(), "thread file should exist after connection A closed"

        # --- Connection B: reconnect, expect turn_count=1.
        with fresh.websocket_connect(
            f"/ws/chat/rejoin?token={token}", headers=_LOOPBACK_HEADERS
        ) as ws:
            assert ws.receive_json()["type"] == "schema_version"
            loaded = ws.receive_json()
            assert loaded["type"] == "thread_loaded"
            assert loaded["thread_id"] == "rejoin"
            assert loaded["turn_count"] == 1, (
                f"expected turn_count=1 on reconnect, got {loaded['turn_count']}; "
                f"thread_file contents: {thread_file.read_text(encoding='utf-8')!r}"
            )


def test_unclean_disconnect_still_persists(app: FastAPI, seeded_vault: Path) -> None:
    """A client-side crash mid-turn still leaves the thread persisted.

    This is the case ``ChatSession.turn`` can NOT cover on its own:
    its post-yield ``persistence.write`` sits outside the ``try/finally``
    that appends turns. When the WS closes abnormally mid-stream, the
    route's ``finally`` runs ``turn_task.cancel()`` + ``runner.persist()``
    — which is what this test exercises.

    Simulation mechanism: raise ``RuntimeError`` inside the
    ``websocket_connect`` context manager BEFORE draining to turn_end.
    TestClient's context manager propagates the raise out of the
    generator, which yanks the socket closed abruptly. The route's
    ``except WebSocketDisconnect`` + ``finally`` take over.
    """
    with TestClient(app, base_url="http://localhost") as fresh:
        get_app_ctx(fresh).tool_ctx.llm.queue("assistant reply")
        token = get_app_token(fresh)

        with (
            pytest.raises(RuntimeError, match="simulated client crash"),
            fresh.websocket_connect(
                f"/ws/chat/unclean?token={token}", headers=_LOOPBACK_HEADERS
            ) as ws,
        ):
            ws.receive_json()  # schema_version
            ws.receive_json()  # thread_loaded
            ws.send_json({"type": "turn_start", "content": "partial message", "mode": "ask"})
            # Grab ONE frame so the server has definitely started the
            # turn — then raise out of the context manager to simulate a
            # client crash mid-stream.
            ws.receive_json()
            raise RuntimeError("simulated client crash")

        # finally-block persist() must have written the thread even
        # though ``ChatSession.turn`` was cancelled before its own
        # persistence call.
        chats_dir = seeded_vault / "research" / "chats"
        thread_files = list(chats_dir.glob("unclean*.md"))
        assert len(thread_files) == 1, (
            f"expected thread to persist on unclean disconnect, got files={thread_files}"
        )
        content = thread_files[0].read_text(encoding="utf-8")
        assert "partial message" in content
