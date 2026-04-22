import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Draft-store (Plan 07 Task 19).
 *
 * Owns the single active Draft-mode document plus the queue of pending
 * inline edits the assistant has proposed via ``doc_edit_proposed`` WS
 * events. The DocPanel subscribes to it to render the current body with
 * highlighted spans; the Apply action round-trips through
 * ``brain_propose_note`` (and ``brain_apply_patch`` when the
 * ``autonomous.draft`` config key is true).
 *
 * Each test resets the store to its known-initial shape and clears the
 * tool-API mocks so cross-test leakage doesn't cause a green run to mask
 * a real regression.
 */

const { proposeNoteMock, configGetMock, applyPatchMock } = vi.hoisted(() => ({
  proposeNoteMock: vi.fn(),
  configGetMock: vi.fn(),
  applyPatchMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  proposeNote: proposeNoteMock,
  configGet: configGetMock,
  applyPatch: applyPatchMock,
}));

import { useDraftStore, type ActiveDoc, type DocEdit } from "@/lib/state/draft-store";

function mkDoc(overrides: Partial<ActiveDoc> = {}): ActiveDoc {
  return {
    path: "research/notes/silent-buyer.md",
    domain: "research",
    frontmatter: "---\ntype: note\ndomain: research\n---",
    body: "# Silent buyer\n\nSome body text here.",
    pendingEdits: [],
    ...overrides,
  };
}

function mkEdit(overrides: Partial<DocEdit> = {}): DocEdit {
  return {
    op: "insert",
    anchor: { kind: "line", value: 2 },
    text: "A new sentence.",
    ...overrides,
  };
}

function resetStore() {
  useDraftStore.setState({ activeDoc: null });
  proposeNoteMock.mockReset();
  configGetMock.mockReset();
  applyPatchMock.mockReset();
}

describe("useDraftStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("openDoc() sets activeDoc to the given payload", () => {
    const doc = mkDoc();
    useDraftStore.getState().openDoc(doc);
    expect(useDraftStore.getState().activeDoc).toEqual(doc);
  });

  test("closeDoc() resets activeDoc to null", () => {
    useDraftStore.getState().openDoc(mkDoc());
    expect(useDraftStore.getState().activeDoc).not.toBeNull();
    useDraftStore.getState().closeDoc();
    expect(useDraftStore.getState().activeDoc).toBeNull();
  });

  test("appendEdit() pushes an edit onto activeDoc.pendingEdits", () => {
    useDraftStore.getState().openDoc(mkDoc());
    const edit1 = mkEdit({ text: "first" });
    const edit2 = mkEdit({ op: "delete", text: "second" });
    useDraftStore.getState().appendEdit(edit1);
    useDraftStore.getState().appendEdit(edit2);
    const state = useDraftStore.getState();
    expect(state.activeDoc?.pendingEdits).toHaveLength(2);
    expect(state.activeDoc?.pendingEdits[0]).toEqual(edit1);
    expect(state.activeDoc?.pendingEdits[1]).toEqual(edit2);
  });

  test("applyPendingEdits() clears pendingEdits after proposeNote resolves", async () => {
    useDraftStore.getState().openDoc(mkDoc());
    useDraftStore.getState().appendEdit(mkEdit({ text: "A new sentence." }));
    configGetMock.mockResolvedValue({ text: "", data: { key: "autonomous.draft", value: false } });
    proposeNoteMock.mockResolvedValue({
      text: "",
      data: { patch_id: "p-42", target_path: "research/notes/silent-buyer.md" },
    });

    await useDraftStore.getState().applyPendingEdits();

    // proposeNote called with path + merged body + reason.
    expect(proposeNoteMock).toHaveBeenCalledTimes(1);
    const call = proposeNoteMock.mock.calls[0]![0] as {
      path: string;
      content: string;
      reason: string;
    };
    expect(call.path).toBe("research/notes/silent-buyer.md");
    expect(call.reason).toBe("Draft mode edits");
    // pendingEdits cleared post-apply.
    expect(useDraftStore.getState().activeDoc?.pendingEdits).toEqual([]);
  });

  test("rejectPendingEdits() clears the queue without calling the API", () => {
    useDraftStore.getState().openDoc(mkDoc());
    useDraftStore.getState().appendEdit(mkEdit());
    useDraftStore.getState().appendEdit(mkEdit({ op: "delete" }));
    expect(useDraftStore.getState().activeDoc?.pendingEdits).toHaveLength(2);

    useDraftStore.getState().rejectPendingEdits();

    expect(useDraftStore.getState().activeDoc?.pendingEdits).toEqual([]);
    expect(proposeNoteMock).not.toHaveBeenCalled();
    expect(applyPatchMock).not.toHaveBeenCalled();
  });
});
