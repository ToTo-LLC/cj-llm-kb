"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { Switch } from "@/components/ui/switch";
import { configGet, configSet } from "@/lib/api/tools";
import {
  type AutonomousCategory,
  useSettingsStore,
} from "@/lib/state/settings-store";
import { useSystemStore } from "@/lib/state/system-store";
import { cn } from "@/lib/utils";

/**
 * PanelAutonomous (Plan 07 Task 22).
 *
 * Five per-category toggles: ingest, entities, concepts, index_rewrites,
 * draft. index_rewrites is flagged danger because auto-rewriting index
 * files can erase human curation.
 *
 * Reads initial state via ``configGet("autonomous.<cat>")`` per key.
 * Writes via ``configSet(...)`` and syncs through the settings-store so
 * the Inbox + Pending surface toggles stay consistent with this panel.
 */

interface Row {
  key: AutonomousCategory;
  label: string;
  hint: string;
  danger?: boolean;
}

const ROWS: readonly Row[] = [
  {
    key: "ingest",
    label: "Source ingest",
    hint: "New sources apply without review.",
  },
  {
    key: "entities",
    label: "Entity updates",
    hint: "New entity cards apply without review.",
  },
  {
    key: "concepts",
    label: "Concept notes",
    hint: "New concept cards apply without review.",
  },
  {
    key: "index_rewrites",
    label: "Domain index rewrites",
    hint: "brain edits your index.md files without review. Not recommended — leave this one for manual review.",
    danger: true,
  },
  {
    key: "draft",
    label: "Draft inline edits",
    hint: "Draft-mode inline edits apply without review.",
  },
];

export function PanelAutonomous(): React.ReactElement {
  const autonomous = useSettingsStore((s) => s.autonomous);
  const setAutonomous = useSettingsStore((s) => s.setAutonomous);
  const setMany = useSettingsStore((s) => s.setManyAutonomous);
  const pushToast = useSystemStore((s) => s.pushToast);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      const next: Partial<Record<AutonomousCategory, boolean>> = {};
      for (const row of ROWS) {
        try {
          const r = await configGet({ key: `autonomous.${row.key}` });
          if (typeof r.data?.value === "boolean") {
            next[row.key] = r.data.value;
          }
        } catch {
          /* defaults stay null */
        }
      }
      if (!cancelled && Object.keys(next).length > 0) setMany(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [setMany]);

  const toggle = async (key: AutonomousCategory, next: boolean) => {
    const prev = autonomous[key];
    setAutonomous(key, next);
    try {
      await configSet({ key: `autonomous.${key}`, value: next });
      pushToast({
        lead: next ? "Autonomous on." : "Autonomous off.",
        msg: `autonomous.${key} → ${next ? "enabled" : "disabled"}`,
        variant: next && key === "index_rewrites" ? "danger" : "success",
      });
    } catch {
      // Revert on failure.
      setAutonomous(key, prev ?? false);
      pushToast({
        lead: "Failed to save.",
        msg: `Could not update autonomous.${key}. Your toggle was reverted.`,
        variant: "danger",
      });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
          Autonomous mode
        </h2>
        <p className="mb-4 text-[11px] text-[var(--text-muted)]">
          When autonomous is ON for a category, matching patches apply
          without a human review step. Scope guard, domain routing, and
          budget caps are all still enforced.
        </p>

        <div
          role="group"
          aria-label="Autonomous mode toggles"
          className="flex flex-col gap-2"
        >
          {ROWS.map((row) => {
            const value = autonomous[row.key] ?? false;
            // Issue #42: split the accessible name from the description.
            // The wrapping element used to be a ``<label>`` whose text
            // content concatenated the title + hint, so the Switch
            // announced as "autonomous.ingest, switch, off, Source
            // ingest New sources apply without review." Switching to a
            // ``<div>`` plus ``aria-labelledby`` / ``aria-describedby``
            // on the Switch produces "Source ingest, switch, off, New
            // sources apply without review." instead.
            const labelId = `autonomous-label-${row.key}`;
            const descId = `autonomous-desc-${row.key}`;
            return (
              <div
                key={row.key}
                data-testid={`autonomous-row-${row.key}`}
                data-danger={row.danger ? "true" : "false"}
                className={cn(
                  "flex items-center gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2",
                  row.danger && "border-red-500/30 bg-red-500/5",
                )}
              >
                <Switch
                  checked={value}
                  onCheckedChange={(v) => void toggle(row.key, Boolean(v))}
                  aria-labelledby={labelId}
                  aria-describedby={descId}
                />
                <div className="flex flex-col">
                  <span
                    id={labelId}
                    className={cn(
                      "text-sm font-medium text-[var(--text)]",
                      row.danger && "flex items-center gap-1 text-red-400",
                    )}
                  >
                    {row.danger && (
                      <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
                    )}
                    {row.label}
                  </span>
                  <span
                    id={descId}
                    className="text-[11px] text-[var(--text-muted)]"
                  >
                    {row.hint}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
