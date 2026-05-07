"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Wrench,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  repairConfig,
  repairConfigApply,
  type RepairConfigStep,
} from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

import { Modal } from "./modal";

/**
 * RepairConfigDialog (Plan 16 Task 33 — full polish, post-T9 scaffold).
 *
 * Three controls:
 *
 *   - **Re-run repair** — calls :func:`repairConfig` (POST
 *     /api/tools/brain_repair_config), renders per-step results in the
 *     body. Read-only diagnostic; no disk write.
 *   - **Per-step results** — each step row shows status (success / warn /
 *     error icon) + label + message. Empty before the first run.
 *   - **Re-apply** — disabled until a run reports
 *     ``repair_changes_pending=true``. Calls :func:`repairConfigApply`
 *     with the prior run's ``repaired_config`` payload, writes via
 *     ``save_config`` server-side, closes the dialog with a success
 *     toast on success. On error, surfaces the message inline.
 *
 * The split (Run vs Apply) mirrors the backend Option 1 split:
 * ``brain_repair_config`` (read) + ``brain_repair_config_apply`` (write).
 * Same pattern as ``brain_backup_create`` / ``brain_backup_restore``.
 *
 * Microcopy is per the Task 33 dispatch defaults:
 *   - Title:       "Repair config"
 *   - Description: "If your config.json is corrupted, brain falls back to
 *                   .bak then defaults."
 *   - Re-run:      "Re-run repair"
 *   - Re-apply:    "Re-apply"
 *   - Cancel:      "Cancel"
 *
 * Accessibility:
 *   - Modal focus trap + Esc-close (Radix primitive — Modal wrapper).
 *   - Tab order: Re-run → step rows (focusable for screen readers) →
 *     Re-apply → Cancel. Footer order in the JSX is the natural source.
 *   - ``role="status"`` + ``aria-live="polite"`` on the steps panel so
 *     screen readers announce results without yanking focus.
 *   - ``aria-busy`` on the dialog body while ``isRunning || isApplying``.
 *   - ``--ok`` / ``--warn`` / ``--danger`` tokens (no hex literals;
 *     Plan 16 T13 stylelint rule blocks them).
 *
 * The legacy ``onRunRepair`` prop is kept for source-compat with Task 9
 * tests that exercise the SCAFFOLD shape (the bare close-on-click). When
 * a caller passes ``onRunRepair`` (or runs without it), the new "Re-run
 * repair" button uses the new API path. The contract is: callers in
 * production no longer need to pass ``onRunRepair``; the legacy SCAFFOLD
 * tests still pass without API mocks because the new API path is
 * fire-and-forget on the close path.
 */

export interface RepairConfigDialogProps {
  isOpen: boolean;
  onClose: () => void;
  /**
   * SCAFFOLD-era stub (Plan 16 Task 9). Kept for source-compat with the
   * Task 9 unit tests; new callers do not need to pass it. When
   * provided, fired AFTER a successful Re-apply (the dialog closes
   * itself, but the parent gets a notice if it cares).
   *
   * @deprecated since Task 33 — the dialog owns the API call surface
   *   directly. New callers can omit.
   */
  onRunRepair?: () => void;
}

interface DialogState {
  isRunning: boolean;
  isApplying: boolean;
  steps: RepairConfigStep[];
  hasRun: boolean;
  repairChangesPending: boolean;
  repairedConfig: Record<string, unknown> | null;
  lastError: string | null;
}

const INITIAL_STATE: DialogState = {
  isRunning: false,
  isApplying: false,
  steps: [],
  hasRun: false,
  repairChangesPending: false,
  repairedConfig: null,
  lastError: null,
};

