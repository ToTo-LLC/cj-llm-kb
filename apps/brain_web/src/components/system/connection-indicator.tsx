"use client";

import * as React from "react";

import { useSystemStore } from "@/lib/state/system-store";
import { cn } from "@/lib/utils";

/**
 * ConnectionIndicator — small pip rendered in the topbar while the WS is
 * in a non-OK state. Returns `null` when `connection === "ok"` so the
 * topbar layout is clean in the happy path.
 *
 * Read semantics are deliberate: this component subscribes directly to the
 * system-store rather than accepting a prop, so the topbar doesn't have to
 * be a client component that threads store state down.
 */

export function ConnectionIndicator() {
  const connection = useSystemStore((s) => s.connection);

  if (connection === "ok") return null;

  const label = connection === "reconnecting" ? "reconnecting…" : "offline";
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px]",
        connection === "reconnecting"
          ? "border-[var(--tt-amber,#b8860b)]/60 text-[var(--tt-amber,#b8860b)]"
          : "border-[var(--tt-red,#c0392b)]/60 text-[var(--tt-red,#c0392b)]",
      )}
      data-state={connection}
    >
      <span
        aria-hidden
        className={cn(
          "inline-block h-1.5 w-1.5 rounded-full",
          connection === "reconnecting"
            ? "animate-pulse bg-[var(--tt-amber,#b8860b)]"
            : "bg-[var(--tt-red,#c0392b)]",
        )}
      />
      <span>{label}</span>
    </div>
  );
}
