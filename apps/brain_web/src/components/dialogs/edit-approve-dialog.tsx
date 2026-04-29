"use client";

/**
 * EditApproveDialog — side-by-side before/after editor for a staged patch.
 * Left column shows the current file (read-only, dimmed when empty for a
 * new-file patch). Right column is a textarea initialized with the
 * proposed `after` body. On save we hand the edited string back to the
 * caller via `onConfirm(edited)`.
 *
 * ---------------------------------------------------------------------------
 * Option A vs Option B (see Plan 07 Task 11, "Edit-approve dialog")
 * ---------------------------------------------------------------------------
 * The backend's ``brain_apply_patch`` tool does not accept an ``edited_body``
 * argument, so an edit-then-approve flow cannot be a single atomic tool call.
 * The plan picks **Option A** (three-step): the caller, given ``edited``,
 * issues:
 *
 *   1. ``brain_reject_patch(patchId, "editing")``     — drop the original
 *   2. ``brain_propose_note(path, edited, "edited from patch")``  — re-stage
 *   3. ``brain_apply_patch(newPatchId)``              — approve the replacement
 *
 * We picked Option A because:
 *   - Zero backend changes; keeps the "all writes staged" invariant intact.
 *   - Three round-trips on localhost is ~milliseconds; cost is irrelevant.
 *   - Option B (adding ``edited_body`` to ``brain_apply_patch``) couples the
 *     patch's original body to a rewrite path and widens the tool surface.
 *
 * Do NOT reach for Option B from this dialog. If you think you need it,
 * update the spec first.
 *
 * Component scope: this dialog exposes the side-by-side editor + its
 * ``onConfirm(edited: string)`` signature. The three-step chain itself
 * lives in the host (``components/pending/patch-detail.tsx``,
 * ``handleEdit``) — host calls ``rejectPatch`` → ``proposeNote`` →
 * ``applyPatch`` in sequence, surfacing toasts on success / failure.
 * Verified wired 2026-04-26 while closing issue #19.
 * ---------------------------------------------------------------------------
 */

import * as React from "react";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Modal } from "./modal";

export interface EditApproveDialogProps {
  kind: "edit-approve";
  patchId: string;
  targetPath: string;
  before: string;
  after: string;
  onConfirm: (edited: string) => void;
  onClose: () => void;
}

export function EditApproveDialog({
  targetPath,
  before,
  after,
  onConfirm,
  onClose,
}: EditApproveDialogProps) {
  const [draft, setDraft] = React.useState(after);

  const isNewFile = before.length === 0;

  const handleSave = () => {
    // Hand the edited body up; the host (patch-detail.tsx) runs the
    // reject → propose → apply chain documented above.
    onConfirm(draft);
    onClose();
  };

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow={`Edit · ${targetPath}`}
      title="Tweak the note, then approve."
      description="Edit the proposed note on the right; the current file is shown on the left for reference."
      width={760}
      footer={
        <>
          <span className="mr-auto text-xs text-muted-foreground">
            Saves to vault on approve · {draft.length} chars
          </span>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} className="gap-2">
            <Check className="h-3.5 w-3.5" /> Save &amp; approve
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col">
          <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
            {isNewFile ? "Current (empty — new file)" : "Current"}
          </div>
          <pre
            className={cn(
              "h-72 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 text-xs leading-relaxed",
              isNewFile && "italic text-muted-foreground",
            )}
          >
            {isNewFile ? "(file doesn't exist yet)" : before}
          </pre>
        </div>
        <div className="flex flex-col">
          {/*
            Plan 14 Task 3 a11y populated-state fix: associate the
            "Your edit" caption with the Textarea via ``htmlFor`` /
            ``id`` so axe-core's ``label`` rule passes (was failing
            because the caption was a sibling ``<div>`` with no
            association). Visual presentation unchanged.
          */}
          <label
            htmlFor="edit-approve-draft"
            className="mb-1 text-xs uppercase tracking-wider text-muted-foreground"
          >
            Your edit
          </label>
          <Textarea
            id="edit-approve-draft"
            className="h-72 resize-none font-mono text-xs leading-relaxed"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
          />
        </div>
      </div>
    </Modal>
  );
}
