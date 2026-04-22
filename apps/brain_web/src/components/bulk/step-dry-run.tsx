"use client";

/**
 * Step 3 — Dry-run review (Plan 07 Task 21).
 *
 * Renders the per-file review table backing the bulk-import dry-run. Per
 * file: include checkbox, type badge, size, route-to dropdown, confidence
 * bar, status notes (duplicate / uncertain / personal / skip reason).
 *
 * The summary sidebar counts files per routed domain + skipped. Footer
 * carries the rough cost + time estimate (napkin math on file count and
 * Sonnet token rates). Advance button kicks ``step = 4`` and the store's
 * ``startApply`` loop.
 *
 * Uses a native ``<select>`` for the per-row route dropdown rather than
 * the shadcn Select primitive — the dropdown is purely value-capture and
 * needs to round-trip through userEvent.selectOptions in the table test.
 */

import * as React from "react";
import { ChevronLeft, ChevronRight, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { useBulkStore } from "@/lib/state/bulk-store";

const TYPE_BADGE: Record<string, string> = {
  pdf: "PDF",
  text: "TXT",
  doc: "DOC",
  img: "IMG",
  email: "EML",
  url: "URL",
  sys: "SYS",
};

export interface StepDryRunProps {
  domains: readonly string[];
}

export function StepDryRun({ domains }: StepDryRunProps): React.ReactElement {
  const files = useBulkStore((s) => s.files);
  const toggleInclude = useBulkStore((s) => s.toggleInclude);
  const toggleIncludeAll = useBulkStore((s) => s.toggleIncludeAll);
  const setRoute = useBulkStore((s) => s.setRoute);
  const setStep = useBulkStore((s) => s.setStep);
  const startApply = useBulkStore((s) => s.startApply);

  const totalEligible = files.filter((f) => !f.skip).length;
  const included = files.filter((f) => f.include && !f.skip);
  const skipped = files.filter((f) => f.skip);

  const domainCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    for (const slug of domains) counts[slug] = 0;
    for (const f of files) {
      if (!f.include || f.skip || !f.classified) continue;
      counts[f.classified] = (counts[f.classified] ?? 0) + 1;
    }
    return counts;
  }, [files, domains]);

  const estimatedCost = (included.length * 0.011).toFixed(2);
  const estimatedSeconds = Math.ceil(included.length * 4);

  const allChecked =
    totalEligible > 0 && files.filter((f) => !f.skip).every((f) => f.include);

  const startImport = () => {
    // Kick the apply loop; the store sets step = 4 internally.
    void startApply();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
            Step 3 · Dry-run review
          </div>
          <h2
            className="mt-1 text-xl font-semibold text-[var(--text)]"
            data-testid="included-count"
          >
            {included.length} of {totalEligible} files will be imported.
          </h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Uncheck anything you don&apos;t want to ingest. Re-route files to a
            different domain if the classifier got it wrong.
            {skipped.length > 0 && (
              <> {skipped.length} files were skipped automatically.</>
            )}
          </p>
        </div>
        <div className="min-w-[180px] rounded-md border border-[var(--hairline)] bg-[var(--surface-subtle)] p-3 text-xs">
          {domains.map((slug) => (
            <div
              key={slug}
              className="flex items-center gap-2 py-0.5"
              data-testid={`summary-${slug}`}
            >
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  slug === "personal"
                    ? "bg-rose-500"
                    : slug === "work"
                      ? "bg-emerald-500"
                      : slug === "research"
                        ? "bg-sky-500"
                        : "bg-[var(--accent)]",
                )}
              />
              <span>
                {slug} · {domainCounts[slug]}
              </span>
            </div>
          ))}
          <div
            className="flex items-center gap-2 py-0.5 text-[var(--text-muted)]"
            data-testid="summary-skipped"
          >
            <span className="h-2 w-2 rounded-full bg-[var(--text-dim)]" />
            <span>skipped · {skipped.length}</span>
          </div>
        </div>
      </div>

      <div
        className="overflow-hidden rounded-md border border-[var(--hairline)]"
        role="table"
        aria-label="Dry-run review"
      >
        <div
          className="grid grid-cols-[32px_2fr_60px_80px_160px_140px_1fr] items-center gap-2 border-b border-[var(--hairline)] bg-[var(--surface-subtle)] px-3 py-2 text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
          role="row"
        >
          <div>
            <Checkbox
              checked={allChecked}
              onCheckedChange={(v) => toggleIncludeAll(v === true)}
              aria-label="Toggle all"
            />
          </div>
          <div>File</div>
          <div>Type</div>
          <div>Size</div>
          <div>Route to</div>
          <div>Confidence</div>
          <div>Notes</div>
        </div>

        {files.map((f) => (
          <div
            key={f.id}
            className={cn(
              "grid grid-cols-[32px_2fr_60px_80px_160px_140px_1fr] items-center gap-2 border-b border-[var(--hairline)] px-3 py-2 text-sm last:border-b-0",
              f.skip && "bg-[var(--surface-subtle)]/40 opacity-60",
            )}
            role="row"
            data-testid="dry-row"
            data-skipped={f.skip ? "true" : undefined}
            data-uncertain={f.uncertain ? "true" : undefined}
            data-flagged={f.flagged ?? undefined}
          >
            <div>
              {f.skip ? (
                <span className="text-[var(--text-dim)]">—</span>
              ) : (
                <Checkbox
                  checked={f.include}
                  onCheckedChange={() => toggleInclude(f.id)}
                  aria-label={`Include ${f.name}`}
                />
              )}
            </div>
            <div className="font-mono text-xs text-[var(--text)]">{f.name}</div>
            <div>
              <span className="rounded bg-[var(--surface-subtle)] px-1.5 py-0.5 font-mono text-[10px] uppercase text-[var(--text-muted)]">
                {TYPE_BADGE[f.type] ?? "FILE"}
              </span>
            </div>
            <div className="font-mono text-[11px] text-[var(--text-dim)]">
              {f.size}
            </div>
            <div>
              {f.skip ? (
                <span className="text-[var(--text-dim)]">—</span>
              ) : (
                <select
                  className="h-8 w-full rounded-md border border-[var(--hairline)] bg-transparent px-2 text-xs text-[var(--text)]"
                  value={f.classified ?? ""}
                  onChange={(e) => setRoute(f.id, e.target.value)}
                  aria-label={`Route for ${f.name}`}
                >
                  {f.classified == null && <option value="">—</option>}
                  {domains.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div>
              {f.skip || f.confidence == null ? (
                <span className="text-[var(--text-dim)]">—</span>
              ) : (
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-subtle)]">
                    <span
                      className="block h-full bg-[var(--accent)]"
                      style={{
                        width: `${Math.round(f.confidence * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="font-mono text-[11px] text-[var(--text-muted)]">
                    {Math.round(f.confidence * 100)}%
                  </span>
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-1 text-[10px]">
              {f.skip && (
                <span className="rounded bg-[var(--surface-subtle)] px-1.5 py-0.5 text-[var(--text-muted)]">
                  {f.skip}
                </span>
              )}
              {f.duplicate && (
                <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-600 dark:text-amber-400">
                  duplicate
                </span>
              )}
              {f.uncertain && (
                <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-600 dark:text-amber-400">
                  classifier unsure
                </span>
              )}
              {f.flagged === "personal" && (
                <span className="flex items-center gap-1 rounded bg-rose-500/15 px-1.5 py-0.5 text-rose-600 dark:text-rose-400">
                  <Lock className="h-2.5 w-2.5" /> personal
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between gap-4 border-t border-[var(--hairline)] pt-4">
        <div className="text-xs text-[var(--text-muted)]">
          <div>
            <span className="text-[var(--text-dim)]">Rough estimate</span> —
            based on file size + Sonnet token rates.
          </div>
          <div>
            <strong className="text-[var(--text)]">~${estimatedCost}</strong>{" "}
            total · ~{estimatedSeconds}s total
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => setStep(2)}>
            <ChevronLeft className="mr-1 h-4 w-4" /> Back
          </Button>
          <Button
            size="lg"
            onClick={startImport}
            data-testid="start-import"
            disabled={included.length === 0}
          >
            Import {included.length} files{" "}
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
