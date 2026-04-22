"use client";

import * as React from "react";
import { Check, Edit as EditIcon, MessageSquare, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  applyPatch,
  proposeNote,
  rejectPatch,
} from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import {
  usePendingStore,
  type PatchDetail as PatchDetailData,
} from "@/lib/state/pending-store";
import { useSystemStore } from "@/lib/state/system-store";
import { cn } from "@/lib/utils";

import { DiffView, synthesizeDiff } from "./diff-view";

/**
 * PatchDetail (Plan 07 Task 16) — right pane of the pending screen.
 *
 * Reads the currently-selected patch body from ``usePendingStore`` and
 * renders:
 *   - Target path chip
 *   - Reason (full text, no truncation)
 *   - Diff via ``<DiffView />`` synthesized from the patchset's
 *     ``new_files`` / ``edits`` entries
 *   - Source chat link if the envelope carries ``source_thread``
 *   - Three actions: Approve & write / Edit, then approve / Reject with
 *     reason
 *
 * ---------------------------------------------------------------------
 * Option A edit-approve chain (see Plan 07 Task 16, EditApproveDialog)
 * ---------------------------------------------------------------------
 * The backend's ``brain_apply_patch`` tool does NOT accept an edited
 * body — one atomic tool call can only approve the patch as-staged.
 * Plan picks Option A: we reject the original, stage a new note with
 * the user's edited body, then approve the new patch. Three round-trips
 * on localhost is ~milliseconds.
 *
 *   1. ``brain_reject_patch(patch_id, "editing")``   — drop the original
 *   2. ``brain_propose_note(path, edited, reason)``  — re-stage
 *   3. ``brain_apply_patch(new_patch_id)``           — approve replacement
 *
 * We intentionally run the chain INSIDE the dialog's onConfirm handler
 * opened below. On failure at any step we surface a toast + leave the
 * UI in whatever partial state the server is in (i.e. if step 2 fails
 * after step 1, the original was already rejected — a Task 25 sweep
 * item could retry or keep a retry queue). The comment block above is
 * the load-bearing rationale; please read ``edit-approve-dialog.tsx``
 * for the Option-A-vs-B trade-off.
 */

export interface PatchDetailProps {
  detail: PatchDetailData | null;
  patchId: string | null;
}

