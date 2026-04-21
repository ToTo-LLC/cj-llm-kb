"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * DropOverlay — full-screen overlay rendered while a file is being dragged
 * into the window. Wired to `system-store.draggingFile` by
 * `<SystemOverlays />`; the drag handlers live on `<AppShell />` so any
 * drag target inside the app fires the overlay once.
 *
 * ## Visibility idiom
 *
 * The overlay stays in the DOM in both states — the `visible` prop flips
 * the `aria-hidden` flag and Tailwind `pointer-events-none` / opacity
 * utilities. We do NOT unmount on hide: keeping the overlay mounted lets a
 * fade animation run in both directions without `transitionend` glue, and
 * guarantees drag targets underneath aren't briefly captured while React
 * reconciles the tree.
 *
 * The `data-testid` hook exists so component tests can assert
 * `aria-hidden` toggles correctly; production CSS does the visual gating.
 */

export interface DropOverlayProps {
  visible: boolean;
}

export function DropOverlay({ visible }: DropOverlayProps) {
  return (
    <div
      data-testid="drop-overlay"
      aria-hidden={visible ? "false" : "true"}
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-150",
        visible
          ? "bg-black/50 opacity-100"
          : "pointer-events-none bg-black/0 opacity-0",
      )}
    >
      <div className="flex flex-col items-center gap-4 rounded-xl border border-[var(--hairline,currentColor)] bg-[var(--surface-2,#0f0f10)] px-10 py-8 text-center shadow-2xl">
        <div
          aria-hidden
          className="h-10 w-10 rounded-full"
          style={{ background: "var(--tt-grad-cream-cyan, #e8e0d6)" }}
        />
        <h2 className="text-lg font-medium text-[var(--text,#fff)]">
          Drop to attach
        </h2>
        <p className="max-w-xs text-sm text-[var(--text-muted,#aaa)]">
          brain will ingest and summarize before filing.
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {["pdf", "txt · md", "eml", "url"].map((c) => (
            <span
              key={c}
              className="rounded-full border border-[var(--hairline,currentColor)] px-3 py-1 text-xs text-[var(--text-muted,#aaa)]"
            >
              {c}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
