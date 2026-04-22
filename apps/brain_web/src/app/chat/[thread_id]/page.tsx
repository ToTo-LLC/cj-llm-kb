"use client";

import * as React from "react";

import { Transcript } from "@/components/chat/transcript";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useChatWebSocket } from "@/lib/ws/hooks";

/**
 * /chat/<thread_id> — existing-thread route. Opens the WS for the
 * given thread id, binds server events to the chat-store via
 * ``useChatWebSocket``.
 *
 * Next.js 15 passes ``params`` as a Promise — unwrap with
 * ``React.use`` in a client component. Clearing the transcript on
 * thread change keeps the store shape correct when the user
 * navigates between threads without a full reload.
 *
 * Task 14 accepts an optional ``token`` (null by default) so the
 * hook is inert until Task 15 plumbs the real per-run token through
 * a server component wrapper. That keeps the component renderable in
 * isolation for the Task 23 e2e harness.
 */

type Params = { thread_id: string };

interface ChatThreadPageProps {
  params: Promise<Params>;
}

export default function ChatThreadPage({
  params,
}: ChatThreadPageProps): React.ReactElement {
  const { thread_id } = React.use(params);

  const setActiveThreadId = useAppStore((s) => s.setActiveThreadId);
  const clearTranscript = useChatStore((s) => s.clearTranscript);

  React.useEffect(() => {
    setActiveThreadId(thread_id);
    clearTranscript();
    return () => {
      setActiveThreadId(null);
    };
  }, [thread_id, setActiveThreadId, clearTranscript]);

  // Task 15 will provide the token via a server-component wrapper.
  // Passing null keeps the hook inert (see lib/ws/hooks.ts), so this
  // route is safe to mount in tests.
  useChatWebSocket(thread_id, null);

  return (
    <main className="flex h-full flex-col">
      <Transcript />
    </main>
  );
}
