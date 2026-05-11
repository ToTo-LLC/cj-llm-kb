import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * PendingScreen — Plan 18 T3.7 regression test for the undoLast consumer.
 *
 * Pre-fix, ``handleUndoLast`` read ``data?.reverted_files?.length ?? 0``
 * against a backend that never emits ``reverted_files`` — every successful
 * undo surfaced "Reverted 0 file(s)." regardless of outcome, and the
 * ``nothing_to_undo`` branch was indistinguishable from a successful undo.
 *
 * Post-fix, the handler discriminates on the backend ``status`` field
 * (matches the narrowed ``UndoLastData`` discriminated union at
 * ``apps/brain_web/src/lib/api/tools.ts``) and pushes a meaningful toast
 * per branch. These tests pin both branches.
 *
 * The scope here is just the Undo-last toast path. The full screen mount
 * needs ``listPendingPatches`` mocked (the ``loadPending`` effect fires on
 * mount); we resolve it with an empty list so the rest of the surface is
 * inert.
 */

const {
  undoLastMock,
  listPendingPatchesMock,
  getPendingPatchMock,
  applyPatchMock,
  rejectPatchMock,
  configSetMock,
} = vi.hoisted(() => ({
  undoLastMock: vi.fn(),
  listPendingPatchesMock: vi.fn(),
  getPendingPatchMock: vi.fn(),
  applyPatchMock: vi.fn(),
  rejectPatchMock: vi.fn(),
  configSetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  undoLast: undoLastMock,
  listPendingPatches: listPendingPatchesMock,
  getPendingPatch: getPendingPatchMock,
  applyPatch: applyPatchMock,
  rejectPatch: rejectPatchMock,
  configSet: configSetMock,
}));

import { PendingScreen } from "@/components/pending/pending-screen";
import { usePendingStore } from "@/lib/state/pending-store";
import { useSystemStore } from "@/lib/state/system-store";

function resetStores() {
  usePendingStore.setState({
    patches: [],
    selectedId: null,
    selectedDetail: null,
    filter: "all",
  });
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    toasts: [],
  });
}

describe("PendingScreen — handleUndoLast (Plan 18 T3.7)", () => {
  beforeEach(() => {
    resetStores();
    undoLastMock.mockReset();
    listPendingPatchesMock.mockReset();
    getPendingPatchMock.mockReset();
    applyPatchMock.mockReset();
    rejectPatchMock.mockReset();
    configSetMock.mockReset();
    // Empty initial list — mount's loadPending() resolves cleanly without
    // populating any cards. We assert toast contents after clicking Undo.
    listPendingPatchesMock.mockResolvedValue({ text: "", data: { patches: [] } });
  });

  test("reverted branch: toast names the undo_id and reloads pending", async () => {
    undoLastMock.mockResolvedValue({
      text: "reverted undo_id=20260511T120000",
      data: { status: "reverted", undo_id: "20260511T120000" },
    });

    const user = userEvent.setup();
    render(<PendingScreen />);

    // Wait for the initial loadPending() effect to settle so the second
    // listPendingPatches call (post-undo reload) is distinguishable.
    await Promise.resolve();
    await Promise.resolve();

    await user.click(screen.getByRole("button", { name: /undo last/i }));

    // Wait for the promise chain inside handleUndoLast (undoLast →
    // pushToast → loadPending) to settle.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(undoLastMock).toHaveBeenCalledTimes(1);
    const toasts = useSystemStore.getState().toasts;
    expect(toasts.length).toBeGreaterThanOrEqual(1);
    const latest = toasts[toasts.length - 1];
    expect(latest.lead).toMatch(/undone/i);
    expect(latest.msg).toMatch(/reverted change 20260511T120000\./i);
    expect(latest.variant).toBe("success");

    // Successful undo triggers a vault reload: listPendingPatches called
    // twice — once on mount, once after the undo resolves.
    expect(listPendingPatchesMock).toHaveBeenCalledTimes(2);
  });

  test("nothing_to_undo branch: distinct toast, does NOT reload pending", async () => {
    undoLastMock.mockResolvedValue({
      text: "nothing to undo — no undo history",
      data: { status: "nothing_to_undo" },
    });

    const user = userEvent.setup();
    render(<PendingScreen />);

    await Promise.resolve();
    await Promise.resolve();

    await user.click(screen.getByRole("button", { name: /undo last/i }));

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(undoLastMock).toHaveBeenCalledTimes(1);
    const toasts = useSystemStore.getState().toasts;
    expect(toasts.length).toBeGreaterThanOrEqual(1);
    const latest = toasts[toasts.length - 1];
    expect(latest.lead).toMatch(/nothing to undo/i);
    expect(latest.msg).toMatch(/no undo history was available\./i);
    // Variant intentionally neutral — this branch is a no-op, not a
    // success (no vault state changed) and not a failure.
    expect(latest.variant).toBe("default");

    // Crucially: the no-op branch must NOT trigger a redundant reload.
    // Pre-fix this branch reused the success path and reloaded; post-fix
    // it returns before loadPending(). listPendingPatches stays at 1 (the
    // initial mount call).
    expect(listPendingPatchesMock).toHaveBeenCalledTimes(1);
  });
});
