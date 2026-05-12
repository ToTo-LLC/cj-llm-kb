"use client";

import Link from "next/link";
import * as React from "react";
import { AlertTriangle, Eye } from "lucide-react";

import { useWatchedFoldersStore } from "@/lib/state/watched-folders-store";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Watched-folders topbar status indicator (Plan 22 T14).
 *
 * Glanceable system-state pill that lives in the topbar between the
 * vault-state affordances (Scope / Autonomy) and the global controls
 * (Theme / Settings). Reads from the shared :func:`useWatchedFoldersStore`
 * — the same canonical source that the Settings → Watched folders panel
 * (T12) and the Settings → Orphans panel (T13) consume. When a watcher
 * event in another part of the app mutates the store (resync, restore,
 * delete, watch / unwatch), the indicator reflects the new counts
 * automatically via zustand subscription.
 *
 * Implements the mockup at ``docs/design/plan-22/topbar-status.md``.
 *
 * State summary (per mockup §"States summary table"):
 *
 * | Watched | Orphans | Render                | Color                     |
 * |---------|---------|-----------------------|---------------------------|
 * | 0       | 0       | hidden                | n/a                       |
 * | ≥1      | 0       | ``[👁 N]``            | ``--text-muted``          |
 * | 0       | ≥1      | ``[⚠ N]``             | ``--warn``                |
 * | ≥1      | ≥1      | ``[👁 N · ⚠ M]``      | muted then warn (· dim)   |
 * | error   | error   | ``[👁 !]``            | ``--danger``              |
 *
 * Click-through routes:
 *   - orphan_count > 0  → ``/settings/orphans`` (high-attention path)
 *   - orphan_count == 0 → ``/settings/watched-folders`` (manage path)
 *   - error state       → fires ``store.refresh()`` (no navigation)
 *
 * Accessibility:
 *   - The trigger is a real ``<a>`` (via Next.js ``Link`` + Radix
 *     ``asChild``), so Tab lands on it, Enter / Space activates it,
 *     and the screen-reader name is the explicit ``aria-label``.
 *   - The hidden state (0 watched + 0 orphans + no error) renders
 *     ``null`` — the topbar layout stays stable because the indicator
 *     occupies no width when absent, and an animated slide-in (per
 *     mockup §"Implementation guidance" reconsideration) draws
 *     attention when the indicator appears mid-session.
 *   - A separate ``role="status" aria-live="polite"`` sibling node
 *     announces orphan-count changes (e.g. a watcher event fires
 *     mid-session and orphan count flips from 0 → 1). The ``aria-label``
 *     on the button itself wouldn't re-announce on update — Radix and
 *     screen-readers don't re-read static labels — so the dedicated
 *     live region carries the change announcement.
 *   - Color is never the only signal: ``Eye`` and ``AlertTriangle``
 *     are visually distinct AND the ``aria-label`` text spells out the
 *     full state.
 */

/**
 * Pluralise an English noun based on count. The mockup microcopy
 * specifies "orphaned note needs attention" (singular) vs "orphaned
 * notes need attention" (plural) — handled here to keep the call-site
 * tooltip / aria-label templates readable.
 */
function plural(count: number, singular: string, pluralForm: string): string {
  return count === 1 ? singular : pluralForm;
}

/**
 * Compose the tooltip + aria-label strings for the current state. The
 * tooltip text is the user-facing copy; the aria-label is the full
 * "what + what to do" sentence so a screen-reader user gets both halves
 * in one announcement.
 *
 * Pure function — easy to unit-test without rendering.
 */
export function composeIndicatorCopy(args: {
  watchedCount: number;
  orphanCount: number;
  hasError: boolean;
}): { tooltip: string; ariaLabel: string } {
  const { watchedCount, orphanCount, hasError } = args;

  if (hasError) {
    return {
      tooltip: "Couldn't load watched folders. Click to retry.",
      ariaLabel: "Watched folder status failed to load. Click to retry.",
    };
  }

  const foldersPhrase = `${watchedCount} ${plural(watchedCount, "folder", "folders")} watched`;
  const orphansPhrase = `${orphanCount} orphaned ${plural(orphanCount, "note needs", "notes need")} attention`;

  if (watchedCount > 0 && orphanCount > 0) {
    return {
      tooltip: `${foldersPhrase} · ${orphansPhrase}.`,
      ariaLabel: `${foldersPhrase}, ${orphansPhrase}. Open Settings to manage.`,
    };
  }
  if (watchedCount > 0 && orphanCount === 0) {
    return {
      tooltip: `${foldersPhrase}.`,
      ariaLabel: `${foldersPhrase}. Open Settings to manage.`,
    };
  }
  // watched == 0 && orphans > 0 — the orphans-only state. Per mockup
  // microcopy, this collapses to a single "needs attention" sentence
  // because there's no folder-count signal worth showing.
  return {
    tooltip: `${orphansPhrase}. Click to review.`,
    ariaLabel: `${orphansPhrase}. Click to review.`,
  };
}

