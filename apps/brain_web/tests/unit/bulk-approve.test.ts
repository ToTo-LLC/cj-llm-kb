import { describe, expect, test, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Bulk approve (Plan 07 Task 16) — serial loop over ``applyPatch`` with a
 * per-step progress callback and a cancel hook. The serial rule is
 * deliberate: approving in parallel risks the user hitting the budget cap
 * halfway through with no signal to stop. Progress fires BEFORE each
 * attempt so the UI can show "Approving 3 of 12…" with the current id.
 */

const { applyPatchMock, rejectPatchMock } = vi.hoisted(() => ({
  applyPatchMock: vi.fn(),
  rejectPatchMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  applyPatch: applyPatchMock,
  rejectPatch: rejectPatchMock,
}));

import { approveAll } from "@/lib/pending/bulk-approve";

describe("approveAll", () => {
  beforeEach(() => {
    applyPatchMock.mockReset();
    rejectPatchMock.mockReset();
  });

  test("calls applyPatch sequentially for each patchId", async () => {
    const order: string[] = [];
    applyPatchMock.mockImplementation(async ({ patch_id }: { patch_id: string }) => {
      order.push(patch_id);
      return { text: "", data: { patch_id, undo_id: "u", applied_files: [] } };
    });
    await approveAll(["p-1", "p-2", "p-3"], () => {}, () => false);
    expect(applyPatchMock).toHaveBeenCalledTimes(3);
    expect(order).toEqual(["p-1", "p-2", "p-3"]);
  });

  test("progress callback fires once per step with incrementing applied counts", async () => {
    applyPatchMock.mockResolvedValue({
      text: "",
      data: { patch_id: "p", undo_id: "u", applied_files: [] },
    });
    const events: Array<{ applied: number; total: number; current?: string }> = [];
    await approveAll(
      ["p-1", "p-2", "p-3"],
      (ev) => events.push({ applied: ev.applied, total: ev.total, current: ev.current }),
      () => false,
    );
    // One progress event per patch + one final completion summary.
    expect(events.length).toBe(4);
    expect(events[0]).toMatchObject({ applied: 0, total: 3, current: "p-1" });
    expect(events[1]).toMatchObject({ applied: 1, total: 3, current: "p-2" });
    expect(events[2]).toMatchObject({ applied: 2, total: 3, current: "p-3" });
    expect(events[3]).toMatchObject({ applied: 3, total: 3 });
  });

  test("shouldCancel() returning true mid-loop halts subsequent applyPatch calls", async () => {
    let count = 0;
    applyPatchMock.mockImplementation(async ({ patch_id }: { patch_id: string }) => {
      count += 1;
      return { text: "", data: { patch_id, undo_id: "u", applied_files: [] } };
    });
    // Cancel after the first apply — i.e. on entering step index 1.
    const shouldCancel = vi.fn(() => count >= 1);
    await approveAll(["p-1", "p-2", "p-3"], () => {}, shouldCancel);
    // Only p-1 was applied; p-2 and p-3 skipped.
    expect(count).toBe(1);
    expect(applyPatchMock).toHaveBeenCalledTimes(1);
  });
});
