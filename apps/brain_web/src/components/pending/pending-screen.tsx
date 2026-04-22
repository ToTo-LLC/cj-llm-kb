"use client";

import * as React from "react";
import { Check, Undo2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { undoLast } from "@/lib/api/tools";
import { approveAll, rejectAll } from "@/lib/pending/bulk-approve";
import {
  usePendingStore,
  type PatchEnvelope,
} from "@/lib/state/pending-store";
import { useSystemStore } from "@/lib/state/system-store";

import { AutonomousToggle } from "./autonomous-toggle";
import { FilterBar, matchesFilter } from "./filter-bar";
import { PatchCard, type PatchCardPatch } from "./patch-card";
import { PatchDetail } from "./patch-detail";

/**
 * PendingScreen (Plan 07 Task 16) — full pending-changes surface.
 *
 * Two-column layout:
 *   [filter + card list]   [detail pane with diff]
 * Header row above carries the title, count, AutonomousToggle, and three
 * global actions: Undo last / Reject all / Approve all.
 *
 * The screen is a thin view wrapper around ``usePendingStore``. All API
 * calls go through the store (single / selection) or through
 * ``bulk-approve.ts`` (global Approve-all / Reject-all). The shell's
 * DialogHost handles the reject-reason and edit-approve modals opened by
 * PatchDetail; we never render dialogs directly here.
 */

function envelopeToCardPatch(envelope: PatchEnvelope): PatchCardPatch {
  // The list tool does not currently expose the patch's domain, so we
  // derive it from the leading directory of the target path (the vault
  // convention). Task 25 sweep item: promote ``domain`` to the list
  // envelope so we don't need this best-effort inference.
  const domain =
    typeof envelope.domain === "string"
      ? envelope.domain
      : envelope.target_path.split("/")[0] ?? "research";
  return {
    patch_id: envelope.patch_id,
    tool: (envelope.tool as string) ?? "propose_note",
    domain,
    target_path: envelope.target_path,
    reason: envelope.reason,
    created_at: envelope.created_at,
    isNew: envelope.isNew === true,
  };
}

export function PendingScreen(): React.ReactElement {
  const patches = usePendingStore((s) => s.patches);
  const filter = usePendingStore((s) => s.filter);
  const selectedId = usePendingStore((s) => s.selectedId);
  const selectedDetail = usePendingStore((s) => s.selectedDetail);
  const loadPending = usePendingStore((s) => s.loadPending);
  const select = usePendingStore((s) => s.select);
  const setFilter = usePendingStore((s) => s.setFilter);
  const approve = usePendingStore((s) => s.approve);
  const reject = usePendingStore((s) => s.reject);
  const pushToast = useSystemStore((s) => s.pushToast);

  // Initial load — one-shot on mount. Task 14's WS hook will push
  // ``patch_proposed`` events into the store incrementally later, but
  // the screen must render a warm list on open.
  React.useEffect(() => {
    loadPending().catch(() => {
      pushToast({
        lead: "Load failed.",
        msg: "Could not fetch pending changes.",
        variant: "danger",
      });
    });
  }, [loadPending, pushToast]);

  const visible = patches.filter((p) =>
    matchesFilter((p.tool as string) ?? "", filter),
  );

  const handleApproveAll = async () => {
    const ids = visible.map((p) => p.patch_id);
    if (ids.length === 0) return;
    const result = await approveAll(
      ids,
      (ev) => {
        // Intermediate events intentionally ignored for the toast — the
        // Plan 07 Task 15 cost HUD is the right place for "N of M" UX;
        // for now we reload once the loop ends.
        void ev;
      },
      () => false,
    );
    await loadPending();
    pushToast({
      lead: "Approve all complete.",
      msg: `${result.applied} applied, ${result.failed.length} failed.`,
      variant: result.failed.length === 0 ? "success" : "warn",
    });
  };

  const handleRejectAll = async () => {
    const ids = visible.map((p) => p.patch_id);
    if (ids.length === 0) return;
    const result = await rejectAll(
      ids,
      "bulk reject from pending screen",
      (ev) => {
        void ev;
      },
      () => false,
    );
    await loadPending();
    pushToast({
      lead: "Reject all complete.",
      msg: `${result.applied} rejected, ${result.failed.length} failed.`,
      variant: result.failed.length === 0 ? "default" : "warn",
    });
  };

  const handleUndoLast = async () => {
    try {
      const res = await undoLast({});
      const data = res.data as { reverted_files?: string[] } | null;
      pushToast({
        lead: "Undone.",
        msg: `Reverted ${data?.reverted_files?.length ?? 0} file(s).`,
        variant: "success",
      });
      await loadPending();
    } catch (err) {
      pushToast({
        lead: "Undo failed.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  return (
    <div className="pending-screen flex h-full flex-col">
      <header className="flex items-start justify-between gap-4 border-b border-[var(--hairline)] px-4 py-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
            Your approval queue
          </div>
          <h1 className="text-xl font-semibold text-[var(--text)]">
            Pending Changes
            <span className="ml-2 text-sm font-normal text-[var(--text-muted)]">
              · {patches.length}
            </span>
          </h1>
        </div>
        <div className="flex items-start gap-4">
          <div className="w-[320px]">
            <AutonomousToggle />
          </div>
          <div className="flex flex-col gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="gap-1"
              onClick={handleUndoLast}
            >
              <Undo2 className="h-3.5 w-3.5" /> Undo last
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1"
              onClick={handleRejectAll}
              disabled={visible.length === 0}
            >
              <X className="h-3.5 w-3.5" /> Reject all
            </Button>
            <Button
              size="sm"
              className="gap-1"
              onClick={handleApproveAll}
              disabled={visible.length === 0}
            >
              <Check className="h-3.5 w-3.5" /> Approve all ({visible.length})
            </Button>
          </div>
        </div>
      </header>

      <div className="pending-content grid flex-1 grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-0 overflow-hidden">
        <div className="flex flex-col gap-2 overflow-auto border-r border-[var(--hairline)] p-3">
          <FilterBar value={filter} onChange={setFilter} />
          {visible.length === 0 ? (
            <div className="mt-8 rounded-md border border-dashed border-[var(--hairline)] p-6 text-center text-sm text-[var(--text-dim)]">
              All clear.
            </div>
          ) : (
            visible.map((envelope) => {
              const cardPatch = envelopeToCardPatch(envelope);
              return (
                <div
                  key={envelope.patch_id}
                  id={`patch-card-${envelope.patch_id}`}
                >
                  <PatchCard
                    patch={cardPatch}
                    selected={selectedId === envelope.patch_id}
                    onSelect={(id) => {
                      select(id).catch(() => {
                        pushToast({
                          lead: "Load failed.",
                          msg: "Could not fetch patch detail.",
                          variant: "danger",
                        });
                      });
                    }}
                    onApprove={(p) => {
                      approve(p.patch_id).then(() => {
                        pushToast({
                          lead: "Approved.",
                          msg: `${p.target_path} written to vault.`,
                          variant: "success",
                        });
                      }).catch((err) => {
                        pushToast({
                          lead: "Apply failed.",
                          msg:
                            err instanceof Error ? err.message : "Unknown error.",
                          variant: "danger",
                        });
                      });
                    }}
                    onEdit={(p) => {
                      select(p.patch_id).catch(() => {});
                    }}
                    onReject={(p) => {
                      reject(p.patch_id, "rejected from pending list").then(() => {
                        pushToast({
                          lead: "Rejected.",
                          msg: `${p.target_path} discarded.`,
                          variant: "default",
                        });
                      }).catch((err) => {
                        pushToast({
                          lead: "Reject failed.",
                          msg:
                            err instanceof Error ? err.message : "Unknown error.",
                          variant: "danger",
                        });
                      });
                    }}
                  />
                </div>
              );
            })
          )}
        </div>
        <div className="overflow-auto">
          <PatchDetail detail={selectedDetail} patchId={selectedId} />
        </div>
      </div>
    </div>
  );
}
