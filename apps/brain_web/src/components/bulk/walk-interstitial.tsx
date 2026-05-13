"use client";

/**
 * Walk interstitial — Plan 25 T4 (timer skeleton) + Plan 26 T3 (real
 * SSE-driven progress).
 *
 * Step 1 (Pick folder) renders this between the user submitting a path
 * (or picking a folder) and the dry-run plan landing in the store.
 *
 * **Plan 26 T3 — SSE wiring.** The component subscribes to the
 * ``GET /api/bulk/walk-progress`` SSE endpoint via the
 * :func:`subscribeWalkProgress` wrapper. Four event types map to
 * concrete state updates:
 *
 *   - ``walk_started``  → flip out of "connecting" into "walking"; the
 *     UI was already mounted by the caller's :func:`beginWalk` so this
 *     is mostly a record-the-fact flag.
 *   - ``walk_progress`` → REAL file counter + current path. Replaces
 *     the Plan 25 T4 "timer-only / no fake counts" approach with the
 *     live count emitted every 50 files (D9 flood control).
 *   - ``walk_complete`` → caller's ``runDryRun`` resolves separately
 *     and calls ``pickFolder()`` which clears walk state. We close the
 *     EventSource here but do NOT call ``endWalk(true)`` (avoid double-
 *     close races).
 *   - ``walk_error``    → call ``endWalk(false)`` so the store flips to
 *     the ``error`` phase + show the error to the user via the system
 *     toast (already done by the caller's catch in ``step-pick-folder``;
 *     we mirror it here for the streaming path).
 *
 * **Graceful degradation (per D3).** If the EventSource fires
 * ``onerror`` BEFORE ANY event arrives, we fall back to the Plan 25 T4
 * timer-only behavior — fade-in panel, spinner, "Scanning folder..."
 * heading, elapsed counter, NO file counter. If the connection opens
 * successfully then errors later, we treat it as terminal (the SSE
 * stream emits a structured ``walk_error`` for application-level
 * failures; a transport error mid-stream is genuinely a connection
 * failure and the user should know).
 *
 * The 1s elapsed timer (Plan 25 T4) is INDEPENDENT of the SSE
 * subscription — it runs regardless of streaming success/failure so
 * the user always sees forward motion. It's also the only progress
 * signal when graceful-degradation kicks in.
 *
 * Accessibility note: animations stay simple (Tailwind ``transition-
 * opacity duration-200``, no Radix dialog wrappers) so axe-core
 * color-contrast checks don't have to wait for mid-animation opacity
 * keyframes (``feedback_axe_dialog_animation_wait.md``).
 */

import * as React from "react";
import { Loader2 } from "lucide-react";

import {
  subscribeWalkProgress,
  type WalkErrorEvent,
} from "@/lib/api/bulk-progress";
import { useBulkStore } from "@/lib/state/bulk-store";
import { useSystemStore } from "@/lib/state/system-store";
import { getToken } from "@/lib/state/token-store";

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

/**
 * Error-code → user-facing copy. Keep these short — the toast layer
 * surfaces the verbose ``error_message`` separately.
 */
const ERROR_COPY: Record<WalkErrorEvent["error_code"], string> = {
  permission_denied: "Permission denied while scanning folder.",
  path_not_found: "Folder disappeared during scan.",
  internal_error: "Scan failed.",
};

