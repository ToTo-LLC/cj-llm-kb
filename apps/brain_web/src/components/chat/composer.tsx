"use client";

import * as React from "react";
import {
  Layers,
  Lock,
  Paperclip,
  Send,
  Square,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import type { ChatMode } from "@/lib/ws/events";

/**
 * Composer (Plan 07 Task 15).
 *
 * Renders the bottom-of-chat input bar: a mode-aware placeholder, a
 * scope chip, a context-used meter, the attached-source chip row, and
 * the send/cancel button. State comes from two stores:
 *   - app-store: ``mode``, ``scope``
 *   - chat-store: ``streaming``, ``cumulativeTokensIn``,
 *                 ``pendingAttachedSources``
 *
 * Behaviour contract:
 *   - Enter submits; Shift+Enter inserts a newline.
 *   - Send is disabled when the trimmed text is empty OR streaming.
 *   - While streaming, the send button is replaced by a cancel button
 *     wired to ``onCancel``.
 *   - The textarea autosizes up to 220px — past that the browser adds a
 *     scrollbar.
 *
 * Callbacks (``onSend`` / ``onCancel`` / ``onDetach``) are passed in by
 * ``ChatScreen`` which wires them to the WS hook.
 */

const PLACEHOLDERS: Record<ChatMode, string> = {
  ask: "Ask the vault — it will cite what it uses…",
  brainstorm:
    "Bring a half-formed idea — brain will push back and co-develop…",
  draft: "Open a document and collaborate inline…",
};

const MAX_CONTEXT_TOKENS = 200_000;
const MAX_AUTOSIZE_PX = 220;

export interface ComposerProps {
  /** Called with the trimmed text when the user hits Enter or clicks Send. */
  onSend: (text: string) => void;
  /** Called when the user clicks the Cancel (stop) button during streaming. */
  onCancel: () => void;
  /** Called with a source id when the user clicks the "×" on an attach chip. */
  onDetach: (id: string) => void;
  /**
   * Override the streaming flag. Primarily for tests / Storybook; at
   * runtime the composer reads ``chat-store.streaming`` directly.
   */
  streaming?: boolean;
}

export function Composer({
  onSend,
  onCancel,
  onDetach,
  streaming: streamingProp,
}: ComposerProps): React.ReactElement {
  const mode = useAppStore((s) => s.mode);
  const scope = useAppStore((s) => s.scope);
  const streamingStore = useChatStore((s) => s.streaming);
  const streaming = streamingProp ?? streamingStore;
  const cumulativeTokensIn = useChatStore((s) => s.cumulativeTokensIn);
  const pendingAttachedSources = useChatStore(
    (s) => s.pendingAttachedSources,
  );
  const pendingQuote = useChatStore((s) => s.pendingQuote);
  const consumePendingQuote = useChatStore((s) => s.consumePendingQuote);

  const [text, setText] = React.useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

  // Issue #16: when ``msg-actions.tsx`` stages a quote via
  // ``setPendingQuote(body)``, this effect picks it up on next render,
  // formats each line as a markdown blockquote (``> ...``), prepends
  // it to whatever the user has already typed, focuses the textarea,
  // and consumes the pending value so the same quote isn't re-applied
  // on the next render. The blank line after the quote is the
  // markdown-standard separator between blockquote and the user's
  // own reply text.
  React.useEffect(() => {
    if (pendingQuote === null) return;
    const quoted =
      pendingQuote
        .split("\n")
        .map((line) => `> ${line}`)
        .join("\n") + "\n\n";
    setText((prev) => quoted + prev);
    consumePendingQuote();
    // Defer focus + autosize until after the setText flush.
    queueMicrotask(() => {
      textareaRef.current?.focus();
      const el = textareaRef.current;
      if (el) {
        el.style.height = "auto";
        el.style.height = `${Math.min(MAX_AUTOSIZE_PX, el.scrollHeight)}px`;
        // Park the cursor at the very end so the user can start
        // typing their reply immediately.
        const len = el.value.length;
        el.setSelectionRange(len, len);
      }
    });
  }, [pendingQuote, consumePendingQuote]);

  const placeholder = PLACEHOLDERS[mode];
  const ctxPct = Math.min(
    100,
    Math.round((cumulativeTokensIn / MAX_CONTEXT_TOKENS) * 100),
  );

  const scopeLabel =
    scope.length === 0
      ? "no scope"
      : scope.length === 1
        ? scope[0]
        : `${scope.length} domains`;
  const scopeIncludesPersonal = scope.includes("personal");

  const autosize = React.useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(MAX_AUTOSIZE_PX, el.scrollHeight)}px`;
  }, []);

  const sendIfReady = React.useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;
    onSend(trimmed);
    setText("");
    // Run after React flushes the clear so scrollHeight recomputes.
    queueMicrotask(autosize);
  }, [text, streaming, onSend, autosize]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendIfReady();
    }
  };

  const sendDisabled = streaming || text.trim() === "";

  return (
    <div className="border-t border-hairline bg-surface-0 px-4 py-3">
      <div className="mx-auto w-full max-w-3xl">
        {pendingAttachedSources.length > 0 && (
          <div
            className="mb-2 flex flex-wrap gap-1.5"
            aria-label="Attached sources"
          >
            {pendingAttachedSources.map((id) => (
              <span
                key={id}
                className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-xs text-foreground"
              >
                <span className="max-w-[18rem] truncate">{id}</span>
                <button
                  type="button"
                  onClick={() => onDetach(id)}
                  className="inline-flex h-4 w-4 items-center justify-center rounded-full text-text-muted hover:bg-surface-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  aria-label={`Detach ${id}`}
                >
                  <X className="h-3 w-3" aria-hidden="true" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div
          className={cn(
            "flex flex-col gap-2 rounded-lg border border-hairline bg-surface-1 p-3",
            "focus-within:border-ring focus-within:ring-1 focus-within:ring-ring",
          )}
        >
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              autosize();
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            aria-label="Message brain"
            className="min-h-[24px] w-full resize-none bg-transparent text-sm text-foreground placeholder:text-text-muted focus:outline-none"
          />

          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-xs text-foreground",
                  `dom-${scope[0] ?? "research"}`,
                )}
                aria-label={`Scope: ${scopeLabel}`}
              >
                <Layers className="h-3 w-3" aria-hidden="true" />
                <span>{scopeLabel}</span>
                {scopeIncludesPersonal && (
                  <Lock className="h-3 w-3" aria-hidden="true" />
                )}
              </span>

              <button
                type="button"
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label="Attach"
                title="Attach (drag a file in, or paste — Task 17 wires the picker)"
              >
                <Paperclip className="h-4 w-4" aria-hidden="true" />
              </button>

              <div
                className="flex items-center gap-2 text-xs text-text-muted"
                title={`~${cumulativeTokensIn.toLocaleString()} of ${
                  MAX_CONTEXT_TOKENS / 1000
                }k tokens`}
              >
                <span>context</span>
                <div
                  className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-2"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={ctxPct}
                  aria-label="Context used"
                >
                  <div
                    className="h-full bg-foreground/60"
                    style={{ width: `${ctxPct}%` }}
                  />
                </div>
                <span>≈{ctxPct}%</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {streaming ? (
                <Button
                  type="button"
                  size="icon"
                  variant="destructive"
                  onClick={onCancel}
                  aria-label="Cancel"
                  title="Cancel"
                >
                  <Square className="h-4 w-4" aria-hidden="true" />
                </Button>
              ) : (
                <Button
                  type="button"
                  size="icon"
                  disabled={sendDisabled}
                  onClick={sendIfReady}
                  aria-label="Send"
                  title="Send"
                >
                  <Send className="h-4 w-4" aria-hidden="true" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
