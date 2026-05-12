"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RotateCcw,
  RotateCw,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { OrphanEntry } from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useOrphansStore } from "@/lib/state/orphans-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelOrphans (Plan 22 T13).
 *
 * Implements the mockup at ``docs/design/plan-22/orphan-management.md``.
 * Reads orphan rows from :func:`useOrphansStore`; mutates via
 * :func:`restoreOrphan` / :func:`deleteOrphan` (both pass through the
 * store so peer subscribers re-render). Bulk-delete typed-confirm goes
 * through :class:`TypedConfirmDialog` with the literal phrase
 * ``"delete N notes"`` (mockup §"Bulk mode"); single-row delete uses
 * the note's slug (per ``modal-orphan-delete.md`` line 39).
 *
 * State management mirrors :func:`PanelWatchedFolders` (Plan 22 T12):
 * single source of truth is the zustand store, first-mount
 * ``refresh()`` hydrates the list, inline error banner surfaces a
 * failed fetch (resolve-always semantics record errors on store state
 * rather than rejecting). The selection set (which rows are checked)
 * lives in component-local state — per mockup hand-off note, selection
 * is a transient adjudication action that does NOT need to persist
 * across tab switches.
 *
 * Microcopy strings come verbatim from the mockup's "Microcopy"
 * section. Do not paraphrase — drift between mockup + UI is a
 * documented Plan 22 D9 lint surface.
 *
 * Cross-store: after restore / delete success the orphans store fires
 * a follow-up ``refresh()`` — the watched-folders store's
 * ``orphan_count`` column reads off ``brain_list_watched_folders`` so
 * the user has to re-mount the Watched-folders panel to see the
 * updated count. v1 (T13) does not auto-invalidate the watched-folders
 * store from here; flagged as a Plan 23 candidate.
 */

// ---------- Domain dot color helper (shared with sibling settings panels) ----

const BUILTIN_DOMAIN_ACCENT: Record<string, string> = {
  research: "var(--dom-research)",
  work: "var(--dom-work)",
  personal: "var(--dom-personal)",
};

function accentFor(domain: string): string {
  return BUILTIN_DOMAIN_ACCENT[domain] ?? "var(--text-dim)";
}

// ---------- Relative-time helper (shared shape with watched-folders) ----------

/**
 * Render an ISO-8601 timestamp as a relative-time string matching the
 * mockup's "Orphaned ${relative_time}" copy. Plurals are explicit (no
 * "1 minutes ago"). Returns "just now" for very recent values.
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

/** Derive the note slug (basename without ``.md`` extension) used as
 *  the typed-confirm word for single-row delete (mockup line 39). */
function slugFromNotePath(notePath: string): string {
  const basename = notePath.split(/[/\\]/).pop() ?? notePath;
  return basename.replace(/\.md$/i, "");
}

/** Derive a display title. Mockup §"Per-row anatomy" says
 *  "The note's title (frontmatter title or slug fallback)" — the
 *  backend's :class:`OrphanEntry` doesn't carry the frontmatter title
 *  (T5 pinned only 5 fields), so we always fall back to the slug here.
 *  Wider titles are a documented Plan 23 candidate. */
function titleFromNotePath(notePath: string): string {
  return slugFromNotePath(notePath);
}

// ---------- Sentinel values for the filter Select primitives ----------

/** Radix ``Select.Item`` cannot use an empty string for its ``value``
 *  prop (it throws at runtime). We model "no filter" with this sentinel
 *  and translate it at the filter-application boundary. */
const FILTER_ALL = "__all__";

// ---------- Per-row component ----------

interface OrphanRowProps {
  entry: OrphanEntry;
  selected: boolean;
  onToggleSelect: (notePath: string) => void;
  onRestore: (notePath: string) => void;
  onDelete: (entry: OrphanEntry) => void;
  /** True while a per-row restore is in flight. Mockup §"Bulk action
   *  in-flight" maps this to a fade + ``aria-busy``; we additionally
   *  disable the row actions so the user can't double-fire. */
  restoring: boolean;
  /** True while a per-row delete is in flight (post-confirm). Same
   *  fade-out + aria-busy treatment. */
  deleting: boolean;
}