export function WalkInterstitial(): React.ReactElement | null {
  const phase = useBulkStore((s) => s.phase);
  const walkPath = useBulkStore((s) => s.walkPath);
  const walkStartedAt = useBulkStore((s) => s.walkStartedAt);
  const endWalk = useBulkStore((s) => s.endWalk);
  const pushToast = useSystemStore((s) => s.pushToast);

  // Re-render every 1s so the elapsed counter advances. INDEPENDENT of
  // the SSE subscription — runs whenever we're in the walking phase.
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    if (phase !== "walking") return;
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => {
      window.clearInterval(id);
    };
  }, [phase]);

  // SSE-driven progress state. ``filesSeen`` and ``currentPath`` mirror
  // the most recent ``walk_progress`` event. ``fallbackToTimer``
  // flips to true when the EventSource errors BEFORE any event arrives
  // — the UI then renders the Plan 25 T4 timer-only layout. Structured
  // ``walk_error`` frames and post-frame transport errors surface via
  // ``pushToast`` (matching ``step-pick-folder.tsx``'s pattern) +
  // ``endWalk(false)``; the resulting phase change unmounts this
  // component so the picker UI can re-render and the user retries.
  const [filesSeen, setFilesSeen] = React.useState<number | null>(null);
  const [currentPath, setCurrentPath] = React.useState<string | null>(null);
  const [fallbackToTimer, setFallbackToTimer] = React.useState(false);

  React.useEffect(() => {
    if (phase !== "walking" || !walkPath) return;
    const token = getToken();
    if (!token) {
      // Without a token we cannot open the stream — fall back to the
      // timer-only behavior. The caller's ``apiFetch`` (separately
      // driving the dry-run) will surface a 403 toast if auth is
      // actually broken; here we just degrade quietly.
      setFallbackToTimer(true);
      return;
    }

    // Track whether ANY event (started OR progress OR complete OR error)
    // has arrived. This drives the graceful-degradation decision in
    // ``onConnectionError``. Use a ref so the closure reads the latest
    // value without re-subscribing.
    let receivedAnyEvent = false;

    const close = subscribeWalkProgress(walkPath, token, {
      onStarted: () => {
        receivedAnyEvent = true;
      },
      onProgress: (event) => {
        receivedAnyEvent = true;
        setFilesSeen(event.files_seen);
        setCurrentPath(event.current_path);
      },
      onComplete: () => {
        receivedAnyEvent = true;
        // Caller's ``runDryRun`` ALSO sees walk-complete (via the
        // dry-run response landing) and calls ``pickFolder()``, which
        // resets phase to idle. We don't double-handle here — the
        // close() in the subscriber wrapper already tore down the
        // EventSource on the terminal frame.
      },
      onError: (event) => {
        receivedAnyEvent = true;
        pushToast({
          lead: ERROR_COPY[event.error_code] ?? "Scan failed.",
          msg: event.error_message,
          variant: "danger",
        });
        endWalk(false);
      },
      onConnectionError: () => {
        if (!receivedAnyEvent) {
          // No events ever arrived — graceful-degradation: render the
          // Plan 25 T4 timer-only layout. The caller's separate
          // ``bulkImport`` HTTP call still drives the actual walk
          // result; we're just losing the live progress signal.
          setFallbackToTimer(true);
          return;
        }
        // Connection died mid-stream — treat as terminal. The toast
        // surfaces a generic "scan failed" message; the caller's
        // ``bulkImport`` HTTP catch (if it also errors) will push its
        // own toast with the more specific failure.
        pushToast({
          lead: "Scan failed.",
          msg: "Connection to walk-progress stream dropped.",
          variant: "danger",
        });
        endWalk(false);
      },
    });

    return () => {
      close();
    };
  }, [phase, walkPath, endWalk, pushToast]);

  // Reset SSE state on phase exit so re-entering the walk phase doesn't
  // inherit stale counters from a previous run.
  React.useEffect(() => {
    if (phase === "walking") return;
    setFilesSeen(null);
    setCurrentPath(null);
    setFallbackToTimer(false);
  }, [phase]);

  if (phase !== "walking") return null;

  const elapsed =
    walkStartedAt !== null ? formatElapsed(Date.now() - walkStartedAt) : "0s";

  // Live SSE mode: show real ``filesSeen`` once at least one progress
  // event has landed. The path display prefers ``currentPath`` (most
  // recently scanned file from the SSE stream) over ``walkPath`` (the
  // root folder typed by the user) because it's the more useful "where
  // is the walker right now" signal.
  const showLiveCounter = !fallbackToTimer && filesSeen !== null;
  const pathDisplay = currentPath ?? walkPath ?? "";

  return (
    <div
      className="mx-auto mt-8 max-w-xl rounded-lg border border-[var(--hairline)] bg-[var(--surface)] p-6 transition-opacity duration-200 ease-out"
      role="status"
      aria-live="polite"
      data-testid="walk-interstitial"
      data-phase="walking"
      data-streaming-mode={
        fallbackToTimer
          ? "timer-fallback"
          : showLiveCounter
            ? "live"
            : "connecting"
      }
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
          title={pathDisplay}
        >
          {pathDisplay ? truncatePath(pathDisplay) : ""}
        </span>
      </div>
      {showLiveCounter && (
        <p
          className="mt-3 text-sm text-[var(--text)]"
          data-testid="walk-files-seen"
        >
          {filesSeen?.toLocaleString()} files seen
        </p>
      )}
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
