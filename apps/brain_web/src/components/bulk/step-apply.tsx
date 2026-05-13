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
import { Check, CircleStop, Eye } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useBulkStore } from "@/lib/state/bulk-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";

const TYPE_BADGE: Record<string, string> = {
  pdf: "PDF",
  text: "TXT",
  doc: "DOC",
  img: "IMG",
  email: "EML",
  url: "URL",
  sys: "SYS",
};

/**
 * Plan 25 T4 — ETA estimate.
 *
 * Napkin math: each file averages ~10s for the full extract → classify →
 * summarize → integrate pipeline (real measurements during Plan 22 land
 * 8–12s for text-shaped sources; PDFs/DOCX run longer when the OCR
 * branch fires per Plan 25 T3). We compute ``remaining × 10s`` and
 * format minutes for any value ≥ 60s; below that we elide the ETA line
 * entirely (a sub-minute ETA is noise — the bar speaks for itself).
 *
 * If the apply loop has been running long enough that ``applyIdx > 0``,
 * we could swap to a measured rolling rate, but per D11 (timer-based
 * pseudo-progress) we keep the napkin assumption stable for v1.
 */
function formatEta(remaining: number): string | null {
  if (remaining <= 0) return null;
  const seconds = remaining * 10;
  if (seconds < 60) return null;
  const minutes = Math.ceil(seconds / 60);
  return `~${minutes}m`;
}

/**
 * Plan 26 T4 — leading-ellipsis truncation for the per-file filename
 * microcopy under the apply-phase progress bar. Mirrors the inline
 * helper in :file:`walk-interstitial.tsx` (rule-of-three not met yet —
 * D10 explicitly keeps these duplicated so neither side has to grow a
 * shared dependency before the abstraction earns its keep).
 *
 * The leaf filename is more useful than the prefix when a path overflows
 * 60 chars, so we keep the last 59 chars and prepend a single ellipsis.
 */
function truncatePath(path: string, max = 60): string {
  if (path.length <= max) return path;
  return `…${path.slice(-(max - 1))}`;
}

export function StepApply(): React.ReactElement {
  const files = useBulkStore((s) => s.files);
  const folder = useBulkStore((s) => s.folder);
  const bulkDomain = useBulkStore((s) => s.domain);
  const applying = useBulkStore((s) => s.applying);
  const applyIdx = useBulkStore((s) => s.applyIdx);
  const cancelled = useBulkStore((s) => s.cancelled);
  const done = useBulkStore((s) => s.done);
  const results = useBulkStore((s) => s.results);
  const currentFile = useBulkStore((s) => s.currentFile);
  const cancel = useBulkStore((s) => s.cancel);
  const reset = useBulkStore((s) => s.reset);
  const openDialog = useDialogsStore((s) => s.open);

  const included = files.filter((f) => f.include && !f.skip);
  const progress = included.length === 0 ? 0 : applyIdx / included.length;
  // Plan 25 T4 — ETA from remaining files. Only shown while applying.
  const eta = applying && !done && !cancelled
    ? formatEta(included.length - applyIdx)
    : null;
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
        {/* Plan 25 T4 — apply-phase headline microcopy. While applying we
            show "Importing N of M files" (per plan-doc verbatim). Once
            complete we fall back to the "applied" count copy. */}
        <div
          className="mb-2 text-sm font-medium text-[var(--text)]"
          data-testid="apply-headline"
        >
          {done
            ? "Done!"
            : applying && !cancelled
              ? `Importing ${applyIdx} of ${included.length} files`
              : `${applyIdx} of ${included.length} applied`}
        </div>
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
            className="block h-full bg-[var(--accent)] transition-all duration-500"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
        {eta && (
          <div
            className="mt-2 text-xs text-[var(--text-muted)]"
            data-testid="apply-eta"
          >
            Estimated time remaining: {eta}
          </div>
        )}
        {currentFile && (
          // Plan 26 T4 — per-file filename microcopy. Renders under the
          // progress bar while the apply loop has an in-flight file.
          // Truncated to 60 chars with a leading ellipsis so very long
          // paths (deep nesting, long folder names) don't break the
          // single-line layout. Cleared at complete/error/finally (D11).
          <p
            className="mt-2 text-sm text-[var(--text-muted)]"
            data-testid="apply-current-file"
            title={currentFile}
          >
            Current: {truncatePath(currentFile)}
          </p>
        )}
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
            {/* Plan 22 T15 / D6 — Bulk Import → Watch bridge. Opens the
                watch-enable modal pre-filled with the just-imported
                folder + the bulk-import domain so the user can convert
                a one-shot import into an ongoing watch without
                re-entering either field. Only renders when we have a
                folder path AND the bulk-import landed at least one file
                (an all-failed run shouldn't suggest watching). */}
            {folder && results.applied.length > 0 && (
              <Button
                variant="ghost"
                onClick={() => {
                  openDialog({
                    kind: "watch-enable",
                    prefilledFolder: folder.path,
                    // ``bulkDomain`` is "auto" when the user picked
                    // lazy classify — in that branch we don't pre-fill
                    // domain so the modal lets the user pick (defaults
                    // to the active domain).
                    prefilledDomain:
                      bulkDomain && bulkDomain !== "auto"
                        ? bulkDomain
                        : undefined,
                  });
                }}
                data-testid="bulk-watch-cta"
                className="gap-1.5"
              >
                <Eye className="h-4 w-4" />
                Watch this folder for changes
              </Button>
            )}
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
