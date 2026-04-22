"use client";

import * as React from "react";

import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

import { Message } from "./message";
import { NewThreadEmpty } from "./new-thread-empty";

/**
 * Transcript — scrollable container that renders the chat-store's
 * transcript array. Auto-scrolls to the bottom whenever the
 * transcript grows OR the streaming text updates, so the streaming
 * caret stays visible without the user having to chase it.
 *
 * Empty + no active thread → NewThreadEmpty. Empty + active thread
 * means the socket hasn't hydrated yet (Task 14 intentionally shows
 * a bare container while we wait; Task 15 adds a skeleton).
 */

export function Transcript(): React.ReactElement {
  const transcript = useChatStore((s) => s.transcript);
  const streaming = useChatStore((s) => s.streaming);
  const streamingText = useChatStore((s) => s.streamingText);
  const activeThreadId = useAppStore((s) => s.activeThreadId);

  const scrollRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [transcript, streamingText]);

  const showEmpty = transcript.length === 0 && !activeThreadId;

  return (
    <div
      ref={scrollRef}
      className="flex h-full flex-col overflow-y-auto px-6"
      data-testid="transcript"
    >
      <div className="mx-auto w-full max-w-3xl">
        {showEmpty ? (
          <NewThreadEmpty />
        ) : (
          transcript.map((msg, i) => {
            const isLast = i === transcript.length - 1;
            const isLastStreaming = isLast && streaming && msg.role === "brain";
            return (
              <Message
                key={i}
                msg={msg}
                streamingText={isLastStreaming ? streamingText : undefined}
                isStreaming={isLastStreaming}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
