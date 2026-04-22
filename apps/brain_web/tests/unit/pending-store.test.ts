import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Pending-store (Plan 07 Task 16).
 *
 * The store lives between the typed tools API and the pending screen. It
 * holds the list of envelopes (metadata only — bodies are fetched on-demand
 * via ``getPendingPatch``), the active selection, and the filter chip state.
 * All five exercises here reset the store to its known-initial shape and
 * mock the API surface, same pattern as ``chat-store.test.ts`` and
 * ``budget-wall.test.tsx``.
 */

const { listPendingPatchesMock, getPendingPatchMock, applyPatchMock, rejectPatchMock } =
  vi.hoisted(() => ({
    listPendingPatchesMock: vi.fn(),
    getPendingPatchMock: vi.fn(),
    applyPatchMock: vi.fn(),
    rejectPatchMock: vi.fn(),
  }));

vi.mock("@/lib/api/tools", () => ({
  listPendingPatches: listPendingPatchesMock,
  getPendingPatch: getPendingPatchMock,
  applyPatch: applyPatchMock,
  rejectPatch: rejectPatchMock,
}));

import { usePendingStore } from "@/lib/state/pending-store";

function resetStore() {
  usePendingStore.setState({
    patches: [],
    selectedId: null,
    selectedDetail: null,
    filter: "all",
  });
  listPendingPatchesMock.mockReset();
  getPendingPatchMock.mockReset();
  applyPatchMock.mockReset();
  rejectPatchMock.mockReset();
}

function mkEnvelope(patchId: string, extra: Record<string, unknown> = {}) {
  return {
    patch_id: patchId,
    target_path: "research/notes/foo.md",
    reason: "staged by integrate step",
    created_at: "2026-04-21T10:00:00Z",
    tool: "propose_note",
    source_thread: "t-1",
    mode: "brainstorm",
    ...extra,
  };
}

describe("usePendingStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("loadPending() populates patches from the API", async () => {
    listPendingPatchesMock.mockResolvedValue({
      text: "",
      data: {
        patches: [mkEnvelope("p-1"), mkEnvelope("p-2", { target_path: "work/x.md" })],
      },
    });
    await usePendingStore.getState().loadPending();
    const state = usePendingStore.getState();
    expect(state.patches).toHaveLength(2);
    expect(state.patches[0].patch_id).toBe("p-1");
    expect(state.patches[1].target_path).toBe("work/x.md");
  });

  test("setFilter() changes the active filter chip", () => {
    expect(usePendingStore.getState().filter).toBe("all");
    usePendingStore.getState().setFilter("notes");
    expect(usePendingStore.getState().filter).toBe("notes");
    usePendingStore.getState().setFilter("ingested");
    expect(usePendingStore.getState().filter).toBe("ingested");
  });

  test("select() sets selectedId and fetches the detail via getPendingPatch", async () => {
    getPendingPatchMock.mockResolvedValue({
      text: "",
      data: {
        envelope: mkEnvelope("p-42"),
        patchset: {
          new_files: [{ path: "research/notes/foo.md", content: "# hi\n" }],
          edits: [],
          index_entries: [],
          log_entry: null,
          reason: "r",
          category: "other",
        },
      },
    });
    await usePendingStore.getState().select("p-42");
    const state = usePendingStore.getState();
    expect(state.selectedId).toBe("p-42");
    expect(state.selectedDetail).not.toBeNull();
    expect(state.selectedDetail!.envelope.patch_id).toBe("p-42");
    expect(getPendingPatchMock).toHaveBeenCalledWith({ patch_id: "p-42" });
  });

  test("approve() calls applyPatch and removes the patch from the list", async () => {
    usePendingStore.setState({
      patches: [mkEnvelope("p-1"), mkEnvelope("p-2")],
      selectedId: "p-1",
      selectedDetail: null,
      filter: "all",
    });
    applyPatchMock.mockResolvedValue({
      text: "",
      data: { patch_id: "p-1", undo_id: "u-1", applied_files: ["research/notes/foo.md"] },
    });
    await usePendingStore.getState().approve("p-1");
    const state = usePendingStore.getState();
    expect(applyPatchMock).toHaveBeenCalledWith({ patch_id: "p-1" });
    expect(state.patches.map((p) => p.patch_id)).toEqual(["p-2"]);
    // Selection was the removed patch → cleared.
    expect(state.selectedId).toBeNull();
  });

  test("reject() calls rejectPatch with reason and removes the patch from the list", async () => {
    usePendingStore.setState({
      patches: [mkEnvelope("p-1"), mkEnvelope("p-2")],
      selectedId: null,
      selectedDetail: null,
      filter: "all",
    });
    rejectPatchMock.mockResolvedValue({
      text: "",
      data: { patch_id: "p-2", rejected: true },
    });
    await usePendingStore.getState().reject("p-2", "wrong domain");
    const state = usePendingStore.getState();
    expect(rejectPatchMock).toHaveBeenCalledWith({
      patch_id: "p-2",
      reason: "wrong domain",
    });
    expect(state.patches.map((p) => p.patch_id)).toEqual(["p-1"]);
  });
});
