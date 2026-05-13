"""Tests for the WalkEvent discriminated-union models — Plan 26 T3.

Round-trip serialize/deserialize per concrete type, plus discriminated-
union dispatch via :class:`pydantic.TypeAdapter`.
"""

from __future__ import annotations

import pytest
from brain_core.ingest.walk_events import (
    WalkComplete,
    WalkError,
    WalkEvent,
    WalkProgress,
    WalkStarted,
)
from pydantic import TypeAdapter, ValidationError

_walk_event_adapter: TypeAdapter[WalkEvent] = TypeAdapter(WalkEvent)


def test_walk_started_round_trip() -> None:
    """Serialize/deserialize a :class:`WalkStarted` event without drift."""
    event = WalkStarted(path="/Users/cj/Documents/brain")
    payload = event.model_dump_json()
    restored = WalkStarted.model_validate_json(payload)
    assert restored == event
    assert restored.type == "walk_started"


def test_walk_progress_round_trip_and_ge_constraint() -> None:
    """``files_seen`` must be >= 0; round-trip preserves all fields."""
    event = WalkProgress(files_seen=150, current_path="/Users/cj/notes/big-folder/a.md")
    payload = event.model_dump_json()
    restored = WalkProgress.model_validate_json(payload)
    assert restored == event
    assert restored.files_seen == 150

    with pytest.raises(ValidationError):
        WalkProgress(files_seen=-1, current_path="x")


def test_walk_complete_round_trip() -> None:
    """``total_count`` >= 0; ``plan_id`` is preserved verbatim."""
    event = WalkComplete(
        total_count=237,
        plan_id="11111111-2222-3333-4444-555555555555",
    )
    payload = event.model_dump_json()
    restored = WalkComplete.model_validate_json(payload)
    assert restored == event

    with pytest.raises(ValidationError):
        WalkComplete(total_count=-1, plan_id="x")


def test_walk_error_round_trip_and_code_literal() -> None:
    """``error_code`` is constrained to the documented enum."""
    event = WalkError(
        error_message="Permission denied: /System",
        error_code="permission_denied",
    )
    payload = event.model_dump_json()
    restored = WalkError.model_validate_json(payload)
    assert restored == event

    # Free-form codes are rejected by the Literal[...] constraint.
    with pytest.raises(ValidationError):
        WalkError(error_message="x", error_code="nope")  # type: ignore[arg-type]


def test_discriminated_union_dispatches_by_type_field() -> None:
    """``WalkEvent`` TypeAdapter routes each ``type`` value to its model."""
    started = _walk_event_adapter.validate_python(
        {"type": "walk_started", "path": "/x"}
    )
    progress = _walk_event_adapter.validate_python(
        {"type": "walk_progress", "files_seen": 50, "current_path": "/x/y"}
    )
    complete = _walk_event_adapter.validate_python(
        {"type": "walk_complete", "total_count": 1, "plan_id": "abc"}
    )
    error = _walk_event_adapter.validate_python(
        {
            "type": "walk_error",
            "error_message": "boom",
            "error_code": "internal_error",
        }
    )

    assert isinstance(started, WalkStarted)
    assert isinstance(progress, WalkProgress)
    assert isinstance(complete, WalkComplete)
    assert isinstance(error, WalkError)

    # Unknown discriminator value: ValidationError, not silent fallback.
    with pytest.raises(ValidationError):
        _walk_event_adapter.validate_python(
            {"type": "walk_unknown", "path": "/x"}
        )
