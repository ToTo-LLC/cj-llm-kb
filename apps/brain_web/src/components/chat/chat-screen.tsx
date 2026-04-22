"use client";

import * as React from "react";

import { ChatSubHeader } from "./chat-sub-header";
import { Composer } from "./composer";
import { Transcript } from "./transcript";
import { DocPanel } from "@/components/draft/doc-panel";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useDraftStore } from "@/lib/state/draft-store";
import { useChatWebSocket } from "@/lib/ws/hooks";

/**
 * ChatScreen (Plan 07 Task 15).
 *
 * Composition root for the /chat and /chat/<thread_id> routes. Owns the
 * per-thread WS lifecycle via ``useChatWebSocket`` and wires the
 * Composer's send/cancel/detach events back to the hook's typed send
 * methods.
 *
 * Active thread → ``threadId`` is non-null, WS opens, transcript
 *   hydrates via ``thread_loaded`` + replay events.
 * New thread → ``threadId === null``, WS stays closed, Transcript
 *   renders NewThreadEmpty until the backend creates the thread.
 *
 * The ``token`` prop is read by the server-component wrapper around the
 * chat route (``app/chat/page.tsx`` / ``app/chat/[thread_id]/page.tsx``)
 * from the per-run API token file. Null token → hook stays inert, so
 * the screen is safe to mount before setup completes.
 */

export interface ChatScreenProps {
  /** Active thread id or ``null`` for the new-thread route. */
  threadId: string | null;
  /** Per-run API token from ``.brain/run/api-secret.txt``. */
  token: string | null;
}

export function ChatScreen({
  threadId,
  token,
}: ChatScreenProps): React.ReactElement {
  const setActiveThreadId = useAppStore((s) => s.setActiveThreadId);
  const clearTranscript = useChatStore((s) => s.clearTranscript);
  const mode = useAppStore((s) => s.mode);
  const pendingAttachedSources = useChatStore(
    (s) => s.pendingAttachedSources,
  );
  const removeAttachedSource = useChatStore((s) => s.removeAttachedSource);

  const activeDoc = useDraftStore((s) => s.activeDoc);
  const showDocPanel = mode === "draft" && activeDoc !== null;

  const { sendTurnStart, cancelTurn } = useChatWebSocket(threadId, token);

  // Keep the URL-derived active-thread-id in sync with app-store so the
  // topbar / rail can react without digging into Next.js params. Clear
  // transcript on thread-id change to avoid bleeding state across threads.
  React.useEffect(() => {
    setActiveThreadId(threadId);
    clearTranscript();
    return () => {
      setActiveThreadId(null);
    };
  }, [threadId, setActiveThreadId, clearTranscript]);

  // Task 20 will feed real thread metadata (turn count, cost) from the
  // threads API. For now show the new-thread variant when no id is
  // present — the active-thread title hydrates off ``turn_end``'s
  // ``title`` field via Task 20's wiring.
  const subHeaderThread = threadId
    ? { title: "untitled thread", turns: 0, cost: 0 }
    : null;

  const handleSend = React.useCallback(
    (text: string) => {
      sendTurnStart(text, {
        mode,
        attachedSources:
          pendingAttachedSources.length > 0
            ? pendingAttachedSources
            : undefined,
      });
    },
    [sendTurnStart, mode, pendingAttachedSources],
  );

  const chatColumn = (
    <div className="flex h-full flex-col">
      <ChatSubHeader thread={subHeaderThread} />
      <div className="flex-1 overflow-hidden">
        <Transcript />
      </div>
      <Composer
        onSend={handleSend}
        onCancel={cancelTurn}
        onDetach={removeAttachedSource}
      />
    </div>
  );

  if (showDocPanel) {
    return (
      <main
        className="grid h-full"
        style={{ gridTemplateColumns: "1fr 420px" }}
      >
        {chatColumn}
        <DocPanel />
      </main>
    );
  }

  return <main className="h-full">{chatColumn}</main>;
}
