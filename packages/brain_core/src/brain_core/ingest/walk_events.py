"""Typed event models for streaming walk-phase progress — Plan 26 T3.

The bulk-import wizard's walk phase can take seconds to minutes on a
large folder. Plan 25 T4 shipped timer-driven pseudo-progress at the
frontend; Plan 26 T3 replaces it with real progress emitted by the
backend over a Server-Sent Events stream.

Four event types, discriminated by ``type``:

- :class:`WalkStarted` — emitted once at the top of the walk.
- :class:`WalkProgress` — emitted every 50 files seen (flood control;
  see D9 in ``tasks/plans/26-critical-fix-and-plan-25-aftermath.md``).
- :class:`WalkComplete` — emitted once at the end, carrying the final
  total and a UUID4 ``plan_id`` correlation token.
- :class:`WalkError` — emitted on exception during walk, classifying the
  failure into a small set of stable codes so the frontend can render
  actionable copy without parsing free-form text.

The :data:`WalkEvent` ``Annotated`` alias is the discriminated-union
top-type the SSE endpoint serializes through ``model_dump_json``.
Pydantic v2 dispatches the right concrete model by inspecting the
``type`` literal.

This module is import-side-effect-free and has no LLM or vault
dependencies — it MUST stay cheap so the brain_api router can register
the SSE endpoint without paying the full ingest pipeline import cost
during boot.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class WalkStarted(BaseModel):
    """First event in every stream — confirms the walk has begun.

    The frontend uses receipt of this event to flip its UI state out of
    "connecting" into "walking" so the user sees progress within ~1
    network round trip rather than waiting for the first
    :class:`WalkProgress` (which doesn't fire until 50 files are seen
    and may never fire for small folders).
    """

    type: Literal["walk_started"] = "walk_started"
    path: str


class WalkProgress(BaseModel):
    """Periodic progress update — emitted every 50 files seen.

    ``files_seen`` is the running count of CANDIDATE files the walker
    has examined, not the count of items that will end up in the plan
    (system files and unsupported extensions are filtered AFTER the
    counter increments). This matches the "scanning" UX intent: the
    user wants to know the walker is making forward progress through
    the source tree, not how many items will survive filtering.
    """

    type: Literal["walk_progress"] = "walk_progress"
    files_seen: int = Field(ge=0)
    current_path: str


class WalkComplete(BaseModel):
    """Terminal success event — carries the final count + correlation id.

    ``plan_id`` is a fresh UUID4 minted by the streaming walk. Plan 26
    T3 decision (a): the SSE endpoint emits progress ONLY. The wizard
    separately calls :meth:`BulkImporter.plan` after the stream
    completes to obtain the actual ``BulkPlan`` it will display and
    apply. ``plan_id`` is therefore a correlation token for telemetry /
    logs, not a server-side cache key. This keeps the endpoint
    stateless and sidesteps an entire class of cache-invalidation bugs.
    """

    type: Literal["walk_complete"] = "walk_complete"
    total_count: int = Field(ge=0)
    plan_id: str


class WalkError(BaseModel):
    """Terminal failure event — emitted in place of :class:`WalkComplete`
    when the walk raises.

    ``error_code`` is a small stable enum the frontend dispatches off:

    - ``permission_denied`` — :class:`PermissionError` raised while
      reading a directory entry.
    - ``path_not_found`` — :class:`FileNotFoundError` raised because
      ``source_root`` disappeared between the endpoint's pre-check
      and the walk reaching it.
    - ``internal_error`` — any other exception (OSError variants,
      bugs in the walker). The endpoint logs the full exception via
      structlog; the frontend shows generic "scan failed" copy and
      offers retry.

    ``error_message`` is a short ``str(exc)`` for log/diagnostic use.
    Frontend microcopy is keyed off ``error_code``, not this string.
    """

    type: Literal["walk_error"] = "walk_error"
    error_message: str
    error_code: Literal["permission_denied", "path_not_found", "internal_error"]


WalkEvent = Annotated[
    WalkStarted | WalkProgress | WalkComplete | WalkError,
    Field(discriminator="type"),
]
"""Discriminated-union top-type for the streaming walk-progress events.

The SSE endpoint serializes each event via ``event.model_dump_json()``
and frames it as ``data: <json>\\n\\n``. The wire format is therefore
4 distinct JSON shapes keyed by the ``type`` literal — clients use a
``switch`` on that field to dispatch handling.
"""


__all__ = [
    "WalkComplete",
    "WalkError",
    "WalkEvent",
    "WalkProgress",
    "WalkStarted",
]
