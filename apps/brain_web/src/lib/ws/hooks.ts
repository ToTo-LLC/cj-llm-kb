"use client";

import * as React from "react";

import { useSystemStore } from "@/lib/state/system-store";
import { BrainWebSocket } from "./client";

/**
 * useChatWebSocket — per-thread WS hook (STUB for Plan 07 Task 12).
 *
 * Today this only wires the WS CONNECTION state (open → "ok", close →
 * "reconnecting") into `system-store`. It does NOT forward server events
 * to the chat store — that wiring lands in Task 14 (auth+threads) and
 * Task 15 (stream-to-chat-store events).
 *
 * Callers pass a `threadId` + per-run `token`. When either is null we
 * skip opening the socket — the caller is still loading or the setup
 * wizard hasn't run yet.
 *
 * ## TODO (Task 14/15)
 *
 * - Thread server events through an `onEvent` callback / reducer that
 *   appends deltas to the chat store, surfaces tool calls, and pops
 *   mid-turn toasts on error events.
 * - Detect "reconnect exhausted" and flip to `"offline"` after the
 *   backoff hits its max attempt count (Task 14 gets the socket client
 *   to expose that signal first).
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
      onEvent: () => {
        // TODO(Task 14/15): dispatch server events into the chat store.
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
