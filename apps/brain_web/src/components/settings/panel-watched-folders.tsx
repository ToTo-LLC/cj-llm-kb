"use client";

import * as React from "react";
import { Eye, ExternalLink, FolderPlus, RotateCw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { unwatchFolder, type WatchedFolderEntry } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";
import { useWatchedFoldersStore } from "@/lib/state/watched-folders-store";

/**
 * PanelWatchedFolders (Plan 22 T12).
 *
 * Implements the mockup at ``docs/design/plan-22/watched-folders-settings.md``.
 * Reads watched-folder rows from :func:`useWatchedFoldersStore`; mutates
 * via :func:`unwatchFolder` (and, in T15, ``brain_watch_folder`` via the
 * watch-enable modal). The "Resync now" + "Open in Finder" affordances
 * are placeholders pending follow-up tooling (the backend
 * ``brain_resync_folder`` did not ship in T5 — tracked below; the
 * Integrations open-in-OS helper does not exist yet either). They render
 * as disabled buttons with tooltips so the visual rhythm of the row
 * matches the mockup; T15 + a future resync-handler task wire them up.
 *
 * State management mirrors :func:`PanelDomains` (Plan 12 T5 / Plan 13
 * T2): single source of truth is the zustand store, first-mount
 * ``refresh()`` hydrates the list, inline error banner surfaces a
 * failed fetch (resolve-always semantics record errors on store state
 * rather than rejecting). v1 does NOT add a BroadcastChannel for
 * cross-tab pubsub — flagged as Plan 23 candidate.
 *
 * Microcopy strings come verbatim from the mockup's "Microcopy" section.
 * Do not paraphrase — drift between mockup + UI is a documented Plan 22
 * D9 lint surface.
 */

// --------- Domain dot color helper (shared with panel-domains) ---------

/**
 * Resolve the domain dot color for a watched-folder row. Built-ins map
 * to the brand-skin's semantic ``--dom-*`` tokens so the dot matches the
 * topbar's scope-picker chip and the Settings → Domains row dots.
 * User-created domains fall back to a neutral surface color — Plan 22
 * v1 does not thread the ``ACCENT_SWATCHES`` rotation through (the
 * watched-folders store would need to learn the user-index of each
 * domain, which is the domains-store's job). When Plan 23 promotes the
 * topbar status indicator to share the same color resolver, the dot
 * here picks that up automatically.
 */
const BUILTIN_DOMAIN_ACCENT: Record<string, string> = {
  research: "var(--dom-research)",
  work: "var(--dom-work)",
  personal: "var(--dom-personal)",
};

function accentFor(domain: string): string {
  return BUILTIN_DOMAIN_ACCENT[domain] ?? "var(--text-dim)";
}

// --------- Relative-time helper (granular: minutes/hours/days) ---------

/**
 * Render an ISO-8601 timestamp as a relative-time string matching the
 * mockup's microcopy ("4 minutes ago", "1 hour ago"). The mockup
 * specifies minute + hour precision; the doc-picker's coarser helper
 * (day-bucket only) doesn't fit here. Plurals are explicit (no "1
 * minutes ago").
 *
 * Returns the empty string on parse failure so the caller can decide
 * what to render (typically "never").
 */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const delta = Math.max(0, Date.now() - then);
  const minute = 60_000;
  const hour = minute * 60;
  const day = hour * 24;
  if (delta < minute) return "just now";
  if (delta < hour) {
    const m = Math.floor(delta / minute);
    return `${m} minute${m === 1 ? "" : "s"} ago`;
  }
  if (delta < day) {
    const h = Math.floor(delta / hour);
    return `${h} hour${h === 1 ? "" : "s"} ago`;
  }
  const days = Math.floor(delta / day);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/**
 * Compose the row sub-line (file count · orphan count · last-sync
 * timestamp) per the mockup's exact-strings spec. The zero-orphan
 * branch omits the orphan count entirely ("cleaner" — see mockup
 * microcopy `Row sub-line template`).
 */
function subLineLabel(entry: WatchedFolderEntry): string {
  const fileLabel = `${entry.file_count} file${entry.file_count === 1 ? "" : "s"}`;
  const orphanFragment =
    entry.orphan_count > 0
      ? ` · ${entry.orphan_count} orphan${entry.orphan_count === 1 ? "" : "s"}`
      : "";
  const syncLabel = entry.last_sync
    ? `last synced ${relativeTime(entry.last_sync)}`
    : "never synced";
  return `${fileLabel}${orphanFragment} · ${syncLabel}`;
}

// ---------- Per-row component ----------

interface WatchedFolderRowProps {
  entry: WatchedFolderEntry;
  onUnwatch: (folder: string) => void;
}

/**
 * Single watched-folder row. Pure presentation: every mutation bubbles
 * up via callback. Mirrors the ``PanelDomainsRow`` discipline so the
 * orchestrator owns optimistic updates + error reconciliation.
 *
 * The "Resync now" + "Open in Finder" buttons render as disabled
 * placeholders pending follow-up tooling — they hold their visual slot
 * in the mockup so the row's gravity stays right (without them the row
 * collapses to two actions and feels lopsided). Both surfaces will wire
 * up in a follow-up Plan 22 task (resync) / Plan 23 (Integrations
 * helper).
 */
function WatchedFolderRow({
  entry,
  onUnwatch,
}: WatchedFolderRowProps): React.ReactElement {
  const subLine = subLineLabel(entry);
  const personalDomain = entry.domain === "personal";

  return (
    <li
      data-testid="watched-folder-row"
      className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-3 transition-colors duration-100 hover:bg-[var(--surface-3)]"
    >
      <div className="flex flex-col gap-2">
        {/* Top line — accent dot, path, domain badge, toggle. */}
        <div className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ background: accentFor(entry.domain) }}
          />
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                data-testid="watched-folder-path"
                className="min-w-0 flex-1 truncate font-mono text-sm text-[var(--text)]"
              >
                {entry.path}
              </span>
            </TooltipTrigger>
            <TooltipContent>{entry.path}</TooltipContent>
          </Tooltip>
          <span
            data-testid={`domain-badge-${entry.domain}`}
            className="inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{
              background: `var(--dom-${entry.domain}-soft, var(--surface-2))`,
              color: `var(--dom-${entry.domain}, var(--text-muted))`,
            }}
          >
            {entry.domain}
          </span>
          {/* Toggle is always ON in v1 — clicking OFF goes through the
              watch-disable confirmation (T15) which calls unwatchFolder
              and removes the row entirely. We expose the Switch for
              keyboard parity with the mockup's row-keyboard-order spec
              (the toggle is the first focusable element in each row). */}
          <Switch
            checked={entry.enabled}
            onCheckedChange={() => onUnwatch(entry.path)}
            aria-label={`Stop watching ${entry.path}`}
            data-testid={`watched-folder-toggle-${entry.path}`}
            className="shrink-0"
          />
        </div>

        {/* Sub-line — aggregated for screen readers. */}
        <p
          className="pl-4 text-[11px] text-[var(--text-muted)]"
          aria-label={subLine.replace(/·/g, ",")}
          data-testid="watched-folder-subline"
        >
          {entry.last_sync ? (
            <>
              <time dateTime={entry.last_sync}>{subLine}</time>
            </>
          ) : (
            subLine
          )}
        </p>

        {personalDomain && (
          <p
            className="pl-4 text-[10px] text-[var(--text-dim)]"
            data-testid="watched-folder-personal-note"
          >
            <span aria-hidden="true">{"ⓘ "}</span>
            This folder syncs into your personal domain (privacy-railed
            by default).
          </p>
        )}

        {/* Action row — "Include subfolders" checkbox, Resync, Open in
            Finder, Unwatch. Per the mockup's row-keyboard-order spec:
            checkbox → resync → open → unwatch. */}
        <div className="flex flex-wrap items-center gap-3 pl-4">
          <span className="inline-flex items-center gap-1.5">
            <Checkbox
              id={`include-subdirs-${entry.path}`}
              checked={entry.include_subdirs}
              disabled
              data-testid={`watched-folder-include-subdirs-${entry.path}`}
              aria-label={`Include subfolders for ${entry.path}`}
            />
            <label
              htmlFor={`include-subdirs-${entry.path}`}
              className="text-[11px] text-[var(--text-muted)]"
            >
              Include subfolders
            </label>
          </span>

          {/* Resync placeholder — backend ``brain_resync_folder`` did
              not ship in T5; tooltip explains the disabled state so the
              user understands it's intentional, not a UI bug. */}
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled
                  data-testid={`watched-folder-resync-${entry.path}`}
                  aria-label={`Resync now ${entry.path}`}
                  className="h-7 gap-1 px-2 text-xs"
                >
                  <RotateCw className="h-3 w-3" />
                  Resync now
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              Coming soon — manual resync ships in a follow-up.
            </TooltipContent>
          </Tooltip>

          {/* Open-in-Finder placeholder — no Integrations helper yet. */}
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled
                  data-testid={`watched-folder-open-${entry.path}`}
                  aria-label={`Open ${entry.path} in Finder`}
                  className="h-7 gap-1 px-2 text-xs"
                >
                  <ExternalLink className="h-3 w-3" />
                  Open in Finder
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              Coming soon — OS-native open ships in a follow-up.
            </TooltipContent>
          </Tooltip>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => onUnwatch(entry.path)}
            data-testid={`watched-folder-unwatch-${entry.path}`}
            aria-label={`Unwatch ${entry.path}`}
            className="ml-auto h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
          >
            <X className="h-3 w-3" />
            Unwatch
          </Button>
        </div>
      </div>
    </li>
  );
}

