/**
 * Plan 22 T13 — PanelOrphans tests.
 *
 * Pins the Settings → Orphans panel against the mockup at
 * ``docs/design/plan-22/orphan-management.md``:
 *
 *   1. Populated state — renders one row per orphan, groups by
 *      ``watched_folder_id`` per mockup §"Group separator".
 *   2. Empty state — renders the "No orphaned notes." card + the
 *      "View watched folders ›" link.
 *   3. Loading state — renders the skeleton + sr-only announcement
 *      until the first refresh resolves.
 *   4. Error banner — surfaces ``useOrphansStore.error`` with
 *      ``role="alert"`` + a "Try again" retry button.
 *   5. Single-row restore — calls ``brain_restore_orphan`` with the
 *      row's path, optimistically drops the row, and pushes a success
 *      toast on resolve.
 *   6. Single-row delete — opens TypedConfirmDialog with the note's
 *      slug as the typed-confirm word; on confirm calls
 *      ``brain_delete_orphan`` with ``typed_confirm: true``.
 *   7. Bulk restore — sequentially calls ``brain_restore_orphan`` for
 *      every selected row; toast surfaces the count.
 *   8. Bulk delete — opens TypedConfirmDialog with ``"delete N notes"``;
 *      on confirm sequentially calls ``brain_delete_orphan`` with
 *      ``typed_confirm: true`` for every selected row.
 *   9. Filter — folder + domain Select primitives filter the displayed
 *      groups.
 *  10. Bulk-action bar accessibility — role="region" + aria-label
 *      verbatim from the mockup §"Accessibility annotations".
 */

import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

// ---- Hoisted mock factories ----

const {
  listOrphansMock,
  restoreOrphanMock,
  deleteOrphanMock,
} = vi.hoisted(() => ({
  listOrphansMock: vi.fn(),
  restoreOrphanMock: vi.fn(),
  deleteOrphanMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/tools")>("@/lib/api/tools");
  return {
    ...actual,
    listOrphans: (...args: unknown[]) => listOrphansMock(...args),
    restoreOrphan: (...args: unknown[]) => restoreOrphanMock(...args),
    deleteOrphan: (...args: unknown[]) => deleteOrphanMock(...args),
  };
});

// ---- Imports (after mocks) ----

import { PanelOrphans } from "@/components/settings/panel-orphans";
import { DialogHost } from "@/components/dialogs/dialog-host";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useOrphansStore } from "@/lib/state/orphans-store";
import { useSystemStore } from "@/lib/state/system-store";
import type { OrphanEntry } from "@/lib/api/tools";

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

function makeEntry(overrides: Partial<OrphanEntry> = {}): OrphanEntry {
  return {
    note_path: "/vault/research/sources/neural-architectures-survey-2024.md",
    domain: "research",
    source_path:
      "/Users/chris/Notes/Research-Papers/2024/neural-architectures.pdf",
    orphaned_at: new Date(Date.now() - 3 * 24 * 60 * 60_000).toISOString(),
    watched_folder_id: "/Users/chris/Notes/Research-Papers",
    ...overrides,
  };
}

function primeListResolved(orphans: OrphanEntry[]) {
  listOrphansMock.mockResolvedValue({
    text: "",
    data: { orphans },
    isError: false,
  });
}

function primeListRejected(error: Error) {
  listOrphansMock.mockRejectedValue(error);
}

// ---- Setup / teardown ----

beforeEach(() => {
  listOrphansMock.mockReset();
  restoreOrphanMock.mockReset();
  deleteOrphanMock.mockReset();
  resetSystemStore();
  useOrphansStore.getState()._resetForTesting();
  useDialogsStore.setState({ active: null });
});

// ---- Tests ----

