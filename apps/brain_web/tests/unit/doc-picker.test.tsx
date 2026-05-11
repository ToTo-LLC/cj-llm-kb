import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * DocPickerDialog (Plan 07 Task 19) — modal for selecting a vault
 * document to open in Draft mode. Fetches recent docs via the
 * ``brain_recent`` typed tool (mocked here), renders a substring filter
 * on the row path, and offers a "start a blank scratch doc" option
 * below the divider.
 *
 * Plan 18 T1 narrowed ``RecentEntry`` to the actual backend shape
 * (``{path, modified_at}`` only) and fixed two latent bugs in the
 * picker (path-prefix scope filter, dropped redundant search clause).
 * The ``seed()`` mock below emits ONLY the real backend shape — earlier
 * the mock seeded ``title`` / ``domain`` / ``modified`` which papered
 * over the runtime ``TypeError`` users hit when typing in the filter.
 *
 * Task 25 sweeps proper fuzzy / Levenshtein ranking. For Task 19 the
 * filter is a case-insensitive substring match on the row path, which
 * already carries the domain slug as its first segment.
 */

const { recentMock } = vi.hoisted(() => ({ recentMock: vi.fn() }));

vi.mock("@/lib/api/tools", () => ({
  recent: recentMock,
}));

import { DocPickerDialog } from "@/components/draft/doc-picker-dialog";
import { useAppStore } from "@/lib/state/app-store";

function seed() {
  // Plan 18 T1: mirror the REAL ``brain_recent`` backend row shape —
  // ``{path, modified_at}`` only. Pre-T1 this mock seeded ``title`` /
  // ``domain`` / ``modified`` fields the backend never emits, which
  // silently masked the runtime TypeError in the doc-picker scope /
  // search filters. Regression tests below depend on this shape.
  recentMock.mockResolvedValue({
    text: "",
    data: {
      items: [
        {
          path: "research/notes/fisher-ury-interests.md",
          modified_at: "2026-04-18T10:00:00Z",
        },
        {
          path: "research/synthesis/silent-buyer-synthesis.md",
          modified_at: "2026-04-14T10:00:00Z",
        },
        {
          path: "work/people/helios-champion.md",
          modified_at: "2026-04-12T10:00:00Z",
        },
      ],
    },
  });
}

function resetAppStore() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "draft",
    scope: ["research", "work"],
    view: "chat",
    railOpen: true,
    activeThreadId: null,
    streaming: false,
  });
}

beforeEach(() => {
  recentMock.mockReset();
  resetAppStore();
  seed();
});

