"use client";

import * as React from "react";
import { AlertTriangle, Clock, Layers, X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * MidTurnToast — non-blocking banner shown inside the chat stream when the
 * current turn hits a recoverable or soft-invalid state. Covers five fixed
 * kinds; copy is locked by the design system (do NOT rewrite these strings
 * without a plan update — Task 15 WS wiring depends on them).
 *
 * Auto-dismiss is NOT built in here; `<SystemOverlays />` pops the toast in
 * response to `turn_start` / `turn_end` events (Task 15).
 */

export type MidTurnKind =
  | "rate-limit"
  | "context-full"
  | "tool-failed"
  | "invalid-state-turn"
  | "invalid-state-mode";

interface MidTurnCopy {
  lead: string;
  msg: string;
  icon: "alert" | "layers" | "x" | "clock";
  tone: "warn" | "danger";
}

/**
 * COPY MAP — single source of truth for mid-turn issue strings. The unit
 * tests pin each of these; bumping copy requires a plan update + test
 * update in lock-step.
 */
const COPY: Record<MidTurnKind, MidTurnCopy> = {
  "rate-limit": {
    lead: "Rate limit.",
    msg: "Anthropic slowed us down. Retrying in 8s — or retry now.",
    icon: "alert",
    tone: "warn",
  },
  "context-full": {
    lead: "Context full.",
    msg: "Compact the thread to keep going, or start a fresh one.",
    icon: "layers",
    tone: "warn",
  },
  "tool-failed": {
    lead: "Tool failed.",
    msg: "A tool couldn't complete — the vault path may not be reachable.",
    icon: "x",
    tone: "danger",
  },
  "invalid-state-turn": {
    lead: "Finish this turn first.",
    msg: "Wait for it to complete, or cancel to start fresh.",
    icon: "clock",
    tone: "warn",
  },
  "invalid-state-mode": {
    lead: "Can't switch mid-turn.",
    msg: "Mode change takes effect on the next turn.",
    icon: "alert",
    tone: "warn",
  },
};

const ICONS = {
  alert: AlertTriangle,
  layers: Layers,
  x: X,
  clock: Clock,
} as const;

export interface MidTurnToastProps {
  kind: MidTurnKind;
  /** Optional dismiss handler; when omitted, the Dismiss button is hidden. */
  onDismiss?: () => void;
  /** Optional retry handler; when omitted, the Retry button is hidden. */
  onRetry?: () => void;
}

export function MidTurnToast({ kind, onDismiss, onRetry }: MidTurnToastProps) {
  const copy = COPY[kind];
  const IconComponent = ICONS[copy.icon];

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-auto mx-auto my-2 flex max-w-3xl items-center gap-3 rounded-md border px-3 py-2 text-sm shadow-sm",
        copy.tone === "danger"
          ? "border-[var(--tt-red,#c0392b)]/60 bg-[var(--tt-red,#c0392b)]/10"
          : "border-[var(--tt-amber,#b8860b)]/60 bg-[var(--tt-amber,#b8860b)]/10",
      )}
      data-kind={kind}
      data-tone={copy.tone}
    >
      <IconComponent className="h-4 w-4 shrink-0" aria-hidden />
      <div className="flex flex-1 flex-wrap items-baseline gap-x-2">
        <div className="font-medium">{copy.lead}</div>
        <div className="text-[var(--text-muted,inherit)]">{copy.msg}</div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-[var(--hairline,currentColor)] px-2 py-1 text-[11px] hover:bg-[var(--surface-3,transparent)]"
        >
          Retry
        </button>
      ) : null}
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md border border-[var(--hairline,currentColor)] px-2 py-1 text-[11px] hover:bg-[var(--surface-3,transparent)]"
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}
