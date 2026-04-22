"use client";

/**
 * BulkScreen (Plan 07 Task 21).
 *
 * Top-level client component for the bulk-import surface. Owns the
 * "what to render" switch between the four step panes, lifts the
 * ``listDomains`` call so downstream steps don't each duplicate it, and
 * keeps the stepper + back affordance in a single header row.
 *
 * State lives in ``useBulkStore``. This component never mutates the
 * store beyond the top-level Back button and the one-shot domain
 * warm-up.
 */

import * as React from "react";
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { listDomains } from "@/lib/api/tools";
import { useBulkStore } from "@/lib/state/bulk-store";
import { useSystemStore } from "@/lib/state/system-store";

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
  const pushToast = useSystemStore((s) => s.pushToast);

  const [domains, setDomains] =
    React.useState<readonly string[]>(DOMAIN_FALLBACK);

  React.useEffect(() => {
    let cancelled = false;
    listDomains()
      .then((res) => {
        if (cancelled) return;
        const list = (res.data?.domains ?? []) as string[];
        if (list.length > 0) setDomains(list);
      })
      .catch(() => {
        pushToast({
          lead: "Load failed.",
          msg: "Could not fetch domains.",
          variant: "danger",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [pushToast]);

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
