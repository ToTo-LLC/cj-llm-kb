"use client";

import * as React from "react";

import { Transcript } from "@/components/chat/transcript";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

/**
 * /chat — "new thread" route. No ``thread_id`` in the URL yet; the
 * Transcript renders NewThreadEmpty because the store is empty and
 * ``activeThreadId`` is null.
 *
 * On mount we clear any stale transcript left over from a previous
 * thread. Task 15 wires the POST /threads on first send and then
 * navigates to the ``/chat/<id>`` route (which opens the WS).
 */
export default function ChatPage(): React.ReactElement {
  const setActiveThreadId = useAppStore((s) => s.setActiveThreadId);
  const clearTranscript = useChatStore((s) => s.clearTranscript);

  React.useEffect(() => {
    setActiveThreadId(null);
    clearTranscript();
  }, [setActiveThreadId, clearTranscript]);

  return (
    <main className="flex h-full flex-col">
      <Transcript />
    </main>
  );
}
