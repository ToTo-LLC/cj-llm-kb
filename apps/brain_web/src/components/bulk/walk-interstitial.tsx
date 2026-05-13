"use client";

/**
 * Walk interstitial — Plan 25 T4.
 *
 * Step 1 (Pick folder) renders this between the user submitting a path
 * (or picking a folder) and the dry-run plan landing in the store. The
 * backend ``BulkImporter.plan()`` walks the folder + classifies files;
 * the wire response is one shot, no streaming, so we render a spinner +
 * the folder path + helper text + elapsed time. Per D11 (Plan 25) this
 * is intentionally timer-only — no fake file counts, no fake percentages.
 *
 * The component reads ``walkStartedAt`` + ``walkPath`` from the bulk
 * store. Elapsed time updates every second via ``setInterval`` (cleared
 * on unmount). The fade-in animation is a Tailwind ``animate-fade-in``
 * utility — pure CSS opacity, no Radix dialog wrappers (see
 * ``feedback_axe_dialog_animation_wait.md``: keep animations simple so
 * axe-core color-contrast checks don't have to wait for mid-animation
 * opacity).
 */

import * as React from "react";
import { Loader2 } from "lucide-react";

import { useBulkStore } from "@/lib/state/bulk-store";

function truncatePath(path: string, max = 60): string {
  if (path.length <= max) return path;
  // Show ``...<last 57 chars>`` so the leaf folder name is visible.
  return `…${path.slice(-(max - 1))}`;
}

function formatElapsed(ms: number): string {
  const sec = Math.max(0, Math.floor(ms / 1000));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem.toString().padStart(2, "0")}s`;
}

export function WalkInterstitial(): React.ReactElement | null {
  const phase = useBulkStore((s) => s.phase);
  const walkPath = useBulkStore((s) => s.walkPath);
  const walkStartedAt = useBulkStore((s) => s.walkStartedAt);

  // Re-render every 1s so the elapsed counter advances. Cleanup on unmount
  // so we don't leak intervals between mounts.
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    if (phase !== "walking") return;
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => {
      window.clearInterval(id);
    };
  }, [phase]);

  if (phase !== "walking") return null;

  const elapsed =
    walkStartedAt !== null ? formatElapsed(Date.now() - walkStartedAt) : "0s";

  return (
    <div
      className="mx-auto mt-8 max-w-xl rounded-lg border border-[var(--hairline)] bg-[var(--surface)] p-6 transition-opacity duration-200 ease-out"
      role="status"
      aria-live="polite"
      data-testid="walk-interstitial"
      data-phase="walking"
    >
      <h2 className="text-lg font-semibold text-[var(--text)]">
        Scanning folder...
      </h2>
      <div className="mt-4 flex items-center gap-3">
        <Loader2
          className="h-5 w-5 animate-spin text-[var(--accent)]"
          aria-hidden="true"
          data-testid="walk-spinner"
        />
        <span
          className="font-mono text-sm text-[var(--text-muted)]"
          data-testid="walk-path"
          title={walkPath ?? ""}
        >
          {walkPath ? truncatePath(walkPath) : ""}
        </span>
      </div>
      <p className="mt-4 text-sm text-[var(--text-muted)]">
        This may take a moment for large folders.
      </p>
      {walkStartedAt !== null && (
        <p
          className="mt-2 text-xs text-[var(--text-dim)]"
          data-testid="walk-elapsed"
        >
          Elapsed: {elapsed}
        </p>
      )}
    </div>
  );
}
