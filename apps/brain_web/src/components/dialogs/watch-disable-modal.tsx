"use client";

import * as React from "react";
import { ArrowRight, Check, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { unwatchFolder, type WatchedFolderEntry } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";
import { useWatchedFoldersStore } from "@/lib/state/watched-folders-store";
import { Modal } from "./modal";

/**
 * WatchDisableModal (Plan 22 T15).
 *
 * Implements per ``docs/design/plan-22/modal-watch-disable.md``. The
 * user is about to stop watching a folder. The action is REVERSIBLE
 * (they can re-enable later from the same Settings tab) so the mockup
 * deliberately picks a confirmation modal — NOT a typed-confirm — and
 * uses the default button variant (NOT destructive) because nothing is
 * being deleted (D2: existing notes stay; orphans stay marked).
 *
 * Microcopy strings come verbatim from the mockup's "Microcopy" section
 * (lines 91-110). Do NOT paraphrase — Plan 22 D9 lints for drift.
 *
 * On confirm, fires ``brain_unwatch_folder`` and refreshes the watched-
 * folders store so peer subscribers (panel, topbar indicator) pick up
 * the row drop. Toast copy carries the orphan count when > 0 per the
 * mockup's conditional orphan-info-line (mockup line 104).
 */

export interface WatchDisableModalProps {
  /** The watched-folder row the user clicked Unwatch on. */
  folder: WatchedFolderEntry;
  /** Fired when the user dismisses (Cancel / Esc / backdrop / success). */
  onClose: () => void;
}

function basenameOf(folderPath: string): string {
  return folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath;
}

export function WatchDisableModal({
  folder,
  onClose,
}: WatchDisableModalProps): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [confirming, setConfirming] = React.useState<boolean>(false);

  const handleConfirm = React.useCallback(async () => {
    setConfirming(true);
    // Optimistic drop — matches the panel-watched-folders ``handleUnwatch``
    // precedent so peer subscribers re-render without waiting for the
    // round-trip. On failure we re-fetch to restore.
    useWatchedFoldersStore.getState().removeFolderOptimistic(folder.path);
    try {
      await unwatchFolder({ folder: folder.path });
      void useWatchedFoldersStore.getState().refresh();
      const basename = basenameOf(folder.path);
      pushToast({
        lead: `Stopped watching ${basename}.`,
        msg:
          folder.orphan_count > 0
            ? `Existing notes kept. ${folder.orphan_count} orphan${
                folder.orphan_count === 1 ? "" : "s"
              } remain marked.`
            : "Existing notes kept.",
        variant: "success",
      });
      onClose();
    } catch (err) {
      // Reconcile the optimistic drop on failure.
      await useWatchedFoldersStore.getState().refresh();
      const msg = err instanceof Error ? err.message : "Unknown error.";
      pushToast({
        lead: "Couldn't stop watching.",
        msg,
        variant: "danger",
      });
      setConfirming(false);
    }
  }, [folder.orphan_count, folder.path, pushToast, onClose]);

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow="WATCHED FOLDERS"
      title="Stop watching this folder?"
      description="Brain will stop monitoring this folder for changes."
      width={480}
      onOpenAutoFocus={(e) => {
        // Mockup §"Interaction": default focus on Cancel button is a
        // safety design — accidental-Enter on modal mount cancels
        // rather than confirming. Radix focuses the first tabbable;
        // our first tabbable IS the Cancel button so default behavior
        // matches the spec. Preventing default + manually focusing is
        // unnecessary here. Keep the override for explicit doc trail.
        void e;
      }}
      footer={
        <>
          <Button
            variant="ghost"
            onClick={onClose}
            data-testid="watch-disable-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="default"
            disabled={confirming}
            aria-busy={confirming}
            onClick={() => void handleConfirm()}
            data-testid="watch-disable-confirm"
          >
            {confirming && (
              <Loader2
                className="mr-1.5 h-3.5 w-3.5 animate-spin"
                aria-hidden="true"
              />
            )}
            {confirming ? "Stopping…" : "Stop watching"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Path display — mono on surface-2, mockup §anatomy. */}
        <div
          data-testid="watch-disable-path"
          className="rounded-md bg-[var(--surface-2)] px-3 py-2 font-mono text-[11px] text-[var(--text-muted)]"
        >
          {folder.path}
        </div>

        {/* Body — exact strings, mockup §microcopy lines 96-103. */}
        <p className="text-sm text-[var(--text)]">
          Brain will stop monitoring this folder for changes.
        </p>

        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-medium text-[var(--text-muted)]">
            Here&rsquo;s what stays the same:
          </h4>
          <ul
            className="flex flex-col gap-1.5 text-xs text-[var(--text)]"
            data-testid="watch-disable-stays-list"
          >
            <li className="flex items-start gap-2">
              <Check
                className="mt-0.5 h-3.5 w-3.5 shrink-0"
                style={{ color: "var(--ok, #4ADE80)" }}
                aria-hidden="true"
              />
              <span>
                Existing notes from this folder stay in your knowledge base.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <Check
                className="mt-0.5 h-3.5 w-3.5 shrink-0"
                style={{ color: "var(--ok, #4ADE80)" }}
                aria-hidden="true"
              />
              <span>
                Notes already marked as orphans stay marked. You can review them
                in Settings → Orphans.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <Check
                className="mt-0.5 h-3.5 w-3.5 shrink-0"
                style={{ color: "var(--ok, #4ADE80)" }}
                aria-hidden="true"
              />
              <span>
                You can start watching this folder again any time.
              </span>
            </li>
          </ul>
        </div>

        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-medium text-[var(--text-muted)]">
            Here&rsquo;s what changes:
          </h4>
          <ul
            className="flex flex-col gap-1.5 text-xs text-[var(--text)]"
            data-testid="watch-disable-changes-list"
          >
            <li className="flex items-start gap-2">
              <ArrowRight
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]"
                aria-hidden="true"
              />
              <span>New or edited source files won&rsquo;t sync.</span>
            </li>
            <li className="flex items-start gap-2">
              <ArrowRight
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]"
                aria-hidden="true"
              />
              <span>Deleted source files won&rsquo;t mark new orphans.</span>
            </li>
          </ul>
        </div>

        {/* Conditional orphan-count info-line — only renders when > 0. */}
        {folder.orphan_count > 0 && (
          <div
            role="note"
            aria-label={`Orphan notice: ${folder.orphan_count} orphan${
              folder.orphan_count === 1 ? "" : "s"
            } from earlier deletions remain`}
            data-testid="watch-disable-orphan-note"
            className="rounded-md border-l-[3px] border-[var(--info,_#56B4D3)] bg-[var(--surface-2)] p-3 text-xs text-[var(--text)]"
          >
            <span aria-hidden="true">{"ⓘ "}</span>
            The folder&rsquo;s {folder.orphan_count} orphan
            {folder.orphan_count === 1 ? "" : "s"} from earlier deletions will
            still be there. Manage them in Settings → Orphans.
          </div>
        )}
      </div>
    </Modal>
  );
}
