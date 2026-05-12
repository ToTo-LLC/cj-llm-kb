import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * Plan 22 T15 — Watch-enable / watch-disable / orphan-delete modals
 * + Bulk Import → Watch CTA bridge.
 *
 * Three modal surfaces + one cross-surface bridge:
 *
 *   1. WatchEnableModal — fires dry-run on mount, shows cost panel,
 *      renders D1 overwrite-contract callout verbatim, fires real-run
 *      on confirm with toast + close + store refresh.
 *   2. WatchDisableModal — renders stays/changes lists, optional
 *      orphan-count info-line, fires unwatch on confirm with toast.
 *   3. OrphanDeleteModal (via builders + TypedConfirmDialog headerSlot
 *      extension) — single-note slug typed-confirm; bulk "delete N
 *      notes" phrase typed-confirm; header card with warn icon and
 *      filename / source paths.
 *   4. Bulk Import → Watch CTA — apply-complete screen renders the
 *      "Watch this folder for changes" button when the import succeeded;
 *      click opens watch-enable-modal pre-filled.
 *
 * All API helpers are mocked (matching the panel-watched-folders test
 * factory pattern). The dialogs are rendered through ``DialogHost``
 * so the watch-enable / watch-disable kinds get exercised end-to-end
 * via ``useDialogsStore.open()``.
 */

// ---------- Hoisted mocks (Plan 17 T17 monkeypatch-binding lesson:
//             route through the resolved-at-call-time namespace by
//             intercepting the named exports of @/lib/api/tools) ----------

const {
  watchFolderMock,
  unwatchFolderMock,
  listDomainsMock,
  listWatchedFoldersMock,
} = vi.hoisted(() => ({
  watchFolderMock: vi.fn(),
  unwatchFolderMock: vi.fn(),
  listDomainsMock: vi.fn(),
  listWatchedFoldersMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/tools")>(
      "@/lib/api/tools",
    );
  return {
    ...actual,
    watchFolder: (...args: unknown[]) => watchFolderMock(...args),
    unwatchFolder: (...args: unknown[]) => unwatchFolderMock(...args),
    listDomains: (...args: unknown[]) => listDomainsMock(...args),
    listWatchedFolders: (...args: unknown[]) =>
      listWatchedFoldersMock(...args),
  };
});

// ---------- Imports (after mocks) ----------

import { DialogHost } from "@/components/dialogs/dialog-host";
import { TypedConfirmDialog } from "@/components/dialogs/typed-confirm-dialog";
import { WatchDisableModal } from "@/components/dialogs/watch-disable-modal";
import { WatchEnableModal } from "@/components/dialogs/watch-enable-modal";
import {
  buildBulkOrphanDeleteDialog,
  buildSingleOrphanDeleteDialog,
  slugFromNotePath,
} from "@/components/dialogs/orphan-delete-modal";
import { StepApply } from "@/components/bulk/step-apply";
import { useBulkStore } from "@/lib/state/bulk-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useDomainsStore } from "@/lib/state/domains-store";
import { _setDomainsCacheForTesting } from "@/lib/hooks/use-domains";
import { useSystemStore } from "@/lib/state/system-store";
import { useWatchedFoldersStore } from "@/lib/state/watched-folders-store";
import type {
  OrphanEntry,
  WatchedFolderEntry,
} from "@/lib/api/tools";

// ---------- Helpers ----------

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

function primeDomains() {
  listDomainsMock.mockResolvedValue({
    text: "",
    data: { domains: ["research", "work", "personal"] },
    isError: false,
  });
}

function makeWatchedEntry(
  overrides: Partial<WatchedFolderEntry> = {},
): WatchedFolderEntry {
  return {
    path: "/Users/test/Notes/Research-Papers",
    domain: "research",
    enabled: true,
    last_sync: null,
    policy: "overwrite",
    include_subdirs: true,
    file_count: 0,
    orphan_count: 0,
    ...overrides,
  };
}