function OrphanRow({
  entry,
  selected,
  onToggleSelect,
  onRestore,
  onDelete,
  restoring,
  deleting,
}: OrphanRowProps): React.ReactElement {
  const title = titleFromNotePath(entry.note_path);
  const busy = restoring || deleting;
  const subLine = `Orphaned ${relativeTime(entry.orphaned_at)} · was last synced ${entry.orphaned_at}`;

  return (
    <li
      data-testid="orphan-row"
      data-note-path={entry.note_path}
      aria-busy={busy}
      aria-label={`${title}, orphaned from ${entry.source_path}, ${relativeTime(entry.orphaned_at)}`}
      className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-3 transition-opacity duration-150 data-[busy=true]:opacity-50"
      style={{ opacity: busy ? 0.5 : undefined }}
    >
      <div className="flex flex-col gap-1.5">
        {/* Top line — checkbox, warn icon, title. */}
        <div className="flex items-start gap-2">
          <Checkbox
            id={`orphan-select-${entry.note_path}`}
            checked={selected}
            onCheckedChange={() => onToggleSelect(entry.note_path)}
            disabled={busy}
            aria-label={`Select ${title}`}
            data-testid={`orphan-row-checkbox-${entry.note_path}`}
            className="mt-0.5 shrink-0"
          />
          <AlertTriangle
            className="mt-0.5 h-3.5 w-3.5 shrink-0"
            style={{ color: "var(--warn, #E0A03A)" }}
            aria-hidden="true"
          />
          <span
            data-testid="orphan-row-title"
            className="min-w-0 flex-1 truncate font-mono text-sm text-[var(--text)]"
          >
            {title}.md
          </span>
        </div>

        {/* Sub-line — source path + orphaned timestamp. */}
        <p
          className="pl-7 font-mono text-[11px] text-[var(--text-muted)]"
          data-testid="orphan-row-source"
        >
          Source: {entry.source_path}
        </p>
        <p
          className="pl-7 text-[10px] text-[var(--text-dim)]"
          data-testid="orphan-row-orphaned-at"
        >
          <time dateTime={entry.orphaned_at}>{subLine}</time>
        </p>

        {/* Action row — Restore + Delete (right-aligned per mockup). */}
        <div className="flex flex-wrap items-center justify-end gap-2 pl-7">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRestore(entry.note_path)}
            disabled={busy}
            aria-busy={restoring}
            aria-label={`Restore ${title}`}
            data-testid={`orphan-row-restore-${entry.note_path}`}
            className="h-7 gap-1 px-2 text-xs"
          >
            {restoring ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            ) : (
              <RotateCcw className="h-3 w-3" aria-hidden="true" />
            )}
            Restore
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(entry)}
            disabled={busy}
            aria-busy={deleting}
            aria-label={`Delete ${title}`}
            data-testid={`orphan-row-delete-${entry.note_path}`}
            className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
          >
            {deleting ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            ) : (
              <Trash2 className="h-3 w-3" aria-hidden="true" />
            )}
            Delete
          </Button>
        </div>
      </div>
    </li>
  );
}

// ---------- Helpers: group + filter the orphan list ----------

/** Group orphans by ``watched_folder_id``. Preserves first-seen order
 *  of folders for stable rendering across re-renders. */
function groupByFolder(
  orphans: OrphanEntry[],
): Array<{ folder: string; entries: OrphanEntry[] }> {
  const byFolder = new Map<string, OrphanEntry[]>();
  for (const entry of orphans) {
    const bucket = byFolder.get(entry.watched_folder_id);
    if (bucket) {
      bucket.push(entry);
    } else {
      byFolder.set(entry.watched_folder_id, [entry]);
    }
  }
  return Array.from(byFolder.entries()).map(([folder, entries]) => ({
    folder,
    entries,
  }));
}

// ---------- Panel orchestrator ----------