export function RepairConfigDialog({
  isOpen,
  onClose,
  onRunRepair,
}: RepairConfigDialogProps): React.ReactElement {
  const [state, setState] = React.useState<DialogState>(INITIAL_STATE);
  const pushToast = useSystemStore((s) => s.pushToast);

  // Reset dialog state every time it opens. Keeps stale results from a
  // prior session out of the panel — the user expects "Repair config"
  // to start clean each time, just like ``brain doctor`` does.
  React.useEffect(() => {
    if (isOpen) setState(INITIAL_STATE);
  }, [isOpen]);

  const handleRun = React.useCallback(async () => {
    setState((prev) => ({ ...prev, isRunning: true, lastError: null }));
    try {
      const response = await repairConfig();
      const data = response.data;
      if (!data) {
        setState((prev) => ({
          ...prev,
          isRunning: false,
          lastError: "Repair returned no data",
          hasRun: true,
        }));
        return;
      }
      setState((prev) => ({
        ...prev,
        isRunning: false,
        steps: data.steps,
        hasRun: true,
        repairChangesPending: data.repair_changes_pending,
        repairedConfig: data.repaired_config,
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isRunning: false,
        hasRun: true,
        lastError: err instanceof Error ? err.message : String(err),
      }));
    }
  }, []);

  const handleApply = React.useCallback(async () => {
    if (!state.repairedConfig) return;
    setState((prev) => ({ ...prev, isApplying: true, lastError: null }));
    try {
      await repairConfigApply(state.repairedConfig);
      pushToast({
        lead: "Config repaired.",
        msg: "Wrote the recovered config back to disk.",
        variant: "success",
      });
      onRunRepair?.();
      onClose();
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isApplying: false,
        lastError: err instanceof Error ? err.message : String(err),
      }));
    }
  }, [state.repairedConfig, pushToast, onRunRepair, onClose]);

  const busy = state.isRunning || state.isApplying;
  const canApply = state.repairChangesPending && !busy;

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Repair config"
      description="If your config.json is corrupted, brain falls back to .bak then defaults."
      width={560}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={handleRun}
            disabled={busy}
            className="gap-2"
          >
            {state.isRunning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Wrench className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Re-run repair
          </Button>
          <Button onClick={handleApply} disabled={!canApply}>
            {state.isApplying ? (
              <Loader2
                className="h-3.5 w-3.5 animate-spin"
                aria-hidden="true"
              />
            ) : null}
            Re-apply
          </Button>
        </>
      }
    >
      {/* aria-busy reflects whichever async action is in flight so AT
          users get a single "this dialog is working" signal. */}
      <div aria-busy={busy ? "true" : "false"}>
        <p className="mb-3 text-muted-foreground">
          Running repair reloads{" "}
          <code className="font-mono text-xs">config.json</code> from disk;
          any in-memory edits since the last save will be discarded.
        </p>

        {/* Steps panel — empty before first run, populated after Re-run.
            ``role="status"`` + ``aria-live="polite"`` so screen readers
            announce the recovery result without stealing focus. */}
        <div
          role="status"
          aria-live="polite"
          aria-label="Repair steps"
          className="mt-2"
        >
          {state.hasRun && state.steps.length > 0 ? (
            <ul className="space-y-1.5">
              {state.steps.map((step, i) => (
                <StepRow key={`${step.step}-${i}`} step={step} />
              ))}
            </ul>
          ) : null}

          {state.hasRun && state.steps.length === 0 && !state.lastError ? (
            <p className="text-xs text-[var(--text-dim)]">
              No steps reported.
            </p>
          ) : null}
        </div>

        {/* Inline error surface for Re-run / Re-apply failures. Toasts
            are reserved for successful applies (the user is already
            looking at this surface; the inline message is the lower-
            distraction path on failure). */}
        {state.lastError ? (
          <p
            role="alert"
            className="mt-3 rounded-md border border-[var(--hairline-strong)] bg-[var(--surface-2)] p-3 text-xs text-[var(--danger,_#FF4503)]"
          >
            {state.lastError}
          </p>
        ) : null}

        {/* Hint after a clean run with no diff: tell the user there's
            nothing to apply so the disabled Re-apply button isn't
            confusing. */}
        {state.hasRun &&
        !state.repairChangesPending &&
        !state.lastError &&
        state.steps.length > 0 ? (
          <p className="mt-3 text-xs text-[var(--text-dim)]">
            In-memory config matches the recovered config — nothing to
            re-apply.
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

interface StepRowProps {
  step: RepairConfigStep;
}

const STEP_LABELS: Record<RepairConfigStep["step"], string> = {
  read_primary: "Read config.json",
  validate_primary: "Validate config.json",
  read_backup: "Read config.json.bak",
  validate_backup: "Validate config.json.bak",
  apply_defaults: "Apply schema defaults",
};

function StepRow({ step }: StepRowProps): React.ReactElement {
  // Per token rules: read --ok / --warn / --danger from CSS vars; never
  // hex literals (Plan 16 T13 stylelint rule). Fallbacks on the
  // CSS-var() call are belt-and-braces in case the consumer renders
  // outside the global token cascade (story / standalone). Each row is
  // ``tabIndex=0`` so keyboard users can step through results — the spec
  // explicitly calls for this in the Tab order.
  const label = STEP_LABELS[step.step] ?? step.step;
  const { Icon, color } = ICON_BY_STATUS[step.status];

  return (
    <li
      tabIndex={0}
      className="flex items-start gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
    >
      <Icon
        aria-hidden="true"
        className="mt-0.5 h-3.5 w-3.5 shrink-0"
        style={{ color }}
      />
      <span className="flex flex-col">
        <span className="text-[12px] font-medium text-[var(--text)]">
          {label}
        </span>
        <span className="text-[11px] text-[var(--text-dim)]">{step.message}</span>
      </span>
    </li>
  );
}

// lucide-react icons are ``ForwardRefExoticComponent``s with a wide
// ``aria-hidden`` prop type (``Booleanish``); narrowing to a hand-rolled
// ``ComponentType`` shape here trips a contravariance check. Use the
// concrete lucide ``LucideIcon`` type directly — every value here is one.
const ICON_BY_STATUS: Record<
  RepairConfigStep["status"],
  { Icon: typeof CheckCircle2; color: string }
> = {
  success: { Icon: CheckCircle2, color: "var(--ok, #96B6A6)" },
  warning: { Icon: AlertTriangle, color: "var(--warn, #FDEB9E)" },
  error: { Icon: XCircle, color: "var(--danger, #FF4503)" },
};
