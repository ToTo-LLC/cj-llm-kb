/**
 * Plan 22 T12 — PanelWatchedFolders tests.
 *
 * Pins the Settings → Watched folders panel against the mockup at
 * ``docs/design/plan-22/watched-folders-settings.md``:
 *
 *   1. Populated state — renders one row per
 *      ``useWatchedFoldersStore.folders`` entry; row contents include
 *      path, domain badge, file/orphan/last-sync sub-line per the
 *      mockup's microcopy spec.
 *   2. Empty state — renders the "No folders being watched yet."
 *      heading + supporting copy + empty-state CTA.
 *   3. Loading state — renders the skeleton + sr-only "Loading
 *      watched folders…" announcement until the first refresh resolves.
 *   4. Error banner — surfaces ``useWatchedFoldersStore.error`` with
 *      ``role="alert"`` + a "Try again" retry button.
 *   5. Unwatch action — clicking the per-row "Unwatch" button calls
 *      ``brain_unwatch_folder({folder})`` with the row's path,
 *      optimistically drops the row, and pushes a success toast on
 *      resolve.
 *   6. Unwatch toast — basename + orphan count make it into the toast
 *      copy verbatim from the mockup's microcopy spec.
 *   7. Personal-domain note — the privacy-rail informational note
 *      renders only for entries whose ``domain === "personal"``.
 *   8. Watch-new CTA placement — the populated branch shows the
 *      header-anchored CTA; the empty branch shows the centered
 *      empty-state CTA. Clicking either pushes the placeholder toast
 *      until T15 wires the watch-enable modal.
 *   9. Resync action (T12 fix-up) — the per-row "Resync now" button is
 *      wired to ``brain_resync_folder``; button is NOT disabled when
 *      row data is present, calls the tool with the row's path, shows
 *      a spinner + ``aria-busy`` while in flight, surfaces a success
 *      toast with the backend's summary fields, and a danger toast on
 *      backend failure. (The earlier T12 mistakenly disabled this
 *      button on the false claim that the backend handler did not
 *      ship in T5; it did. Plan 22 T12 fix-up wires it.)
 */

import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

// ---- Hoisted mock factories ----

const { unwatchFolderMock, listWatchedFoldersMock, resyncFolderMock } =
  vi.hoisted(() => ({
    unwatchFolderMock: vi.fn(),
    listWatchedFoldersMock: vi.fn(),
    resyncFolderMock: vi.fn(),
  }));

vi.mock("@/lib/api/tools", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/tools")>("@/lib/api/tools");
  return {
    ...actual,
    unwatchFolder: (...args: unknown[]) => unwatchFolderMock(...args),
    listWatchedFolders: (...args: unknown[]) =>
      listWatchedFoldersMock(...args),
    resyncFolder: (...args: unknown[]) => resyncFolderMock(...args),
  };
});

// ---- Imports (after mocks) ----

import { PanelWatchedFolders } from "@/components/settings/panel-watched-folders";
import { useSystemStore } from "@/lib/state/system-store";
import { useWatchedFoldersStore } from "@/lib/state/watched-folders-store";
import type { WatchedFolderEntry } from "@/lib/api/tools";

// ---- Helpers ----

function resetSystemStore() {
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    searchOpen: false,
    toasts: [],
  });
}

function makeEntry(
  overrides: Partial<WatchedFolderEntry> = {},
): WatchedFolderEntry {
  return {
    path: "/Users/test/Notes/Research-Papers",
    domain: "research",
    enabled: true,
    last_sync: new Date(Date.now() - 4 * 60_000).toISOString(),
    policy: "overwrite",
    include_subdirs: true,
    file_count: 142,
    orphan_count: 3,
    ...overrides,
  };
}

/** Resolve the store-side ``refresh()`` promise with the given folders
 *  WITHOUT triggering an actual network call. We mock the API binding
 *  so the store's ``listWatchedFolders().then`` lands with our payload. */
function primeListResolved(folders: WatchedFolderEntry[]) {
  listWatchedFoldersMock.mockResolvedValue({
    text: "",
    data: { folders },
    isError: false,
  });
}

function primeListRejected(error: Error) {
  listWatchedFoldersMock.mockRejectedValue(error);
}

// ---- Setup / teardown ----