describe("DocPickerDialog", () => {
  test("typing into the filter input narrows the list (substring match)", async () => {
    const user = userEvent.setup();
    render(
      <DocPickerDialog
        kind="doc-picker"
        onPick={vi.fn()}
        onNewBlank={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    // Wait for the seeded list to render.
    await screen.findByText("silent-buyer-synthesis.md");
    // All three rows start visible.
    expect(screen.getByText("fisher-ury-interests.md")).toBeInTheDocument();
    expect(screen.getByText("helios-champion.md")).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/filter by path or domain/i);
    await user.type(input, "helios");

    // Only the matching row remains.
    await waitFor(() => {
      expect(screen.queryByText("fisher-ury-interests.md")).not.toBeInTheDocument();
    });
    expect(screen.getByText("helios-champion.md")).toBeInTheDocument();
  });

  test("each row renders a domain chip", async () => {
    render(
      <DocPickerDialog
        kind="doc-picker"
        onPick={vi.fn()}
        onNewBlank={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByText("silent-buyer-synthesis.md");
    // Modal renders through a Radix portal; query the whole document
    // rather than the `render` container because the chips live inside
    // the portal root.
    const researchChips = document.querySelectorAll(".dom-research");
    const workChips = document.querySelectorAll(".dom-work");
    expect(researchChips.length).toBeGreaterThanOrEqual(2);
    expect(workChips.length).toBeGreaterThanOrEqual(1);
  });

  test("scratch option invokes onNewBlank with a path under <scope[0]>/scratch/ dated today", async () => {
    const user = userEvent.setup();
    const onNewBlank = vi.fn();
    const onClose = vi.fn();
    render(
      <DocPickerDialog
        kind="doc-picker"
        onPick={vi.fn()}
        onNewBlank={onNewBlank}
        onClose={onClose}
      />,
    );
    await screen.findByText("silent-buyer-synthesis.md");
    const scratch = screen.getByRole("button", { name: /blank scratch/i });
    await user.click(scratch);
    expect(onNewBlank).toHaveBeenCalledTimes(1);
    const pathArg = onNewBlank.mock.calls[0]![0] as string;
    const today = new Date().toISOString().slice(0, 10);
    // scope[0] is "research" for the seeded app-store.
    expect(pathArg.startsWith("research/scratch/")).toBe(true);
    expect(pathArg).toContain(today);
    expect(pathArg.endsWith("-untitled.md")).toBe(true);
  });

  test("Enter on the highlighted (first) row selects it via onPick", async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(
      <DocPickerDialog
        kind="doc-picker"
        onPick={onPick}
        onNewBlank={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByText("silent-buyer-synthesis.md");
    // Focus starts on the filter input (autoFocus). Pressing Enter
    // commits the currently-highlighted row — by default the first one
    // in the visible list.
    await user.keyboard("{Enter}");
    expect(onPick).toHaveBeenCalledTimes(1);
    // The first seeded item is fisher-ury-interests.md.
    expect(onPick.mock.calls[0]![0]).toBe(
      "research/notes/fisher-ury-interests.md",
    );
  });

  test("scope filter keeps research-prefixed rows and drops work-prefixed rows (regression: path-prefix not it.domain)", async () => {
    // Plan 18 T1 regression: pre-fix, scope filtering used
    // ``scope.includes(it.domain)`` where ``it.domain`` was undefined
    // (the backend never emits a ``domain`` field). With a non-empty
    // scope, EVERY row got filtered out — the user saw an empty picker.
    // Post-fix, scope is matched via path-prefix so only
    // ``research/*`` rows render here.
    useAppStore.setState({
      theme: "dark",
      density: "comfortable",
      mode: "draft",
      scope: ["research"],
      view: "chat",
      railOpen: true,
      activeThreadId: null,
      streaming: false,
    });
    render(
      <DocPickerDialog
        kind="doc-picker"
        onPick={vi.fn()}
        onNewBlank={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByText("silent-buyer-synthesis.md");
    expect(screen.getByText("fisher-ury-interests.md")).toBeInTheDocument();
    expect(screen.getByText("silent-buyer-synthesis.md")).toBeInTheDocument();
    expect(screen.queryByText("helios-champion.md")).not.toBeInTheDocument();
  });

  test("search filter does not throw TypeError on rows without a domain field (regression: drop redundant clause)", async () => {
    // Plan 18 T1 regression: pre-fix, typing into the filter input
    // ran ``it.domain.toLowerCase()`` on every row, throwing
    // ``TypeError: Cannot read properties of undefined`` immediately
    // (the backend never emits a ``domain`` field). Post-fix the
    // domain-side clause is gone — the path already carries the domain
    // slug as its first segment, so a query like "buy" still matches
    // ``silent-buyer-synthesis.md`` via path.
    const user = userEvent.setup();
    render(
      <DocPickerDialog
        kind="doc-picker"
        onPick={vi.fn()}
        onNewBlank={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByText("silent-buyer-synthesis.md");
    const input = screen.getByPlaceholderText(/filter by path or domain/i);
    // The typing itself must not throw; the matching row must remain;
    // the non-matching rows must be filtered out.
    await user.type(input, "buy");
    await waitFor(() => {
      expect(screen.queryByText("fisher-ury-interests.md")).not.toBeInTheDocument();
    });
    expect(screen.getByText("silent-buyer-synthesis.md")).toBeInTheDocument();
    expect(screen.queryByText("helios-champion.md")).not.toBeInTheDocument();
  });
});
