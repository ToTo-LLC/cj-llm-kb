"use client";

/**
 * Step 2 — Target domain (Plan 07 Task 21).
 *
 * Cards for "Auto-classify" plus one per discovered domain (loaded from
 * ``brain_list_domains`` at the screen level). Selecting a card updates
 * ``useBulkStore.domain``.
 *
 * The 20-file cap input appears when ``folder.fileCount > 20``. Clamped
 * to ``[1, folder.fileCount]`` by the store. Passed through to
 * ``brain_bulk_import({max_files: cap})`` when step 3 re-runs the dry-run
 * with the final target domain.
 */

import * as React from "react";
import { ChevronLeft, ChevronRight, Folder, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useBulkStore } from "@/lib/state/bulk-store";

const DOMAIN_DOT_CLASS: Record<string, string> = {
  research: "bg-[var(--dom-research,theme(colors.blue.500))]",
  work: "bg-[var(--dom-work,theme(colors.emerald.500))]",
  personal: "bg-[var(--dom-personal,theme(colors.rose.500))]",
};

function dotColor(slug: string): string {
  return DOMAIN_DOT_CLASS[slug] ?? "bg-[var(--accent)]";
}

function niceName(slug: string): string {
  return slug.slice(0, 1).toUpperCase() + slug.slice(1);
}

export interface StepTargetDomainProps {
  domains: readonly string[];
}

export function StepTargetDomain({
  domains,
}: StepTargetDomainProps): React.ReactElement {
  const folder = useBulkStore((s) => s.folder);
  const domain = useBulkStore((s) => s.domain);
  const cap = useBulkStore((s) => s.cap);
  const setDomain = useBulkStore((s) => s.setDomain);
  const setCap = useBulkStore((s) => s.setCap);
  const setStep = useBulkStore((s) => s.setStep);

  if (!folder) {
    return (
      <div className="text-sm text-[var(--text-muted)]">
        Pick a folder first.
      </div>
    );
  }

  const total = folder.fileCount;
  const needsCap = total > 20;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
        Step 2 · Target domain
      </div>
      <h2 className="mt-1 text-xl font-semibold text-[var(--text)]">
        Where should these files land?
      </h2>

      <div className="mt-4 flex items-center gap-3 rounded-lg border border-[var(--hairline)] bg-[var(--surface-subtle)] p-3">
        <Folder className="h-4 w-4 text-[var(--text-muted)]" />
        <div className="flex-1">
          <div className="font-mono text-[13px] text-[var(--text)]">
            {folder.path}
          </div>
          <div className="text-xs text-[var(--text-muted)]">
            {total} files · picked {folder.picked}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setStep(1)}
          data-testid="change-folder"
        >
          Change
        </Button>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          className={cn(
            "rounded-lg border p-3 text-left transition-colors",
            domain === "auto"
              ? "border-[var(--accent)] bg-[var(--accent)]/5"
              : "border-[var(--hairline)] hover:border-[var(--accent)]",
          )}
          onClick={() => setDomain("auto")}
          aria-pressed={domain === "auto"}
          data-testid="route-card-auto"
        >
          <div className="mb-2 h-2.5 w-2.5 rounded-full bg-gradient-to-r from-sky-500 to-emerald-500" />
          <div className="text-sm font-medium text-[var(--text)]">
            Auto-classify
          </div>
          <div className="mt-1 text-xs text-[var(--text-muted)]">
            Let brain route each file by content. Recommended.
          </div>
        </button>
        {domains.map((d) => (
          <button
            type="button"
            key={d}
            className={cn(
              "rounded-lg border p-3 text-left transition-colors",
              domain === d
                ? "border-[var(--accent)] bg-[var(--accent)]/5"
                : "border-[var(--hairline)] hover:border-[var(--accent)]",
            )}
            onClick={() => setDomain(d)}
            aria-pressed={domain === d}
            data-testid={`route-card-${d}`}
          >
            <div className={cn("mb-2 h-2.5 w-2.5 rounded-full", dotColor(d))} />
            <div className="flex items-center gap-1 text-sm font-medium text-[var(--text)]">
              {niceName(d)}
              {d === "personal" && (
                <Lock className="h-3 w-3 text-[var(--text-muted)]" />
              )}
            </div>
            <div className="mt-1 text-xs text-[var(--text-muted)]">
              Send everything into <strong>{d}</strong>, skip classifier.
            </div>
          </button>
        ))}
      </div>

      {needsCap && (
        <div
          className="mt-5 flex items-center gap-3 rounded-lg border border-[var(--hairline)] bg-[var(--surface-subtle)] p-3"
          data-testid="cap-row"
        >
          <div className="flex-1">
            <div className="text-sm font-medium text-[var(--text)]">
              This folder has {total} files.
            </div>
            <div className="text-xs text-[var(--text-muted)]">
              brain caps bulk imports at 20 by default. Raise the cap if you
              want more in one run.
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCap(cap - 5)}
              aria-label="Decrease cap"
            >
              −
            </Button>
            <Input
              type="number"
              value={cap}
              onChange={(e) => setCap(Number(e.target.value) || 1)}
              min={1}
              max={total}
              className="w-16 text-center"
              aria-label="File cap"
              data-testid="cap-input"
            />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCap(cap + 5)}
              aria-label="Increase cap"
            >
              +
            </Button>
          </div>
        </div>
      )}

      <div className="mt-7 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={() => setStep(1)}>
          <ChevronLeft className="mr-1 h-4 w-4" /> Back
        </Button>
        <Button
          size="lg"
          onClick={() => setStep(3)}
          data-testid="to-dry-run"
        >
          Run dry-run on {Math.min(cap, total)} files{" "}
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
