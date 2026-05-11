"use client";

import * as React from "react";
import { File as FileIcon, Plus, Search } from "lucide-react";

import { Modal } from "@/components/dialogs/modal";
import { Input } from "@/components/ui/input";
import { useAppStore } from "@/lib/state/app-store";
import { recent as recentTool, type RecentEntry } from "@/lib/api/tools";
import { cn } from "@/lib/utils";

/**
 * DocPickerDialog (Plan 07 Task 19).
 *
 * Modal for picking a vault document to open in Draft mode. Fetches
 * recent docs via ``brain_recent`` (up to 200, filtered by active
 * scope), renders a case-insensitive substring filter on the row path
 * (which carries the domain slug as its first segment, so a query like
 * ``"research"`` still matches via path), and offers a "start a blank
 * scratch doc" option below the divider that materialises as
 * ``<scope[0]>/scratch/<yyyy-mm-dd>-untitled.md``.
 *
 * Proper fuzzy ranking (Levenshtein / FZF-style) is a Task 25 sweep
 * item. Substring is plenty for the ~200-item ceiling this picker
 * operates on.
 *
 * Plan 18 T1 narrowed ``RecentEntry`` to ``{path, modified_at}`` and
 * fixed two latent bugs in this picker:
 *   - the scope filter now matches on path-prefix (``scope.some(s =>
 *     it.path.startsWith(s + "/"))``) rather than ``it.domain`` (which
 *     was always ``undefined`` at runtime, so the filter silently
 *     dropped every row when scope was non-empty).
 *   - the search filter dropped a redundant ``it.domain`` clause that
 *     threw ``TypeError: Cannot read properties of undefined`` the
 *     moment the user typed anything (the path already contains the
 *     domain slug, so the OR clause was strictly redundant).
 *
 * Keyboard model:
 *   - Filter input autofocuses.
 *   - ArrowDown / ArrowUp move the highlight through the visible rows.
 *   - Enter commits the highlighted row — or the scratch option when
 *     the row list is empty.
 */

