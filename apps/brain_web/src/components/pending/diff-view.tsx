"use client";

import * as React from "react";
import { FileIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * DiffView (Plan 07 Task 16) — read-only line-diff renderer.
 *
 * The backend PatchSet does NOT carry a precomputed unified diff on
 * edits. It ships ``new_files: [{path, content}]`` (every line is an
 * addition — no previous state) and ``edits: [{path, old, new}]``
 * (full before/after strings). The pending screen synthesizes a
 * line-level diff via :func:`synthesizeDiff` below and passes the
 * resulting ``DiffLine[]`` here for presentation.
 *
 * Rendering choices:
 *   - Each row is a flex line: ``[gutter]  [± marker]  [code]``.
 *   - Gutter is the line number in the target file (1-indexed).
 *   - add  → green tint
 *   - del  → red tint
 *   - ctx  → dim (context / unchanged)
 *   - monospace throughout
 *
 * We deliberately don't reach for a third-party diff library here —
 * the inputs are small (single-note patches, ~1 KB) and the output
 * shape is simple. A hand-rolled LCS-like pass keeps the client
 * bundle small and the rendering primitives matrix-friendly for the
 * token-scale design system.
 */

export interface DiffLine {
  /** "add" (green), "del" (red), or "ctx" (unchanged). */
  type: "add" | "del" | "ctx";
  /** 1-indexed line number in the target file. */
  n: number;
  /** The line text, verbatim (no trailing newline). */
  code: string;
}

export interface DiffViewProps {
  targetPath: string;
  lines: DiffLine[];
  /** Extra CSS on the outer container. */
  className?: string;
}

export function DiffView({
  targetPath,
  lines,
  className,
}: DiffViewProps): React.ReactElement {
  const addedCount = lines.filter((l) => l.type === "add").length;
  const removedCount = lines.filter((l) => l.type === "del").length;

  return (
    <div
      className={cn(
        "rounded-md border border-[var(--hairline)] bg-[var(--surface-1)]",
        className,
      )}
      role="group"
      aria-label={`Diff preview for ${targetPath}`}
    >
      <div className="flex items-center gap-2 border-b border-[var(--hairline)] px-3 py-2 text-xs">
        <FileIcon className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        <span className="font-mono text-[var(--text)]">{targetPath}</span>
        <span className="ml-auto text-[var(--text-dim)]">
          {addedCount} added, {removedCount} removed · read-only preview
        </span>
      </div>
      <div className="diff-body overflow-auto p-2 font-mono text-xs leading-relaxed">
        {lines.map((l, i) => (
          <div
            key={i}
            className={cn(
              "diff-line flex gap-3 whitespace-pre px-2",
              l.type,
              l.type === "add" && "bg-green-950/30 text-green-300",
              l.type === "del" && "bg-red-950/30 text-red-300",
              l.type === "ctx" && "text-[var(--text-dim)]",
            )}
          >
            <span
              className="gutter w-10 select-none text-right text-[var(--text-dim)]"
              role="rowheader"
              aria-label={`line ${l.n}`}
            >
              {l.n}
            </span>
            <span className="marker w-3 select-none">
              {l.type === "add" ? "+" : l.type === "del" ? "-" : " "}
            </span>
            <span className="code">{l.code}</span>
          </div>
        ))}
        {lines.length === 0 && (
          <div className="px-3 py-4 text-[var(--text-dim)]">
            No body preview available.
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Synthesize a line-level diff from a backend PatchSet shape.
 *
 * For a ``new_files[]`` entry: every line of ``content`` is an
 * addition numbered from 1.
 *
 * For an ``edits[]`` entry: we run a classic LCS diff (issue #15
 * — was a naive zipping that mislabeled mid-document insertions
 * as "everything from the insertion point changed"). The LCS
 * pass identifies the common subsequence of lines between
 * ``old`` and ``new`` and emits:
 *   - ``ctx`` for every line on the LCS — line numbers track
 *     the OLD file (which equals the NEW file for those lines);
 *   - ``del`` for old-only lines (numbered from OLD);
 *   - ``add`` for new-only lines (numbered from NEW).
 *
 * Output ordering matches a unified diff: each contiguous change
 * region renders ``del`` lines first, then ``add`` lines, with
 * surrounding ``ctx`` lines for context. This is what reviewers
 * expect.
 *
 * Complexity: O(N×M) time and space for ``oldLines.length`` ×
 * ``newLines.length``. Acceptable for the single-note patches
 * brain stages (~hundreds of lines). If a future plan ships
 * multi-MB patches we'll switch to Myers' O((N+M)·D) algorithm.
 *
 * We accept the patchset as an opaque record so the function can be
 * called straight from the store's ``selectedDetail.patchset`` without
 * a further type-cast dance.
 */
export function synthesizeDiff(
  patchset: Record<string, unknown>,
  targetPath: string,
): DiffLine[] {
  const newFiles = (patchset.new_files ?? []) as Array<{
    path: string;
    content: string;
  }>;
  const edits = (patchset.edits ?? []) as Array<{
    path: string;
    old: string;
    new: string;
  }>;

  // Accept both forward-slash and native-path variants for the match.
  const pathMatches = (p: string) =>
    p === targetPath || p.replace(/\\/g, "/") === targetPath;

  const nf = newFiles.find((n) => pathMatches(n.path));
  if (nf) {
    return nf.content.split("\n").map((code, i) => ({
      type: "add" as const,
      n: i + 1,
      code,
    }));
  }

  const ed = edits.find((e) => pathMatches(e.path));
  if (ed) {
    return lcsDiff(ed.old.split("\n"), ed.new.split("\n"));
  }

  return [];
}

/**
 * Classic LCS-based diff. Builds an ``(m+1) × (n+1)`` length table
 * in O(N×M), then backtracks to produce the edit script. Exported
 * for tests; production code reaches it through ``synthesizeDiff``.
 */
export function lcsDiff(
  oldLines: readonly string[],
  newLines: readonly string[],
): DiffLine[] {
  const m = oldLines.length;
  const n = newLines.length;

  // table[i][j] = length of LCS of oldLines[0..i-1] and newLines[0..j-1].
  // Storing as a flat Int32Array keeps the working set CPU-cache-friendly
  // even for ~10k-line patches.
  const stride = n + 1;
  const table = new Int32Array((m + 1) * stride);
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        table[i * stride + j] = table[(i - 1) * stride + (j - 1)] + 1;
      } else {
        const up = table[(i - 1) * stride + j];
        const left = table[i * stride + (j - 1)];
        table[i * stride + j] = up >= left ? up : left;
      }
    }
  }

  // Backtrack from (m, n) → (0, 0). Build the result in reverse.
  // Line numbers: ctx + del use the OLD index; add uses the NEW index
  // (this matches unified-diff conventions and lets a reviewer cross-
  // reference the gutter against the unmodified file).
  const out: DiffLine[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      out.push({ type: "ctx", n: i, code: oldLines[i - 1]! });
      i -= 1;
      j -= 1;
    } else if (
      j > 0 &&
      (i === 0 || table[i * stride + (j - 1)] >= table[(i - 1) * stride + j])
    ) {
      out.push({ type: "add", n: j, code: newLines[j - 1]! });
      j -= 1;
    } else {
      out.push({ type: "del", n: i, code: oldLines[i - 1]! });
      i -= 1;
    }
  }
  out.reverse();
  return out;
}
