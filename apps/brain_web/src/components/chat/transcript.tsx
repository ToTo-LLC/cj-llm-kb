"use client";

import * as React from "react";

import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useDraftStore } from "@/lib/state/draft-store";
import { DraftEmpty } from "@/components/draft/draft-empty";

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
  const mode = useAppStore((s) => s.mode);
  const activeDoc = useDraftStore((s) => s.activeDoc);

  const scrollRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [transcript, streamingText]);

  const showEmpty = transcript.length === 0 && !activeThreadId;
  // Draft mode with no active doc always shows DraftEmpty instead of
  // the generic NewThreadEmpty — the starter prompts only make sense
  // once the user has picked a doc to draft on.
  const showDraftEmpty =
    mode === "draft" && activeDoc === null && transcript.length === 0;

  return (
    <div
      ref={scrollRef}
      className="flex h-full flex-col overflow-y-auto px-6"
      data-testid="transcript"
    >
      <div className="mx-auto w-full max-w-3xl">
        {showDraftEmpty ? (
          <DraftEmpty />
        ) : showEmpty ? (
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