beforeEach(() => {
  unwatchFolderMock.mockReset();
  listWatchedFoldersMock.mockReset();
  resyncFolderMock.mockReset();
  resetSystemStore();
  useWatchedFoldersStore.getState()._resetForTesting();
});

// ---- Tests ----

describe("PanelWatchedFolders — populated state", () => {
  test("renders one row per folder with path + domain badge", async () => {
    primeListResolved([
      makeEntry({
        path: "/Users/test/Notes/Research-Papers",
        domain: "research",
        file_count: 142,
        orphan_count: 3,
      }),
      makeEntry({
        path: "/Users/test/Documents/Work-Logs",
        domain: "work",
        file_count: 38,
        orphan_count: 0,
        last_sync: new Date(Date.now() - 60 * 60_000).toISOString(),
      }),
      makeEntry({
        path: "/Users/test/Private/Journal",
        domain: "personal",
        file_count: 7,
        orphan_count: 0,
        last_sync: new Date(Date.now() - 12 * 60_000).toISOString(),
      }),
    ]);

    render(<PanelWatchedFolders />);

    // Wait for the store's refresh to land + the panel to switch from
    // loading to populated.
    await waitFor(() =>
      expect(screen.queryByTestId("watched-folders-loading")).not.toBeInTheDocument(),
    );

    const rows = screen.getAllByTestId("watched-folder-row");
    expect(rows).toHaveLength(3);

    expect(
      screen.getByText("/Users/test/Notes/Research-Papers"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("/Users/test/Documents/Work-Logs"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("/Users/test/Private/Journal"),
    ).toBeInTheDocument();

    // Domain badges render with the slug as visible text.
    expect(screen.getByTestId("domain-badge-research")).toHaveTextContent(
      "research",
    );
    expect(screen.getByTestId("domain-badge-work")).toHaveTextContent("work");
    expect(screen.getByTestId("domain-badge-personal")).toHaveTextContent(
      "personal",
    );
  });

  test("sub-line renders file count, orphan count, and last sync", async () => {
    primeListResolved([
      makeEntry({
        path: "/p/A",
        domain: "research",
        file_count: 142,
        orphan_count: 3,
        last_sync: new Date(Date.now() - 4 * 60_000).toISOString(),
      }),
    ]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    const subline = screen.getByTestId("watched-folder-subline");
    // "142 files · 3 orphans · last synced 4 minutes ago" per mockup.
    expect(subline).toHaveTextContent("142 files");
    expect(subline).toHaveTextContent("3 orphans");
    expect(subline).toHaveTextContent(/4 minutes ago/);
  });

  test("sub-line omits orphan count when zero (mockup §microcopy)", async () => {
    primeListResolved([
      makeEntry({
        path: "/p/B",
        domain: "work",
        file_count: 38,
        orphan_count: 0,
        last_sync: new Date(Date.now() - 60 * 60_000).toISOString(),
      }),
    ]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    const subline = screen.getByTestId("watched-folder-subline");
    expect(subline).toHaveTextContent("38 files");
    expect(subline).not.toHaveTextContent(/orphan/);
    expect(subline).toHaveTextContent(/1 hour ago/);
  });

  test('renders "never synced" when last_sync is null', async () => {
    primeListResolved([
      makeEntry({
        path: "/p/never",
        domain: "research",
        file_count: 0,
        orphan_count: 0,
        last_sync: null,
      }),
    ]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    expect(
      screen.getByTestId("watched-folder-subline"),
    ).toHaveTextContent(/never synced/);
  });

  test("personal-domain note renders only for personal-domain rows", async () => {
    primeListResolved([
      makeEntry({ path: "/p/research", domain: "research" }),
      makeEntry({ path: "/p/personal", domain: "personal" }),
    ]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getAllByTestId("watched-folder-row")).toHaveLength(2),
    );
    const notes = screen.queryAllByTestId("watched-folder-personal-note");
    expect(notes).toHaveLength(1);
    expect(notes[0]).toHaveTextContent(
      /This folder syncs into your personal domain \(privacy-railed by default\)/,
    );
  });
});

describe("PanelWatchedFolders — empty state", () => {
  test("renders empty-state card with mockup-verbatim copy", async () => {
    primeListResolved([]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(
        screen.getByTestId("watched-folders-empty-state"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText("No folders being watched yet."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Pick a folder and Brain will keep its notes in sync automatically.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("watched-folders-empty-cta"),
    ).toHaveTextContent("Watch a folder");
    // Populated-state CTA must NOT render in empty branch (mockup spec).
    expect(
      screen.queryByTestId("watched-folders-add-cta"),
    ).not.toBeInTheDocument();
  });
});

describe("PanelWatchedFolders — loading state", () => {
  test("renders skeleton + sr-only announcement before refresh resolves", async () => {
    // Hold the resolution open so we observe the loading state.
    let resolveFn: ((v: unknown) => void) | undefined;
    listWatchedFoldersMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    render(<PanelWatchedFolders />);
    // Loading container with status role.
    const loading = screen.getByTestId("watched-folders-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(loading).toHaveAttribute("aria-live", "polite");
    // sr-only announcement copy.
    expect(screen.getByText(/Loading watched folders/)).toBeInTheDocument();
    // Resolve so we don't leak the pending promise.
    resolveFn?.({ text: "", data: { folders: [] }, isError: false });
    await waitFor(() =>
      expect(screen.queryByTestId("watched-folders-loading")).not.toBeInTheDocument(),
    );
  });
});

describe("PanelWatchedFolders — error banner", () => {
  test("renders error banner + retry button when refresh rejects", async () => {
    primeListRejected(new Error("backend unreachable"));
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(
        screen.getByTestId("watched-folders-error-banner"),
      ).toBeInTheDocument(),
    );
    const banner = screen.getByTestId("watched-folders-error-banner");
    expect(banner).toHaveAttribute("role", "alert");
    expect(banner).toHaveTextContent(/Couldn.t load watched folders/);
    expect(banner).toHaveTextContent("backend unreachable");
    expect(
      screen.getByTestId("watched-folders-retry"),
    ).toBeInTheDocument();
  });

  test("retry button triggers a new fetch", async () => {
    const user = userEvent.setup();
    primeListRejected(new Error("first fail"));
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(
        screen.getByTestId("watched-folders-error-banner"),
      ).toBeInTheDocument(),
    );
    // Next call resolves with one folder.
    primeListResolved([makeEntry({ path: "/p/A", domain: "research" })]);
    await user.click(screen.getByTestId("watched-folders-retry"));
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
  });
});

describe("PanelWatchedFolders — unwatch action", () => {
  test("clicking Unwatch calls brain_unwatch_folder with the row path", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ path: "/p/A", domain: "research", orphan_count: 2 }),
    ]);
    unwatchFolderMock.mockResolvedValue({
      text: "",
      data: { status: "unwatched", folder: "/p/A", remaining_notes: 5 },
      isError: false,
    });
    // Mock the SUBSEQUENT refresh after the unwatch resolves — the
    // panel re-fetches to reconcile. Empty list is fine for the assertion.
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    // After first refresh resolves with [A], queue the post-unwatch
    // refresh to resolve with []. The store re-uses the same mock so
    // the next mockResolvedValueOnce takes over.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: { folders: [] },
      isError: false,
    });
    await user.click(screen.getByTestId("watched-folder-unwatch-/p/A"));
    await waitFor(() =>
      expect(unwatchFolderMock).toHaveBeenCalledWith({ folder: "/p/A" }),
    );
  });

  test("unwatch optimistically drops the row before the API resolves", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ path: "/p/A", domain: "research" }),
      makeEntry({ path: "/p/B", domain: "work" }),
    ]);
    // Hold the unwatch open so we observe the optimistic drop.
    let resolveFn: ((v: unknown) => void) | undefined;
    unwatchFolderMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getAllByTestId("watched-folder-row")).toHaveLength(2),
    );
    await user.click(screen.getByTestId("watched-folder-unwatch-/p/A"));
    // Optimistic drop — only B remains before the API resolves.
    await waitFor(() =>
      expect(screen.getAllByTestId("watched-folder-row")).toHaveLength(1),
    );
    expect(screen.getByText("/p/B")).toBeInTheDocument();
    expect(screen.queryByText("/p/A")).not.toBeInTheDocument();
    // Resolve so the test doesn't leak the pending promise.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: { folders: [makeEntry({ path: "/p/B", domain: "work" })] },
      isError: false,
    });
    resolveFn?.({
      text: "",
      data: { status: "unwatched", folder: "/p/A", remaining_notes: 0 },
      isError: false,
    });
  });

  test("unwatch toast includes basename and orphan count", async () => {
    const user = userEvent.setup();
    // First call (mount refresh) resolves with the populated row;
    // default (mockResolvedValue) catches the second call (post-unwatch
    // reconcile refresh) with an empty list. Order matters — `Once`
    // queue is consumed before falling through to the default.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: {
        folders: [
          makeEntry({
            path: "/Users/test/Notes/Research-Papers",
            domain: "research",
            orphan_count: 3,
          }),
        ],
      },
      isError: false,
    });
    listWatchedFoldersMock.mockResolvedValue({
      text: "",
      data: { folders: [] },
      isError: false,
    });
    unwatchFolderMock.mockResolvedValue({
      text: "",
      data: {
        status: "unwatched",
        folder: "/Users/test/Notes/Research-Papers",
        remaining_notes: 142,
      },
      isError: false,
    });
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByTestId(
        "watched-folder-unwatch-/Users/test/Notes/Research-Papers",
      ),
    );
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Stopped watching Research-Papers.");
      expect(toasts[0].msg).toContain("3 orphans remain marked");
      expect(toasts[0].variant).toBe("success");
    });
  });

  test("unwatch failure restores the row and pushes danger toast", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ path: "/p/A", domain: "research" }),
    ]);
    unwatchFolderMock.mockRejectedValue(new Error("disk full"));
    // The error-recovery refresh re-fetches; resolve with [A] again so
    // the row reappears.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: {
        folders: [makeEntry({ path: "/p/A", domain: "research" })],
      },
      isError: false,
    });
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("watched-folder-unwatch-/p/A"));
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Couldn't unwatch folder.");
      expect(toasts[0].msg).toBe("disk full");
      expect(toasts[0].variant).toBe("danger");
    });
    // Row restored after the error-recovery refresh.
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
  });
});

