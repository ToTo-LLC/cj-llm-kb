import { describe, expect, test, beforeEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

/**
 * Inbox-store ``loadRecent`` id-keyed merge (Plan 16 Task 1, D1).
 *
 * The original implementation called ``set({ sources: items })``
 * unconditionally, which raced ``addOptimistic`` callers: a slow
 * ``loadRecent`` resolution overwrote just-inserted optimistic rows
 * with the (typically empty) server list. Plan 14 Task 6 captured the
 * symptom in the e2e (``ingest-drag-drop.spec.ts``) by arming a
 * ``waitForResponse`` band-aid before navigating; Plan 16 Task 1 lands
 * the production fix and removes the band-aid.
 *
 * The merge contract:
 *   - Optimistic rows with status === "queued" whose id is NOT in the
 *     server response are preserved (they're the in-flight adds).
 *   - Optimistic rows whose id IS in the server response are dropped
 *     (the server now has the canonical row).
 *   - Optimistic rows with any other status (``complete``, ``failed``,
 *     etc.) are NOT preserved — those came from the server originally
 *     and re-appear in ``items`` if still recent. Preserving them would
 *     duplicate stale rows.
 *   - Order: optimistic-preserved rows lead, server rows follow. This
 *     matches ``addOptimistic`` prepend semantics — the user-visible
 *     order shouldn't change just because ``loadRecent`` resolves.
 */

const { recentIngestsMock } = vi.hoisted(() => ({
  recentIngestsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  recentIngests: recentIngestsMock,
}));

import { useInboxStore } from "@/lib/state/inbox-store";

function resetStore() {
  useInboxStore.setState({
    sources: [],
    activeTab: "progress",
  });
  recentIngestsMock.mockReset();
}

/** Server-shape row as returned by ``brain_recent_ingests``. Mirrors
 *  the real backend dict (see ``recent_ingests.py:65-79``): ``ingests``
 *  outer key, ``classified_at`` / ``cost_usd`` / ``source_type`` inner
 *  keys. Plan 18 T3.1 brought this in line with the backend after the
 *  T2 drift audit. */
function mkServerItem(
  patch_id: string,
  source: string,
  classified_at: string = "2026-04-21T10:00:00Z",
) {
  return {
    patch_id,
    source,
    source_type: "url",
    domain: "research",
    status: "done",
    classified_at,
    cost_usd: 0,
  };
}

describe("useInboxStore.loadRecent — Plan 16 Task 1 id-keyed merge", () => {
  beforeEach(() => {
    resetStore();
  });

  test("preserves an optimistic queued row whose id is not in the server response", async () => {
    // 1. User drops a file → addOptimistic prepends a queued row.
    useInboxStore.getState().addOptimistic({
      id: "foo-id",
      source: "foo.md",
      title: "foo.md",
      type: "file",
    });
    // 2. The mount-time loadRecent fetch resolves with two server rows
    //    that don't yet include the optimistic row (it's still being
    //    ingested server-side).
    recentIngestsMock.mockResolvedValue({
      text: "",
      data: {
        ingests: [
          mkServerItem("bar-id", "https://example.com/bar"),
          mkServerItem("baz-id", "https://example.com/baz"),
        ],
      },
    });

    await useInboxStore.getState().loadRecent();

    const state = useInboxStore.getState();
    expect(state.sources).toHaveLength(3);
    // Optimistic row preserved.
    const ids = state.sources.map((s) => s.id);
    expect(ids).toContain("foo-id");
    expect(ids).toContain("bar-id");
    expect(ids).toContain("baz-id");
    // Order: optimistic-preserved leads, server rows follow. Matches
    // addOptimistic prepend semantics.
    expect(state.sources[0].id).toBe("foo-id");
    expect(state.sources[0].status).toBe("queued");
    expect(state.sources[1].id).toBe("bar-id");
    expect(state.sources[2].id).toBe("baz-id");
  });

  test("dedupes when an optimistic row's id IS in the server response (server wins)", async () => {
    // The user uploaded a file, the optimistic row was added with id
    // ``shared-id``, and by the time loadRecent resolves the server has
    // already finished ingestion and returns a canonical row with the
    // same id. The optimistic row should NOT be preserved (would
    // duplicate); the server row is canonical.
    useInboxStore.getState().addOptimistic({
      id: "shared-id",
      source: "shared.md",
      title: "shared.md (optimistic)",
      type: "file",
    });
    recentIngestsMock.mockResolvedValue({
      text: "",
      data: {
        ingests: [
          {
            patch_id: "shared-id",
            source: "shared.md",
            source_type: "file",
            domain: "research",
            status: "done",
            classified_at: "2026-04-21T11:00:00Z",
            cost_usd: 0,
            title: "shared.md (server)",
            progress: 100,
          },
          mkServerItem("other-id", "https://example.com/other"),
        ],
      },
    });

    await useInboxStore.getState().loadRecent();

    const state = useInboxStore.getState();
    // No duplicate of shared-id.
    const ids = state.sources.map((s) => s.id);
    expect(ids).toEqual(["shared-id", "other-id"]);
    // Server row wins — title + status come from the server payload,
    // not from the dropped optimistic row.
    const shared = state.sources.find((s) => s.id === "shared-id")!;
    expect(shared.title).toBe("shared.md (server)");
    expect(shared.status).toBe("done");
  });

  test("does NOT preserve optimistic rows with status other than 'queued'", async () => {
    // The store can hold rows in non-queued states (e.g., the previous
    // loadRecent populated them with ``done``, or a WS event flipped
    // them to ``failed``). These rows came from the server originally
    // and would re-appear in the next loadRecent ``items`` if still
    // recent — preserving them would duplicate stale rows. Only
    // ``queued`` (the addOptimistic starter status) is preserved.
    useInboxStore.setState({
      sources: [
        {
          id: "done-row",
          source: "done.md",
          title: "done.md",
          type: "file",
          status: "done",
          domain: "research",
          progress: 100,
          at: "2026-04-21T09:00:00Z",
        },
        {
          id: "failed-row",
          source: "failed.md",
          title: "failed.md",
          type: "file",
          status: "failed",
          domain: null,
          progress: 0,
          at: "2026-04-21T09:30:00Z",
          error: "boom",
        },
        {
          id: "classifying-row",
          source: "classifying.md",
          title: "classifying.md",
          type: "file",
          status: "classifying",
          domain: null,
          progress: 35,
          at: "2026-04-21T09:45:00Z",
        },
        {
          id: "queued-row",
          source: "queued.md",
          title: "queued.md",
          type: "file",
          status: "queued",
          domain: null,
          progress: 0,
          at: "2026-04-21T09:50:00Z",
        },
      ],
      activeTab: "progress",
    });
    recentIngestsMock.mockResolvedValue({
      text: "",
      data: {
        ingests: [mkServerItem("server-row", "https://example.com/server")],
      },
    });

    await useInboxStore.getState().loadRecent();

    const state = useInboxStore.getState();
    const ids = state.sources.map((s) => s.id);
    // Only the queued row survived alongside the server row.
    expect(ids).toEqual(["queued-row", "server-row"]);
    expect(ids).not.toContain("done-row");
    expect(ids).not.toContain("failed-row");
    expect(ids).not.toContain("classifying-row");
  });

  test("falls back to plain replacement when no optimistic queued rows are in flight", async () => {
    // Sanity: the merge must not regress the simple case. Empty store
    // + server rows → store contains exactly the server rows in their
    // original order.
    recentIngestsMock.mockResolvedValue({
      text: "",
      data: {
        ingests: [
          mkServerItem("a", "https://example.com/a"),
          mkServerItem("b", "https://example.com/b"),
        ],
      },
    });

    await useInboxStore.getState().loadRecent();

    const state = useInboxStore.getState();
    expect(state.sources.map((s) => s.id)).toEqual(["a", "b"]);
  });
});
