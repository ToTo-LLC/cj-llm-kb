"use client";

import { applyPatch, rejectPatch } from "@/lib/api/tools";

/**
 * Bulk approve / reject (Plan 07 Task 16).
 *
 * Serial loop over the per-patch action. The serial rule is deliberate:
 *   - budget caps and rate-limit signals live server-side and apply per
 *     call; parallel requests would pass the cap with no back-pressure.
 *   - the pending UI shows a "Approving N of M…" line and lets the user
 *     cancel mid-loop; parallelism makes progress reporting and cancel
 *     semantics confusing.
 *
 * Progress events fire BEFORE each attempt (so the UI can show the
 * ``current`` id) and once more at the end with the final summary. The
 * ``shouldCancel`` callback is re-checked at the top of every iteration.
 * An exception from one apply is caught; its id is appended to
 * ``failed`` and the loop continues — one broken patch should not block
 * the rest of the queue. On cancel the remaining patches are simply
 * left staged.
 */

export interface BulkProgressEvent {
  applied: number;
  total: number;
  /** The patch_id currently being attempted. Absent on the final summary. */
  current?: string;
  /** patch_ids that threw during apply/reject. */
  failed: string[];
}

async function bulkLoop(
  patchIds: string[],
  step: (id: string) => Promise<unknown>,
  onProgress: (ev: BulkProgressEvent) => void,
  shouldCancel: () => boolean,
): Promise<BulkProgressEvent> {
  const failed: string[] = [];
  let i = 0;
  for (; i < patchIds.length; i++) {
    if (shouldCancel()) break;
    const id = patchIds[i];
    onProgress({
      applied: i,
      total: patchIds.length,
      current: id,
      failed: [...failed],
    });
    try {
      await step(id);
    } catch {
      failed.push(id);
    }
  }
  const applied = i - failed.length;
  const summary: BulkProgressEvent = {
    applied,
    total: patchIds.length,
    failed,
  };
  onProgress(summary);
  return summary;
}

/** Serially apply every patch in ``patchIds``. See module docstring. */
export function approveAll(
  patchIds: string[],
  onProgress: (ev: BulkProgressEvent) => void,
  shouldCancel: () => boolean,
): Promise<BulkProgressEvent> {
  return bulkLoop(
    patchIds,
    (id) => applyPatch({ patch_id: id }),
    onProgress,
    shouldCancel,
  );
}

/** Serially reject every patch with a single reason. */
export function rejectAll(
  patchIds: string[],
  reason: string,
  onProgress: (ev: BulkProgressEvent) => void,
  shouldCancel: () => boolean,
): Promise<BulkProgressEvent> {
  return bulkLoop(
    patchIds,
    (id) => rejectPatch({ patch_id: id, reason }),
    onProgress,
    shouldCancel,
  );
}
