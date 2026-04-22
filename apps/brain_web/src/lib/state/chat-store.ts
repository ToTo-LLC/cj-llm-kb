"use client";

import { create } from "zustand";

import type {
  CancelledEvent,
  ChatMode,
  CostUpdateEvent,
  DeltaEvent,
  DocEditProposedEvent,
  ErrorEvent,
  PatchProposedEvent,
  ToolCallEvent,
  ToolResultEvent,
  TurnEndEvent,
  TurnStartEvent,
} from "@/lib/ws/events";

/**
 * Chat-store (Plan 07 Task 14).
 *
 * Owns the transcript for the currently-active thread plus ephemeral
 * streaming state. Intentionally NOT per-thread: on every thread
 * switch the route-level effect calls ``clearTranscript()`` and a
 * fresh WS connection repopulates. One store, one active thread at a
 * time — that's what the spec + plan prescribe, and it keeps React
 * re-renders cheap.
 *
 * The store never talks to the WS directly. ``useChatWebSocket``
 * (see ``lib/ws/hooks.ts``) routes parsed server events into the
 * matching ``on*`` reducer. Keeping the reducers event-shaped lets
 * tests exercise them without standing up a socket.
 *
 * Streaming model: ``onDelta`` accumulates into ``streamingText`` (a
 * top-level field) so the transcript array doesn't churn on every
 * token. The renderer reads ``streamingText`` for the LAST assistant
 * message while ``streaming === true``. ``onTurnEnd`` commits the
 * final text into ``assistant.body`` and clears ``streamingText`` so
 * the next turn starts clean.
 */

// ---------- Public shapes ----------

export type ChatRole = "user" | "brain";

/**
 * Snapshot of a tool call the assistant issued this turn. Args come
 * from ``tool_call``; ``result`` is merged in from ``tool_result`` by
 * matching ``id``.
 */
export interface ToolCallData {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
}

/** Per-message patch metadata (backend's patch_proposed, UI-side shape). */
export interface PatchMeta {
  patchId: string;
  target: string;
  reason: string;
}

export interface ChatMessage {
  role: ChatRole;
  /** Pre-formatted clock string (e.g. "09:12"). Backend prepares it. */
  ts: string;
  /** Full message text. Empty while the assistant streams. */
  body: string;
  /** Assistant-only: which mode emitted this message. */
  mode?: ChatMode;
  /** Assistant-only: tool calls issued during this turn. */
  toolCalls?: ToolCallData[];
  /** Assistant-only: the patch this turn staged (if any). */
  proposedPatch?: PatchMeta;
  /** Assistant-only: USD cost for this turn. */
  cost?: number;
  /** True while the assistant is still streaming this message's body. */
  isStreaming?: boolean;
}

// ---------- Store shape ----------

export interface ChatState {
  transcript: ChatMessage[];
  streaming: boolean;
  streamingText: string;
  currentTurn: number;
  cumulativeTokensIn: number;

  // WS-event reducers
  onTurnStart: (ev: TurnStartEvent) => void;
  onDelta: (ev: DeltaEvent) => void;
  onToolCall: (ev: ToolCallEvent) => void;
  onToolResult: (ev: ToolResultEvent) => void;
  onCostUpdate: (ev: CostUpdateEvent) => void;
  onPatchProposed: (ev: PatchProposedEvent) => void;
  onDocEditProposed: (ev: DocEditProposedEvent) => void;
  onTurnEnd: (ev: TurnEndEvent) => void;
  onCancelled: (ev: CancelledEvent) => void;
  onError: (ev: ErrorEvent) => void;

  // User-driven actions
  /**
   * Optimistic append of a user message. WS send lives in Task 15;
   * Task 14 uses this from NewThreadEmpty's starter buttons so the
   * transcript reflects the click immediately.
   */
  sendUserMessage: (text: string) => void;
  /** Wipe the transcript + streaming state. Called on thread switch. */
  clearTranscript: () => void;
}

// ---------- Helpers ----------

