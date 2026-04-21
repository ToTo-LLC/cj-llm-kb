"""Typed WS event and message Pydantic models (D5a).

The WS wire format is ``{"type": "<name>", ...fields}`` with ``type``
acting as the discriminator. Pydantic v2's ``TypeAdapter`` handles
dispatch for inbound messages; ``model_dump(mode="json")`` handles
outbound serialization.

Server → client events (12): ``schema_version``, ``thread_loaded``,
``turn_start``, ``delta``, ``tool_call``, ``tool_result``,
``cost_update``, ``patch_proposed``, ``doc_edit_proposed``,
``turn_end``, ``cancelled``, ``error``.

Client → server messages (4): ``turn_start``, ``cancel_turn``,
``switch_mode``, ``set_open_doc``.

Every variant pins a ``Literal["..."]`` default on ``type`` — the
discriminator tag is always present on the wire, even if the caller
forgets to set it explicitly when constructing the model.

``SCHEMA_VERSION`` is a major-version pin. Bumping it is a breaking
contract change: the frontend asserts the version it was compiled
against matches, and a mismatch should force a reload / upgrade.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

SCHEMA_VERSION = "2"
# Plan 07 Task 5 bumped this from ``"1"`` → ``"2"`` to signal the
# addition of ``doc_edit_proposed``. The new event is technically
# additive (v1 clients could ignore it), but the bump makes the
# surface change explicit and lets a pinned client disconnect cleanly
# rather than silently miss structured-edit frames.


# ---------- Server → client ----------


class SchemaVersionEvent(BaseModel):
    """First frame after accept. Lets a pinned client disconnect cleanly
    if the server has bumped the WS contract since the client built."""

    type: Literal["schema_version"] = "schema_version"
    version: str


class ThreadLoadedEvent(BaseModel):
    """Second frame after accept. Tells the client which thread it's
    attached to, the current mode, and how many turns have already run
    (so the client can request history if it doesn't have them cached)."""

    type: Literal["thread_loaded"] = "thread_loaded"
    thread_id: str
    mode: str
    turn_count: int


class TurnStartEvent(BaseModel):
    """Server acknowledges the start of a new turn. ``turn_number`` is
    1-indexed and monotonic within a thread — used as the correlation
    ID for subsequent ``delta`` / ``turn_end`` / ``cancelled`` frames."""

    type: Literal["turn_start"] = "turn_start"
    turn_number: int


class DeltaEvent(BaseModel):
    """A chunk of model-generated text. May be partial (sub-word). The
    client concatenates deltas in order until the matching ``turn_end``."""

    type: Literal["delta"] = "delta"
    text: str


class ToolCallEvent(BaseModel):
    """Announces a tool invocation. ``id`` ties this to the matching
    ``tool_result``; ``arguments`` is the JSON sent to the tool."""

    type: Literal["tool_call"] = "tool_call"
    id: str
    tool: str
    arguments: dict[str, Any]


class ToolResultEvent(BaseModel):
    """Result of a tool invocation. Correlates with ``ToolCallEvent``
    via ``id``. ``data`` is the JSON returned by the tool."""

    type: Literal["tool_result"] = "tool_result"
    id: str
    data: dict[str, Any]


class CostUpdateEvent(BaseModel):
    """Running cost telemetry. ``cumulative_usd`` is the thread-level
    total; the UI uses it to drive a live cost meter.

    Plan 07 Task 3: ``cumulative_tokens_in`` is the running total of
    input tokens across every turn on this WS connection. The frontend
    uses it to show a live context-window gauge. Defaults to ``0`` so
    every Plan 05 test pinning the existing field set still passes.
    """

    type: Literal["cost_update"] = "cost_update"
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cumulative_usd: float
    cumulative_tokens_in: int = 0


class PatchProposedEvent(BaseModel):
    """The LLM has staged a vault mutation. Per CLAUDE.md principle #3
    these are ALWAYS staged, never direct — the client surfaces the
    patch to the user and routes through the approval queue."""

    type: Literal["patch_proposed"] = "patch_proposed"
    patch_id: str
    target_path: str
    reason: str


class DocEditProposedEvent(BaseModel):
    """Draft-mode structured edits travel as their own event.

    Plan 07 Task 5: the Draft-mode ``\\`\\`\\`edits`` fence parser
    (Task 2) yields one ``ChatEventKind.DOC_EDIT`` per edit entry;
    the WS layer maps each to a ``DocEditProposedEvent`` with a single
    edit in ``edits``. Batching multiple edits into one event is left
    to the frontend — emitting per-edit keeps the event ordering
    observable for the UI's undo/redo stack.

    Each edit is ``{op, anchor: {kind, value}, text}`` per the Plan 07
    draft-mode edit contract. The shape is loosely typed (``dict``)
    here because the frontend owns richer edit-op schemas than the
    backend needs to validate.
    """

    type: Literal["doc_edit_proposed"] = "doc_edit_proposed"
    edits: list[dict[str, Any]]


class TurnEndEvent(BaseModel):
    """Signals the end of the turn started by the matching
    ``TurnStartEvent``. ``title`` is an optional short summary the
    backend may attach (e.g., first-turn auto-title for the thread)."""

    type: Literal["turn_end"] = "turn_end"
    turn_number: int
    title: str | None = None


class CancelledEvent(BaseModel):
    """The in-flight turn was cancelled (via a client ``cancel_turn``
    message). No further ``delta`` frames for this ``turn_number``."""

    type: Literal["cancelled"] = "cancelled"
    turn_number: int


class ErrorEvent(BaseModel):
    """Non-fatal error. ``recoverable=True`` means the WS stays open
    and the client can retry; ``False`` typically precedes a close."""

    type: Literal["error"] = "error"
    code: str
    message: str
    recoverable: bool = True


ServerEvent = (
    SchemaVersionEvent
    | ThreadLoadedEvent
    | TurnStartEvent
    | DeltaEvent
    | ToolCallEvent
    | ToolResultEvent
    | CostUpdateEvent
    | PatchProposedEvent
    | DocEditProposedEvent
    | TurnEndEvent
    | CancelledEvent
    | ErrorEvent
)


def serialize_server_event(event: ServerEvent) -> dict[str, Any]:
    """Dump a server event to a JSON-safe dict.

    ``mode="json"`` forces Pydantic to emit only JSON-representable
    scalars (dates become ISO strings, etc.) — the result is directly
    passable to ``WebSocket.send_json``.
    """
    return event.model_dump(mode="json")


# ---------- Client → server ----------


class TurnStartMessage(BaseModel):
    """User kicks off a new turn. ``mode`` is optional — if omitted the
    server keeps the thread's current mode. When set it overrides for
    this turn AND becomes the thread's new mode."""

    type: Literal["turn_start"] = "turn_start"
    content: str
    mode: Literal["ask", "brainstorm", "draft"] | None = None


class CancelTurnMessage(BaseModel):
    """User aborted the in-flight turn. Server emits ``CancelledEvent``
    once the background task has wound down."""

    type: Literal["cancel_turn"] = "cancel_turn"


class SwitchModeMessage(BaseModel):
    """Change the thread's default mode without starting a turn.
    ``mode`` is strict — anything outside the three valid values raises
    ``ValidationError`` (guards against stale frontend builds / typos)."""

    type: Literal["switch_mode"] = "switch_mode"
    mode: Literal["ask", "brainstorm", "draft"]


class SetOpenDocMessage(BaseModel):
    """User focused a note in the sidebar — the server passes this into
    the prompt builder as context. ``path=None`` clears the focus."""

    type: Literal["set_open_doc"] = "set_open_doc"
    path: str | None = None


ClientMessage = Annotated[
    TurnStartMessage | CancelTurnMessage | SwitchModeMessage | SetOpenDocMessage,
    Field(discriminator="type"),
]


# Pydantic v2 discriminated-union adapter. Using ``Annotated[Union[...],
# Field(discriminator="type")]`` rather than ``TypeAdapter(..., config=
# {"discriminator": "type"})`` because the latter is a runtime-only dict
# that mypy cannot infer as a ``ConfigDict``. Both produce equivalent
# behavior: dispatch by ``type`` field on each variant; unknown
# discriminator values raise ``ValidationError`` which ``chat_ws``
# catches and converts to a typed ``ErrorEvent``.
_CLIENT_ADAPTER: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(raw: dict[str, Any]) -> ClientMessage:
    """Parse a JSON dict into the correct ``ClientMessage`` variant by
    its ``type`` discriminator.

    Raises ``pydantic.ValidationError`` on:
    - Missing ``type`` field
    - Unknown ``type`` value
    - Field type / value mismatches within the matched variant
      (e.g., ``SwitchModeMessage.mode="telepathy"``)

    The caller (``routes/chat.py``) catches ``ValidationError`` and
    sends back a typed ``ErrorEvent`` — it MUST NOT silently accept
    malformed messages.
    """
    return _CLIENT_ADAPTER.validate_python(raw)
