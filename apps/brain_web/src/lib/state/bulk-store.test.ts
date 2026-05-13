import { describe, expect, test, beforeEach, vi } from "vitest";

/**
 * Plan 26 T4 — per-file filename display in the apply-phase UI.
 *
 * The store gains a ``currentFile: string | null`` field plus a
 * ``setCurrentFile(name)`` action. Three D11 clear-sites:
 *
 *   1. ``startApply``'s outer ``finally`` (complete state-machine
 *      transition) — clears alongside ``phase: "complete"``.
 *   2. ``endWalk(false)`` (error state-machine transition) — clears
 *      alongside ``phase: "error"``.
 *   3. The apply-loop's outer ``finally`` block — same as (1) since the
 *      ``set({ ..., currentFile: null })`` lives inside it.
 *
 * We exercise the setter contract directly + each clear-site so a
 * regression in any one of them surfaces in isolation.
 */

import { useBulkStore } from "@/lib/state/bulk-store";

function resetStore(): void {
  // Mirror the INITIAL shape from bulk-store.ts so we don't drift if the
  // store grows new fields.
  useBulkStore.setState({
    step: 1,
    folder: null,
    domain: "auto",
    cap: 20,
    files: [],
    applying: false,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
    phase: "idle",
    walkPath: null,
    walkStartedAt: null,
    applyStartedAt: null,
    currentFile: null,
  });
}

describe("bulk-store currentFile (Plan 26 T4)", () => {
  beforeEach(() => {
    resetStore();
  });

  test("setCurrentFile updates the currentFile field with the given path", () => {
    useBulkStore.getState().setCurrentFile("research/papers/foo.pdf");
    expect(useBulkStore.getState().currentFile).toBe(
      "research/papers/foo.pdf",
    );
  });

  test("setCurrentFile(null) clears a previously-set currentFile", () => {
    useBulkStore.getState().setCurrentFile("a/b/c.md");
    expect(useBulkStore.getState().currentFile).toBe("a/b/c.md");

    useBulkStore.getState().setCurrentFile(null);
    expect(useBulkStore.getState().currentFile).toBeNull();
  });

  test("endWalk(false) clears currentFile alongside the error phase transition (D11 error clear-site)", () => {
    // Seed both walk-phase markers AND a stale currentFile to prove the
    // error transition cleans up ALL of them, not just the walk fields.
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
      currentFile: "lingering/from/previous/apply.pdf",
    });

    useBulkStore.getState().endWalk(false);

    const state = useBulkStore.getState();
    expect(state.phase).toBe("error");
    expect(state.walkPath).toBeNull();
    expect(state.walkStartedAt).toBeNull();
    expect(state.currentFile).toBeNull();
  });

  test("startApply's outer finally clears currentFile alongside the complete phase transition (D11 complete + finally clear-site)", async () => {
    // Mock the ingest tool so startApply runs synchronously without
    // hitting the network. Each ingest call should observe currentFile
    // set to that file's name BEFORE awaiting, but by the time
    // startApply resolves the finally block has cleared it.
    vi.doMock("@/lib/api/tools", () => ({
      ingest: vi.fn(async () => ({
        ok: true,
        data: { status: "pending", patch_id: "p1", target_path: "x.md" },
      })),
    }));

    // Re-import after the mock so the store binds to the mocked module.
    const mod = await import("@/lib/state/bulk-store");

    // Seed two includeable files + a leftover currentFile so we can also
    // confirm the finally clears any value the loop's own setCurrentFile
    // calls left behind on the last iteration.
    mod.useBulkStore.setState({
      files: [
        {
          id: 1,
          name: "foo.md",
          type: "text",
          size: "1 KB",
          classified: null,
          confidence: null,
          include: true,
        },
        {
          id: 2,
          name: "bar.md",
          type: "text",
          size: "1 KB",
          classified: null,
          confidence: null,
          include: true,
        },
      ],
      currentFile: "stale-from-before/something.pdf",
    });

    await mod.useBulkStore.getState().startApply();

    const state = mod.useBulkStore.getState();
    expect(state.phase).toBe("complete");
    expect(state.done).toBe(true);
    expect(state.applying).toBe(false);
    // D11 third clear-site: outer finally clears currentFile.
    expect(state.currentFile).toBeNull();

    vi.doUnmock("@/lib/api/tools");
  });
});