export function PanelOrphans(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const openDialog = useDialogsStore((s) => s.open);
  const orphans = useOrphansStore((s) => s.orphans);
  const loaded = useOrphansStore((s) => s.loaded);
  const storeError = useOrphansStore((s) => s.error);

  // Selection state — local. Per mockup hand-off note: selection is a
  // transient adjudication action that does NOT persist across tab
  // switches, so component-local ``Set<string>`` is exactly the right
  // shape.
  const [selected, setSelected] = React.useState<Set<string>>(
    () => new Set(),
  );
  const [folderFilter, setFolderFilter] = React.useState<string>(FILTER_ALL);
  const [domainFilter, setDomainFilter] = React.useState<string>(FILTER_ALL);
  const [restoringPaths, setRestoringPaths] = React.useState<Set<string>>(
    () => new Set(),
  );
  const [deletingPaths, setDeletingPaths] = React.useState<Set<string>>(
    () => new Set(),
  );

  // First-mount fetch.
  React.useEffect(() => {
    void useOrphansStore.getState().refresh();
  }, []);

  // Filter dropdown options — derive from data.
  const allFolders = React.useMemo(() => {
    const set = new Set<string>();
    for (const o of orphans) set.add(o.watched_folder_id);
    return Array.from(set).sort();
  }, [orphans]);
  const allDomains = React.useMemo(() => {
    const set = new Set<string>();
    for (const o of orphans) set.add(o.domain);
    return Array.from(set).sort();
  }, [orphans]);

  // Apply filters before grouping.
  const filteredOrphans = React.useMemo(() => {
    return orphans.filter((o) => {
      if (folderFilter !== FILTER_ALL && o.watched_folder_id !== folderFilter)
        return false;
      if (domainFilter !== FILTER_ALL && o.domain !== domainFilter)
        return false;
      return true;
    });
  }, [orphans, folderFilter, domainFilter]);

  const groups = React.useMemo(() => groupByFolder(filteredOrphans), [filteredOrphans]);

  // Selection helpers.
  const toggleRow = React.useCallback((notePath: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(notePath)) next.delete(notePath);
      else next.add(notePath);
      return next;
    });
  }, []);
  const toggleGroup = React.useCallback(
    (folderId: string) => {
      setSelected((prev) => {
        const next = new Set(prev);
        const groupEntries = filteredOrphans.filter(
          (o) => o.watched_folder_id === folderId,
        );
        const allSelected = groupEntries.every((e) =>
          next.has(e.note_path),
        );
        if (allSelected) {
          for (const e of groupEntries) next.delete(e.note_path);
        } else {
          for (const e of groupEntries) next.add(e.note_path);
        }
        return next;
      });
    },
    [filteredOrphans],
  );
  const clearSelection = React.useCallback(() => {
    setSelected(new Set());
  }, []);

  // The filteredOrphans-relative selection count drives the bulk bar.
  // We deliberately count the intersection (selected ∩ filteredOrphans)
  // so an active filter showing 0 selected rows hides the bar even if
  // there are off-screen selections.
  const visibleSelectedCount = React.useMemo(() => {
    let n = 0;
    for (const o of filteredOrphans) if (selected.has(o.note_path)) n += 1;
    return n;
  }, [filteredOrphans, selected]);
  const totalVisible = filteredOrphans.length;

  // ----- Per-row restore -----

  const handleRestore = React.useCallback(
    async (notePath: string) => {
      const entry = orphans.find((o) => o.note_path === notePath);
      const title = entry ? titleFromNotePath(notePath) : notePath;
      // Optimistic drop — restore is fully reversible by re-orphan on
      // next sync if the source is still missing (mockup §Interaction).
      useOrphansStore.getState().removeOrphanOptimistic(notePath);
      setRestoringPaths((prev) => {
        const next = new Set(prev);
        next.add(notePath);
        return next;
      });
      // Drop from selection if present so the bulk bar stays correct.
      setSelected((prev) => {
        if (!prev.has(notePath)) return prev;
        const next = new Set(prev);
        next.delete(notePath);
        return next;
      });
      try {
        await useOrphansStore.getState().restoreOrphan(notePath);
        pushToast({
          lead: "Note restored.",
          msg: `${title} is back in your knowledge base.`,
          variant: "success",
        });
      } catch (err) {
        // API failed — restore the row by re-fetching the canonical
        // server list (mirrors the panel-domains rollback pattern).
        await useOrphansStore.getState().refresh();
        pushToast({
          lead: "Couldn't restore.",
          msg: err instanceof Error ? err.message : "Unknown error.",
          variant: "danger",
        });
      } finally {
        setRestoringPaths((prev) => {
          const next = new Set(prev);
          next.delete(notePath);
          return next;
        });
      }
    },
    [orphans, pushToast],
  );

  // ----- Per-row delete (opens single-note typed-confirm modal) -----

  const handleDelete = React.useCallback(
    (entry: OrphanEntry) => {
      const slug = slugFromNotePath(entry.note_path);
      const title = titleFromNotePath(entry.note_path);
      openDialog({
        kind: "typed-confirm",
        eyebrow: "ORPHAN MANAGEMENT",
        title: "Delete this orphaned note?",
        body: `The source file for this note no longer exists. Deleting moves the note to your vault's trash. You can restore it from ~/Documents/brain/.brain/trash/ within 30 days, or undo this with brain_undo_last.`,
        word: slug,
        danger: true,
        onConfirm: async () => {
          // Optimistic drop — typed-confirm has already gated the
          // destructive action.
          useOrphansStore.getState().removeOrphanOptimistic(entry.note_path);
          setDeletingPaths((prev) => {
            const next = new Set(prev);
            next.add(entry.note_path);
            return next;
          });
          setSelected((prev) => {
            if (!prev.has(entry.note_path)) return prev;
            const next = new Set(prev);
            next.delete(entry.note_path);
            return next;
          });
          try {
            await useOrphansStore.getState().deleteOrphan(entry.note_path);
            pushToast({
              lead: "Note deleted.",
              msg: `${title} moved to .brain/trash/. Undo via brain_undo_last.`,
              variant: "success",
            });
          } catch (err) {
            await useOrphansStore.getState().refresh();
            pushToast({
              lead: "Couldn't delete.",
              msg: err instanceof Error ? err.message : "Unknown error.",
              variant: "danger",
            });
          } finally {
            setDeletingPaths((prev) => {
              const next = new Set(prev);
              next.delete(entry.note_path);
              return next;
            });
          }
        },
      });
    },
    [openDialog, pushToast],
  );

  // ----- Bulk restore -----

  const handleBulkRestore = React.useCallback(async () => {
    const paths = Array.from(selected).filter((p) =>
      filteredOrphans.some((o) => o.note_path === p),
    );
    if (paths.length === 0) return;
    // Mark every selected row as restoring so the fade lands together;
    // optimistic drop all of them.
    setRestoringPaths((prev) => {
      const next = new Set(prev);
      for (const p of paths) next.add(p);
      return next;
    });
    for (const p of paths) {
      useOrphansStore.getState().removeOrphanOptimistic(p);
    }
    // Sequential calls — the backend has no batch endpoint (T5 only
    // shipped per-note tools). Sequential keeps the optimistic-drop +
    // failure-reconcile pattern simple and avoids overlapping
    // ``refresh()`` calls that share an in-flight Promise.
    let okCount = 0;
    let firstErr: Error | null = null;
    for (const p of paths) {
      try {
        await useOrphansStore.getState().restoreOrphan(p);
        okCount += 1;
      } catch (err) {
        if (!firstErr) {
          firstErr = err instanceof Error ? err : new Error(String(err));
        }
      }
    }
    setRestoringPaths((prev) => {
      const next = new Set(prev);
      for (const p of paths) next.delete(p);
      return next;
    });
    // Clear selection regardless — leaving stale checks creates the
    // wrong affordance after an action completes.
    setSelected(new Set());
    if (firstErr && okCount === 0) {
      // Reconcile so failed rows reappear.
      await useOrphansStore.getState().refresh();
      pushToast({
        lead: "Couldn't restore.",
        msg: firstErr.message,
        variant: "danger",
      });
    } else if (firstErr) {
      await useOrphansStore.getState().refresh();
      pushToast({
        lead: `${okCount} of ${paths.length} notes restored.`,
        msg: `${paths.length - okCount} failed. ${firstErr.message}`,
        variant: "warn",
      });
    } else {
      pushToast({
        lead: `${paths.length} note${paths.length === 1 ? "" : "s"} restored.`,
        msg: "They're back in your knowledge base.",
        variant: "success",
      });
    }
  }, [filteredOrphans, selected, pushToast]);

  // ----- Bulk delete (opens single batch typed-confirm modal) -----

  const handleBulkDelete = React.useCallback(() => {
    const paths = Array.from(selected).filter((p) =>
      filteredOrphans.some((o) => o.note_path === p),
    );
    const n = paths.length;
    if (n === 0) return;
    const phrase = `delete ${n} note${n === 1 ? "" : "s"}`;
    openDialog({
      kind: "typed-confirm",
      eyebrow: "ORPHAN MANAGEMENT",
      title: `Delete ${n} orphaned note${n === 1 ? "" : "s"}?`,
      body: `The source files for these notes no longer exist. Deleting moves them to your vault's trash. You can restore each one from ~/Documents/brain/.brain/trash/ within 30 days, or undo the whole batch with brain_undo_last.`,
      word: phrase,
      danger: true,
      onConfirm: async () => {
        setDeletingPaths((prev) => {
          const next = new Set(prev);
          for (const p of paths) next.add(p);
          return next;
        });
        for (const p of paths) {
          useOrphansStore.getState().removeOrphanOptimistic(p);
        }
        let okCount = 0;
        let firstErr: Error | null = null;
        for (const p of paths) {
          try {
            await useOrphansStore.getState().deleteOrphan(p);
            okCount += 1;
          } catch (err) {
            if (!firstErr) {
              firstErr = err instanceof Error ? err : new Error(String(err));
            }
          }
        }
        setDeletingPaths((prev) => {
          const next = new Set(prev);
          for (const p of paths) next.delete(p);
          return next;
        });
        setSelected(new Set());
        if (firstErr && okCount === 0) {
          await useOrphansStore.getState().refresh();
          pushToast({
            lead: "Couldn't delete.",
            msg: firstErr.message,
            variant: "danger",
          });
        } else if (firstErr) {
          await useOrphansStore.getState().refresh();
          pushToast({
            lead: `${okCount} of ${n} notes deleted.`,
            msg: `${n - okCount} failed. ${firstErr.message}`,
            variant: "warn",
          });
        } else {
          pushToast({
            lead: `${n} note${n === 1 ? "" : "s"} deleted.`,
            msg: "Moved to .brain/trash/. Undo via brain_undo_last.",
            variant: "success",
          });
        }
      },
    });
  }, [filteredOrphans, openDialog, pushToast, selected]);

  // ---------- Render ----------

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Orphaned notes
        </h2>
        <p className="text-[11px] text-[var(--text-muted)]">
          These notes used to come from watched folders, but their source
          files no longer exist. Restore brings them back into your
          knowledge base; delete moves them to trash.
        </p>
      </header>

      {/* Inline error banner — surfaces a failed
          ``useOrphansStore.refresh()``. Mirrors the
          ``panel-watched-folders`` error-banner pattern. */}
      {storeError && (
        <div
          role="alert"
          data-testid="orphans-error-banner"
          className="rounded-md border border-[var(--hairline-strong)] bg-[var(--surface-2)] p-3 text-xs text-[var(--danger,_#FF4503)]"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <span className="font-semibold">
                Couldn&rsquo;t load orphans.
              </span>{" "}
              <span className="text-[var(--text)]">{storeError.message}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void useOrphansStore.getState().refresh()}
              data-testid="orphans-retry"
              aria-label="Retry loading orphans"
              className="h-7 gap-1 px-2 text-xs"
            >
              <RotateCw className="h-3 w-3" />
              Try again
            </Button>
          </div>
        </div>
      )}

      {!loaded ? (
        // Loading state — three skeleton rows + sr-only announcement.
        <div
          role="status"
          aria-live="polite"
          data-testid="orphans-loading"
          className="flex flex-col gap-2"
        >
          <span className="sr-only">Loading orphans…</span>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-md border border-[var(--hairline)] bg-[var(--surface-2)]"
            />
          ))}
        </div>
      ) : orphans.length === 0 ? (
        // Empty state — centered card with "good news" --ok accent.
        <div
          data-testid="orphans-empty-state"
          className="mx-auto flex w-full max-w-md flex-col items-center gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-6 text-center"
        >
          <CheckCircle2
            className="h-10 w-10"
            style={{ color: "var(--ok, #4ADE80)" }}
            aria-hidden="true"
          />
          <h3 className="text-sm font-semibold text-[var(--text)]">
            No orphaned notes.
          </h3>
          <p className="text-[11px] text-[var(--text-muted)]">
            Every note in your vault still has a source file behind it.
            Nice work.
          </p>
          <Link
            href="/settings/watched-folders"
            data-testid="orphans-empty-link"
            className="text-[11px] text-[var(--tt-cyan)] hover:underline"
          >
            View watched folders ›
          </Link>
        </div>
      ) : (
        // Populated state — filters, bulk bar, groups.
        <>
          {/* Filter row */}
          <div
            className="flex flex-wrap items-center gap-3"
            data-testid="orphans-filter-row"
          >
            <label className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
              Filter by folder:
              <Select
                value={folderFilter}
                onValueChange={(v) => setFolderFilter(v)}
              >
                <SelectTrigger
                  className="h-7 w-[200px] text-xs"
                  data-testid="orphans-filter-folder"
                  aria-label="Filter by folder"
                >
                  <SelectValue placeholder="All folders" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={FILTER_ALL}>All folders</SelectItem>
                  {allFolders.map((f) => (
                    <SelectItem key={f} value={f}>
                      {f}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
              Filter by domain:
              <Select
                value={domainFilter}
                onValueChange={(v) => setDomainFilter(v)}
              >
                <SelectTrigger
                  className="h-7 w-[160px] text-xs"
                  data-testid="orphans-filter-domain"
                  aria-label="Filter by domain"
                >
                  <SelectValue placeholder="All domains" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={FILTER_ALL}>All domains</SelectItem>
                  {allDomains.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <span
              data-testid="orphans-selection-count"
              aria-live="polite"
              className="ml-auto text-[11px] text-[var(--text-muted)]"
            >
              {visibleSelectedCount > 0
                ? `${visibleSelectedCount} selected of ${totalVisible}`
                : `${totalVisible} orphan${totalVisible === 1 ? "" : "s"}`}
            </span>
          </div>

          {/* Bulk-action bar — sticky-top, only shown when ≥1 selected. */}
          {visibleSelectedCount > 0 && (
            <div
              role="region"
              aria-label="Bulk actions for selected orphans"
              data-testid="orphans-bulk-bar"
              className="sticky top-0 z-10 flex flex-wrap items-center gap-3 rounded-md border border-[var(--hairline-strong)] bg-[var(--surface-2)] px-3 py-2"
            >
              <span className="text-xs font-medium text-[var(--text)]">
                Selected: {visibleSelectedCount}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleBulkRestore()}
                data-testid="orphans-bulk-restore"
                className="h-7 gap-1 px-2 text-xs"
              >
                <RotateCcw className="h-3 w-3" aria-hidden="true" />
                Restore selected
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleBulkDelete}
                data-testid="orphans-bulk-delete"
                className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
              >
                <Trash2 className="h-3 w-3" aria-hidden="true" />
                Delete selected…
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearSelection}
                data-testid="orphans-bulk-clear"
                className="ml-auto h-7 gap-1 px-2 text-xs"
              >
                Clear selection
              </Button>
            </div>
          )}

          {/* Groups by source folder. */}
          {groups.length === 0 ? (
            <p
              data-testid="orphans-filter-empty"
              className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-center text-xs text-[var(--text-muted)]"
            >
              No orphans match the current filters.
            </p>
          ) : (
            groups.map((group) => {
              const domainsInGroup = Array.from(
                new Set(group.entries.map((e) => e.domain)),
              );
              const count = group.entries.length;
              const allInGroupSelected = group.entries.every((e) =>
                selected.has(e.note_path),
              );
              return (
                <section
                  key={group.folder}
                  data-testid="orphan-group"
                  data-folder={group.folder}
                  className="flex flex-col gap-2"
                >
                  <h3
                    className="flex flex-wrap items-center gap-2 border-t border-[var(--hairline)] pt-3 text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
                    aria-label={`${count} orphans from ${group.folder}, in ${domainsInGroup.join(", ")} domain`}
                  >
                    <span>From</span>
                    <span className="font-mono normal-case tracking-normal text-[var(--text-muted)]">
                      {group.folder}
                    </span>
                    {domainsInGroup.map((d) => (
                      <span
                        key={d}
                        data-testid={`orphan-group-domain-${d}`}
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
                        style={{
                          background: `var(--dom-${d}-soft, var(--surface-2))`,
                          color: `var(--dom-${d}, var(--text-muted))`,
                        }}
                      >
                        <span
                          aria-hidden="true"
                          className="mr-1 h-1.5 w-1.5 rounded-full"
                          style={{ background: accentFor(d) }}
                        />
                        {d}
                      </span>
                    ))}
                    <span className="normal-case tracking-normal">
                      · {count} orphan{count === 1 ? "" : "s"}
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleGroup(group.folder)}
                      data-testid={`orphan-group-select-all-${group.folder}`}
                      aria-label={`Select all orphans from ${group.folder}`}
                      className="ml-auto text-[10px] lowercase tracking-normal text-[var(--text-muted)] underline-offset-2 hover:text-[var(--text)] hover:underline"
                    >
                      {allInGroupSelected ? "clear all" : "select all"}
                    </button>
                  </h3>
                  <ul
                    role="list"
                    data-testid="orphan-group-list"
                    className="flex flex-col gap-2"
                  >
                    {group.entries.map((entry) => (
                      <OrphanRow
                        key={entry.note_path}
                        entry={entry}
                        selected={selected.has(entry.note_path)}
                        onToggleSelect={toggleRow}
                        onRestore={(p) => void handleRestore(p)}
                        onDelete={handleDelete}
                        restoring={restoringPaths.has(entry.note_path)}
                        deleting={deletingPaths.has(entry.note_path)}
                      />
                    ))}
                  </ul>
                </section>
              );
            })
          )}
        </>
      )}
    </div>
  );
}
