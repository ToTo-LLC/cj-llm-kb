import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Bulk-store (Plan 07 Task 21).
 *
 * Drives the bulk-import 4-step flow (Pick → Scope → Dry-run → Apply).
 * Owns ``step`` + ``folder`` + ``domain`` + per-file classification state
 * + apply progress. Same test pattern as ``pending-store.test.ts``: each
 * test resets the store, mocks the typed tools API, and exercises a
 * single action in isolation.
 *
 * Six exercises:
 *   1. pickFolder() sets step=2, captures folder, seeds files.
 *   2. setCap() clamps to folder.fileCount (20-file cap pre-check).
 *   3. toggleInclude() flips the file's include flag.
 *   4. setRoute() updates file.classified + bumps confidence.
 *   5. startApply() runs the serial ingest loop, advances applyIdx.
 *   6. cancel() mid-loop stops the apply loop before the next file.
 */

const { bulkImportMock, ingestMock, listDomainsMock } = vi.hoisted(() => ({
  bulkImportMock: vi.fn(),
  ingestMock: vi.fn(),
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  bulkImport: bulkImportMock,
  ingest: ingestMock,
  listDomains: listDomainsMock,
}));

import {
  useBulkStore,
  type BulkFile,
} from "@/lib/state/bulk-store";

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
  });
  bulkImportMock.mockReset();
  ingestMock.mockReset();
  listDomainsMock.mockReset();
}

describe("useBulkStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("pickFolder() transitions to step 2 with folder + files", () => {
    useBulkStore
      .getState()
      .pickFolder("~/Archive/old-vault", [mkFile(1), mkFile(2), mkFile(3)]);
    const state = useBulkStore.getState();
    expect(state.step).toBe(2);
    expect(state.folder?.path).toBe("~/Archive/old-vault");
    expect(state.folder?.fileCount).toBe(3);
    expect(state.files).toHaveLength(3);
  });

  test("setCap() clamps value to [1, folder.fileCount]", () => {
    useBulkStore
      .getState()
      .pickFolder(
        "~/Archive/big",
        Array.from({ length: 47 }, (_, i) => mkFile(i + 1)),
      );
    useBulkStore.getState().setCap(500);
    expect(useBulkStore.getState().cap).toBe(47);
    useBulkStore.getState().setCap(0);
    expect(useBulkStore.getState().cap).toBe(1);
    useBulkStore.getState().setCap(15);
    expect(useBulkStore.getState().cap).toBe(15);
  });

  test("toggleInclude() flips include flag for one file", () => {
    useBulkStore.setState({
      step: 3,
      files: [mkFile(1, { include: true }), mkFile(2, { include: true })],
    });
    useBulkStore.getState().toggleInclude(1);
    const state = useBulkStore.getState();
    expect(state.files[0].include).toBe(false);
    expect(state.files[1].include).toBe(true);
  });

  test("setRoute() updates file.classified + bumps confidence to 1", () => {
    useBulkStore.setState({
      step: 3,
      files: [mkFile(1, { classified: "research", confidence: 0.62 })],
    });
    useBulkStore.getState().setRoute(1, "work");
    const file = useBulkStore.getState().files[0];
    expect(file.classified).toBe("work");
    expect(file.confidence).toBe(1);
  });

  test("startApply() runs ingest per included file + advances applyIdx", async () => {
    ingestMock.mockResolvedValue({
      text: "",
      data: { patch_id: "p-1", applied: false, domain: "research" },
    });
    useBulkStore.setState({
      step: 4,
      files: [mkFile(1), mkFile(2), mkFile(3, { include: false })],
    });
    await useBulkStore.getState().startApply();
    const state = useBulkStore.getState();
    expect(ingestMock).toHaveBeenCalledTimes(2); // 3rd excluded
    expect(state.applyIdx).toBe(2);
    expect(state.done).toBe(true);
    expect(state.applying).toBe(false);
    expect(state.results.applied).toHaveLength(2);
  });

  test("cancel() mid-loop stops the apply loop before the next ingest", async () => {
    // Wire ingest so the second call triggers cancel() before it resolves.
    let callCount = 0;
    ingestMock.mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        // After the first file finishes, user hits cancel.
        useBulkStore.getState().cancel();
      }
      return { text: "", data: { patch_id: null, applied: false, domain: null } };
    });
    useBulkStore.setState({
      step: 4,
      files: [mkFile(1), mkFile(2), mkFile(3)],
    });
    await useBulkStore.getState().startApply();
    const state = useBulkStore.getState();
    // Only the first file was ingested; cancel halted the loop.
    expect(ingestMock).toHaveBeenCalledTimes(1);
    expect(state.cancelled).toBe(true);
    expect(state.results.applied).toHaveLength(1);
    expect(state.applying).toBe(false);
  });
});
