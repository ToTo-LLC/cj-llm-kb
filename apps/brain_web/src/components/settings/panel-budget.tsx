"use client";

import * as React from "react";
import { AlertTriangle, DollarSign } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { configGet, configSet } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelBudget (Plan 07 Task 22).
 *
 * Three controls:
 *   - Daily cap       — number input → `budget.daily_usd`.
 *   - Monthly cap     — number input → `budget.monthly_usd`. Stubbed until
 *                        Task 1's config-schema extension (noted inline).
 *   - Alert threshold — read-only display of `budget.alert_threshold_pct`.
 */

export function PanelBudget(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [daily, setDaily] = React.useState<string>("");
  const [monthly, setMonthly] = React.useState<string>("");
  const [threshold, setThreshold] = React.useState<number | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await configGet({ key: "budget.daily_usd" });
        if (!cancelled && typeof r.data?.value === "number") {
          setDaily(String(r.data.value));
        }
      } catch {
        /* leave empty */
      }
      try {
        const r = await configGet({ key: "budget.alert_threshold_pct" });
        if (!cancelled && typeof r.data?.value === "number") {
          setThreshold(r.data.value);
        }
      } catch {
        /* leave null */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const saveDaily = async () => {
    const n = Number(daily);
    if (!Number.isFinite(n) || n < 0) {
      pushToast({
        lead: "Invalid cap.",
        msg: "Enter a non-negative number.",
        variant: "danger",
      });
      return;
    }
    try {
      await configSet({ key: "budget.daily_usd", value: n });
      pushToast({
        lead: "Daily cap saved.",
        msg: `budget.daily_usd → $${n}`,
        variant: "success",
      });
    } catch {
      pushToast({
        lead: "Save failed.",
        msg: "Could not update budget.daily_usd.",
        variant: "danger",
      });
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Spend caps
        </h2>
        <p className="mb-4 text-[11px] text-[var(--text-muted)]">
          Hard kill switches, not soft warnings — when either cap is
          reached brain refuses LLM calls until the next window rolls
          over (or you call ``brain_budget_override``).
        </p>

        <div className="flex flex-col gap-3">
          <div>
            <label
              htmlFor="budget-daily"
              className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
            >
              Daily cap (USD)
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <DollarSign className="pointer-events-none absolute left-2 top-2.5 h-3.5 w-3.5 text-[var(--text-dim)]" />
                <Input
                  id="budget-daily"
                  type="number"
                  min="0"
                  step="0.5"
                  value={daily}
                  onChange={(e) => setDaily(e.target.value)}
                  className="pl-7 font-mono"
                />
              </div>
              <Button variant="default" onClick={() => void saveDaily()}>
                Save
              </Button>
            </div>
          </div>

          <div>
            <label
              htmlFor="budget-monthly"
              className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
            >
              Monthly cap (USD) — pending Task 25
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <DollarSign className="pointer-events-none absolute left-2 top-2.5 h-3.5 w-3.5 text-[var(--text-dim)]" />
                <Input
                  id="budget-monthly"
                  type="number"
                  min="0"
                  step="1"
                  value={monthly}
                  onChange={(e) => setMonthly(e.target.value)}
                  className="pl-7 font-mono"
                  disabled
                  title="budget.monthly_usd lands with the Task 25 config-schema sweep"
                />
              </div>
              <Button variant="outline" disabled>
                Save
              </Button>
            </div>
            <p className="mt-1 text-[10px] text-[var(--text-dim)]">
              Pending: add ``budget.monthly_usd`` to the config schema.
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Alerting
        </h2>
        <div className="flex items-center gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2 text-xs">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-[var(--text)]">Alert threshold</span>
          <span className="ml-auto font-mono text-[var(--text-muted)]">
            {threshold != null ? `${threshold}%` : "—"} of cap
          </span>
        </div>
        <p className="mt-2 text-[11px] text-[var(--text-muted)]">
          Read-only — warnings fire at this % of either cap. Tune via{" "}
          <code className="font-mono">brain_config_set</code> with the key{" "}
          <code className="font-mono">budget.alert_threshold_pct</code> from
          the CLI if you need a different value.
        </p>
      </section>
    </div>
  );
}