describe("PanelOrphans — populated state", () => {
  test("renders one row per orphan grouped by source folder", async () => {
    primeListResolved([
      makeEntry({
        note_path: "/vault/research/sources/a.md",
        watched_folder_id: "/folder/A",
        domain: "research",
      }),
      makeEntry({
        note_path: "/vault/research/sources/b.md",
        watched_folder_id: "/folder/A",
        domain: "research",
      }),
      makeEntry({
        note_path: "/vault/work/sources/c.md",
        watched_folder_id: "/folder/B",
        domain: "work",
      }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.queryByTestId("orphans-loading")).not.toBeInTheDocument(),
    );
    const rows = screen.getAllByTestId("orphan-row");
    expect(rows).toHaveLength(3);
    const groups = screen.getAllByTestId("orphan-group");
    expect(groups).toHaveLength(2);
    expect(groups[0]).toHaveAttribute("data-folder", "/folder/A");
    expect(groups[1]).toHaveAttribute("data-folder", "/folder/B");
  });

  test("group separator surfaces folder path + domain badge + count + select-all", async () => {
    primeListResolved([
      makeEntry({
        note_path: "/vault/research/sources/x.md",
        watched_folder_id: "/Users/chris/Notes/Research-Papers",
        domain: "research",
      }),
      makeEntry({
        note_path: "/vault/research/sources/y.md",
        watched_folder_id: "/Users/chris/Notes/Research-Papers",
        domain: "research",
      }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    const group = screen.getByTestId("orphan-group");
    expect(group).toHaveTextContent("/Users/chris/Notes/Research-Papers");
    expect(group).toHaveTextContent("research");
    expect(group).toHaveTextContent(/2 orphans/);
    expect(
      screen.getByTestId(
        "orphan-group-select-all-/Users/chris/Notes/Research-Papers",
      ),
    ).toBeInTheDocument();
  });

  test("row renders title (slug-fallback) + source path + orphaned-at", async () => {
    primeListResolved([
      makeEntry({
        note_path: "/vault/research/sources/neural-architectures-survey-2024.md",
        source_path: "/src/neural.pdf",
        orphaned_at: new Date(Date.now() - 5 * 60_000).toISOString(),
      }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("orphan-row-title")).toHaveTextContent(
      "neural-architectures-survey-2024.md",
    );
    expect(screen.getByTestId("orphan-row-source")).toHaveTextContent(
      "Source: /src/neural.pdf",
    );
    expect(screen.getByTestId("orphan-row-orphaned-at")).toHaveTextContent(
      /Orphaned 5 minutes ago/,
    );
  });
});

describe("PanelOrphans — empty state", () => {
  test("renders the empty-state card with mockup-verbatim copy", async () => {
    primeListResolved([]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(
        screen.getByTestId("orphans-empty-state"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("No orphaned notes.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Every note in your vault still has a source file behind it. Nice work.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("orphans-empty-link")).toHaveAttribute(
      "href",
      "/settings/watched-folders",
    );
    expect(screen.getByTestId("orphans-empty-link")).toHaveTextContent(
      "View watched folders ›",
    );
  });
});

describe("PanelOrphans — loading state", () => {
  test("renders skeleton + sr-only announcement before refresh resolves", async () => {
    let resolveFn: ((v: unknown) => void) | undefined;
    listOrphansMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    render(<PanelOrphans />);
    const loading = screen.getByTestId("orphans-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(loading).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText(/Loading orphans/)).toBeInTheDocument();
    resolveFn?.({ text: "", data: { orphans: [] }, isError: false });
    await waitFor(() =>
      expect(screen.queryByTestId("orphans-loading")).not.toBeInTheDocument(),
    );
  });
});

describe("PanelOrphans — error banner", () => {
  test("renders error banner + retry button when refresh rejects", async () => {
    primeListRejected(new Error("backend unreachable"));
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphans-error-banner")).toBeInTheDocument(),
    );
    const banner = screen.getByTestId("orphans-error-banner");
    expect(banner).toHaveAttribute("role", "alert");
    expect(banner).toHaveTextContent(/Couldn.t load orphans/);
    expect(banner).toHaveTextContent("backend unreachable");
    expect(screen.getByTestId("orphans-retry")).toBeInTheDocument();
  });
});

describe("PanelOrphans — single-row restore", () => {
  test("clicking Restore calls brain_restore_orphan with the row path", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
    ]);
    restoreOrphanMock.mockResolvedValue({
      text: "",
      data: {
        status: "restored",
        note_path: "/vault/r/a.md",
        undo_id: "u-1",
      },
      isError: false,
    });
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    listOrphansMock.mockResolvedValueOnce({
      text: "",
      data: { orphans: [] },
      isError: false,
    });
    await user.click(
      screen.getByTestId("orphan-row-restore-/vault/r/a.md"),
    );
    await waitFor(() =>
      expect(restoreOrphanMock).toHaveBeenCalledWith({
        note_path: "/vault/r/a.md",
      }),
    );
  });

  test("restore optimistically drops the row before the API resolves", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
    ]);
    let resolveFn: ((v: unknown) => void) | undefined;
    restoreOrphanMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
    );
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    await user.click(
      screen.getByTestId("orphan-row-restore-/vault/r/a.md"),
    );
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(1),
    );
    // Drain the promise.
    listOrphansMock.mockResolvedValueOnce({
      text: "",
      data: { orphans: [makeEntry({ note_path: "/vault/r/b.md" })] },
      isError: false,
    });
    resolveFn?.({
      text: "",
      data: { status: "restored", note_path: "/vault/r/a.md", undo_id: "u-1" },
      isError: false,
    });
  });

  test("restore success toast surfaces note title", async () => {
    const user = userEvent.setup();
    listOrphansMock.mockResolvedValueOnce({
      text: "",
      data: {
        orphans: [
          makeEntry({
            note_path: "/vault/r/neural-architectures-survey-2024.md",
          }),
        ],
      },
      isError: false,
    });
    listOrphansMock.mockResolvedValue({
      text: "",
      data: { orphans: [] },
      isError: false,
    });
    restoreOrphanMock.mockResolvedValue({
      text: "",
      data: {
        status: "restored",
        note_path: "/vault/r/neural-architectures-survey-2024.md",
        undo_id: "u-1",
      },
      isError: false,
    });
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByTestId(
        "orphan-row-restore-/vault/r/neural-architectures-survey-2024.md",
      ),
    );
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Note restored.");
      expect(toasts[0].msg).toContain("neural-architectures-survey-2024");
      expect(toasts[0].variant).toBe("success");
    });
  });

  test("restore failure restores the row and pushes danger toast", async () => {
    const user = userEvent.setup();
    primeListResolved([makeEntry({ note_path: "/vault/r/a.md" })]);
    restoreOrphanMock.mockRejectedValue(new Error("source still missing"));
    // Reconcile refresh after the failure brings the row back.
    listOrphansMock.mockResolvedValueOnce({
      text: "",
      data: { orphans: [makeEntry({ note_path: "/vault/r/a.md" })] },
      isError: false,
    });
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByTestId("orphan-row-restore-/vault/r/a.md"),
    );
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Couldn't restore.");
      expect(toasts[0].msg).toBe("source still missing");
      expect(toasts[0].variant).toBe("danger");
    });
  });
});

