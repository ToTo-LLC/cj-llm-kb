"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import type { ToolCallData } from "@/lib/state/chat-store";

/**
 * ToolCall — collapsible card for an assistant-issued tool invocation.
 *
 * Visual contract (v3):
 *   - Head: tool name + one-line args summary + caret icon.
 *   - Body (when open): hit rows for search-like tools — score (2
 *     decimals), path (monospace), snippet (dim). For non-search
 *     tools with no ``hits`` field we simply leave the body empty;
 *     Task 19 adds tool-specific body renderers.
 *
 * Starts collapsed by default. Clicking the head toggles. Renders as
 * a button so keyboard users reach it via Tab; ``aria-expanded``
 * mirrors the state so AT announces open/close.
 */

interface SearchHit {
  path: string;
  snippet: string;
  score: number;
}

export interface ToolCallProps {
  call: ToolCallData;
  /** Force-open for Storybook-style fixtures; default false. */
  defaultOpen?: boolean;
}

/** Render args as ``k: "v", k2: 42`` one-liner (JSON-stringified values). */
function argSummary(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
    .join(", ");
}

function isSearchHit(value: unknown): value is SearchHit {
  if (typeof value !== "object" || value === null) return false;
  const h = value as Record<string, unknown>;
  return (
    typeof h.path === "string" &&
    typeof h.snippet === "string" &&
    typeof h.score === "number"
  );
}

export function ToolCall({
  call,
  defaultOpen = false,
}: ToolCallProps): React.ReactElement {
  const [open, setOpen] = React.useState(defaultOpen);
  const argStr = argSummary(call.args);
  const hitsRaw = (call.result as { hits?: unknown } | undefined)?.hits;
  const hits = Array.isArray(hitsRaw) ? hitsRaw.filter(isSearchHit) : [];

  return (
    <div
      className={cn(
        "rounded-md border border-hairline bg-surface-1 text-sm mb-2",
        open && "bg-surface-2",
      )}
    >
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-medium text-foreground">{call.tool}</span>
        {argStr && (
          <span className="text-text-muted truncate">({argStr})</span>
        )}
        <span
          className={cn(
            "ml-auto text-text-muted transition-transform",
            open && "rotate-90",
          )}
          aria-hidden="true"
        >
          ›
        </span>
      </button>
      {open && hits.length > 0 && (
        <ul className="divide-y divide-hairline px-3 pb-2">
          {hits.map((h, i) => (
            <li
              key={i}
              className="flex items-baseline gap-2 py-1.5"
            >
              <span className="shrink-0 tabular-nums text-text-muted">
                {h.score.toFixed(2)}
              </span>
              <span className="shrink-0 font-mono text-xs text-foreground">
                {h.path}
              </span>
              <span className="truncate text-text-dim">{h.snippet}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