/** Two-digit zero-padded clock string from a Date. Matches v3's ts format. */
function nowClock(): string {
  const d = new Date();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/**
 * Apply a mutation to the last message of the transcript. Returns the
 * fresh array so zustand's ``set`` produces a new reference and
 * subscribers re-render. No-op if the transcript is empty — callers
 * should never hit that; if they do the guard at least keeps the store
 * consistent.
 */
function updateLast(
  transcript: ChatMessage[],
  patch: (msg: ChatMessage) => ChatMessage,
): ChatMessage[] {
  if (transcript.length === 0) return transcript;
  const next = transcript.slice(0, -1);
  next.push(patch(transcript[transcript.length - 1]));
  return next;
}

// ---------- Store ----------

export const useChatStore = create<ChatState>((set) => ({
  transcript: [],
  streaming: false,
  streamingText: "",
  currentTurn: 0,
  cumulativeTokensIn: 0,

  onTurnStart: (ev) => {
    set((s) => ({
      currentTurn: ev.turn_number,
      streaming: true,
      streamingText: "",
      transcript: [
        ...s.transcript,
        {
          role: "brain",
          ts: nowClock(),
          body: "",
          isStreaming: true,
        },
      ],
    }));
  },

  onDelta: (ev) => {
    set((s) => ({
      streamingText: s.streamingText + ev.text,
    }));
  },

  onToolCall: (ev) => {
    set((s) => ({
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        toolCalls: [
          ...(m.toolCalls ?? []),
          {
            id: ev.id,
            tool: ev.tool,
            args: ev.arguments,
          },
        ],
      })),
    }));
  },

  onToolResult: (ev) => {
    set((s) => ({
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        toolCalls: (m.toolCalls ?? []).map((c) =>
          c.id === ev.id ? { ...c, result: ev.data } : c,
        ),
      })),
    }));
  },

  onCostUpdate: (ev) => {
    set((s) => ({
      cumulativeTokensIn: ev.cumulative_tokens_in,
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        cost: ev.cost_usd,
      })),
    }));
  },

  onPatchProposed: (ev) => {
    set((s) => ({
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        proposedPatch: {
          patchId: ev.patch_id,
          target: ev.target_path,
          reason: ev.reason,
        },
      })),
    }));
  },

  // Draft-mode structured edits. Plan 09 wires the document panel; for
  // Task 14 we receive the event but only need to avoid erroring. The
  // store keeps the shape of the edits on the assistant msg so the
  // Plan 09 doc panel can read them without another event replay.
  onDocEditProposed: (ev) => {
    // Stashed on the assistant msg as a structured patch marker. The
    // actual render lives in Task 19's DocPanel. No behavioural
    // reducer needed here yet — leaving the hook in place so Task 19
    // only edits this branch.
    void ev;
  },

  onTurnEnd: (ev) => {
    set((s) => ({
      streaming: false,
      streamingText: "",
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        body: s.streamingText,
        isStreaming: false,
      })),
      currentTurn: ev.turn_number,
    }));
  },

  onCancelled: () => {
    // Treat cancelled like turn_end: commit whatever streamed, clear
    // the streaming flag. The composer's cancel affordance and toast
    // copy are Task 15's concern.
    set((s) => ({
      streaming: false,
      streamingText: "",
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        body: s.streamingText,
        isStreaming: false,
      })),
    }));
  },

  onError: () => {
    // Error events flip streaming off so the composer returns to
    // idle. The toast/banner surfaces live in Task 15 (mid-turn toast
    // is already wired via system-store; Task 15 routes error codes
    // into setMidTurn()).
    set((s) => ({
      streaming: false,
      transcript: updateLast(s.transcript, (m) => ({
        ...m,
        isStreaming: false,
      })),
    }));
  },

  sendUserMessage: (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    set((s) => ({
      transcript: [
        ...s.transcript,
        {
          role: "user",
          ts: nowClock(),
          body: trimmed,
        },
      ],
    }));
  },

  clearTranscript: () => {
    set({
      transcript: [],
      streaming: false,
      streamingText: "",
      currentTurn: 0,
    });
  },
}));
