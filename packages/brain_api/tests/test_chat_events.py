"""Tests for typed WS event + client-message models — Plan 05 Task 18.

The WS wire format (D5a) is ``{"type": "<name>", ...fields}`` with ``type``
as the discriminator. These tests verify:

1. Server events serialize with ``type`` as the discriminator tag.
2. Client messages parse by ``type`` into the correct Pydantic variant.
3. Unknown / invalid messages raise ``ValidationError`` — no silent
   passthrough (the plan's Hard Rule #4).
"""

from __future__ import annotations

import pytest
from brain_api.chat.events import (
    SCHEMA_VERSION,
    CancelTurnMessage,
    DeltaEvent,
    SwitchModeMessage,
    TurnStartMessage,
    parse_client_message,
    serialize_server_event,
)
from pydantic import ValidationError


def test_schema_version_is_pinned_to_1() -> None:
    """Plan 07 frontend pins to this value; bumping is a breaking change."""
    assert SCHEMA_VERSION == "1"


def test_delta_event_serializes_with_type_discriminator() -> None:
    """``type`` must appear on the wire — it's the discriminator the
    frontend dispatches on. ``mode="json"`` ensures the result is
    websocket-sendable (no non-JSON scalars leak through).
    """
    event = DeltaEvent(text="hello ")
    payload = serialize_server_event(event)
    assert payload == {"type": "delta", "text": "hello "}


def test_parse_turn_start_message() -> None:
    """The most common client → server message: user sends content + mode."""
    raw = {"type": "turn_start", "content": "Hi!", "mode": "ask"}
    msg = parse_client_message(raw)
    assert isinstance(msg, TurnStartMessage)
    assert msg.content == "Hi!"
    assert msg.mode == "ask"


def test_parse_cancel_turn_message() -> None:
    """Cancel has no payload beyond ``type`` — smallest message surface."""
    raw = {"type": "cancel_turn"}
    msg = parse_client_message(raw)
    assert isinstance(msg, CancelTurnMessage)


def test_parse_switch_mode_message() -> None:
    """Mode is a strict Literal — ``brainstorm`` is one of the three valid values."""
    raw = {"type": "switch_mode", "mode": "brainstorm"}
    msg = parse_client_message(raw)
    assert isinstance(msg, SwitchModeMessage)
    assert msg.mode == "brainstorm"


def test_parse_unknown_type_raises() -> None:
    """Unknown discriminator values must ``ValidationError`` — NO silent
    passthrough. A bogus ``type`` from a malicious client should trip the
    ``ErrorEvent`` branch in ``chat_ws``, not be treated as some default.
    """
    with pytest.raises(ValidationError):
        parse_client_message({"type": "bogus"})


def test_switch_mode_rejects_invalid_mode() -> None:
    """``mode`` is ``Literal["ask", "brainstorm", "draft"]`` — Pydantic
    rejects anything else. This guards the chat session from being dropped
    into an undefined mode by a typo or stale frontend build.
    """
    with pytest.raises(ValidationError):
        parse_client_message({"type": "switch_mode", "mode": "telepathy"})
