"use client";

import * as React from "react";
import { Link, FileText, Mail, File as FileIcon, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
  IngestSource,
  IngestStatus,
  IngestType,
} from "@/lib/state/inbox-store";
import { cn } from "@/lib/utils";

/**
 * SourceRow (Plan 07 Task 17) — a single ingest row inside the inbox
 * list. Layout: type badge, title + status sub-line, domain chip,
 * progress bar, status pill. Failed rows bump the error onto the
 * sub-line and expose a Retry button.
 *
 * Presentation-only: the store owns all state. The caller wires
 * ``onRetry`` from the inbox screen (Task 17 stubs it for now — retry
 * re-queues the source for ingest; the actual retry tool lands in
 * Plan 09).
 */

function typeLabel(type: IngestType): string {
  switch (type) {
    case "url":
      return "URL";
    case "pdf":
      return "PDF";
    case "text":
      return "TXT";
    case "email":
      return "EML";
    case "file":
    default:
      return "FILE";
  }
}

function TypeIcon({ type }: { type: IngestType }): React.ReactElement {
  const cls = "h-3 w-3";
  switch (type) {
    case "url":
      return <Link className={cls} />;
    case "email":
      return <Mail className={cls} />;
    case "pdf":
    case "text":
      return <FileText className={cls} />;
    case "file":
    default:
      return <FileIcon className={cls} />;
  }
}

function statusBucket(status: IngestStatus): "progress" | "done" | "failed" {
  if (status === "done") return "done";
  if (status === "failed") return "failed";
  return "progress";
}

export interface SourceRowProps {
  source: IngestSource;
  /** Invoked when the user clicks Retry on a failed row. Required when
   *  the row is ``failed`` — the button is hidden otherwise. */
  onRetry?: (source: IngestSource) => void;
}

export function SourceRow({
  source,
  onRetry,
}: SourceRowProps): React.ReactElement {
  const bucket = statusBucket(source.status);

  return (
    <div
      data-testid="source-row"
      data-status={source.status}
      className={cn(
        "grid grid-cols-[56px_1fr_auto_120px_auto] items-center gap-3 rounded-lg border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2.5",
        bucket === "failed" && "border-red-500/40",
      )}
    >
      {/* Type badge */}
      <div
        className={cn(
          "flex h-9 w-14 items-center justify-center gap-1 rounded-md bg-[var(--surface-2)] text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]",
        )}
      >
        <TypeIcon type={source.type} />
        <span>{typeLabel(source.type)}</span>
      </div>

      {/* Title + sub-line */}
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-[var(--text)]">
          {source.title}
        </div>
        <div className="truncate text-[11px] text-[var(--text-dim)]">
          {source.status === "failed" ? (
            <span className="text-red-400">
              {source.error ?? "Failed. Try again."}
            </span>
          ) : source.status === "done" ? (
            <span>
              Filed to <strong>{source.domain ?? "unclassified"}</strong>
              {typeof source.cost === "number" && (
                <> · ${source.cost.toFixed(3)}</>
              )}
            </span>
          ) : (
            <span>
              {source.status} · {source.at}
            </span>
          )}
        </div>
      </div>

      {/* Domain chip */}
      <span
        className={cn(
          "inline-flex items-center rounded-full border border-[var(--hairline)] px-2 py-0.5 text-[10px] uppercase tracking-wider",
          source.domain
            ? "bg-[var(--accent)]/15 text-[var(--text)]"
            : "text-[var(--text-dim)]",
        )}
      >
        {source.domain ?? "unclassified"}
      </span>

      {/* Progress bar */}
      <div
        className="relative h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-2)]"
        aria-hidden={bucket !== "progress"}
      >
        <span
          data-testid="source-row-progress-fill"
          className={cn(
            "block h-full rounded-full transition-[width] duration-300",
            bucket === "failed"
              ? "bg-red-500"
              : bucket === "done"
                ? "bg-emerald-500"
                : "bg-[var(--accent)]",
          )}
          style={{ width: `${Math.max(0, Math.min(100, source.progress))}%` }}
        />
      </div>

      {/* Status pill + retry */}
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
            bucket === "failed"
              ? "bg-red-500/15 text-red-400"
              : bucket === "done"
                ? "bg-emerald-500/15 text-emerald-400"
                : "bg-[var(--surface-2)] text-[var(--text-muted)]",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              bucket === "failed"
                ? "bg-red-500"
                : bucket === "done"
                  ? "bg-emerald-500"
                  : "bg-[var(--accent)]",
            )}
          />
          {source.status}
        </span>
        {bucket === "failed" && onRetry && (
          <Button
            size="sm"
            variant="ghost"
            className="gap-1"
            onClick={() => onRetry(source)}
          >
            <RotateCcw className="h-3 w-3" /> Retry
          </Button>
        )}
      </div>
    </div>
  );
}
