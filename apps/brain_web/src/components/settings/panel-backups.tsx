"use client";

import * as React from "react";
import { AlertTriangle, Archive, Save } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * PanelBackups (Plan 07 Task 22).
 *
 * Stubbed panel. The Task 25 sweep will add the backend tools:
 *   - ``brain_backup_create``
 *   - ``brain_backup_list``
 *   - ``brain_backup_restore``
 *
 * Until they land, render the panel chrome with an empty list, a
 * disabled "Back up now" button (with a tooltip), and a "Coming soon"
 * explainer so the route stays reachable without crashing.
 */

export function PanelBackups(): React.ReactElement {
  return (
    <div className="flex flex-col gap-6">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
              <Archive className="h-3.5 w-3.5" />
              Vault backups
            </h2>
            <p className="mt-1 text-[11px] text-[var(--text-muted)]">
              Scheduled snapshots of the vault, plus on-demand backups.
              Restore rewinds the vault to any listed point.
            </p>
          </div>
          <Button
            disabled
            className="gap-2"
            title="Backup tooling lands with the Task 25 sweep (brain_backup_create)."
          >
            <Save className="h-3.5 w-3.5" />
            Back up now
          </Button>
        </div>

        <div
          data-testid="backups-empty"
          className="rounded-md border border-dashed border-[var(--hairline)] bg-[var(--surface-1)] p-8 text-center"
        >
          <Archive
            aria-hidden="true"
            className="mx-auto mb-3 h-8 w-8 text-[var(--text-dim)]"
          />
          <h3 className="text-sm font-medium text-[var(--text)]">
            No backups yet.
          </h3>
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
            Backup list renders here once tooling ships.
          </p>
        </div>
      </section>

      <section>
        <div
          className="flex items-start gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-100"
          role="status"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <div>
            <div className="mb-1 font-medium">Coming soon</div>
            <p className="text-[11px] text-amber-100/90">
              Backup tooling is part of the Task 25 sweep. The tools
              (<code className="font-mono">brain_backup_create</code>,{" "}
              <code className="font-mono">brain_backup_list</code>, and{" "}
              <code className="font-mono">brain_backup_restore</code>) and
              the restore typed-confirm flow will light up this panel
              end-to-end once they land.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
