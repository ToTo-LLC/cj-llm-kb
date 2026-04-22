"use client";

import * as React from "react";

import { readNote } from "@/lib/api/tools";

/**
 * WikilinkHover (Plan 07 Task 18).
 *
 * Debounced (150 ms) hover popover that fetches the target note
 * via ``readNote`` and renders title + first paragraph (≤220
 * chars) + domain chip + "↵ to open" hint.
 *
 * Results are cached in a module-level map so repeat hovers in
 * the same session don't round-trip. Task 25 sweep: drop the
 * cache in favour of TanStack Query once query-client is wired.
 */

interface CachedNote {
  path: string;
  domain: string;
  title: string;
  snippet: string;
}

const CACHE = new Map<string, CachedNote>();

export interface WikilinkHoverProps {
  /** Resolved vault-relative path for the hovered wikilink. */
  path: string | null;
  /** Anchor element the popover should position off of. */
  anchor: HTMLAnchorElement | null;
  /** Called when the user clicks the popover's "open" affordance. */
  onOpen: (path: string) => void;
}

export function WikilinkHover({
  path,
  anchor,
  onOpen,
}: WikilinkHoverProps): React.ReactElement | null {
  const [data, setData] = React.useState<CachedNote | null>(null);

  React.useEffect(() => {
    if (!path) {
      setData(null);
      return;
    }
    const cached = CACHE.get(path);
    if (cached) {
      setData(cached);
      return;
    }
    let cancelled = false;
    readNote({ path })
      .then((res) => {
        if (cancelled) return;
        const body = res.data?.body ?? "";
        const fm = res.data?.frontmatter ?? {};
        const domain =
          typeof fm.domain === "string"
            ? fm.domain
            : path.split("/")[0] ?? "research";
        const title =
          typeof fm.title === "string"
            ? fm.title
            : path.split("/").pop()?.replace(/\.md$/, "") ?? path;
        const firstPara = body.split(/\n\n/)[0].slice(0, 220);
        const record: CachedNote = {
          path,
          domain,
          title,
          snippet: firstPara,
        };
        CACHE.set(path, record);
        setData(record);
      })
      .catch(() => {
        if (cancelled) return;
        setData(null);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  if (!path || !anchor || !data) return null;

  const rect = anchor.getBoundingClientRect();
  const top = rect.bottom + 6;
  const left = rect.left;

  return (
    <div
      role="tooltip"
      className="wiki-hover pointer-events-auto fixed z-[70] w-[340px] overflow-hidden rounded-lg border border-[var(--hairline)] bg-[var(--surface-2)] p-3 text-xs shadow-xl"
      style={{ top, left }}
      onClick={() => onOpen(data.path)}
    >
      <div className="wh-path font-mono text-[10px] text-[var(--text-dim)]">
        {data.path}
      </div>
      <div className="wh-title mt-1 text-sm font-medium text-[var(--text)]">
        {data.title}
      </div>
      <div className="wh-body mt-1 text-[var(--text-muted)]">
        {data.snippet}
        {data.snippet.length === 220 ? "…" : ""}
      </div>
      <div className="wh-foot mt-2 flex items-center gap-2">
        <span
          className="chip inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-[var(--text)]"
          style={{ background: `var(--dom-${data.domain}-soft)` }}
        >
          {data.domain}
        </span>
        <span className="ml-auto text-[10px] text-[var(--text-dim)]">
          ↵ to open
        </span>
      </div>
    </div>
  );
}