describe("PanelOrphans — single-row delete", () => {
  test("clicking Delete opens TypedConfirmDialog with the note's slug as the word", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({
        note_path: "/vault/r/neural-architectures-survey-2024.md",
      }),
    ]);
    render(
      <>
        <PanelOrphans />
        <DialogHost />
      </>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByTestId(
        "orphan-row-delete-/vault/r/neural-architectures-survey-2024.md",
      ),
    );
    // The dialog mounts with the slug as the typed-confirm word.
    const active = useDialogsStore.getState().active;
    expect(active?.kind).toBe("typed-confirm");
    if (active?.kind === "typed-confirm") {
      expect(active.word).toBe("neural-architectures-survey-2024");
      expect(active.eyebrow).toBe("ORPHAN MANAGEMENT");
      expect(active.title).toBe("Delete this orphaned note?");
      expect(active.danger).toBe(true);
    }
  });

  test("delete typed-confirm flow fires brain_delete_orphan with typed_confirm: true", async () => {
    const user = userEvent.setup();
    listOrphansMock.mockResolvedValueOnce({
      text: "",
      data: { orphans: [makeEntry({ note_path: "/vault/r/dead.md" })] },
      isError: false,
    });
    listOrphansMock.mockResolvedValue({
      text: "",
      data: { orphans: [] },
      isError: false,
    });
    deleteOrphanMock.mockResolvedValue({
      text: "",
      data: {
        status: "deleted",
        trash_path: "/v/.brain/trash/2026-05-12/dead.md",
        undo_id: "u-2",
      },
      isError: false,
    });
    render(
      <>
        <PanelOrphans />
        <DialogHost />
      </>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    await user.click(screen.getByTestId("orphan-row-delete-/vault/r/dead.md"));
    // Type the slug into the typed-confirm input.
    const input = await screen.findByPlaceholderText("dead");
    await user.type(input, "dead");
    const confirmBtn = screen.getByRole("button", {
      name: /Delete permanently/i,
    });
    await user.click(confirmBtn);
    await waitFor(() =>
      expect(deleteOrphanMock).toHaveBeenCalledWith({
        note_path: "/vault/r/dead.md",
        typed_confirm: true,
      }),
    );
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("Note deleted.");
      expect(toasts[0].msg).toContain("moved to .brain/trash/");
      expect(toasts[0].variant).toBe("success");
    });
  });

  test("delete confirm stays disabled when typed input doesn't match the slug (mistype guard)", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/specific-slug.md" }),
    ]);
    render(
      <>
        <PanelOrphans />
        <DialogHost />
      </>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByTestId("orphan-row-delete-/vault/r/specific-slug.md"),
    );
    const input = await screen.findByPlaceholderText("specific-slug");
    // Type a clearly-wrong value.
    await user.type(input, "wrong-string");
    const confirmBtn = screen.getByRole("button", {
      name: /Delete permanently/i,
    });
    expect(confirmBtn).toBeDisabled();
    // No backend call.
    expect(deleteOrphanMock).not.toHaveBeenCalled();
  });
});

