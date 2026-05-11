import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Inbox-store (Plan 07 Task 17).
 *
 * Holds the list of ingest sources (feeds the three inbox tabs), the
 * active tab, and optimistic in-flight rows for drag-drop / paste
 * uploads. The store is the seam between ``brain_recent_ingests`` (Task
 * 4 tool) and the inbox screen. Envelope metadata only — no body data.
 *
 * Each test resets the store to the known-initial shape and mocks the
 * typed tools API, same pattern as ``pending-store.test.ts``.
 */

const { recentIngestsMock } = vi.hoisted(() => ({
  recentIngestsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  recentIngests: recentIngestsMock,
}));

import { useInboxStore, type IngestSource } from "@/lib/state/inbox-store";

function resetStore() {
  useInboxStore.setState({
    sources: [],
    activeTab: "progress",
  });
  recentIngestsMock.mockReset();
}

function mkSource(
  id: string,
  extra: Partial<IngestSource> = {},
): IngestSource {
  return {
    id,
    source: `https://example.com/${id}`,
    title: `Source ${id}`,
    type: "url",
    status: "done",
    domain: "research",
    progress: 100,
    at: "2026-04-21T10:00:00Z",
    ...extra,
  };
}

describe("useInboxStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("loadRecent() populates sources from brain_recent_ingests", async () => {
    recentIngestsMock.mockResolvedValue({
      text: "",
      data: {
        ingests: [
          {
            source: "https://example.com/a",
            source_type: "url",
            domain: "research",
            status: "done",
            classified_at: "2026-04-21T10:00:00Z",
            cost_usd: 0,
          },
          {
            source: "https://example.com/b",
            source_type: "url",
            domain: "work",
            status: "done",
            classified_at: "2026-04-21T11:00:00Z",
            cost_usd: 0,
          },
        ],
      },
    });
    await useInboxStore.getState().loadRecent();
    const state = useInboxStore.getState();
    expect(state.sources).toHaveLength(2);
    expect(state.sources[0].source).toBe("https://example.com/a");
    expect(state.sources[1].domain).toBe("work");
  });

  test("loadRecent() reads backend `ingests`/`classified_at`/`cost_usd` (Plan 18 T3.1 regression)", async () => {
    // Mock the REAL backend shape — `ingests` not `items`, `classified_at` not `at`,
    // `cost_usd` not `cost`. Plan 18 T3.1 narrowed the TS interface; this regression
    // would fail RED against pre-fix code (consumer reads `data.items` = undefined →
    // empty sources, and `it.cost` = undefined → silent zero cost).
    recentIngestsMock.mockResolvedValue({
      text: "",
      data: {
        ingests: [
          {
            source: "https://example.com/a",
            source_type: "url",
            domain: "research",
            status: "done",
            classified_at: "2026-04-21T10:00:00Z",
            cost_usd: 0.0123,
          },
        ],
      },
    });
    await useInboxStore.getState().loadRecent();
    const state = useInboxStore.getState();
    expect(state.sources).toHaveLength(1);
    expect(state.sources[0].source).toBe("https://example.com/a");
    expect(state.sources[0].at).toBe("2026-04-21T10:00:00Z");
    expect(state.sources[0].cost).toBe(0.0123);
  });

  test("filter by tab returns the matching subset", () => {
    useInboxStore.setState({
      sources: [
        mkSource("a", { status: "queued", progress: 5 }),
        mkSource("b", { status: "classifying", progress: 40 }),
        mkSource("c", { status: "done", progress: 100 }),
        mkSource("d", { status: "failed", progress: 0, error: "boom" }),
      ],
      activeTab: "progress",
    });

    // In-progress bucket covers queued / classifying / summarizing / integrating.
    const progress = useInboxStore
      .getState()
      .sources.filter((s) =>
        ["queued", "extracting", "classifying", "summarizing", "integrating"].includes(
          s.status,
        ),
      );
    expect(progress.map((s) => s.id)).toEqual(["a", "b"]);

    const failed = useInboxStore
      .getState()
      .sources.filter((s) => s.status === "failed");
    expect(failed.map((s) => s.id)).toEqual(["d"]);

    const recent = useInboxStore
      .getState()
      .sources.filter((s) => s.status === "done");
    expect(recent.map((s) => s.id)).toEqual(["c"]);
  });

  test("addOptimistic() prepends a new source with status=queued", () => {
    useInboxStore.setState({
      sources: [mkSource("existing")],
      activeTab: "progress",
    });
    useInboxStore.getState().addOptimistic({
      id: "opt-1",
      source: "pasted text",
      title: "pasted text",
      type: "text",
    });
    const state = useInboxStore.getState();
    expect(state.sources).toHaveLength(2);
    // Newest on top.
    expect(state.sources[0].id).toBe("opt-1");
    expect(state.sources[0].status).toBe("queued");
    expect(state.sources[0].progress).toBe(0);
    // Preserved existing row.
    expect(state.sources[1].id).toBe("existing");
  });

  test("updateStatus() transitions a source from queued → classifying → done", () => {
    useInboxStore.setState({
      sources: [mkSource("opt-1", { status: "queued", progress: 0 })],
      activeTab: "progress",
    });
    useInboxStore
      .getState()
      .updateStatus("opt-1", { status: "classifying", progress: 35 });
    expect(useInboxStore.getState().sources[0].status).toBe("classifying");
    expect(useInboxStore.getState().sources[0].progress).toBe(35);
    useInboxStore
      .getState()
      .updateStatus("opt-1", { status: "done", progress: 100 });
    expect(useInboxStore.getState().sources[0].status).toBe("done");
    expect(useInboxStore.getState().sources[0].progress).toBe(100);
  });
});
