import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * DocPickerDialog (Plan 07 Task 19) — modal for selecting a vault
 * document to open in Draft mode. Fetches recent docs via the
 * ``brain_recent`` typed tool (mocked here), renders a fuzzy (substring)
 * filter, and offers a "start a blank scratch doc" option below the
 * divider.
 *
 * Task 25 sweeps proper fuzzy / Levenshtein ranking. For Task 19 the
 * filter is a case-insensitive substring match over both path and
 * domain, which is already plenty to test the interaction surface.
 */

const { recentMock } = vi.hoisted(() => ({ recentMock: vi.fn() }));

vi.mock("@/lib/api/tools", () => ({
  recent: recentMock,
}));

import { DocPickerDialog } from "@/components/draft/doc-picker-dialog";
import { useAppStore } from "@/lib/state/app-store";

function seed() {
  recentMock.mockResolvedValue({
    text: "",
    data: {
      items: [
        {
          path: "research/notes/fisher-ury-interests.md",
          title: "fisher-ury-interests",
          modified: "2026-04-18T10:00:00Z",
          domain: "research",
        },
        {
          path: "research/synthesis/silent-buyer-synthesis.md",
          title: "silent-buyer-synthesis",
          modified: "2026-04-14T10:00:00Z",
          domain: "research",
        },
        {
          path: "work/people/helios-champion.md",
          title: "helios-champion",
          modified: "2026-04-12T10:00:00Z",
          domain: "work",
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
});