function makeOrphan(overrides: Partial<OrphanEntry> = {}): OrphanEntry {
  return {
    note_path:
      "/Users/test/Documents/brain/research/neural-architectures-survey-2024.md",
    domain: "research",
    source_path:
      "/Users/test/Notes/Research-Papers/2024/neural-architectures.pdf",
    orphaned_at: new Date(Date.now() - 60 * 60_000).toISOString(),
    watched_folder_id: "/Users/test/Notes/Research-Papers",
    ...overrides,
  };
}

// ---------- Setup / teardown ----------

beforeEach(() => {
  watchFolderMock.mockReset();
  unwatchFolderMock.mockReset();
  listDomainsMock.mockReset();
  listWatchedFoldersMock.mockReset();
  resetSystemStore();
  useDialogsStore.getState().close();
  useWatchedFoldersStore.getState()._resetForTesting();
  useDomainsStore.getState()._resetForTesting();
  useBulkStore.getState().reset();
  primeDomains();
  // Default mock for the watched-folders store auto-refresh that fires
  // when the watch-enable modal mounts and triggers a re-render of the
  // host panel. Tests that need a specific shape override per-case.
  listWatchedFoldersMock.mockResolvedValue({
    text: "",
    data: { folders: [] },
    isError: false,
  });
});

// =========================================================================
// 1. WatchEnableModal
// =========================================================================

