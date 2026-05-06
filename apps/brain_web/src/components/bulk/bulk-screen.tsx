"use client";

/**
 * BulkScreen (Plan 07 Task 21 → Plan 16 Task 3).
 *
 * Top-level client component for the bulk-import surface. Owns the
 * "what to render" switch between the four step panes, lifts the
 * domain list at the screen level so downstream steps don't each
 * duplicate it, and keeps the stepper + back affordance in a single
 * header row.
 *
 * Plan 16 Task 3 (D3): the domain list now reads through
 * ``useDomains()`` (Plan 12 Task 5 zustand selector) — same migration
 * shape as Plan 13 Task 2's panel-domains.tsx. The previous
 * ``useState``/``useEffect``/direct API-call triple is gone; one
 * source of truth, peer-consumer pubsub, no drift between this surface
 * and the topbar / browse / settings.
 *
 * State lives in ``useBulkStore``. This component never mutates the
 * store beyond the top-level Back button.
 */

import * as React from "react";
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useDomains } from "@/lib/hooks/use-domains";
import { useBulkStore } from "@/lib/state/bulk-store";

import { StepApply } from "./step-apply";
import { StepDryRun } from "./step-dry-run";
import { StepPickFolder } from "./step-pick-folder";
import { StepTargetDomain } from "./step-target-domain";
import { Stepper } from "./stepper";

const DOMAIN_FALLBACK = ["research", "work", "personal"] as const;

export function BulkScreen(): React.ReactElement {
  const step = useBulkStore((s) => s.step);
  const applying = useBulkStore((s) => s.applying);
  const done = useBulkStore((s) => s.done);
  const setStep = useBulkStore((s) => s.setStep);

  // Plan 16 Task 3: route through ``useDomains()`` instead of holding
  // a parallel local list hydrated from a direct API call. The
  // downstream steps want a ``readonly string[]`` of slugs,
  // so we project the store's ``DomainEntry[]`` to slugs here. The
  // ``DOMAIN_FALLBACK`` fallback covers the pre-hydration window
  // (``[]`` until the store's auto-refresh resolves) AND the error
  // case (the store stashes errors in ``store.error`` and leaves
  // ``domains`` empty), so the UI always renders sensible step panes
  // even if the backend is unavailable.
  const { domains: domainEntries } = useDomains();
  const domains = React.useMemo<readonly string[]>(
    () =>
      domainEntries.length > 0
        ? domainEntries.map((d) => d.slug)
        : DOMAIN_FALLBACK,
    [domainEntries],
  );

  const canBack = step > 1 && !applying && !done;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-[var(--hairline)] px-4 py-3">
        <Stepper step={step} />
        <div className="flex-1" />
        {canBack && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setStep(Math.max(1, step - 1) as 1 | 2 | 3 | 4)}
            data-testid="stepper-back"
          >
            <ChevronLeft className="mr-1 h-4 w-4" /> Back
          </Button>
        )}
      </header>

      <section className="flex-1 overflow-auto p-6">
        {step === 1 && <StepPickFolder />}
        {step === 2 && <StepTargetDomain domains={domains} />}
        {step === 3 && <StepDryRun domains={domains} />}
        {step === 4 && <StepApply />}
      </section>
    </div>
  );
}