// ---------- Orchestrator ----------

/**
 * "Watch a new folder" CTA. v1 (T12) renders the visual slot per the
 * mockup but does not open a modal — T15 wires the watch-enable modal.
 * The CTA logs a warning on click so a developer who lands here mid-
 * Plan-22 sees the breadcrumb; the button stays interactive (not
 * disabled) so the focus ring, hover, and keyboard binding all read
 * correctly in axe + Playwright. The intent is documented inline rather
 * than as a TODO comment so the next engineer reads it without context-
 * switching to the plan doc.
 */
function WatchNewFolderCta({
  variant = "primary",
}: {
  variant?: "primary" | "empty-state";
}): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const onClick = () => {
    // T15 deliverable — until the watch-enable modal lands, surface a
    // toast so the user gets confirmation the click registered (rather
    // than wondering whether the UI broke). The toast copy is
    // intentionally informative, not apologetic.
    pushToast({
      lead: "Coming soon.",
      msg: "The watch-folder picker ships in the next Plan 22 task (T15).",
      variant: "default",
    });
  };
  if (variant === "empty-state") {
    return (
      <Button
        onClick={onClick}
        data-testid="watched-folders-empty-cta"
        className="gap-2"
      >
        <FolderPlus className="h-4 w-4" />
        Watch a folder
      </Button>
    );
  }
  return (
    <Button
      onClick={onClick}
      data-testid="watched-folders-add-cta"
      className="gap-2"
    >
      <FolderPlus className="h-4 w-4" />
      Watch a new folder
    </Button>
  );
}