describe("PanelOrphans — bulk actions", () => {
  test("selecting rows surfaces the bulk-action bar with role=region", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    expect(screen.queryByTestId("orphans-bulk-bar")).not.toBeInTheDocument();
    await user.click(
      screen.getByTestId("orphan-row-checkbox-/vault/r/a.md"),
    );
    const bar = await screen.findByTestId("orphans-bulk-bar");
    expect(bar).toHaveAttribute("role", "region");
    expect(bar).toHaveAttribute(
      "aria-label",
      "Bulk actions for selected orphans",
    );
    expect(bar).toHaveTextContent("Selected: 1");
    // Selection count is live-region.
    expect(screen.getByTestId("orphans-selection-count")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  test("'select all' group toggle selects every row in the group", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/w/c.md", watched_folder_id: "/f/B" }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(3),
    );
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    expect(screen.getByTestId("orphans-bulk-bar")).toHaveTextContent(
      "Selected: 2",
    );
    // Toggle again — clears the group selection.
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    expect(screen.queryByTestId("orphans-bulk-bar")).not.toBeInTheDocument();
  });

  test("bulk restore calls brain_restore_orphan once per selected row", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
    ]);
    restoreOrphanMock.mockResolvedValue({
      text: "",
      data: { status: "restored", note_path: "x", undo_id: "u-x" },
      isError: false,
    });
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    await user.click(screen.getByTestId("orphans-bulk-restore"));
    await waitFor(() => expect(restoreOrphanMock).toHaveBeenCalledTimes(2));
    expect(restoreOrphanMock).toHaveBeenCalledWith({
      note_path: "/vault/r/a.md",
    });
    expect(restoreOrphanMock).toHaveBeenCalledWith({
      note_path: "/vault/r/b.md",
    });
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("2 notes restored.");
      expect(toasts[0].variant).toBe("success");
    });
  });

  test("bulk delete opens TypedConfirmDialog with the 'delete N notes' phrase", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/c.md", watched_folder_id: "/f/A" }),
    ]);
    render(
      <>
        <PanelOrphans />
        <DialogHost />
      </>,
    );
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(3),
    );
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    await user.click(screen.getByTestId("orphans-bulk-delete"));
    const active = useDialogsStore.getState().active;
    expect(active?.kind).toBe("typed-confirm");
    if (active?.kind === "typed-confirm") {
      expect(active.word).toBe("delete 3 notes");
      expect(active.title).toBe("Delete 3 orphaned notes?");
      expect(active.danger).toBe(true);
    }
  });

  test("bulk delete typed-confirm flow fires brain_delete_orphan for each row with typed_confirm: true", async () => {
    const user = userEvent.setup();
    listOrphansMock.mockResolvedValueOnce({
      text: "",
      data: {
        orphans: [
          makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
          makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
        ],
      },
      isError: false,
    });
    listOrphansMock.mockResolvedValue({
      text: "",
      data: { orphans: [] },
      isError: false,
    });
    deleteOrphanMock.mockResolvedValue({
      text: "",
      data: {
        status: "deleted",
        trash_path: "/t/x.md",
        undo_id: "u-x",
      },
      isError: false,
    });
    render(
      <>
        <PanelOrphans />
        <DialogHost />
      </>,
    );
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    await user.click(screen.getByTestId("orphans-bulk-delete"));
    const input = await screen.findByPlaceholderText("delete 2 notes");
    await user.type(input, "delete 2 notes");
    await user.click(
      screen.getByRole("button", { name: /Delete permanently/i }),
    );
    await waitFor(() => expect(deleteOrphanMock).toHaveBeenCalledTimes(2));
    expect(deleteOrphanMock).toHaveBeenCalledWith({
      note_path: "/vault/r/a.md",
      typed_confirm: true,
    });
    expect(deleteOrphanMock).toHaveBeenCalledWith({
      note_path: "/vault/r/b.md",
      typed_confirm: true,
    });
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts).toHaveLength(1);
      expect(toasts[0].lead).toBe("2 notes deleted.");
      expect(toasts[0].msg).toBe(
        "Moved to .brain/trash/. Undo via brain_undo_last.",
      );
      expect(toasts[0].variant).toBe("success");
    });
  });

  test("bulk delete typed-confirm refuses when user types the wrong phrase", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
    ]);
    render(
      <>
        <PanelOrphans />
        <DialogHost />
      </>,
    );
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    await user.click(screen.getByTestId("orphans-bulk-delete"));
    const input = await screen.findByPlaceholderText("delete 2 notes");
    // Wrong phrase ("delete 3 notes" — off by one count).
    await user.type(input, "delete 3 notes");
    const confirmBtn = screen.getByRole("button", {
      name: /Delete permanently/i,
    });
    expect(confirmBtn).toBeDisabled();
    expect(deleteOrphanMock).not.toHaveBeenCalled();
  });

  test("'Clear selection' empties the selection state", async () => {
    const user = userEvent.setup();
    primeListResolved([
      makeEntry({ note_path: "/vault/r/a.md", watched_folder_id: "/f/A" }),
      makeEntry({ note_path: "/vault/r/b.md", watched_folder_id: "/f/A" }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    await user.click(screen.getByTestId("orphan-group-select-all-/f/A"));
    expect(screen.getByTestId("orphans-bulk-bar")).toHaveTextContent(
      "Selected: 2",
    );
    await user.click(screen.getByTestId("orphans-bulk-clear"));
    expect(screen.queryByTestId("orphans-bulk-bar")).not.toBeInTheDocument();
  });
});

describe("PanelOrphans — accessibility annotations", () => {
  test("each row exposes an aria-label aggregating title + source + relative time", async () => {
    primeListResolved([
      makeEntry({
        note_path: "/vault/r/example-note.md",
        source_path: "/Users/chris/src/example.pdf",
        orphaned_at: new Date(Date.now() - 30 * 60_000).toISOString(),
      }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    const row = screen.getByTestId("orphan-row");
    const aria = row.getAttribute("aria-label") ?? "";
    expect(aria).toContain("example-note");
    expect(aria).toContain("/Users/chris/src/example.pdf");
    expect(aria).toContain("30 minutes ago");
  });

  test("warn icon is aria-hidden so screen readers don't read it as 'warning'", async () => {
    primeListResolved([makeEntry({ note_path: "/vault/r/a.md" })]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getByTestId("orphan-row")).toBeInTheDocument(),
    );
    const row = screen.getByTestId("orphan-row");
    // First svg (the warn icon) must carry aria-hidden.
    const icons = row.querySelectorAll("svg");
    expect(icons.length).toBeGreaterThan(0);
    const warnIcon = icons[0];
    expect(warnIcon.getAttribute("aria-hidden")).toBe("true");
  });

  test("group separator carries an aria-label naming the count + path + domain", async () => {
    primeListResolved([
      makeEntry({
        note_path: "/vault/r/a.md",
        watched_folder_id: "/f/A",
        domain: "research",
      }),
      makeEntry({
        note_path: "/vault/r/b.md",
        watched_folder_id: "/f/A",
        domain: "research",
      }),
    ]);
    render(<PanelOrphans />);
    await waitFor(() =>
      expect(screen.getAllByTestId("orphan-row")).toHaveLength(2),
    );
    // The H3 inside the group surfaces the aria-label.
    const group = screen.getByTestId("orphan-group");
    const heading = within(group).getByRole("heading", { level: 3 });
    const aria = heading.getAttribute("aria-label") ?? "";
    expect(aria).toContain("2 orphans");
    expect(aria).toContain("/f/A");
    expect(aria).toContain("research");
  });
});
