"use client";

import * as React from "react";

import { useChatStore } from "@/lib/state/chat-store";
import { useSystemStore } from "@/lib/state/system-store";
import { BrainWebSocket } from "./client";
import type { ServerEvent } from "./events";

/**
 * useChatWebSocket — per-thread WS hook (Plan 07 Task 14).
 *
 * Opens a ``BrainWebSocket`` to brain_api for ``threadId`` + ``token``
 * and fans server events out to:
 *   - ``chat-store.on*`` reducers (transcript, streaming, tool calls,
 *     patches).
 *   - ``system-store.setConnection`` for the live connection pip.
 *
 * Both arguments must be non-null for the hook to open a socket —
 * that's how callers signal "we're not ready yet". Task 15 wires the
 * token flow via a server-component wrapper that reads the per-run
 * token from ``.brain/run/token``; today a null-token call is a safe
 * no-op so component-level harnesses can mount the chat routes
 * without standing up the backend.
 *
 * Passing a new threadId or token rebuilds the socket via the
 * dependency array — that's important on thread switch because the
 * backend scopes WS paths to a single thread id. Tearing down cleanly
 * cancels any pending reconnect in the client.
 */
export function useChatWebSocket(
  threadId: string | null,
  token: string | null = null,
): void {
  const setConnection = useSystemStore((s) => s.setConnection);

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
            store.onDocEditProposed(event);
            return;
          case "turn_end":
            store.onTurnEnd(event);
            return;
          case "cancelled":
            store.onCancelled(event);
            return;
          case "error":
            store.onError(event);
            return;
          case "schema_version":
          case "thread_loaded":
            // schema_version mismatch is surfaced by the WS client via
            // onSchemaVersionMismatch; thread_loaded is a hydration
            // marker with no reducer today. Task 15 may light up a
            // "thread hydrated" toast on thread_loaded — leaving the
            // no-op here until that UX decision lands.
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

    return () => {
      socket.close();
    };
  }, [threadId, token, setConnection]);
}
