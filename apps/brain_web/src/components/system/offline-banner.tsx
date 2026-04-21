"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * OfflineBanner — full-width system banner shown above the app grid while
 * the WS is offline or reconnecting. Copy matches the v3 design.
 *
 * The two visual states map to `system-store.connection`:
 *   - `"reconnecting"` — amber pip, "Reconnecting…" lead.
 *   - `"offline"`      — red pip, "brain is offline." lead.
 *
 * `ok` is never rendered — the compositor hides this component in that
 * case — but we still gate in the component for defensive reasons so
 * direct callers can pass any state safely.
 */

export type OfflineBannerState = "offline" | "reconnecting";

export interface OfflineBannerProps {
  state: OfflineBannerState;
  /** Optional click handler for the "Retry now" affordance. */
  onRetry?: () => void;
}

export function OfflineBanner({ state, onRetry }: OfflineBannerProps) {
  const isOffline = state === "offline";
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex w-full items-center gap-3 border-b px-4 py-2 text-xs",
        isOffline
          ? "border-[var(--tt-red,#c0392b)] bg-[var(--tt-red,#c0392b)]/10 text-[var(--text)]"
          : "border-[var(--tt-amber,#b8860b)] bg-[var(--tt-amber,#b8860b)]/10 text-[var(--text)]",
      )}
      data-state={state}
    >
      <span
        aria-hidden
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          isOffline
            ? "bg-[var(--tt-red,#c0392b)]"
            : "animate-pulse bg-[var(--tt-amber,#b8860b)]",
        )}
      />
      <div className="flex flex-1 flex-wrap items-baseline gap-x-2">
        {isOffline ? (
          <>
            <strong className="font-medium">brain is offline.</strong>
            <span className="text-[var(--text-muted,inherit)]">
              Your last turn didn&apos;t send. Reads from vault still work.
            </span>
          </>
        ) : (
          <>
            <strong className="font-medium">Reconnecting…</strong>
            <span className="text-[var(--text-muted,inherit)]">
              Dropped connection to the local runtime. Queued turns will resend.
            </span>
          </>
        )}
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md border border-[var(--hairline,currentColor)] px-2 py-1 text-[11px] hover:bg-[var(--surface-3,transparent)]"
      >
        Retry now
      </button>
    </div>
  );
}