describe("PanelWatchedFolders — Watch-new CTA placement", () => {
  test("populated branch renders the header-anchored CTA", async () => {
    primeListResolved([makeEntry({ path: "/p/A", domain: "research" })]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("watched-folders-add-cta")).toHaveTextContent(
      "Watch a new folder",
    );
  });

  test("empty branch renders the centered empty-state CTA", async () => {
    primeListResolved([]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(
        screen.getByTestId("watched-folders-empty-cta"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByTestId("watched-folders-add-cta"),
    ).not.toBeInTheDocument();
  });

  test("clicking the CTA pushes the placeholder toast (T15 will wire the modal)", async () => {
    const user = userEvent.setup();
    primeListResolved([makeEntry({ path: "/p/A", domain: "research" })]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folders-add-cta")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("watched-folders-add-cta"));
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Coming soon.");
      expect(toasts[0].msg).toContain("T15");
    });
  });
});

describe("PanelWatchedFolders — Resync action (T12 fix-up)", () => {
  test("Resync button is NOT disabled when a row is present", async () => {
    primeListResolved([makeEntry({ path: "/p/A", domain: "research" })]);
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    const btn = screen.getByTestId("watched-folder-resync-/p/A");
    // The earlier T12 disabled this button with a "Coming soon"
    // tooltip; the fix-up wires it. The button must be interactive at
    // rest (only disabled while a resync is in flight).
    expect(btn).not.toBeDisabled();
    expect(btn).not.toHaveAttribute("aria-busy", "true");
  });

  test("clicking Resync calls brain_resync_folder with the row path", async () => {
    const user = userEvent.setup();
    // Order matters: ``mockResolvedValueOnce`` queue is consumed first
    // for the mount fetch + post-resync reconcile fetch; falls through
    // to the default ``mockResolvedValue`` after that. Same pattern as
    // the unwatch toast test above. Critically: we must NOT call
    // ``primeListResolved`` here because that uses ``mockResolvedValue``
    // which would be overwritten by the empty-list default below.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: {
        folders: [
          makeEntry({
            path: "/Users/test/Notes/Research-Papers",
            domain: "research",
          }),
        ],
      },
      isError: false,
    });
    listWatchedFoldersMock.mockResolvedValue({
      text: "",
      data: { folders: [] },
      isError: false,
    });
    resyncFolderMock.mockResolvedValue({
      text: "",
      data: {
        status: "resynced",
        folder: "/Users/test/Notes/Research-Papers",
        summary: {
          updated: 4,
          no_change: 138,
          newly_orphaned: 0,
          restored_from_orphan: 0,
        },
      },
      isError: false,
    });
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByTestId(
        "watched-folder-resync-/Users/test/Notes/Research-Papers",
      ),
    );
    await waitFor(() =>
      expect(resyncFolderMock).toHaveBeenCalledWith({
        folder: "/Users/test/Notes/Research-Papers",
      }),
    );
  });

  test("Resync shows spinner + aria-busy + 'Syncing…' label while in flight", async () => {
    const user = userEvent.setup();
    primeListResolved([makeEntry({ path: "/p/A", domain: "research" })]);
    // Hold the resync open so we can observe the in-flight state.
    let resolveFn: ((v: unknown) => void) | undefined;
    resyncFolderMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("watched-folder-resync-/p/A"));
    // In-flight state assertions per mockup §"Mutation in-flight state".
    await waitFor(() => {
      const btn = screen.getByTestId("watched-folder-resync-/p/A");
      expect(btn).toBeDisabled();
      expect(btn).toHaveAttribute("aria-busy", "true");
      expect(btn).toHaveAttribute(
        "aria-label",
        "Resyncing /p/A, please wait",
      );
      expect(btn).toHaveTextContent("Syncing…");
    });
    // Sibling Unwatch on the same row must also disable during resync.
    expect(screen.getByTestId("watched-folder-unwatch-/p/A")).toBeDisabled();
    // Drain the promise so the test doesn't leak it. The reconcile-
    // refresh after resync needs the row to STILL exist (the resync
    // shouldn't remove the folder — just update its stats), so we
    // queue the same single-row payload, not an empty list.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: { folders: [makeEntry({ path: "/p/A", domain: "research" })] },
      isError: false,
    });
    resolveFn?.({
      text: "",
      data: {
        status: "resynced",
        folder: "/p/A",
        summary: {
          updated: 0,
          no_change: 0,
          newly_orphaned: 0,
          restored_from_orphan: 0,
        },
      },
      isError: false,
    });
    // After resolve the spinner must clear.
    await waitFor(() => {
      const btn = screen.getByTestId("watched-folder-resync-/p/A");
      expect(btn).not.toBeDisabled();
      expect(btn).toHaveTextContent("Resync now");
    });
  });

  test("Resync success toast includes summary counts from the backend", async () => {
    const user = userEvent.setup();
    // Don't call ``primeListResolved`` here — its default would be
    // overwritten by the reconcile-refresh default below. Queue the
    // mount fetch with ``mockResolvedValueOnce`` instead.
    listWatchedFoldersMock.mockResolvedValueOnce({
      text: "",
      data: {
        folders: [makeEntry({ path: "/p/A", domain: "research" })],
      },
      isError: false,
    });
    listWatchedFoldersMock.mockResolvedValue({
      text: "",
      data: { folders: [] },
      isError: false,
    });
    resyncFolderMock.mockResolvedValue({
      text: "",
      data: {
        status: "resynced",
        folder: "/p/A",
        summary: {
          updated: 4,
          no_change: 138,
          newly_orphaned: 2,
          restored_from_orphan: 1,
        },
      },
      isError: false,
    });
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("watched-folder-resync-/p/A"));
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Resync complete.");
      expect(toasts[0].variant).toBe("success");
      // All four summary counts must surface in the message.
      expect(toasts[0].msg).toContain("4 updated");
      expect(toasts[0].msg).toContain("138 unchanged");
      expect(toasts[0].msg).toContain("2 newly orphaned");
      expect(toasts[0].msg).toContain("1 restored");
    });
  });

  test("Resync failure pushes a danger toast with the error message", async () => {
    const user = userEvent.setup();
    primeListResolved([makeEntry({ path: "/p/A", domain: "research" })]);
    resyncFolderMock.mockRejectedValue(new Error("source unreachable"));
    render(<PanelWatchedFolders />);
    await waitFor(() =>
      expect(screen.getByTestId("watched-folder-row")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("watched-folder-resync-/p/A"));
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Resync failed.");
      expect(toasts[0].msg).toBe("source unreachable");
      expect(toasts[0].variant).toBe("danger");
    });
    // After the failure the spinner clears (finally arm runs).
    await waitFor(() => {
      const btn = screen.getByTestId("watched-folder-resync-/p/A");
      expect(btn).not.toBeDisabled();
      expect(btn).toHaveTextContent("Resync now");
    });
  });
});