export interface DocPickerDialogProps {
  kind: "doc-picker";
  onPick: (path: string) => void;
  onNewBlank: (path: string) => void;
  onClose: () => void;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function makeScratchPath(domain: string): string {
  return `${domain}/scratch/${todayStr()}-untitled.md`;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const delta = Date.now() - then;
  const day = 1000 * 60 * 60 * 24;
  if (delta < day) return "today";
  const days = Math.floor(delta / day);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

export function DocPickerDialog({
  onPick,
  onNewBlank,
  onClose,
}: DocPickerDialogProps) {
  const scope = useAppStore((s) => s.scope);
  const [q, setQ] = React.useState("");
  const [items, setItems] = React.useState<RecentEntry[]>([]);
  const [highlight, setHighlight] = React.useState(0);

  // Scope[0] is the destination for scratch docs per the plan; default
  // to "work" so we always produce a sensible path even if the user has
  // an empty scope list (which shouldn't happen but is worth defensive).
  const scratchDomain = scope[0] ?? "work";
  const scratchPath = makeScratchPath(scratchDomain);

  React.useEffect(() => {
    let cancelled = false;
    recentTool({ limit: 200 })
      .then((resp) => {
        if (cancelled) return;
        const all = resp.data?.items ?? [];
        // Scope filter is a cheap safety net — the backend already
        // respects scope_guard, but filtering client-side keeps out
        // stale cached rows that might straddle a scope change.
        // Plan 18 T1: path-prefix is the source of truth for which
        // domain a row belongs to; the prior ``scope.includes(it.domain)``
        // depended on a ``domain`` field the backend never emits.
        const filtered =
          scope.length > 0
            ? all.filter((it) =>
                scope.some((s) => it.path.startsWith(s + "/")),
              )
            : all;
        setItems(filtered);
      })
      .catch(() => {
        // Swallow — the empty state in the picker handles the "nothing
        // to pick" case gracefully.
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, [scope]);

  const matches = React.useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return items;
    // Plan 18 T1: the path's first segment IS the domain slug
    // (e.g., ``research/foo.md``), so a query of ``"research"`` still
    // matches via path. The prior redundant ``|| it.domain.toLowerCase()``
    // clause threw TypeError because the backend never emits ``domain``.
    return items.filter((it) => it.path.toLowerCase().includes(n));
  }, [q, items]);

  // Clamp the highlight whenever the filter changes so an offscreen
  // index doesn't leave Enter firing on a stale row.
  React.useEffect(() => {
    if (highlight >= matches.length) setHighlight(0);
  }, [matches, highlight]);

  const pickByIndex = React.useCallback(
    (idx: number) => {
      const row = matches[idx];
      if (!row) return;
      onPick(row.path);
      onClose();
    },
    [matches, onPick, onClose],
  );

  const chooseScratch = React.useCallback(() => {
    onNewBlank(scratchPath);
    onClose();
  }, [onNewBlank, onClose, scratchPath]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((i) => Math.min(matches.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (matches.length > 0) {
        pickByIndex(highlight);
      } else {
        chooseScratch();
      }
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow="Draft mode"
      title="Open a document."
      description="Pick a vault document to draft on, or start a blank scratch doc."
      width={620}
    >
      <div className="mb-3 flex items-center gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-2">
        <Search className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        <Input
          placeholder="filter by path… (try 'synthesis' or 'helios')"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
        />
        <span className="font-mono text-[11px] text-[var(--text-dim)]">
          {matches.length}
        </span>
      </div>

      <div
        className="max-h-72 overflow-y-auto rounded-md border border-[var(--hairline)]"
        role="listbox"
        aria-label="Matching documents"
      >
        {matches.length === 0 ? (
          <div className="px-3 py-8 text-center text-xs text-[var(--text-dim)]">
            No docs match{" "}
            <code className="font-mono">{q || "\u2014"}</code>.
          </div>
        ) : (
          matches.map((d, i) => {
            const parts = d.path.split("/");
            const slug = parts[parts.length - 1];
            const dir = parts.slice(0, -1).join("/") + "/";
            // Plan 18 T1: derive ``domain`` from the path's first segment.
            // The backend's ``brain_recent`` row shape is ``{path,
            // modified_at}`` only; richer display fields are reconstructed
            // at the call site (see browse-screen.tsx for the same pattern).
            const domain = parts[0] ?? "";
            const words = (d as RecentEntry & { words?: number }).words ?? 0;
            const isHot = i === highlight;
            return (
              <button
                key={d.path}
                type="button"
                role="option"
                aria-selected={isHot}
                onMouseEnter={() => setHighlight(i)}
                onClick={() => pickByIndex(i)}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors",
                  isHot
                    ? "bg-[var(--surface-2)] text-[var(--text)]"
                    : "hover:bg-[var(--surface-2)]",
                )}
              >
                <FileIcon className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
                <div className="min-w-0 flex-1 truncate">
                  <span className="text-[var(--text-dim)]">{dir}</span>
                  <span>{slug}</span>
                </div>
                <span
                  className={cn(
                    "rounded-full border border-[var(--hairline)] px-2 py-0.5 text-[10px]",
                    `dom-${domain}`,
                  )}
                >
                  {domain}
                </span>
                <span className="shrink-0 font-mono text-[10px] text-[var(--text-dim)]">
                  {words > 0 ? `${words}w · ` : ""}
                  {relativeTime(d.modified_at)}
                </span>
              </button>
            );
          })
        )}
      </div>

      <div className="my-3 flex items-center gap-2 text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
        <div className="h-px flex-1 bg-[var(--hairline)]" />
        or
        <div className="h-px flex-1 bg-[var(--hairline)]" />
      </div>

      <button
        type="button"
        onClick={chooseScratch}
        className="flex w-full items-center gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-3 text-left text-xs hover:bg-[var(--surface-2)]"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--surface-2)]">
          <Plus className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm text-[var(--text)]">
            Start a blank scratch doc
          </div>
          <div className="text-[11px] text-[var(--text-dim)]">
            lands at <code className="font-mono">{scratchPath}</code> on first
            save
          </div>
        </div>
      </button>
    </Modal>
  );
}
