"use client";

import * as React from "react";

import type { InboxTab } from "@/lib/state/inbox-store";
import { cn } from "@/lib/utils";

/**
 * InboxTabs (Plan 07 Task 17) — three-way chip toggle above the inbox
 * source list: "In progress", "Needs attention", "Recent". Each chip
 * renders its count as a subtle badge so the user can triage at a
 * glance.
 *
 * Plain buttons over Radix ToggleGroup: the three options form a
 * simple ARIA tablist and the pattern is already established in
 * ``<FilterBar />``.
 */

export interface InboxTabsProps {
  value: InboxTab;
  onChange: (next: InboxTab) => void;
  counts: Record<InboxTab, number>;
}

const OPTIONS: ReadonlyArray<{ key: InboxTab; label: string }> = [
  { key: "progress", label: "In progress" },
  { key: "failed", label: "Needs attention" },
  { key: "recent", label: "Recent" },
];

export function InboxTabs({
  value,
  onChange,
  counts,
}: InboxTabsProps): React.ReactElement {
  return (
    <div
      role="tablist"
      aria-label="Filter inbox sources by status"
      className="flex flex-wrap gap-2"
    >
      {OPTIONS.map((opt) => {
        const active = value === opt.key;
        const n = counts[opt.key];
        return (
          <button
            key={opt.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.key)}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] transition-colors",
              active
                ? "border-[var(--accent)] bg-[var(--accent)]/20 text-[var(--text)]"
                : "border-[var(--hairline)] bg-transparent text-[var(--text-muted)] hover:text-[var(--text)]",
            )}
          >
            <span>{opt.label}</span>
            <span
              className={cn(
                "rounded-full bg-[var(--surface-2)] px-1.5 text-[10px]",
                active && "bg-[var(--surface-1)]",
              )}
            >
              {n}
            </span>
          </button>
        );
      })}
    </div>
  );
}
