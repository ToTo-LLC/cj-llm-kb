import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Apply loop (Plan 07 Task 21, Step 4).
 *
 * Serial ingest per included non-skipped file. Failures land in
 * ``results.failed``. Cancel halts the loop before the next ingest.
 * The summary object at the end carries correct applied / failed /
 * quarantined counts.
 *
 * Four exercises:
 *   1. Sequential ingest for every included + non-skipped file.
 *   2. Cancel mid-loop stops further ingests.
 *   3. Failed ingests tracked in results.failed, loop keeps going.
 *   4. Final summary matches applied + failed + quarantined totals.
 */

const { ingestMock } = vi.hoisted(() => ({
  ingestMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  bulkImport: vi.fn(),
  ingest: ingestMock,
  listDomains: vi.fn(),
}));

import { useBulkStore, type BulkFile } from "@/lib/state/bulk-store";

function mkFile(id: number, extra: Partial<BulkFile> = {}): BulkFile {
  return {
    id,
    name: `file-${id}.md`,
    type: "text",
    size: "4.2 KB",
    classified: "research",
    confidence: 0.92,
    include: true,
    ...extra,
  };
}

function resetStore() {
  useBulkStore.setState({
    step: 4,
    folder: null,
    domain: "auto",
    cap: 20,
    files: [],
    applying: false,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
  });
  ingestMock.mockReset();
}

beforeEach(() => {
  resetStore();
});

describe("bulk apply loop", () => {
  test("runs ingest sequentially for each included + non-skipped file", async () => {
    const callOrder: string[] = [];
    ingestMock.mockImplementation(async (args: { source: string }) => {
      callOrder.push(args.source);
      return {
        text: "",
        data: { patch_id: "p", applied: false, domain: "research" },
      };
    });
    useBulkStore.setState({
      files: [
        mkFile(1, { name: "a.md" }),
        mkFile(2, { name: "b.md" }),
        mkFile(3, { name: "c.md" }),
      ],
    });
    await useBulkStore.getState().startApply();
    expect(callOrder).toEqual(["a.md", "b.md", "c.md"]);
    expect(useBulkStore.getState().done).toBe(true);
  });

  test("cancel mid-loop stops before the next ingest", async () => {
    let call = 0;
    ingestMock.mockImplementation(async () => {
      call++;
      if (call === 2) {
        useBulkStore.getState().cancel();
      }
      return { text: "", data: { patch_id: null, applied: false, domain: null } };
    });
    useBulkStore.setState({
      files: [mkFile(1), mkFile(2), mkFile(3), mkFile(4)],
    });
    await useBulkStore.getState().startApply();
    // 2 ran, cancel fired during the 2nd, loop stops before 3rd.
    expect(ingestMock).toHaveBeenCalledTimes(2);
    const state = useBulkStore.getState();
    expect(state.cancelled).toBe(true);
    expect(state.results.applied).toHaveLength(2);
  });

  test("failed ingest tracked in results.failed, loop continues", async () => {
    ingestMock.mockImplementation(async (args: { source: string }) => {
      if (args.source === "b.md") {
        throw new Error("ingest boom");
      }
      return {
        text: "",
        data: { patch_id: "p", applied: false, domain: "research" },
      };
    });
    useBulkStore.setState({
      files: [
        mkFile(1, { name: "a.md" }),
        mkFile(2, { name: "b.md" }),
        mkFile(3, { name: "c.md" }),
      ],
    });
    await useBulkStore.getState().startApply();
    const state = useBulkStore.getState();
    expect(state.results.applied).toHaveLength(2);
    expect(state.results.failed).toEqual(["b.md"]);
    expect(state.done).toBe(true);
  });

  test("final summary has correct applied + failed + quarantined counts", async () => {
    ingestMock.mockImplementation(async (args: { source: string }) => {
      if (args.source === "bad.md") throw new Error("x");
      return {
        text: "",
        data: { patch_id: "p", applied: false, domain: "research" },
      };
    });
    useBulkStore.setState({
      files: [
        mkFile(1, { name: "ok1.md" }),
        mkFile(2, { name: "bad.md" }),
        mkFile(3, { name: "ok2.md" }),
        // Skipped files never hit ingest, but land in quarantined.
        mkFile(4, {
          name: ".DS_Store",
          skip: "System file — ignored.",
          include: false,
        }),
        // Excluded-by-user files are neither applied nor quarantined.
        mkFile(5, { name: "excluded.md", include: false }),
      ],
    });
    await useBulkStore.getState().startApply();
    const { results } = useBulkStore.getState();
    expect(results.applied).toEqual(["ok1.md", "ok2.md"]);
    expect(results.failed).toEqual(["bad.md"]);
    expect(results.quarantined).toEqual([".DS_Store"]);
  });
});