export function PanelWatchedFolders(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const folders = useWatchedFoldersStore((s) => s.folders);
  const loaded = useWatchedFoldersStore((s) => s.loaded);
  const storeError = useWatchedFoldersStore((s) => s.error);

  // First-mount fetch. Subsequent fetches fire after mutations
  // (handleUnwatch) so the row list reconciles with the backend after
  // every change.
  React.useEffect(() => {
    void useWatchedFoldersStore.getState().refresh();
  }, []);

  const handleUnwatch = React.useCallback(
    async (folderPath: string) => {
      // T15 will gate this behind a watch-disable confirmation modal.
      // For T12 we fire the API directly so the panel is functionally
      // complete — drop the row optimistically, restore on API failure
      // (mirrors ``panel-domains`` delete handler / Plan 16 T4 / D4).
      const entry = folders.find((f) => f.path === folderPath);
      useWatchedFoldersStore.getState().removeFolderOptimistic(folderPath);
      try {
        await unwatchFolder({ folder: folderPath });
        // Re-fetch so any orphan counts / last-sync timestamps for OTHER
        // rows that the unwatch may have invalidated (rare, but possible
        // if the backend prunes shared state) refresh in lock-step.
        void useWatchedFoldersStore.getState().refresh();
        const basename = folderPath.split(/[/\\]/).pop() ?? folderPath;
        const orphanCount = entry?.orphan_count ?? 0;
        pushToast({
          lead: `Stopped watching ${basename}.`,
          msg:
            orphanCount > 0
              ? `Existing notes kept. ${orphanCount} orphan${
                  orphanCount === 1 ? "" : "s"
                } remain marked.`
              : "Existing notes kept.",
          variant: "success",
        });
      } catch (err) {
        // API failed — restore the row by re-fetching the canonical
        // server list (mirrors the ``panel-domains`` rollback pattern).
        await useWatchedFoldersStore.getState().refresh();
        pushToast({
          lead: "Couldn't unwatch folder.",
          msg: err instanceof Error ? err.message : "Unknown error.",
          variant: "danger",
        });
      }
    },
    [folders, pushToast],
  );

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex flex-col gap-4">
        <header className="flex flex-col gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
            <Eye className="h-4 w-4" aria-hidden="true" />
            Watched folders
          </h2>
          <p className="text-[11px] text-[var(--text-muted)]">
            Brain mirrors files from these folders into your knowledge
            base automatically. Source files are the source of truth —
            vault edits to watched notes are overwritten on the next
            sync.
          </p>
        </header>

        {/* Inline error banner — surfaces a failed
            ``useWatchedFoldersStore.refresh()``. Mirrors the
            ``panel-domains`` error-banner pattern (Plan 16 T4 / D4):
            ``role="alert"`` so screen readers announce; tokens match
            the danger-tinted hairline-strong + surface-2 banner. */}
        {storeError && (
          <div
            role="alert"
            data-testid="watched-folders-error-banner"
            className="rounded-md border border-[var(--hairline-strong)] bg-[var(--surface-2)] p-3 text-xs text-[var(--danger,_#FF4503)]"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="font-semibold">
                  Couldn&rsquo;t load watched folders.
                </span>{" "}
                <span className="text-[var(--text)]">
                  {storeError.message}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  void useWatchedFoldersStore.getState().refresh()
                }
                data-testid="watched-folders-retry"
                aria-label="Retry loading watched folders"
                className="h-7 gap-1 px-2 text-xs"
              >
                <RotateCw className="h-3 w-3" />
                Try again
              </Button>
            </div>
          </div>
        )}

        {!loaded ? (
          // Loading state — keep the header + add CTA visible (mockup
          // §"Loading state"): the loading shimmer below the header
          // gives the user immediate visual feedback that data is
          // arriving without blocking the affordances.
          <>
            <div
              className="self-end"
              aria-hidden="true"
              data-testid="watched-folders-cta-loading"
            >
              <WatchNewFolderCta />
            </div>
            <div
              role="status"
              aria-live="polite"
              data-testid="watched-folders-loading"
              className="flex flex-col gap-2"
            >
              <span className="sr-only">Loading watched folders…</span>
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-16 animate-pulse rounded-md border border-[var(--hairline)] bg-[var(--surface-2)]"
                />
              ))}
            </div>
          </>
        ) : folders.length === 0 ? (
          // Empty state — centered card per mockup §"Empty state". The
          // CTA collapses into the empty card itself; the header CTA
          // is hidden because the empty-state CTA is the primary CTA in
          // this branch (mockup specifies one prominent CTA, not two).
          <div
            data-testid="watched-folders-empty-state"
            className="mx-auto flex w-full max-w-md flex-col items-center gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-6 text-center"
          >
            <FolderPlus
              className="h-10 w-10 text-[var(--text-dim)]"
              aria-hidden="true"
            />
            <h3 className="text-sm font-semibold text-[var(--text)]">
              No folders being watched yet.
            </h3>
            <p className="text-[11px] text-[var(--text-muted)]">
              Pick a folder and Brain will keep its notes in sync
              automatically.
            </p>
            <WatchNewFolderCta variant="empty-state" />
          </div>
        ) : (
          // Populated state — header CTA + list of rows.
          <>
            <div className="self-end">
              <WatchNewFolderCta />
            </div>
            <ul
              role="list"
              data-testid="watched-folders-list"
              className="flex flex-col gap-3"
            >
              {folders.map((entry) => (
                <WatchedFolderRow
                  key={entry.path}
                  entry={entry}
                  onUnwatch={(folder) => void handleUnwatch(folder)}
                />
              ))}
            </ul>
          </>
        )}
      </div>
    </TooltipProvider>
  );
}