describe("WatchEnableModal — Plan 22 T15 §1", () => {
  test("renders eyebrow + title + D1 callout verbatim", async () => {
    render(<WatchEnableModal onClose={vi.fn()} />);
    await screen.findByRole("dialog");
    // Eyebrow.
    expect(screen.getByText(/WATCHED FOLDERS/)).toBeInTheDocument();
    // Title.
    expect(
      screen.getByRole("heading", { name: /watch this folder for changes/i }),
    ).toBeInTheDocument();
    // D1 callout — VERBATIM from mockup §"D1 contract paragraph".
    const callout = screen.getByTestId("watch-enable-d1-callout");
    expect(callout).toHaveTextContent(
      /Heads-up:\s*the source file is the source of truth/i,
    );
    expect(callout).toHaveTextContent(
      /your edits will be overwritten the next time the source file changes/i,
    );
    expect(callout).toHaveTextContent(
      /Deleting a source file marks its note as an orphan in your vault/i,
    );
    expect(callout).toHaveTextContent(/isn.t deleted/i);
    expect(callout).toHaveTextContent(
      /You can review orphans in Settings → Orphans/,
    );
  });

  test("does not fire dry-run when folder is empty (Settings entry)", async () => {
    render(<WatchEnableModal onClose={vi.fn()} />);
    await screen.findByRole("dialog");
    // Folder input is empty; cost panel should NOT render and no dry-run
    // call should fire.
    expect(
      screen.queryByTestId("watch-enable-cost-panel"),
    ).not.toBeInTheDocument();
    expect(watchFolderMock).not.toHaveBeenCalled();
  });

  test("pre-filled folder + domain fires dry-run on mount and renders cost panel", async () => {
    watchFolderMock.mockResolvedValue({
      text: "",
      data: {
        status: "dry_run",
        folder: "/p/A",
        domain: "research",
        initial_sync_summary: null,
        cost_estimate: {
          file_count: 142,
          estimated_tokens: 14200,
          estimated_usd: 0.18,
          classify_model: "claude-haiku-4-5",
        },
      },
      isError: false,
    });
    render(
      <WatchEnableModal
        prefilledFolder="/p/A"
        prefilledDomain="research"
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(watchFolderMock).toHaveBeenCalled();
    });
    expect(watchFolderMock).toHaveBeenCalledWith({
      folder: "/p/A",
      domain: "research",
      include_subdirs: true,
      initial_sync: true,
      dry_run: true,
    });
    // Cost body renders per mockup §microcopy line 160.
    await waitFor(() => {
      expect(
        screen.getByTestId("watch-enable-cost-body"),
      ).toHaveTextContent(/142 files found · estimated cost ~\$0\.18/);
    });
    // Eyebrow + title switch to BULK IMPORT → WATCH variant when
    // prefilledFolder is set (mockup §"State 5").
    expect(screen.getByText("BULK IMPORT → WATCH")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: /watch this folder for ongoing changes/i,
      }),
    ).toBeInTheDocument();
  });

  test("dry-run error renders inline retry without blocking confirm", async () => {
    watchFolderMock.mockRejectedValueOnce(new Error("backend down"));
    render(
      <WatchEnableModal prefilledFolder="/p/A" onClose={vi.fn()} />,
    );
    await waitFor(() => {
      expect(
        screen.getByTestId("watch-enable-cost-error"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("watch-enable-cost-error"),
    ).toHaveTextContent(/Couldn.t estimate cost/);
    // Confirm button is NOT disabled by an estimate error (mockup §"State 4").
    const confirm = screen.getByTestId("watch-enable-confirm");
    expect(confirm).not.toBeDisabled();
  });

  test("already-watched dry-run surfaces inline validation + disables confirm", async () => {
    watchFolderMock.mockResolvedValueOnce({
      text: "",
      data: {
        status: "already_watched",
        folder: "/p/A",
        domain: "research",
        initial_sync_summary: null,
        cost_estimate: null,
      },
      isError: false,
    });
    render(
      <WatchEnableModal prefilledFolder="/p/A" onClose={vi.fn()} />,
    );
    await waitFor(() => {
      expect(
        screen.getByTestId("watch-enable-already-watched"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("watch-enable-already-watched"),
    ).toHaveTextContent(/already being watched/);
    expect(screen.getByTestId("watch-enable-confirm")).toBeDisabled();
  });

  test("Confirm fires real-run with correct args, toasts, and closes", async () => {
    const user = userEvent.setup();
    // Dry-run + real-run both succeed; the modal first fires dry-run
    // on mount, then real-run on confirm click.
    watchFolderMock.mockResolvedValueOnce({
      text: "",
      data: {
        status: "dry_run",
        folder: "/p/A",
        domain: "research",
        initial_sync_summary: null,
        cost_estimate: {
          file_count: 5,
          estimated_tokens: 500,
          estimated_usd: 0.02,
          classify_model: "claude-haiku-4-5",
        },
      },
      isError: false,
    });
    watchFolderMock.mockResolvedValueOnce({
      text: "",
      data: {
        status: "watched",
        folder: "/p/A",
        domain: "research",
        initial_sync_summary: {
          planned: 5,
          applied: 5,
          skipped_duplicate: 0,
          failed: 0,
        },
        cost_estimate: {
          file_count: 5,
          estimated_tokens: 500,
          estimated_usd: 0.02,
          classify_model: "claude-haiku-4-5",
        },
      },
      isError: false,
    });
    const onClose = vi.fn();
    render(
      <WatchEnableModal
        prefilledFolder="/p/A"
        prefilledDomain="research"
        onClose={onClose}
      />,
    );
    // Wait for dry-run to land.
    await waitFor(() => {
      expect(
        screen.getByTestId("watch-enable-cost-body"),
      ).toBeInTheDocument();
    });
    // Click confirm — fires the second (real-run) call.
    await user.click(screen.getByTestId("watch-enable-confirm"));
    await waitFor(() => {
      expect(watchFolderMock).toHaveBeenCalledTimes(2);
    });
    // Second call is the real run.
    expect(watchFolderMock).toHaveBeenNthCalledWith(2, {
      folder: "/p/A",
      domain: "research",
      include_subdirs: true,
      initial_sync: true,
      dry_run: false,
    });
    // Success toast lands.
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(
        toasts.some((t) => /Watching A\.?/.test(t.lead)),
      ).toBe(true);
    });
    // onClose fired.
    expect(onClose).toHaveBeenCalled();
  });

  test("Cancel button closes without firing real-run", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<WatchEnableModal onClose={onClose} />);
    await user.click(screen.getByTestId("watch-enable-cancel"));
    expect(onClose).toHaveBeenCalled();
    // No real-run (no dry_run=false call).
    const realRunCalls = watchFolderMock.mock.calls.filter(
      (c) => (c[0] as { dry_run?: boolean })?.dry_run === false,
    );
    expect(realRunCalls).toHaveLength(0);
  });

  // -------------------------------------------------------------------
  // Plan 23 T2.a — activeDomain default
  // -------------------------------------------------------------------

  test("Plan 23 T2.a — defaults the domain dropdown to Config.active_domain (not domains[0])", async () => {
    // Seed the domains store as if the backend has resolved
    // ``Config.active_domain = "work"`` AND the domain list is
    // ``["research", "work", "personal"]``. Pre-T2.a the modal would
    // default to ``domains[0]`` = ``"research"``; T2.a fixes it to
    // honor the user's active scope. Use ``work`` (not the alphabetical
    // first entry) so the assertion proves the new behavior — if the
    // implementation regresses to ``domains[0]``, the trigger would
    // read ``research`` and the test fails RED.
    _setDomainsCacheForTesting(
      [
        {
          slug: "research",
          label: "Research",
          accent: "var(--dom-research)",
          configured: true,
          on_disk: true,
        },
        {
          slug: "work",
          label: "Work",
          accent: "var(--dom-work)",
          configured: true,
          on_disk: true,
        },
        {
          slug: "personal",
          label: "Personal",
          accent: "var(--dom-personal)",
          configured: true,
          on_disk: true,
        },
      ],
      "work",
    );

    render(<WatchEnableModal onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    // The Select trigger's accessible-name text reflects the current
    // value (the SelectValue placeholder is replaced once a value is
    // set). Reading the trigger by testid keeps the assertion stable
    // against future markup tweaks in shadcn/ui's Select.
    const trigger = screen.getByTestId("watch-enable-domain-select");
    expect(trigger).toHaveTextContent("work");
    expect(trigger).not.toHaveTextContent(/^research$/);
  });

  test("Plan 23 T2.a — falls back to domains[0] when activeDomain is empty (defensive)", async () => {
    // Empty ``activeDomain`` is the pre-Plan-11-T6 backend shape AND
    // the pre-store-hydration state. Pin the defensive fallback so a
    // future refactor that drops the ``|| domains[0]`` arm fails RED.
    _setDomainsCacheForTesting(
      [
        {
          slug: "research",
          label: "Research",
          accent: "var(--dom-research)",
          configured: true,
          on_disk: true,
        },
        {
          slug: "work",
          label: "Work",
          accent: "var(--dom-work)",
          configured: true,
          on_disk: true,
        },
      ],
      "", // empty active_domain — defensive fallback path
    );

    render(<WatchEnableModal onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    const trigger = screen.getByTestId("watch-enable-domain-select");
    expect(trigger).toHaveTextContent("research");
  });

  test("Plan 23 T2.a — prefilledDomain overrides activeDomain default", async () => {
    // Bulk Import → Watch bridge (D6) passes ``prefilledDomain`` so the
    // user lands on the domain they already picked for the bulk import.
    // T2.a's activeDomain default must not override this — the prop is
    // an explicit caller intent.
    _setDomainsCacheForTesting(
      [
        {
          slug: "research",
          label: "Research",
          accent: "var(--dom-research)",
          configured: true,
          on_disk: true,
        },
        {
          slug: "work",
          label: "Work",
          accent: "var(--dom-work)",
          configured: true,
          on_disk: true,
        },
        {
          slug: "personal",
          label: "Personal",
          accent: "var(--dom-personal)",
          configured: true,
          on_disk: true,
        },
      ],
      "work", // activeDomain = work
    );

    render(
      <WatchEnableModal
        prefilledFolder="/p/A"
        prefilledDomain="personal" // explicit caller intent
        onClose={vi.fn()}
      />,
    );
    await screen.findByRole("dialog");

    const trigger = screen.getByTestId("watch-enable-domain-select");
    expect(trigger).toHaveTextContent("personal");
  });
});

// =========================================================================
// 2. WatchDisableModal
// =========================================================================

describe("WatchDisableModal — Plan 22 T15 §2", () => {
  test("renders mockup-verbatim stays/changes lists + path display", async () => {
    const folder = makeWatchedEntry({ path: "/p/A", orphan_count: 0 });
    render(<WatchDisableModal folder={folder} onClose={vi.fn()} />);
    await screen.findByRole("dialog");
    expect(screen.getByText(/WATCHED FOLDERS/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /stop watching this folder\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("watch-disable-path")).toHaveTextContent("/p/A");
    // "Stays" list — 3 bullets, exact strings.
    const stays = screen.getByTestId("watch-disable-stays-list");
    expect(stays).toHaveTextContent(
      /Existing notes from this folder stay in your knowledge base/,
    );
    expect(stays).toHaveTextContent(
      /Notes already marked as orphans stay marked/,
    );
    expect(stays).toHaveTextContent(
      /You can start watching this folder again any time/,
    );
    // "Changes" list — 2 bullets.
    const changes = screen.getByTestId("watch-disable-changes-list");
    expect(changes).toHaveTextContent(
      /New or edited source files won.t sync/,
    );
    expect(changes).toHaveTextContent(
      /Deleted source files won.t mark new orphans/,
    );
  });

  test("orphan-count info-line ONLY renders when > 0", async () => {
    const folder = makeWatchedEntry({ orphan_count: 3 });
    render(<WatchDisableModal folder={folder} onClose={vi.fn()} />);
    await screen.findByRole("dialog");
    const note = screen.getByTestId("watch-disable-orphan-note");
    expect(note).toHaveTextContent(/3 orphans from earlier deletions/);
  });

  test("orphan-count info-line OMITTED when orphan_count === 0", async () => {
    const folder = makeWatchedEntry({ orphan_count: 0 });
    render(<WatchDisableModal folder={folder} onClose={vi.fn()} />);
    await screen.findByRole("dialog");
    expect(
      screen.queryByTestId("watch-disable-orphan-note"),
    ).not.toBeInTheDocument();
  });

  test("Confirm fires unwatchFolder + toast + close", async () => {
    const user = userEvent.setup();
    unwatchFolderMock.mockResolvedValueOnce({
      text: "",
      data: {
        status: "unwatched",
        folder: "/p/A",
        remaining_notes: 12,
      },
      isError: false,
    });
    const folder = makeWatchedEntry({ path: "/p/A", orphan_count: 2 });
    const onClose = vi.fn();
    render(<WatchDisableModal folder={folder} onClose={onClose} />);
    await user.click(screen.getByTestId("watch-disable-confirm"));
    await waitFor(() => {
      expect(unwatchFolderMock).toHaveBeenCalledWith({ folder: "/p/A" });
    });
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts.some((t) => /Stopped watching A\.?/.test(t.lead))).toBe(
        true,
      );
      expect(
        toasts.some((t) => /2 orphans remain marked/.test(t.msg)),
      ).toBe(true);
    });
    expect(onClose).toHaveBeenCalled();
  });

  test("Cancel button closes without firing the unwatch API", async () => {
    const user = userEvent.setup();
    const folder = makeWatchedEntry();
    const onClose = vi.fn();
    render(<WatchDisableModal folder={folder} onClose={onClose} />);
    await user.click(screen.getByTestId("watch-disable-cancel"));
    expect(onClose).toHaveBeenCalled();
    expect(unwatchFolderMock).not.toHaveBeenCalled();
  });
});

