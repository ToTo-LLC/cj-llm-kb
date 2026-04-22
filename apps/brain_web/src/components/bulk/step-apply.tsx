"use client";

/**
 * Step 4 — Apply (Plan 07 Task 21).
 *
 * Streams the progress of the serial apply loop driven by
 * ``useBulkStore.startApply``. Progress bar + per-file state row. The
 * Cancel button sets ``cancelled = true`` — the store stops before the
 * next ingest but does not interrupt the in-flight one.
 *
 * On completion: summary line (applied / skipped / not-run) + CTA to
 * review patches in the Pending screen or import another folder.
 */

import * as React from "react";
import { Check, CircleStop } from "lucide-react";

import { Button } from "@/components/ui/button";
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

export function StepApply(): React.ReactElement {
  const files = useBulkStore((s) => s.files);
  const applying = useBulkStore((s) => s.applying);
  const applyIdx = useBulkStore((s) => s.applyIdx);
  const cancelled = useBulkStore((s) => s.cancelled);
  const done = useBulkStore((s) => s.done);
  const results = useBulkStore((s) => s.results);
  const cancel = useBulkStore((s) => s.cancel);
  const reset = useBulkStore((s) => s.reset);

  const included = files.filter((f) => f.include && !f.skip);
  const progress = included.length === 0 ? 0 : applyIdx / included.length;
  const headline = done
    ? "Import complete."
    : cancelled
      ? "Import cancelled."
      : "Importing your sources…";

  const secondary = done
    ? "Every file went through extract → classify → summarize → integrate. Review each as a patch in Pending."
    : cancelled
      ? `${applyIdx} of ${included.length} applied before you cancelled. The rest are untouched.`
      : "Each file is extracted, summarized, and staged as a patch. Cancel to stop after the in-flight file finishes.";

  return (
    <div className="mx-auto max-w-3xl">
      <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
        Step 4 · Apply
      </div>
      <h2 className="mt-1 text-xl font-semibold text-[var(--text)]">
        {headline}
      </h2>
      <p className="mt-1 text-sm text-[var(--text-muted)]">{secondary}</p>

      <div className="mt-4">
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-subtle)]"
          role="progressbar"
          aria-valuenow={applyIdx}
          aria-valuemin={0}
          aria-valuemax={included.length}
          aria-label="Bulk import progress"
          data-testid="apply-progress"
        >
          <span
            className="block h-full bg-[var(--accent)] transition-[width]"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-[var(--text-muted)]">
          {applyIdx} of {included.length} applied
        </div>
      </div>

      <div
        className="mt-5 overflow-hidden rounded-md border border-[var(--hairline)]"
        role="list"
        aria-label="Per-file apply status"
      >
        {included.slice(0, 14).map((f, i) => {
          const state =
            i < applyIdx
              ? "done"
              : i === applyIdx && applying && !cancelled
                ? "running"
                : "queued";
          return (
            <div
              key={f.id}
              role="listitem"
              className={cn(
                "flex items-center gap-3 border-b border-[var(--hairline)] px-3 py-2 text-sm last:border-b-0",
                state === "done" && "text-[var(--text-muted)]",
              )}
              data-state={state}
              data-testid="apply-row"
            >
              <span className="rounded bg-[var(--surface-subtle)] px-1.5 py-0.5 font-mono text-[10px] uppercase text-[var(--text-muted)]">
                {TYPE_BADGE[f.type] ?? "FILE"}
              </span>
              <span className="flex-1 font-mono text-xs">{f.name}</span>
              {f.classified && (
                <span className="rounded border border-[var(--hairline)] px-1.5 py-0.5 text-[10px] uppercase text-[var(--text-muted)]">
                  {f.classified}
                </span>
              )}
              <span className="flex w-24 items-center justify-end gap-1 text-xs">
                {state === "done" && (
                  <>
                    <Check className="h-3 w-3 text-emerald-500" /> applied
                  </>
                )}
                {state === "running" && (
                  <span className="text-[var(--accent)]">running…</span>
                )}
                {state === "queued" && (
                  <span className="text-[var(--text-dim)]">queued</span>
                )}
              </span>
            </div>
          );
        })}
        {included.length > 14 && !done && (
          <div className="px-3 py-2 text-center text-xs text-[var(--text-muted)]">
            + {included.length - 14} more queued
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        {applying && !done && !cancelled && (
          <Button variant="ghost" onClick={cancel} data-testid="cancel-apply">
            <CircleStop className="mr-1 h-4 w-4" /> Cancel after current file
          </Button>
        )}
        <div className="flex-1" />
        {done && (
          <>
            <div
              className="text-xs text-[var(--text-muted)]"
              data-testid="apply-summary"
            >
              <span className="text-emerald-600 dark:text-emerald-400">
                {results.applied.length} applied
              </span>
              <span className="px-1">·</span>
              <span>{results.quarantined.length} skipped</span>
              {results.failed.length > 0 && (
                <>
                  <span className="px-1">·</span>
                  <span className="text-rose-600 dark:text-rose-400">
                    {results.failed.length} failed
                  </span>
                </>
              )}
              {cancelled &&
                included.length - applyIdx > 0 &&
                ` · ${included.length - applyIdx} not run`}
            </div>
            <Button variant="ghost" onClick={reset}>
              Import another folder
            </Button>
            <a
              href="/pending"
              className="inline-flex h-9 items-center justify-center rounded-md bg-[var(--accent)] px-4 text-sm font-medium text-[var(--accent-fg,white)]"
            >
              Review in Pending →
            </a>
          </>
        )}
      </div>
    </div>
  );
}
