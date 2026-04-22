"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import type { ChatMode } from "@/lib/ws/events";

/**
 * NewThreadEmpty — the empty-state shown on /chat (no thread_id)
 * before the user sends their first message.
 *
 * Reads ``mode`` + ``scope`` from app-store so the displayed starters
 * match the user's current intent. Clicking a starter optimistically
 * appends a user message via ``chat-store.sendUserMessage`` — Task 15
 * adds the WS TurnStart send once the socket-send path is wired.
 *
 * Starter prompt copy is locked by the plan (see lines 2817-2835).
 * Mode description + tone come from the v3 design. Scope chips are
 * plain text slugs for Task 14; Task 19 swaps in the typed domain
 * metadata.
 */

const STARTERS: Record<ChatMode, readonly string[]> = {
  ask: [
    "What has the vault said this year about silent-buyer patterns?",
    "Cross-reference Fisher-Ury with the April Helios call.",
    "Summarize concepts tagged #decision-theory · last 30 days.",
  ],
  brainstorm: [
    "Argue with me about compounding curiosity as a meta-practice.",
    "What am I missing in the deal-stall pattern synthesis?",
    "Propose three angles I haven't considered on tactical empathy.",
  ],
  draft: [
    "Rewrite the intro to fisher-ury-interests.md for a non-expert reader.",
    "Draft a board-memo section on Q2 research threads.",
    "Turn the silent-buyer synthesis into a short public post.",
  ],
} as const;

const MODE_META: Record<ChatMode, { lead: string; desc: string; toneVar: string }> = {
  ask: {
    lead: "Ask",
    desc: "cite from the vault",
    toneVar: "var(--tt-cyan)",
  },
  brainstorm: {
    lead: "Brainstorm",
    desc: "push back, propose notes",
    toneVar: "var(--tt-cream)",
  },
  draft: {
    lead: "Draft",
    desc: "collaborate on a document",
    toneVar: "var(--tt-sage)",
  },
};

export function NewThreadEmpty(): React.ReactElement {
  const mode = useAppStore((s) => s.mode);
  const scope = useAppStore((s) => s.scope);
  // Read the current action imperatively so the store spy in unit
  // tests wins (useChatStore.setState({ sendUserMessage: spy })).
  const meta = MODE_META[mode];
  const starters = STARTERS[mode];

  const handleStarter = React.useCallback((prompt: string) => {
    useChatStore.getState().sendUserMessage(prompt);
  }, []);

  return (
    <section
      className="mx-auto flex max-w-xl flex-col gap-6 py-12"
      aria-label="New thread"
    >
      <header className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-wide text-text-muted">
          New thread
        </p>
        <h1 className="text-2xl font-semibold text-foreground">
          What are we working on?
        </h1>
      </header>

      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span className="w-14 shrink-0 uppercase tracking-wide">Scope</span>
          <div className="flex flex-wrap gap-1.5">
            {scope.length === 0 ? (
              <span className="text-text-dim">
                No domain selected — pick one in the topbar.
              </span>
            ) : (
              scope.map((slug) => (
                <span
                  key={slug}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border border-hairline px-2 py-0.5 text-xs",
                    `dom-${slug}`,
                  )}
                >
                  {slug}
                </span>
              ))
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="w-14 shrink-0 uppercase tracking-wide text-text-muted">
            Mode
          </span>
          <span
            className="inline-flex items-center gap-2"
            style={{ ["--mode-tone" as string]: meta.toneVar }}
          >
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: meta.toneVar }}
              aria-hidden="true"
            />
            <strong className="text-foreground">{meta.lead}</strong>
            <span className="text-text-muted">· {meta.desc}</span>
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-wide text-text-muted">
          Starter prompts
        </p>
        <div className="flex flex-col gap-2">
          {starters.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => handleStarter(prompt)}
              className="flex items-center gap-2 rounded-md border border-hairline bg-surface-1 px-3 py-2 text-left text-sm text-foreground hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <span className="text-text-muted">“</span>
              <span className="flex-1">{prompt}</span>
              <span className="text-text-muted" aria-hidden="true">
                ›
              </span>
            </button>
          ))}
        </div>
      </div>

      <p className="text-xs text-text-muted">
        Your first message becomes the thread title. brain uses{" "}
        <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[10px]">
          BRAIN.md
        </code>{" "}
        as its system prompt.
      </p>
    </section>
  );
}
