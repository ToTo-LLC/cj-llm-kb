"use client";

import * as React from "react";
import { Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Modal } from "./modal";

/**
 * RepairConfigDialog (Plan 16 Task 9 — SCAFFOLD).
 *
 * Per Plan 16 D9, this is a minimal dialog scaffold that satisfies the
 * ``a11y-populated.spec.ts`` gate AND lays the groundwork for full UI in
 * Task 33. Plan 14 Task 3 deferral receipt (``apps/brain_web/tests/e2e/
 * a11y-populated.spec.ts`` lines 19-23) asked for a UI surface so axe-core
 * can scan it.
 *
 * Full implementation (Re-run / per-step / Re-apply controls, telemetry
 * read-out, ``Config.config_version`` integration) lands at Task 33 once
 * Task 34 ships the underlying infrastructure. The ``onRunRepair`` prop is
 * a deliberate stub here — callers may pass nothing and the button reduces
 * to a glorified ``onClose``.
 *
 * Microcopy is verbatim per the Task 9 spec:
 *   - Title:       "Repair config"
 *   - Description: "If your config.json is corrupted, brain falls back to
 *                   .bak then defaults."
 *   - Primary CTA: "Run repair"
 *   - Secondary:   "Cancel"
 *
 * Local-state ``isOpen`` / ``onClose`` (rather than ``dialogs-store``) is
 * intentional: this is a Settings-scoped dialog whose only entry is the
 * General panel's "Repair config" button. Routing it through the global
 * store would buy nothing and add a discriminated-union case the scaffold
 * doesn't need yet.
 */
export interface RepairConfigDialogProps {
  isOpen: boolean;
  onClose: () => void;
  /**
   * Stub callback. Task 33 replaces this with a real ``repairConfig()``
   * action. If omitted, the primary button collapses to ``onClose`` so
   * the scaffold dialog still cleanly dismisses.
   */
  onRunRepair?: () => void;
}

export function RepairConfigDialog({
  isOpen,
  onClose,
  onRunRepair,
}: RepairConfigDialogProps): React.ReactElement {
  const handleRun = React.useCallback(() => {
    if (onRunRepair) {
      onRunRepair();
    }
    onClose();
  }, [onRunRepair, onClose]);

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Repair config"
      description="If your config.json is corrupted, brain falls back to .bak then defaults."
      width={480}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleRun} className="gap-2">
            <Wrench className="h-3.5 w-3.5" /> Run repair
          </Button>
        </>
      }
    >
      <p className="text-muted-foreground">
        If your <code className="font-mono text-xs">config.json</code> is
        corrupted, brain falls back to{" "}
        <code className="font-mono text-xs">.bak</code> then defaults.
      </p>
    </Modal>
  );
}