export function PatchDetail({
  detail,
  patchId,
}: PatchDetailProps): React.ReactElement {
  const openDialog = useDialogsStore((s) => s.open);
  const pushToast = useSystemStore((s) => s.pushToast);
  const reloadPending = usePendingStore((s) => s.loadPending);
  const removeFromList = React.useCallback((id: string) => {
    usePendingStore.setState((s) => ({
      patches: s.patches.filter((p) => p.patch_id !== id),
      selectedId: s.selectedId === id ? null : s.selectedId,
      selectedDetail: s.selectedId === id ? null : s.selectedDetail,
    }));
  }, []);

  // Derive display fields up-front so every hook below sees stable
  // inputs and we can keep them ordered ahead of the early-return. When
  // ``detail`` is null we compute empty strings so synthesizeDiff
  // returns [] and the ``lines`` memo stays consistent across renders.
  const envelope = (detail?.envelope ?? {}) as {
    target_path?: string;
    reason?: string;
    source_thread?: string;
    tool?: string;
  };
  const targetPath = envelope.target_path ?? "";
  const reason = envelope.reason ?? "";
  const sourceThread = envelope.source_thread ?? null;
  const rawPatchset = detail?.patchset;
  const lines = React.useMemo(
    () => synthesizeDiff(rawPatchset ?? {}, targetPath),
    [rawPatchset, targetPath],
  );

  if (!detail || !patchId) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-[var(--text-dim)]">
        <div>
          <div className="mb-2 text-sm">Select a pending change</div>
          <div className="text-xs">
            Click a card on the left to see the proposed diff and approve,
            edit, or reject.
          </div>
        </div>
      </div>
    );
  }

  const handleApprove = async () => {
    try {
      await applyPatch({ patch_id: patchId });
      removeFromList(patchId);
      pushToast({
        lead: "Approved.",
        msg: `${targetPath} written to vault.`,
        variant: "success",
      });
    } catch (err) {
      pushToast({
        lead: "Apply failed.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  const handleReject = () => {
    openDialog({
      kind: "reject-reason",
      patchId,
      targetPath,
      onConfirm: async (rejectReason: string) => {
        try {
          await rejectPatch({
            patch_id: patchId,
            reason: rejectReason || "rejected from pending screen",
          });
          removeFromList(patchId);
          pushToast({
            lead: "Rejected.",
            msg: `Patch for ${targetPath} discarded.`,
            variant: "default",
          });
        } catch (err) {
          pushToast({
            lead: "Reject failed.",
            msg: err instanceof Error ? err.message : "Unknown error.",
            variant: "danger",
          });
        }
      },
    });
  };

  const handleEdit = () => {
    // Gather ``before`` + ``after`` to seed the dialog. For a new-file
    // patch ``before`` is empty; for an edit we show the existing ``old``
    // body so the reviewer can see what changed.
    const patchset = detail.patchset as {
      new_files?: Array<{ path: string; content: string }>;
      edits?: Array<{ path: string; old: string; new: string }>;
    };
    const nf = (patchset.new_files ?? []).find(
      (n) => n.path === targetPath || n.path.replace(/\\/g, "/") === targetPath,
    );
    const ed = (patchset.edits ?? []).find(
      (e) => e.path === targetPath || e.path.replace(/\\/g, "/") === targetPath,
    );
    const before = ed?.old ?? "";
    const after = nf?.content ?? ed?.new ?? "";

    openDialog({
      kind: "edit-approve",
      patchId,
      targetPath,
      before,
      after,
      onConfirm: async (edited: string) => {
        // -----------------------------------------------------------
        // OPTION A (see docstring at top of this file + edit-approve-
        // dialog.tsx). Three-step chain: reject original, propose the
        // edited body, apply the new patch.
        // -----------------------------------------------------------
        try {
          await rejectPatch({ patch_id: patchId, reason: "editing" });
          const proposeRes = await proposeNote({
            path: targetPath,
            content: edited,
            reason: `Edited from patch ${patchId}`,
          });
          const newPatchId = (proposeRes.data as { patch_id?: string } | null)
            ?.patch_id;
          if (!newPatchId) {
            throw new Error("propose_note returned no patch_id");
          }
          await applyPatch({ patch_id: newPatchId });
          removeFromList(patchId);
          await reloadPending();
          pushToast({
            lead: "Edited and approved.",
            msg: `${targetPath} written to vault.`,
            variant: "success",
          });
        } catch (err) {
          pushToast({
            lead: "Edit-approve failed.",
            msg: err instanceof Error ? err.message : "Unknown error.",
            variant: "danger",
          });
        }
      },
    });
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      <section>
        <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
          Target path
        </div>
        <div className="mt-1 inline-block rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-2 py-1 font-mono text-xs">
          {targetPath}
        </div>
      </section>

      <section>
        <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
          Why
        </div>
        <p className="mt-1 text-sm text-[var(--text)]">{reason}</p>
      </section>

      <section>
        <div className="mb-1 text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
          Diff
        </div>
        <DiffView targetPath={targetPath} lines={lines} />
      </section>

      {sourceThread && (
        <section>
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
            Source
          </div>
          <a
            href={`/chat/${sourceThread}`}
            className={cn(
              "mt-1 inline-flex items-center gap-1 rounded-md border border-[var(--hairline)]",
              "bg-[var(--surface-1)] px-2 py-1 text-xs hover:bg-[var(--surface-2)]",
            )}
          >
            <MessageSquare className="h-3 w-3" />
            <span>Open source chat</span>
          </a>
        </section>
      )}

      <div className="mt-auto flex items-center gap-2">
        <Button onClick={handleApprove} className="gap-2">
          <Check className="h-3.5 w-3.5" /> Approve &amp; write to vault
        </Button>
        <Button variant="ghost" onClick={handleEdit} className="gap-2">
          <EditIcon className="h-3.5 w-3.5" /> Edit, then approve
        </Button>
        <div className="flex-1" />
        <Button
          variant="destructive"
          onClick={handleReject}
          className="gap-2"
        >
          <X className="h-3.5 w-3.5" /> Reject with reason
        </Button>
      </div>
    </div>
  );
}