export interface WatchedFoldersTopbarIndicatorProps {
  /** Override the testid prefix. Defaults to ``"watched-folders-indicator"``. */
  testId?: string;
}

/**
 * Topbar status indicator surface. Subscribes to
 * :func:`useWatchedFoldersStore` via individual selectors so React
 * re-renders track exactly the slices that change (folders array,
 * error). Aggregation (``watched_count``, ``orphan_count``) is derived
 * from ``folders`` via :func:`React.useMemo` keyed on the folders
 * reference — zustand's default referential equality means we re-run
 * the memo whenever ``folders`` changes (refresh, optimistic remove).
 */
export function WatchedFoldersTopbarIndicator({
  testId = "watched-folders-indicator",
}: WatchedFoldersTopbarIndicatorProps = {}): React.ReactElement | null {
  const folders = useWatchedFoldersStore((s) => s.folders);
  const error = useWatchedFoldersStore((s) => s.error);
  const refresh = useWatchedFoldersStore((s) => s.refresh);

  const { watchedCount, orphanCount } = React.useMemo(() => {
    const wc = folders.length;
    // Reduce per render is O(n) where n = watched-folder rows. n is
    // bounded by the user's :attr:`Config.watched_folders` length (rare
    // to exceed double digits in practice), and the memo only re-runs
    // when ``folders`` reference changes — cheap.
    const oc = folders.reduce((acc, f) => acc + f.orphan_count, 0);
    return { watchedCount: wc, orphanCount: oc };
  }, [folders]);

  const hasError = error !== null;

  // Memoise the copy strings — pure function of three primitives, so
  // useMemo with the three deps is correct + cheap.
  const { tooltip, ariaLabel } = React.useMemo(
    () => composeIndicatorCopy({ watchedCount, orphanCount, hasError }),
    [watchedCount, orphanCount, hasError],
  );

  // Click-through routing per mockup §"Interaction":
  //   - orphan_count > 0  → /settings/orphans (high-attention path)
  //   - orphan_count == 0 → /settings/watched-folders (manage path)
  // In error state we fall back to /settings/watched-folders + fire
  // refresh() so the user lands on the panel that surfaces the
  // canonical retry banner. Click handler runs BEFORE navigation so the
  // refresh kicks off concurrently with the route change.
  const href = orphanCount > 0 ? "/settings/orphans" : "/settings/watched-folders";

  // Hidden state (per mockup §"Empty state"): 0 watched, 0 orphans, no
  // error → render null entirely. The "slide-in entrance" lives on the
  // visible-state path; absence of the node IS the hidden state.
  if (watchedCount === 0 && orphanCount === 0 && !hasError) {
    return null;
  }

  return (
    <TooltipProvider delayDuration={260}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Link
            href={href}
            aria-label={ariaLabel}
            data-testid={testId}
            onClick={() => {
              if (hasError) {
                // Fire refresh in error state — the navigation still
                // happens (the user lands on the watched-folders panel
                // which surfaces the retry banner), but we proactively
                // re-fetch so the panel hydrates with fresh data.
                void refresh();
              }
            }}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-full border border-[var(--hairline)] bg-[var(--surface-2)] px-2.5 text-xs transition-colors",
              "hover:bg-[var(--surface-3)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--tt-cyan,_currentColor)] focus-visible:ring-offset-2",
            )}
          >
            {hasError ? (
              <span
                className="inline-flex items-center gap-1 text-[var(--danger)]"
                data-testid={`${testId}-error`}
              >
                <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="font-semibold">!</span>
              </span>
            ) : (
              <>
                {watchedCount > 0 && (
                  <span
                    className="inline-flex items-center gap-1 text-[var(--text-muted)]"
                    data-testid={`${testId}-watched`}
                  >
                    <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                    <span className="font-medium">{watchedCount}</span>
                  </span>
                )}
                {watchedCount > 0 && orphanCount > 0 && (
                  <span
                    aria-hidden="true"
                    className="text-[var(--text-dim)]"
                  >
                    {"·"}
                  </span>
                )}
                {orphanCount > 0 && (
                  <span
                    className="inline-flex items-center gap-1 text-[var(--warn)]"
                    data-testid={`${testId}-orphans`}
                  >
                    <AlertTriangle
                      className="h-3.5 w-3.5"
                      aria-hidden="true"
                    />
                    <span className="font-semibold">{orphanCount}</span>
                  </span>
                )}
              </>
            )}
          </Link>
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          align="end"
          data-testid={`${testId}-tooltip`}
        >
          {tooltip}
        </TooltipContent>
      </Tooltip>
      {/*
        Live region for orphan-count-change announcements. The
        ``aria-label`` on the trigger above wouldn't re-announce when
        the underlying counts change while the page is mounted (screen
        readers don't re-read static labels). This sr-only span carries
        the change announcement so a watcher event mid-session ("a
        source file was deleted → orphan_count flips 0 → 1") is
        announced to assistive tech. Polite assertiveness avoids
        interrupting the user's current screen-reader context.
       */}
      <span
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        data-testid={`${testId}-live-region`}
      >
        {ariaLabel}
      </span>
    </TooltipProvider>
  );
}
