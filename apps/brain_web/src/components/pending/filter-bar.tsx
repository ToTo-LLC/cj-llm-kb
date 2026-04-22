"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import type { PendingFilter } from "@/lib/state/pending-store";

/**
 * FilterBar (Plan 07 Task 16) — chip row above the pending list.
 *
 * The filter values map onto the backend's patch categories (plus a
 * friendlier "notes" / "ingested" alias for the two common cases). A
 * selected chip applies to the list filter; clicking ``All`` clears it.
 */

export interface FilterBarProps {
  value: PendingFilter;
  onChange: (next: PendingFilter) => void;
  /** Optional per-category counts rendered in a subtle badge. */
  counts?: Partial<Record<PendingFilter, number>>;
}

const OPTIONS: ReadonlyArray<{ key: PendingFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "notes", label: "Notes" },
  { key: "ingested", label: "Ingested" },
  { key: "entities", label: "Entities" },
  { key: "concepts", label: "Concepts" },
  { key: "index_rewrites", label: "Index rewrites" },
  { key: "draft", label: "Draft" },
];

export function FilterBar({
  value,
  onChange,
  counts,
}: FilterBarProps): React.ReactElement {
  return (
    <div
      role="tablist"
      aria-label="Filter patches by category"
      className="flex flex-wrap gap-2"
    >
      {OPTIONS.map((opt) => {
        const active = value === opt.key;
        const count = counts?.[opt.key];
        return (
          <button
            key={opt.key}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.key)}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-3 py-1 text-[11px] transition-colors",
              active
                ? "border-[var(--accent)] bg-[var(--accent)]/20 text-[var(--text)]"
                : "border-[var(--hairline)] bg-transparent text-[var(--text-muted)] hover:text-[var(--text)]",
            )}
          >
            <span>{opt.label}</span>
            {typeof count === "number" && count > 0 && (
              <span className="rounded-full bg-[var(--surface-2)] px-1.5 text-[10px]">
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Predicate: does a patch envelope match a given filter chip?
 *
 * The tool name from the envelope already carries the mapping we need
 * (``propose_note`` → "notes", ``ingest`` → "ingested"). We don't have
 * server-side category on the list envelope yet, so this is a
 * client-side best-effort mapping — good enough for v1; a Task 25
 * sweep item can promote the category to the list envelope.
 */
export function matchesFilter(
  tool: string,
  filter: PendingFilter,
): boolean {
  if (filter === "all") return true;
  const t = tool.replace(/^brain_/, "");
  switch (filter) {
    case "notes":
      return t === "propose_note";
    case "ingested":
      return t === "ingest";
    case "entities":
      return t.includes("entit");
    case "concepts":
      return t.includes("concept");
    case "index_rewrites":
      return t.includes("index") || t.includes("brain_md");
    case "draft":
      return t.includes("draft") || t.includes("edit_open_doc");
    default:
      return true;
  }
}
