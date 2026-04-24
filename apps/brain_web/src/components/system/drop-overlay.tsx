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
 * `aria-hidden` + the `inert` attribute and Tailwind `pointer-events-none`
 * / opacity utilities. `aria-hidden` alone does not pull inner headings
 * out of the a11y heading tree in every browser, so the hidden state also
 * sets `inert` which (per WHATWG) takes the subtree out of the tab order,
 * removes it from the accessibility tree entirely, and ignores pointer +
 * focus events. Supported in every Chromium >= 102 and Safari >= 15.5.
 *
 * We do NOT unmount on hide: keeping the overlay mounted lets a fade
 * animation run in both directions without `transitionend` glue, and
 * guarantees drag targets underneath aren't briefly captured while React
 * reconciles the tree.
 *
 * The `data-testid` hook exists so component tests can assert
 * `aria-hidden` + `inert` toggle correctly; production CSS does the
 * visual gating.
 */

export interface DropOverlayProps {
  visible: boolean;
}

export function DropOverlay({ visible }: DropOverlayProps) {
  // React 18.3 type defs don't officially ship `inert` on HTMLAttributes;
  // the runtime (+ browsers) accept it fine. We conditionally spread so
  // the attribute is simply absent when visible — avoids React re-emitting
  // `inert={false}` which is a noop either way.
  const inertProp = visible
    ? {}
    : ({ inert: "" } as unknown as Record<string, string>);

  return (
    <div
      data-testid="drop-overlay"
      aria-hidden={visible ? "false" : "true"}
      {...inertProp}
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