// =========================================================================
// 3. Orphan delete modal (TypedConfirmDialog + headerSlot extension)
// =========================================================================

describe("Orphan delete modal — Plan 22 T15 §3", () => {
  test("slugFromNotePath strips folder + .md", () => {
    expect(
      slugFromNotePath("/Users/test/brain/research/foo-bar.md"),
    ).toBe("foo-bar");
    expect(slugFromNotePath("foo.md")).toBe("foo");
    expect(slugFromNotePath("no-ext")).toBe("no-ext");
  });

  test("Single-mode builder yields a typed-confirm DialogKind with header card", () => {
    const orphan = makeOrphan();
    const onConfirm = vi.fn();
    const kind = buildSingleOrphanDeleteDialog({ entry: orphan, onConfirm });
    expect(kind.kind).toBe("typed-confirm");
    if (kind.kind !== "typed-confirm") throw new Error("never");
    expect(kind.title).toBe("Delete this orphaned note?");
    expect(kind.eyebrow).toBe("ORPHAN MANAGEMENT");
    expect(kind.word).toBe("neural-architectures-survey-2024");
    expect(kind.danger).toBe(true);
    expect(kind.headerSlot).toBeTruthy();
  });

  test("Bulk-mode builder uses 'delete N notes' phrase + summary card", () => {
    const entries = [
      makeOrphan({ note_path: "/v/a.md" }),
      makeOrphan({ note_path: "/v/b.md" }),
      makeOrphan({ note_path: "/v/c.md" }),
    ];
    const kind = buildBulkOrphanDeleteDialog({
      entries,
      onConfirm: vi.fn(),
    });
    if (kind.kind !== "typed-confirm") throw new Error("never");
    expect(kind.title).toBe("Delete 3 orphaned notes?");
    expect(kind.word).toBe("delete 3 notes");
    expect(kind.danger).toBe(true);
    expect(kind.headerSlot).toBeTruthy();
  });

  test("Single-note dialog renders warn-icon card with slug + paths", async () => {
    const orphan = makeOrphan();
    const kind = buildSingleOrphanDeleteDialog({
      entry: orphan,
      onConfirm: vi.fn(),
    });
    if (kind.kind !== "typed-confirm") throw new Error("never");
    render(
      <TypedConfirmDialog
        {...kind}
        onClose={vi.fn()}
      />,
    );
    await screen.findByRole("dialog");
    expect(
      screen.getByTestId("orphan-delete-header-single"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("orphan-delete-note-title"),
    ).toHaveTextContent(/neural-architectures-survey-2024\.md/);
    expect(
      screen.getByTestId("orphan-delete-note-source"),
    ).toHaveTextContent(/no longer exists/);
  });

  test("Single-note typed-confirm gates the delete button until slug matches", async () => {
    const user = userEvent.setup();
    const orphan = makeOrphan();
    const onConfirm = vi.fn();
    const kind = buildSingleOrphanDeleteDialog({
      entry: orphan,
      onConfirm,
    });
    if (kind.kind !== "typed-confirm") throw new Error("never");
    render(<TypedConfirmDialog {...kind} onClose={vi.fn()} />);
    const button = screen.getByRole("button", { name: /delete permanently/i });
    expect(button).toBeDisabled();
    const input = screen.getByPlaceholderText(/neural-architectures/);
    await user.type(input, "wrong");
    expect(button).toBeDisabled();
    await user.clear(input);
    await user.type(input, "neural-architectures-survey-2024");
    expect(button).toBeEnabled();
    await user.click(button);
    expect(onConfirm).toHaveBeenCalled();
  });

  test("Bulk-mode summary card lists up to 5 slugs and shows '…and N more'", async () => {
    const entries = Array.from({ length: 7 }, (_, i) =>
      makeOrphan({ note_path: `/v/note-${i}.md` }),
    );
    const kind = buildBulkOrphanDeleteDialog({
      entries,
      onConfirm: vi.fn(),
    });
    if (kind.kind !== "typed-confirm") throw new Error("never");
    render(<TypedConfirmDialog {...kind} onClose={vi.fn()} />);
    await screen.findByRole("dialog");
    const list = screen.getByTestId("orphan-delete-bulk-list");
    // 5 displayed slugs + 1 overflow li = 6 children.
    expect(list.querySelectorAll("li")).toHaveLength(6);
    expect(
      screen.getByTestId("orphan-delete-bulk-overflow"),
    ).toHaveTextContent(/…and 2 more/);
  });
});

// =========================================================================
// 4. Bulk Import → Watch CTA bridge (D6)
// =========================================================================

describe("Bulk Import → Watch CTA — Plan 22 T15 / D6", () => {
  test("does NOT render when no folder is picked", () => {
    useBulkStore.setState({
      step: 4,
      done: true,
      applying: false,
      results: { applied: [], failed: [], quarantined: [] },
    });
    render(<StepApply />);
    expect(screen.queryByTestId("bulk-watch-cta")).not.toBeInTheDocument();
  });

  test("does NOT render when nothing was applied", () => {
    useBulkStore.setState({
      step: 4,
      done: true,
      applying: false,
      folder: { path: "/p/X", fileCount: 3, picked: "just now" },
      results: { applied: [], failed: ["a"], quarantined: [] },
    });
    render(<StepApply />);
    expect(screen.queryByTestId("bulk-watch-cta")).not.toBeInTheDocument();
  });

  test("renders + opens watch-enable modal pre-filled on click", async () => {
    const user = userEvent.setup();
    useBulkStore.setState({
      step: 4,
      done: true,
      applying: false,
      folder: { path: "/p/X", fileCount: 3, picked: "just now" },
      domain: "work",
      results: { applied: ["a", "b"], failed: [], quarantined: [] },
    });
    render(<StepApply />);
    const cta = screen.getByTestId("bulk-watch-cta");
    expect(cta).toHaveTextContent(/Watch this folder for changes/);
    await user.click(cta);
    // useDialogsStore.active now carries the prefilled watch-enable kind.
    const active = useDialogsStore.getState().active;
    expect(active?.kind).toBe("watch-enable");
    if (active?.kind === "watch-enable") {
      expect(active.prefilledFolder).toBe("/p/X");
      expect(active.prefilledDomain).toBe("work");
    }
  });

  test("auto-domain bulk imports do NOT pre-fill the modal's domain", async () => {
    const user = userEvent.setup();
    useBulkStore.setState({
      step: 4,
      done: true,
      applying: false,
      folder: { path: "/p/X", fileCount: 3, picked: "just now" },
      domain: "auto",
      results: { applied: ["a"], failed: [], quarantined: [] },
    });
    render(<StepApply />);
    await user.click(screen.getByTestId("bulk-watch-cta"));
    const active = useDialogsStore.getState().active;
    expect(active?.kind).toBe("watch-enable");
    if (active?.kind === "watch-enable") {
      expect(active.prefilledFolder).toBe("/p/X");
      expect(active.prefilledDomain).toBeUndefined();
    }
  });
});

// =========================================================================
// 5. DialogHost integration — watch-enable / watch-disable kinds
// =========================================================================

describe("DialogHost — watch-enable / watch-disable wire-up", () => {
  test("opening watch-enable via useDialogsStore renders WatchEnableModal", async () => {
    useDialogsStore.getState().open({ kind: "watch-enable" });
    render(<DialogHost />);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /watch this folder for changes/i }),
    ).toBeInTheDocument();
  });

  test("opening watch-disable via useDialogsStore renders WatchDisableModal", async () => {
    const folder = makeWatchedEntry({ path: "/p/A" });
    useDialogsStore.getState().open({ kind: "watch-disable", folder });
    render(<DialogHost />);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /stop watching this folder\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("watch-disable-path")).toHaveTextContent("/p/A");
  });
});
