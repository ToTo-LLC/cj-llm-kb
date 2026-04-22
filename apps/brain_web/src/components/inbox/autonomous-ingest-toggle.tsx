"use client";

import * as React from "react";

import { Switch } from "@/components/ui/switch";
import { configSet } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * AutonomousIngestToggle (Plan 07 Task 17) — single switch in the inbox
 * header bound to ``autonomous.ingest``. Turning it on means new ingest
 * patches apply without showing up on the pending queue (the autonomy
 * gate still enforces scope + domain + budget).
 *
 * This is the inbox-scoped counterpart to ``<AutonomousToggle />`` on
 * the pending screen. We deliberately keep both components because
 * their contexts differ: the pending screen shows all five categories
 * side-by-side for bulk configuration; the inbox only needs the one
 * toggle relevant to its surface.
 */

export interface AutonomousIngestToggleProps {
  /** Optional initial value; caller may seed from ``brain_config_get``. */
  initial?: boolean;
}

export function AutonomousIngestToggle({
  initial = false,
}: AutonomousIngestToggleProps): React.ReactElement {
  const [on, setOn] = React.useState<boolean>(initial);
  const pushToast = useSystemStore((s) => s.pushToast);

  const toggle = async (next: boolean) => {
    const prev = on;
    setOn(next);
    try {
      await configSet({ key: "autonomous.ingest", value: next });
      pushToast({
        lead: next ? "Autonomous ingest on." : "Autonomous ingest off.",
        msg: `autonomous.ingest → ${next ? "enabled" : "disabled"}`,
        variant: "success",
      });
    } catch {
      setOn(prev);
      pushToast({
        lead: "Failed to save.",
        msg: "Could not update autonomous.ingest. Your toggle was reverted.",
        variant: "danger",
      });
    }
  };

  return (
    <label className="flex items-center gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-2 py-1.5 text-[11px]">
      <Switch
        checked={on}
        onCheckedChange={(v) => void toggle(Boolean(v))}
        aria-label="autonomous.ingest"
      />
      <span className="font-medium">Autonomous ingest</span>
      <span className="ml-2 text-[10px] text-[var(--text-dim)]">
        New sources apply without review.
      </span>
    </label>
  );
}
