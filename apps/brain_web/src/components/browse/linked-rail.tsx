"use client";

import * as React from "react";
import Link from "next/link";

import { search as searchTool, type SearchHit } from "@/lib/api/tools";
import { extractWikilinks, resolveLink } from "@/lib/vault/wikilinks";

/**
 * LinkedRail (Plan 07 Task 18).
 *
 * Right-rail variant for the browse view. Two sections:
 *
 *   - **Backlinks** — notes linking TO the current note. We approximate
 *     via ``search({q: "[[<slug>]]"})`` and post-filter. Task 25 sweep:
 *     swap to Plan 09's ``brain_wikilink_status`` tool when available so
 *     we don't rely on BM25 for this.
 *   - **Outlinks** — slugs extracted from the current body via
 *     ``extractWikilinks``, resolved through the caller-provided
 *     ``{[slug]: path}`` index.
 */

export interface LinkedRailProps {
  /** Vault-relative path of the current note. */
  currentPath: string;
  /** Body text of the current note (used for outlink extraction). */
  currentBody: string;
  /** Slug-to-path index used to resolve outlinks. */
  slugIndex: Record<string, string>;
}

function pathSlug(path: string): string {
  return path.split("/").pop()?.replace(/\.md$/, "") ?? path;
}

export function LinkedRail({
  currentPath,
  currentBody,
  slugIndex,
}: LinkedRailProps): React.ReactElement {
  const slug = pathSlug(currentPath);
  const [backlinks, setBacklinks] = React.useState<SearchHit[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    searchTool({ query: `[[${slug}]]`, top_k: 20 })
      .then((res) => {
        if (cancelled) return;
        const hits = (res.data?.hits ?? []).filter(
          (h) => h.path !== currentPath,
        );
        setBacklinks(hits);
      })
      .catch(() => {
        if (cancelled) return;
        setBacklinks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, currentPath]);

  const outlinkLabels = React.useMemo(
    () => extractWikilinks(currentBody),
    [currentBody],
  );
  const outlinks = React.useMemo(
    () =>
      outlinkLabels.map((label) => ({
        label,
        path: resolveLink(label, slugIndex),
      })),
    [outlinkLabels, slugIndex],
  );

  return (
    <div className="linked-rail flex h-full flex-col gap-3 p-3 text-xs text-[var(--text)]">
      <section>
        <div className="mb-2 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
          Backlinks
          <span className="ml-1 text-[var(--text-dim)]">
            ({backlinks.length})
          </span>
        </div>
        {backlinks.length === 0 && (
          <div className="text-[var(--text-dim)]">No backlinks.</div>
        )}
        <div className="flex flex-col gap-1">
          {backlinks.map((hit) => (
            <Link
              key={hit.path}
              href={`/browse/${hit.path}`}
              className="rounded px-2 py-1 hover:bg-[var(--surface-3)]"
            >
              <div className="font-mono text-[10px] text-[var(--text-dim)]">
                {hit.path}
              </div>
              {hit.title && (
                <div className="text-[var(--text)]">{hit.title}</div>
              )}
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-2 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
          Outlinks
          <span className="ml-1 text-[var(--text-dim)]">
            ({outlinks.length})
          </span>
        </div>
        {outlinks.length === 0 && (
          <div className="text-[var(--text-dim)]">No outlinks.</div>
        )}
        <div className="flex flex-col gap-1">
          {outlinks.map(({ label, path }) =>
            path ? (
              <Link
                key={label}
                href={`/browse/${path}`}
                className="rounded px-2 py-1 hover:bg-[var(--surface-3)]"
              >
                <span className="wikilink">{label}</span>
              </Link>
            ) : (
              <span
                key={label}
                className="wikilink broken px-2 py-1 text-[var(--text-dim)]"
              >
                {label}
              </span>
            ),
          )}
        </div>
      </section>
    </div>
  );
}
