"use client";

import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Bulk-import 4-step progress indicator (Plan 07 Task 21).
 *
 * Numbered dots for the four steps: Pick folder → Target domain →
 * Dry-run review → Apply. Completed steps swap the number for a check,
 * the active step takes the accent colour, and unreached steps stay dim.
 * Purely presentational — transitions happen in the owning screen, which
 * passes the current ``step`` in from ``useBulkStore``.
 */

export const BULK_STEP_LABELS: readonly string[] = [
  "Pick folder",
  "Target domain",
  "Dry-run review",
  "Apply",
];

export interface StepperProps {
  /** Current active step (1-indexed). */
  step: 1 | 2 | 3 | 4;
}

export function Stepper({ step }: StepperProps): React.ReactElement {
  return (
    <ol
      className="flex items-center gap-4"
      aria-label="Bulk import progress"
      data-testid="bulk-stepper"
    >
      {BULK_STEP_LABELS.map((label, i) => {
        const n = (i + 1) as 1 | 2 | 3 | 4;
        const done = step > n;
        const active = step === n;
        return (
          <li
            key={n}
            className={cn(
              "flex items-center gap-2 text-sm",
              active && "text-[var(--text)] font-medium",
              done && "text-[var(--text-muted)]",
              !active && !done && "text-[var(--text-dim)]",
            )}
            aria-current={active ? "step" : undefined}
            data-active={active ? "true" : undefined}
            data-done={done ? "true" : undefined}
          >
            <span
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full border text-[11px]",
                active &&
                  "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-fg,white)]",
                done &&
                  "border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--accent)]",
                !active &&
                  !done &&
                  "border-[var(--hairline)] text-[var(--text-dim)]",
              )}
            >
              {done ? <Check className="h-3 w-3" /> : n}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
