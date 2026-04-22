"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search, X } from "lucide-react";

import { search as searchTool, type SearchHit } from "@/lib/api/tools";

/**
 * SearchOverlay (Plan 07 Task 18).
 *
 * ⌘K / Ctrl+K modal:
 *   - Autofocus the search input when opened.
 *   - Debounce (180 ms) and call ``search({q, top_k: 20})``.
 *   - Arrow keys move the selection; Enter opens the selected hit;
 *     Escape closes via ``onClose``.
 *   - Click on a hit routes to ``/browse/<path>`` and closes.
 *
 * The overlay is fully controlled by a parent (AppShell owns the
 * global keydown handler; see ``app-shell.tsx``). Keeping this
 * component dumb makes it trivial to swap the host if we ever
 * build a standalone search page.
 */

export interface SearchOverlayProps {
  open: boolean;
  onClose: () => void;
}

const DEBOUNCE_MS = 180;

export function SearchOverlay({
  open,
  onClose,
}: SearchOverlayProps): React.ReactElement | null {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[]>([]);
  const [cursor, setCursor] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  // Autofocus + reset when opened.
  React.useEffect(() => {
    if (!open) return;
    setQuery("");
    setHits([]);
    setCursor(0);
    // Next tick so the element exists after the conditional render.
    const id = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [open]);

  // Debounced search. Empty query → clear hits without a round-trip.
  React.useEffect(() => {
    if (!open) return;
    if (query.trim().length === 0) {
      setHits([]);
      return;
    }
    let cancelled = false;
    const id = window.setTimeout(() => {
      searchTool({ query, top_k: 20 })
        .then((res) => {
          if (cancelled) return;
          setHits(res.data?.hits ?? []);
          setCursor(0);
        })
        .catch(() => {
          if (cancelled) return;
          setHits([]);
        });
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(id);
    };
  }, [open, query]);

  const openHit = React.useCallback(
    (hit: SearchHit) => {
      router.push(`/browse/${hit.path}`);
      onClose();
    },
    [router, onClose],
  );

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setCursor((c) => Math.min(hits.length - 1, c + 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setCursor((c) => Math.max(0, c - 1));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const hit = hits[cursor];
        if (hit) openHit(hit);
      }
    },
    [hits, cursor, onClose, openHit],
  );

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Search the vault"
      className="search-overlay fixed inset-0 z-[80] flex items-start justify-center bg-black/40 p-20"
      onClick={onClose}
    >
      <div
        className="search-panel flex w-full max-w-[640px] flex-col overflow-hidden rounded-lg border border-[var(--hairline)] bg-[var(--surface-2)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="search-head flex items-center gap-2 border-b border-[var(--hairline)] px-3 py-2 text-sm text-[var(--text)]">
          <Search size={14} aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            role="searchbox"
            aria-label="Search the vault"
            placeholder="Search the vault…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="search-input flex-1 bg-transparent outline-none"
          />
          <span className="text-[11px] text-[var(--text-dim)]">
            {hits.length} results
          </span>
          <button
            type="button"
            aria-label="Close search"
            onClick={onClose}
            className="iconbtn rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-3)]"
          >
            <X size={12} />
          </button>
        </div>

        <div className="search-body max-h-[60vh] overflow-y-auto">
          {query.trim() && hits.length === 0 && (
            <div className="search-empty px-4 py-8 text-center text-sm text-[var(--text-dim)]">
              No matches. Try different words.
            </div>
          )}
          {hits.map((hit, i) => (
            <button
              key={hit.path}
              type="button"
              role="option"
              aria-selected={i === cursor}
              data-active={i === cursor ? "true" : "false"}
              onClick={() => openHit(hit)}
              onMouseEnter={() => setCursor(i)}
              className="search-hit flex w-full flex-col items-start gap-1 border-b border-[var(--hairline)] px-3 py-2 text-left last:border-none hover:bg-[var(--surface-3)] data-[active=true]:bg-[var(--surface-3)]"
            >
              <div className="sh-top flex items-center gap-2 text-[11px]">
                <span className="sh-score rounded bg-[var(--surface-4)] px-1.5 py-0.5 font-mono text-[var(--text-muted)]">
                  {hit.score.toFixed(2)}
                </span>
                <span className="sh-path font-mono text-[var(--text-muted)]">
                  {hit.path}
                </span>
              </div>
              <div className="sh-snip text-xs text-[var(--text-dim)]">
                {hit.snippet}
              </div>
            </button>
          ))}
          <div className="search-shortcuts flex gap-4 border-t border-[var(--hairline)] px-3 py-2 text-[10px] text-[var(--text-dim)]">
            <span>
              <kbd className="rounded border border-[var(--hairline)] px-1">
                ↑
              </kbd>
              <kbd className="ml-0.5 rounded border border-[var(--hairline)] px-1">
                ↓
              </kbd>{" "}
              navigate
            </span>
            <span>
              <kbd className="rounded border border-[var(--hairline)] px-1">
                ↵
              </kbd>{" "}
              open
            </span>
            <span>
              <kbd className="rounded border border-[var(--hairline)] px-1">
                Esc
              </kbd>{" "}
              close
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
