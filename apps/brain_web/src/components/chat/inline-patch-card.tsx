"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import type { PatchMeta } from "@/lib/state/chat-store";

/**
 * InlinePatchCard — chip-style "Staged a new note at <path>" card
 * rendered under an assistant message when the turn staged a patch.
 *
 * Clicking "Review in panel →" should scroll the right-rail pending
 * section to that patch and highlight it. Task 14 dispatches a custom
 * DOM event (``brain:review-patch``) with the patch id as detail;
 * Task 16 (right-rail implementation) listens for it. Keeping the
 * coupling loose means the rail can ship independently of this card.
 */

export interface InlinePatchCardProps {
  patch: PatchMeta;
}

export const REVIEW_PATCH_EVENT = "brain:review-patch";

export function InlinePatchCard({
  patch,
}: InlinePatchCardProps): React.ReactElement {
  const onReview = React.useCallback(() => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(
      new CustomEvent(REVIEW_PATCH_EVENT, { detail: { patchId: patch.patchId } }),
    );
  }, [patch.patchId]);

  return (
    <div
      className="mt-2 flex items-center gap-2 rounded-md border border-hairline bg-surface-1 px-3 py-2 text-sm"
      role="group"
      aria-label="Staged patch"
    >
      <span className="text-text-muted">Staged a new note at</span>
      <span className="font-mono text-xs text-foreground">{patch.target}</span>
      <span className="ml-auto" />
      <Button size="sm" onClick={onReview}>
        Review in panel →
      </Button>
    </div>
  );
}
