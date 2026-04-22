"use client";

import * as React from "react";

import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useDraftStore } from "@/lib/state/draft-store";
import { useSystemStore } from "@/lib/state/system-store";
import { BrainWebSocket } from "./client";
import type { ChatMode, ServerEvent } from "./events";

export interface UseChatWebSocket {
  /**
   * Send a ``turn_start`` to the server. Appends the user message to the
   * transcript optimistically, then sends over the wire. If the chat is
   * already streaming the call is a no-op and an ``invalid-state-turn``
   * toast is raised — users hit this when they mash Enter during the
   * middle of a stream. On successful send the ``pendingAttachedSources``
   * row clears so the next turn starts fresh.
   */
  sendTurnStart: (
    content: string,
    opts?: { mode?: ChatMode; attachedSources?: string[] },
  ) => void;
  /** Send a ``cancel_turn`` frame. Safe to call regardless of streaming. */
  cancelTurn: () => void;
  /**
   * Send a ``switch_mode`` frame AND update ``app-store.mode``. Guarded
   * twice: the reducer in ``app-store.setMode`` also short-circuits when
   * streaming, but the guard here keeps the WS send off the wire even if
   * a caller somehow bypassed the reducer. Mid-stream calls raise an
   * ``invalid-state-mode`` toast.
   */
  switchMode: (mode: ChatMode) => void;
  /**
   * Send a ``set_open_doc`` frame so the backend knows which document is
   * visible (Draft-mode contextual edits rely on this). ``null`` tells
   * the server no doc is open.
   */
  setOpenDoc: (path: string | null) => void;
}

/**
 * useChatWebSocket — per-thread WS hook (Plan 07 Task 15).
 *
 * Opens a ``BrainWebSocket`` to brain_api for ``threadId`` + ``token``
 * and fans server events out to:
 *   - ``chat-store.on*`` reducers (transcript, streaming, tool calls,
 *     patches).
 *   - ``system-store.setConnection`` for the live connection pip.
 *   - ``system-store.setMidTurn`` for ``error`` events with
 *     ``code === "invalid_state"`` — routed to the right toast kind by
 *     inspecting the message for the word "mode".
 *
 * Returns four typed send methods (see ``UseChatWebSocket``). Both
 * arguments must be non-null for the hook to open a socket — that's how
 * callers signal "we're not ready yet". A null-token call is a safe
 * no-op so component-level harnesses can mount the chat routes without
 * standing up the backend.
 *
 * Passing a new threadId or token rebuilds the socket via the dependency
 * array — that's important on thread switch because the backend scopes
 * WS paths to a single thread id. Tearing down cleanly cancels any
 * pending reconnect in the client.
 */
export function useChatWebSocket(
  threadId: string | null,
  token: string | null = null,
): UseChatWebSocket {
  const setConnection = useSystemStore((s) => s.setConnection);

  // The socket instance is owned by a ref so the returned send methods
  // stay stable across renders. ``useEffect`` ties its lifetime to
  // (threadId, token).
  const wsRef = React.useRef<BrainWebSocket | null>(null);

  React.useEffect(() => {
    if (!threadId || !token) return;

    const socket = new BrainWebSocket({
      threadId,
      token,
      onEvent: (event: ServerEvent) => {
        const store = useChatStore.getState();
        switch (event.type) {
          case "turn_start":
            store.onTurnStart(event);
            return;
          case "delta":
            store.onDelta(event);
            return;
          case "tool_call":
            store.onToolCall(event);
            return;
          case "tool_result":
            store.onToolResult(event);
            return;
          case "cost_update":
            store.onCostUpdate(event);
            return;
          case "patch_proposed":
            store.onPatchProposed(event);
            return;
          case "doc_edit_proposed":
            // Keep the chat-store hook firing for any per-message
            // metadata it might stash, then fan each edit into the
            // draft-store so the DocPanel banner lights up.
            store.onDocEditProposed(event);
            {
              const appendEdit = useDraftStore.getState().appendEdit;
              for (const edit of event.edits) {
                appendEdit(edit);
              }
            }
            return;
          case "turn_end":
            store.onTurnEnd(event);
            return;
          case "cancelled":
            store.onCancelled(event);
            return;
          case "error":
            // invalid_state is a soft error — the backend rejects the
            // frame (e.g. turn_start while already streaming) and the
            // UI should surface a mid-turn toast. Other error codes are
            // general failures that the chat-store handles (clears
            // streaming, etc.).
            if (event.code === "invalid_state") {
              const kind = event.message.toLowerCase().includes("mode")
                ? "invalid-state-mode"
                : "invalid-state-turn";
              useSystemStore.getState().setMidTurn(kind);
            } else {
              store.onError(event);
            }
            return;
          case "schema_version":
          case "thread_loaded":
            // schema_version mismatch is surfaced by the WS client via
            // onSchemaVersionMismatch; thread_loaded is a hydration
            // marker with no reducer today.
            return;
        }
      },
      onOpen: () => setConnection("ok"),
      onClose: (clean) => {
        // Manual close is our own teardown — don't flash "reconnecting".
        if (!clean) setConnection("reconnecting");
      },
    });

    socket.connect();
    wsRef.current = socket;

    return () => {
      socket.close();
      wsRef.current = null;
    };
  }, [threadId, token, setConnection]);

  // Send methods read the latest store state imperatively on every call
  // (rather than capturing it in useEffect deps) so they don't churn the
  // effect lifetime on every transcript mutation.
  return React.useMemo<UseChatWebSocket>(
    () => ({
      sendTurnStart: (content, opts) => {
        const chat = useChatStore.getState();
        if (chat.streaming) {
          useSystemStore.getState().setMidTurn("invalid-state-turn");
          return;
        }
        // Optimistic user-message append so the transcript reflects the
        // send immediately. The backend echoes ``turn_start`` which
        // appends the empty assistant placeholder.
        chat.sendUserMessage(content);
        wsRef.current?.send({
          type: "turn_start",
          content,
          mode: opts?.mode,
          attached_sources: opts?.attachedSources,
        });
        // Clear the attached-source row on successful send so the next
        // turn starts fresh. Keep this AFTER .send() — if the send
        // throws the attachments stay staged.
        if (opts?.attachedSources && opts.attachedSources.length > 0) {
          useChatStore.getState().clearAttachedSources();
        }
      },
      cancelTurn: () => {
        wsRef.current?.send({ type: "cancel_turn" });
      },
      switchMode: (mode) => {
        const chat = useChatStore.getState();
        if (chat.streaming) {
          useSystemStore.getState().setMidTurn("invalid-state-mode");
          return;
        }
        wsRef.current?.send({ type: "switch_mode", mode });
        useAppStore.getState().setMode(mode);
      },
      setOpenDoc: (path) => {
        wsRef.current?.send({ type: "set_open_doc", path });
      },
    }),
    [],
  );
}
