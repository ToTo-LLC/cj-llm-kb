"""WS /ws/chat/<thread_id> — chat endpoint.

Plan 05 Task 17 lands the handshake + empty receive loop. Task 18 adds
typed Pydantic events; Task 19 wires ``ChatSession`` into the loop and
emits real turn events; Tasks 20-21 add cancellation and reconnect.

The endpoint does three things today:

1. Validates ``thread_id`` against a kebab-case regex BEFORE accepting
   the upgrade. Any slash / uppercase / invalid char closes the socket
   with code 1008 (Policy Violation) — the bad input never touches any
   vault I/O or chat state.
2. Authenticates via ``?token=<hex>`` query param (browsers cannot set
   custom headers on the ``WebSocket`` constructor). ``check_ws_token``
   closes with 1008 on mismatch; we return immediately.
3. After accept, emits two framing events — ``schema_version`` and
   ``thread_loaded`` — then enters a receive loop that echoes a debug
   ``ack`` for every inbound frame. The ack is a temporary liveness
   probe for the handshake tests; Task 19 replaces it with typed
   dispatch over ``turn_start`` / ``cancel_turn`` / ``switch_mode``.

Middleware (``OriginHostMiddleware``) catches non-loopback Origin on
the upgrade handshake before we even enter this function, so the
endpoint doesn't re-check Origin itself.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from brain_api.auth import check_ws_token
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

# Major-version contract pin for WS events. Plan 07 frontend asserts
# this equals the version it was compiled against; a bump means the
# frontend must opt in to the new shape. Task 25 may relocate to
# ``brain_api.chat.events.SCHEMA_VERSION``.
_SCHEMA_VERSION = "1"


@router.websocket("/ws/chat/{thread_id}")
async def chat_ws(websocket: WebSocket, thread_id: str) -> None:
    """WebSocket endpoint for chat streaming.

    Task 17: handshake (thread_id validation + token auth + schema
    announcement) plus an empty receive loop. Task 19 fills in real
    turn-running.
    """
    # 1. Validate thread_id shape BEFORE accept. Closing without accepting
    # is the cleanest rejection — no leaked state, no half-open socket.
    if not _THREAD_ID_RE.match(thread_id):
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

    # 5. Send handshake events. Two frames, in order: schema version
    # first (so a pinned client can disconnect before processing any
    # content if the major version has changed), then thread metadata.
    await websocket.send_json({"type": "schema_version", "version": _SCHEMA_VERSION})

    # Thread metadata — Task 21 will load from vault + state.sqlite;
    # Task 17 emits defaults so the handshake shape is locked.
    turn_count = 0  # TODO(Task 21): load from vault + state.sqlite
    mode = "ask"
    await websocket.send_json(
        {
            "type": "thread_loaded",
            "thread_id": thread_id,
            "mode": mode,
            "turn_count": turn_count,
        }
    )

    # 6. Receive loop — empty until Task 19. The ack echo exists purely
    # so handshake tests can assert the loop is live; it is NOT part of
    # the Plan 07 frontend contract and will be removed when Task 19
    # lands typed ``turn_start`` / ``cancel_turn`` / ``switch_mode``.
    try:
        while True:
            msg = await websocket.receive_json()
            logger.debug("chat WS received: %s", msg)
            await websocket.send_json({"type": "ack", "received": msg.get("type", "unknown")})
    except WebSocketDisconnect:
        logger.info("chat WS disconnected: thread_id=%s", thread_id)
        # TODO(Task 21): call ``session_runner.persist()`` here so a
        # mid-turn disconnect still flushes partial progress to the
        # vault.
