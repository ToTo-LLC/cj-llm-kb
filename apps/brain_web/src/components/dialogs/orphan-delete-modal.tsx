"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";

import type { OrphanEntry } from "@/lib/api/tools";
import type { DialogKind } from "@/lib/state/dialogs-store";

/**
 * OrphanDeleteModal helpers (Plan 22 T15).
 *
 * Implements per ``docs/design/plan-22/modal-orphan-delete.md``. The
 * orphan-delete UX is built on the existing ``TypedConfirmDialog``
 * primitive (line 3-4 of the mockup explicitly calls out
 * "REUSES existing TypedConfirmDialog — does NOT introduce a new modal
 * component"). T15 extended ``TypedConfirmDialog`` with an optional
 * ``headerSlot`` prop so callers can render a per-note warn-icon card
 * (single mode) or a per-batch summary card (bulk mode) ABOVE the
 * body paragraph without copy-pasting the input-state + typed-confirm
 * logic into a sibling component.
 *
 * This file exports two helpers that build the ``DialogKind`` payload
 * for ``useDialogsStore.open()`` — single mode and bulk mode. Each
 * helper:
 *   - Pre-computes the ``headerSlot`` React node from the orphan(s).
 *   - Pre-computes the typed-confirm ``word`` (slug for single,
 *     ``"delete N notes"`` for bulk).
 *   - Wires the caller's ``onConfirm`` (which fires
 *     ``brain_delete_orphan`` and handles toast / refresh).
 *
 * Callers (panel-orphans.tsx) use these instead of building the
 * DialogKind inline — keeps the per-note / per-batch microcopy in ONE
 * place so a future mockup tweak doesn't drift between single + bulk.
 *
 * Microcopy strings come verbatim from the mockup's "Microcopy" section
 * (lines 142-172). Do NOT paraphrase — Plan 22 D9 lints for drift.
 */

// ---------- Single-note header slot ----------

interface SingleHeaderProps {
  /** Full note metadata for the per-row card (warn-icon + filename + paths). */
  entry: OrphanEntry;
  /** Pre-computed slug (basename without ``.md``) — matches the
   *  ``word`` the user must type. Used as the card title so the user
   *  sees what they're being asked to type. */
  slug: string;
}

function SingleNoteHeader({
  entry,
  slug,
}: SingleHeaderProps): React.ReactElement {
  return (
    <div
      role="group"
      aria-label={`Orphan to be deleted: ${slug}`}
      data-testid="orphan-delete-header-single"
      className="rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0"
          style={{ color: "var(--warn, #E0A03A)" }}
          aria-hidden="true"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span
            className="truncate font-mono text-xs font-medium text-[var(--text)]"
            data-testid="orphan-delete-note-title"
          >
            {slug}.md
          </span>
          <span
            className="truncate font-mono text-[11px] text-[var(--text-muted)]"
            data-testid="orphan-delete-note-vault-path"
          >
            {entry.note_path}
          </span>
          <span
            className="truncate font-mono text-[10px] text-[var(--text-dim)]"
            data-testid="orphan-delete-note-source"
          >
            Source: {entry.source_path}{" "}
            <span className="not-italic">(no longer exists)</span>
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------- Bulk header slot ----------

interface BulkHeaderProps {
  /** Slugs (basenames without ``.md``) for every selected note. Drives
   *  the up-to-5 displayed list + the "…and N more" overflow line. */
  slugs: string[];
}

const BULK_MAX_DISPLAY = 5;

function BulkSummaryHeader({ slugs }: BulkHeaderProps): React.ReactElement {
  const n = slugs.length;
  const head = slugs.slice(0, BULK_MAX_DISPLAY);
  const overflow = Math.max(0, n - BULK_MAX_DISPLAY);
  return (
    <div
      role="group"
      aria-label={`${n} orphans selected for deletion`}
      data-testid="orphan-delete-header-bulk"
      className="rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0"
          style={{ color: "var(--warn, #E0A03A)" }}
          aria-hidden="true"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span
            className="text-xs font-medium text-[var(--text)]"
            data-testid="orphan-delete-bulk-count"
          >
            {n} orphan{n === 1 ? "" : "s"} selected:
          </span>
          <ul
            aria-label={`${n} orphans selected for deletion`}
            data-testid="orphan-delete-bulk-list"
            className="flex flex-col gap-0.5 text-[11px] text-[var(--text)]"
          >
            {head.map((s) => (
              <li key={s} className="truncate font-mono">
                <span aria-hidden="true">{"• "}</span>
                {s}.md
              </li>
            ))}
            {overflow > 0 && (
              <li
                className="text-[var(--text-dim)]"
                data-testid="orphan-delete-bulk-overflow"
              >
                …and {overflow} more
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}

// ---------- DialogKind builders ----------

/** Derive the note slug (basename without ``.md`` extension) used as
 *  the typed-confirm word for single-row delete (mockup line 39). */
export function slugFromNotePath(notePath: string): string {
  const basename = notePath.split(/[/\\]/).pop() ?? notePath;
  return basename.replace(/\.md$/i, "");
}

/**
 * Build a ``typed-confirm`` ``DialogKind`` payload for the single-note
 * orphan-delete flow (mockup §"Layout (single-note mode)" lines 14-53).
 *
 * Caller hands the result to ``useDialogsStore.open()``. The caller's
 * ``onConfirm`` fires ``brain_delete_orphan({note_path, typed_confirm:
 * true})`` and handles the toast / refresh lifecycle.
 */
export function buildSingleOrphanDeleteDialog(args: {
  entry: OrphanEntry;
  onConfirm: () => void;
}): DialogKind {
  const slug = slugFromNotePath(args.entry.note_path);
  return {
    kind: "typed-confirm",
    eyebrow: "ORPHAN MANAGEMENT",
    title: "Delete this orphaned note?",
    body: "The source file for this note no longer exists. Deleting moves the note to your vault's trash. You can restore it from ~/Documents/brain/.brain/trash/ within 30 days, or undo this with brain_undo_last.",
    word: slug,
    danger: true,
    headerSlot: <SingleNoteHeader entry={args.entry} slug={slug} />,
    onConfirm: args.onConfirm,
  };
}

/**
 * Build a ``typed-confirm`` ``DialogKind`` payload for the bulk
 * orphan-delete flow (mockup §"Layout (BULK mode)" lines 99-136).
 *
 * Caller hands the result to ``useDialogsStore.open()``. The caller's
 * ``onConfirm`` iterates ``brain_delete_orphan`` over the selected
 * paths and surfaces a partial-success toast on mixed outcomes.
 */
export function buildBulkOrphanDeleteDialog(args: {
  entries: OrphanEntry[];
  onConfirm: () => void;
}): DialogKind {
  const n = args.entries.length;
  const slugs = args.entries.map((e) => slugFromNotePath(e.note_path));
  const word = `delete ${n} note${n === 1 ? "" : "s"}`;
  return {
    kind: "typed-confirm",
    eyebrow: "ORPHAN MANAGEMENT",
    title: `Delete ${n} orphaned note${n === 1 ? "" : "s"}?`,
    body: "The source files for these notes no longer exist. Deleting moves them to your vault's trash. You can restore each one from ~/Documents/brain/.brain/trash/ within 30 days, or undo the whole batch with brain_undo_last.",
    word,
    danger: true,
    headerSlot: <BulkSummaryHeader slugs={slugs} />,
    onConfirm: args.onConfirm,
  };
}

// Re-export the header components for tests + future direct render
// callers (e.g. a Storybook entry showing the headers in isolation).
export { SingleNoteHeader, BulkSummaryHeader };
