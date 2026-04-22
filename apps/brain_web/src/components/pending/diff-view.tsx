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
 * For an ``edits[]`` entry: we run a trivial line-by-line compare.
 * Equal lines render as ``ctx``; otherwise both the old and new lines
 * appear, ``del`` before ``add``. This is not a full LCS, but for
 * small single-note patches the output reads correctly in 99% of
 * cases. A proper LCS is tracked as a Task 25 sweep item.
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
    const oldLines = ed.old.split("\n");
    const newLines = ed.new.split("\n");
    const out: DiffLine[] = [];
    const maxLen = Math.max(oldLines.length, newLines.length);
    for (let i = 0; i < maxLen; i++) {
      const o = oldLines[i];
      const n = newLines[i];
      if (o === undefined) {
        out.push({ type: "add", n: i + 1, code: n ?? "" });
      } else if (n === undefined) {
        out.push({ type: "del", n: i + 1, code: o });
      } else if (o === n) {
        out.push({ type: "ctx", n: i + 1, code: o });
      } else {
        out.push({ type: "del", n: i + 1, code: o });
        out.push({ type: "add", n: i + 1, code: n });
      }
    }
    return out;
  }

  return [];
}
