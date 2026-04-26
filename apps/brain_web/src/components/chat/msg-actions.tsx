"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/state/chat-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useAppStore } from "@/lib/state/app-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";

/**
 * MsgActions — per-assistant-message action row.
 *
 * Four actions: "File to wiki", "Fork", "Copy", "Quote". Visible on
 * row hover AND always visible to keyboard focus so screen-reader /
 * keyboard users can reach them (hover-only affordances fail WCAG 2.2
 * AA 2.4.11 Focus Not Obscured). The focus-visible utility class +
 * ``group-hover:opacity-100`` combo delivers that pattern.
 *
 * Task 20 wired the FileToWiki + Fork dialogs through `dialogs-store`.
 * Copy writes real clipboard text. Quote stages the message body as
 * a markdown blockquote in ``chat-store.pendingQuote``; the composer
 * consumes it on its next render (issue #16).
 */

export interface MsgActionsProps {
  msg: ChatMessage;
  /** 0-based index of this message in the transcript — used as the
   *  ``turn_index`` the Fork dialog hands to ``brain_fork_thread``. */
  turnIndex?: number;
  className?: string;
}

export function MsgActions({
  msg,
  turnIndex,
  className,
}: MsgActionsProps): React.ReactElement {
  const openDialog = useDialogsStore((s) => s.open);
  const activeThreadId = useAppStore((s) => s.activeThreadId);
  const scope = useAppStore((s) => s.scope);
  const transcriptLength = useChatStore((s) => s.transcript.length);
  const setPendingQuote = useChatStore((s) => s.setPendingQuote);

  const onFile = React.useCallback(() => {
    const threadId = activeThreadId ?? "t-new";
    openDialog({
      kind: "file-to-wiki",
      msg: { body: msg.body, threadId },
      threadId,
      defaultDomain: scope[0],
    });
  }, [openDialog, activeThreadId, scope, msg.body]);

  const onFork = React.useCallback(() => {
    const threadId = activeThreadId;
    if (!threadId) {
      // No active thread yet — fork only makes sense once the source
      // thread exists on the server. Silently no-op.
      return;
    }
    const resolvedTurnIndex =
      typeof turnIndex === "number"
        ? turnIndex
        : Math.max(0, transcriptLength - 1);
    openDialog({
      kind: "fork",
      threadId,
      turnIndex: resolvedTurnIndex,
      summary: msg.body.slice(0, 220),
    });
  }, [openDialog, activeThreadId, turnIndex, transcriptLength, msg.body]);

  const onCopy = React.useCallback(() => {
    const text = msg.body;
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(text);
      return;
    }
    // eslint-disable-next-line no-console
    console.log("clipboard unavailable, would copy:", text);
  }, [msg.body]);

  const onQuote = React.useCallback(() => {
    // Issue #16: stage the message body in chat-store.pendingQuote.
    // The composer's effect picks it up on next render, prepends "> "
    // to each line, drops it ahead of any current draft, focuses the
    // textarea, and clears the pending value.
    setPendingQuote(msg.body);
  }, [setPendingQuote, msg.body]);

  return (
    <div
      className={cn(
        "flex items-center gap-1 opacity-0 transition-opacity",
        "group-hover:opacity-100 group-focus-within:opacity-100",
        className,
      )}
    >
      <button
        type="button"
        onClick={onFile}
        className="rounded-sm px-1.5 py-0.5 text-xs text-text-muted hover:bg-surface-2 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        File to wiki
      </button>
      <button
        type="button"
        onClick={onFork}
        className="rounded-sm px-1.5 py-0.5 text-xs text-text-muted hover:bg-surface-2 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        Fork
      </button>
      <button
        type="button"
        onClick={onCopy}
        className="rounded-sm px-1.5 py-0.5 text-xs text-text-muted hover:bg-surface-2 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        Copy
      </button>
      <button
        type="button"
        onClick={onQuote}
        className="rounded-sm px-1.5 py-0.5 text-xs text-text-muted hover:bg-surface-2 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        Quote
      </button>
    </div>
  );
}
