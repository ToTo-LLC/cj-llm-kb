// Typed WebSocket event + message shapes (Plan 07 Task 9).
//
// Mirrors ``brain_api.chat.events`` — the Pydantic models there are the
// canonical source. The discriminated union below MUST stay in sync with
// that module. Plan 07 Task 5 bumped SCHEMA_VERSION from "1" -> "2" to
// signal the addition of ``doc_edit_proposed`` (Draft-mode structured
// edits).
//
// A pinned client that receives a mismatched ``schema_version`` frame
// should disconnect and prompt the user to reload — silent downgrade
// hides breaking contract changes.

/**
 * Major-version pin. Matches ``SCHEMA_VERSION`` in
 * ``brain_api.chat.events``. Bumping this is a breaking contract change.
 */
export const SCHEMA_VERSION = "2" as const;

// ---------- Server -> client ----------

export interface SchemaVersionEvent {
  type: "schema_version";
  version: string;
}

export interface ThreadLoadedEvent {
  type: "thread_loaded";
  thread_id: string;
  mode: string;
  turn_count: number;
}

export interface TurnStartEvent {
  type: "turn_start";
  turn_number: number;
}

export interface DeltaEvent {
  type: "delta";
  text: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultEvent {
  type: "tool_result";
  id: string;
  data: Record<string, unknown>;
}

export interface CostUpdateEvent {
  type: "cost_update";
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cumulative_usd: number;
  cumulative_tokens_in: number;
}

export interface PatchProposedEvent {
  type: "patch_proposed";
  patch_id: string;
  target_path: string;
  reason: string;
}

export type DocEditOp = "insert" | "delete" | "replace";
export type DocEditAnchorKind = "line" | "text";

export interface DocEditAnchor {
  kind: DocEditAnchorKind;
  value: number | string;
}

export interface DocEdit {
  op: DocEditOp;
  anchor: DocEditAnchor;
  text: string;
}

export interface DocEditProposedEvent {
  type: "doc_edit_proposed";
  edits: DocEdit[];
}

export interface TurnEndEvent {
  type: "turn_end";
  turn_number: number;
  title: string | null;
}

export interface CancelledEvent {
  type: "cancelled";
  turn_number: number;
}

export interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
  recoverable: boolean;
}

/** The 12 server -> client event types. Keep in sync with ``chat/events.py``. */
export type ServerEvent =
  | SchemaVersionEvent
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
  | ErrorEvent;

const KNOWN_SERVER_EVENT_TYPES: ReadonlySet<ServerEvent["type"]> = new Set([
  "schema_version",
  "thread_loaded",
  "turn_start",
  "delta",
  "tool_call",
  "tool_result",
  "cost_update",
  "patch_proposed",
  "doc_edit_proposed",
  "turn_end",
  "cancelled",
  "error",
]);

/**
 * Validate + narrow an untyped WS payload to ``ServerEvent``.
 *
 * Rejects payloads missing the ``type`` discriminator and payloads with
 * a ``type`` value we don't recognise — a pinned client getting an
 * unknown type likely means the backend shipped a new event kind ahead
 * of a ``SCHEMA_VERSION`` bump. Fail loud so the mismatch is visible.
 *
 * The narrowing itself is a pass-through cast: the Pydantic layer on
 * the server validates fields per variant before emit, and
 * double-validating every frame on the client would cost latency on
 * every streamed delta. Structure mismatches that slip through show up
 * as render-time TypeScript errors downstream.
 */
export function parseServerEvent(raw: unknown): ServerEvent {
  if (typeof raw !== "object" || raw === null || !("type" in raw)) {
    throw new Error("WS event missing 'type' discriminator");
  }
  const candidate = raw as { type: unknown };
  if (typeof candidate.type !== "string") {
    throw new Error("WS event 'type' discriminator must be a string");
  }
  if (!KNOWN_SERVER_EVENT_TYPES.has(candidate.type as ServerEvent["type"])) {
    throw new Error(`unknown WS event type: ${candidate.type}`);
  }
  return raw as ServerEvent;
}

// ---------- Client -> server ----------

export type ChatMode = "ask" | "brainstorm" | "draft";

export interface TurnStartMessage {
  type: "turn_start";
  content: string;
  mode?: ChatMode;
  attached_sources?: string[];
}

export interface CancelTurnMessage {
  type: "cancel_turn";
}

export interface SwitchModeMessage {
  type: "switch_mode";
  mode: ChatMode;
}

export interface SetOpenDocMessage {
  type: "set_open_doc";
  path: string | null;
}

/** The 4 client -> server message types. Keep in sync with ``chat/events.py``. */
export type ClientMessage =
  | TurnStartMessage
  | CancelTurnMessage
  | SwitchModeMessage
  | SetOpenDocMessage;
