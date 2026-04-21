"use client";

import * as React from "react";
import { Undo2, X } from "lucide-react";

import { useSystemStore, type Toast } from "@/lib/state/system-store";
import { cn } from "@/lib/utils";

/**
 * Toasts — bottom-right stack that renders toasts pushed via
 * `pushToast()`. Reads live from the system-store; callers generally do
 * NOT render this directly — `<SystemOverlays />` is the single mount
 * point.
 *
 * ## Lifetime
 *
 * - Toasts without `countdown` auto-dismiss at 6s (the timeout lives in
 *   `system-store.pushToast`). We don't duplicate that timer here.
 * - Toasts WITH `countdown` render a live tick-down and fire `undo` at
 *   zero. The caller owns what "undo" does (see Task 16 pending-patches
 *   flow for a concrete example).
 */

export interface ToastsProps {
  /** Optional prop-override; defaults to store-driven render. */
  toasts?: Toast[];
  dismiss?: (id: string) => void;
}

export function Toasts({ toasts: propToasts, dismiss: propDismiss }: ToastsProps = {}) {
  const storeToasts = useSystemStore((s) => s.toasts);
  const storeDismiss = useSystemStore((s) => s.dismissToast);
  const toasts = propToasts ?? storeToasts;
  const dismiss = propDismiss ?? storeDismiss;

  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-40 flex w-80 flex-col gap-2"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [remaining, setRemaining] = React.useState(toast.countdown ?? 0);

  // Live countdown tick + auto-fire-undo-at-zero. Idle when no countdown.
  React.useEffect(() => {
    if (!toast.countdown) return;
    const interval = setInterval(() => {
      setRemaining((n) => {
        if (n <= 1) {
          clearInterval(interval);
          toast.undo?.();
          onDismiss();
          return 0;
        }
        return n - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
    // The effect depends only on the toast identity — a stable id across
    // re-renders since the store never mutates a toast in place.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast.id]);

  const tone = toast.variant ?? "default";
  return (
    <div
      role="status"
      className={cn(
        "pointer-events-auto flex items-start gap-3 rounded-md border bg-[var(--surface-2,#0f0f10)] px-3 py-2 text-sm shadow-lg",
        tone === "success" && "border-[var(--tt-cream,#e8e0d6)]/40",
        tone === "warn" && "border-[var(--tt-amber,#b8860b)]/60",
        tone === "danger" && "border-[var(--tt-red,#c0392b)]/60",
        tone === "default" && "border-[var(--hairline,currentColor)]",
      )}
    >
      <div className="flex flex-1 flex-col">
        <div className="font-medium text-[var(--text,inherit)]">{toast.lead}</div>
        <div className="text-[var(--text-muted,inherit)]">{toast.msg}</div>
        {toast.undo && toast.countdown ? (
          <button
            type="button"
            onClick={() => {
              toast.undo?.();
              onDismiss();
            }}
            className="mt-1 flex items-center gap-1 self-start text-[11px] text-[var(--text,inherit)] hover:underline"
          >
            <Undo2 className="h-3 w-3" /> Undo{remaining ? ` (${remaining}s)` : ""}
          </button>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss toast"
        className="rounded-md p-1 text-[var(--text-muted,inherit)] hover:bg-[var(--surface-3,transparent)]"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
