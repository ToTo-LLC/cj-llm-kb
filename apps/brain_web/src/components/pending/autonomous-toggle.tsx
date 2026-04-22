"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { Switch } from "@/components/ui/switch";
import { configSet } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";
import { cn } from "@/lib/utils";

/**
 * AutonomousToggle (Plan 07 Task 16).
 *
 * Five per-category switches in the pending-screen header that flip
 * ``autonomous.<category>`` in brain_core config. When a category is
 * ``on``, incoming patches of that kind auto-apply on arrival (the
 * autonomy gate still enforces scope + domain + budget — only the
 * "needs human" bit flips).
 *
 * ``index_rewrites`` gets a danger-flagged label because mistakenly
 * auto-rewriting index.md across a domain can erase human curation.
 * The copy reads "brain edits your index files without review" to
 * make the blast radius obvious.
 *
 * Local state mirrors the server values after a successful write. On
 * failure we revert the switch and surface a toast so the UI never
 * shows a state that disagrees with the server.
 */

type Category = "ingest" | "entities" | "concepts" | "index_rewrites" | "draft";

interface Row {
  key: Category;
  label: string;
  hint: string;
  danger?: boolean;
}

const ROWS: readonly Row[] = [
  {
    key: "ingest",
    label: "Ingest",
    hint: "New sources apply without review.",
  },
  {
    key: "entities",
    label: "Entities",
    hint: "New entity cards apply without review.",
  },
  {
    key: "concepts",
    label: "Concepts",
    hint: "New concept cards apply without review.",
  },
  {
    key: "index_rewrites",
    label: "Index rewrites",
    hint: "brain edits your index files without review.",
    danger: true,
  },
  {
    key: "draft",
    label: "Draft edits",
    hint: "Draft-mode edits apply without review.",
  },
];

export interface AutonomousToggleProps {
  /** Optional initial values; caller may seed from ``brain_config_get``. */
  initial?: Partial<Record<Category, boolean>>;
}

export function AutonomousToggle({
  initial = {},
}: AutonomousToggleProps): React.ReactElement {
  const [values, setValues] = React.useState<Record<Category, boolean>>({
    ingest: initial.ingest ?? false,
    entities: initial.entities ?? false,
    concepts: initial.concepts ?? false,
    index_rewrites: initial.index_rewrites ?? false,
    draft: initial.draft ?? false,
  });
  const pushToast = useSystemStore((s) => s.pushToast);

  const toggle = async (key: Category, next: boolean) => {
    const prev = values[key];
    setValues((s) => ({ ...s, [key]: next }));
    try {
      await configSet({ key: `autonomous.${key}`, value: next });
      pushToast({
        lead: next ? "Autonomous on." : "Autonomous off.",
        msg: `autonomous.${key} → ${next ? "enabled" : "disabled"}`,
        variant: next && key === "index_rewrites" ? "danger" : "success",
      });
    } catch {
      // Revert on failure so the UI never lies about server state.
      setValues((s) => ({ ...s, [key]: prev }));
      pushToast({
        lead: "Failed to save.",
        msg: `Could not update autonomous.${key}. Your toggle was reverted.`,
        variant: "danger",
      });
    }
  };

  return (
    <div
      className="flex flex-col gap-1"
      role="group"
      aria-label="Autonomous mode toggles"
    >
      {ROWS.map((row) => (
        <label
          key={row.key}
          className={cn(
            "flex items-center gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-2 py-1.5 text-[11px]",
          )}
        >
          <Switch
            checked={values[row.key]}
            onCheckedChange={(v) => void toggle(row.key, Boolean(v))}
            aria-label={`autonomous.${row.key}`}
          />
          <span
            className={cn(
              "font-medium",
              row.danger && "text-red-400",
              row.danger && "flex items-center gap-1",
            )}
          >
            {row.danger && <AlertTriangle className="h-3 w-3" />}
            {row.label}
          </span>
          <span className="ml-auto text-[10px] text-[var(--text-dim)]">
            {row.hint}
          </span>
        </label>
      ))}
    </div>
  );
}
