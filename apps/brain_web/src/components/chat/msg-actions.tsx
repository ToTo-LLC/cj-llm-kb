"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/state/chat-store";

/**
 * MsgActions — per-assistant-message action row.
 *
 * Four actions: "File to wiki", "Fork", "Copy", "Quote". Visible on
 * row hover AND always visible to keyboard focus so screen-reader /
 * keyboard users can reach them (hover-only affordances fail WCAG 2.2
 * AA 2.4.11 Focus Not Obscured). The focus-visible utility class +
 * ``group-hover:opacity-100`` combo delivers that pattern.
 *
 * Task 14 stubs:
 *   - File to wiki → console.log placeholder (Task 20 wires the
 *     FileToWiki dialog through dialogs-store).
 *   - Fork        → console.log placeholder (Task 20).
 *   - Copy        → real clipboard write via navigator.clipboard
 *     (with a safe fallback log when the API is unavailable, e.g.
 *     jsdom in tests).
 *   - Quote       → console.log placeholder (Task 15 wires the
 *     composer; Quote prepends ``> `` to the current composer text).
 */

export interface MsgActionsProps {
  msg: ChatMessage;
  className?: string;
}

export function MsgActions({
  msg,
  className,
}: MsgActionsProps): React.ReactElement {
  const onFile = React.useCallback(() => {
    // TODO(Task 20): open dialogs-store "file-to-wiki" dialog.
    // eslint-disable-next-line no-console
    console.log("TODO Task 20: file-to-wiki", { body: msg.body });
  }, [msg.body]);

  const onFork = React.useCallback(() => {
    // TODO(Task 20): open dialogs-store "fork" dialog.
    // eslint-disable-next-line no-console
    console.log("TODO Task 20: fork", { body: msg.body });
  }, [msg.body]);

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
    // TODO(Task 15): route into composer-store with "> " prefix.
    // eslint-disable-next-line no-console
    console.log("TODO Task 15: quote", { body: msg.body });
  }, [msg.body]);

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
