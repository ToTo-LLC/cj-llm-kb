import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import { useDialogsStore, type DialogKind } from "@/lib/state/dialogs-store";

/**
 * Dialog store owns single-active dialog state.
 *
 * Rules under test (Plan 07 Task 11):
 *   - open() sets active
 *   - close() resets active to null
 *   - A second open() while one is active REPLACES the first.
 *     (No stacking — one-dialog-at-a-time invariant.)
 *   - The discriminated-union payload is preserved verbatim through the store.
 */

function resetStore() {
  useDialogsStore.setState({ active: null });
}

describe("useDialogsStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("open() sets active to the given dialog payload", () => {
    const payload: DialogKind = {
      kind: "reject-reason",
      patchId: "p-1",
      targetPath: "research/notes/foo.md",
      onConfirm: vi.fn(),
    };
    useDialogsStore.getState().open(payload);
    expect(useDialogsStore.getState().active).toBe(payload);
  });

  test("close() resets active to null", () => {
    useDialogsStore.getState().open({
      kind: "typed-confirm",
      title: "Delete it?",
      body: "Permanent.",
      word: "DELETE",
      onConfirm: vi.fn(),
    });
    expect(useDialogsStore.getState().active).not.toBeNull();
    useDialogsStore.getState().close();
    expect(useDialogsStore.getState().active).toBeNull();
  });

  test("second open() replaces the first — no stacking", () => {
    const first: DialogKind = {
      kind: "reject-reason",
      patchId: "p-1",
      targetPath: "research/a.md",
      onConfirm: vi.fn(),
    };
    const second: DialogKind = {
      kind: "typed-confirm",
      title: "Delete",
      body: "Body",
      word: "DELETE",
      onConfirm: vi.fn(),
    };
    const { open } = useDialogsStore.getState();
    open(first);
    open(second);
    // Only the second is active; nothing stacked.
    expect(useDialogsStore.getState().active).toBe(second);
    expect(useDialogsStore.getState().active).not.toBe(first);
  });

  test("typed payload round-trips through the store (edit-approve)", () => {
    const onConfirm = vi.fn();
    const payload: DialogKind = {
      kind: "edit-approve",
      patchId: "p-42",
      targetPath: "work/meetings/2026-04-21.md",
      before: "old body",
      after: "new body",
      onConfirm,
    };
    useDialogsStore.getState().open(payload);
    const active = useDialogsStore.getState().active;
    expect(active).not.toBeNull();
    // Narrow the union and assert every field is preserved.
    if (active && active.kind === "edit-approve") {
      expect(active.patchId).toBe("p-42");
      expect(active.targetPath).toBe("work/meetings/2026-04-21.md");
      expect(active.before).toBe("old body");
      expect(active.after).toBe("new body");
      expect(active.onConfirm).toBe(onConfirm);
    } else {
      throw new Error("expected edit-approve kind");
    }
  });
});
