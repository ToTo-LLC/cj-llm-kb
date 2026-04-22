import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * SearchOverlay wires ⌘K-opened vault search. Plan 07 Task 18.
 *
 * We mock both `next/navigation` (the overlay navigates via `router.push`)
 * and `@/lib/api/tools` (the overlay calls ``search`` to fetch hits).
 */
const { routerPushMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPushMock,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const { searchMock } = vi.hoisted(() => ({
  searchMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  search: searchMock,
}));

import { SearchOverlay } from "@/components/browse/search-overlay";

describe("SearchOverlay", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routerPushMock.mockReset();
    searchMock.mockReset();
  });

  test("when opened it autofocuses the input and Escape closes via onClose", async () => {
    const onClose = vi.fn();
    render(<SearchOverlay open onClose={onClose} />);
    const input = screen.getByRole("searchbox");
    await waitFor(() => expect(input).toHaveFocus());
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("typing a query renders results from the mocked search tool", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue({
      text: "",
      data: {
        hits: [
          {
            path: "research/concepts/conflict-avoidance-tells.md",
            title: "Conflict-Avoidance Tells",
            snippet: "…widening of the attendee list…",
            score: 0.94,
          },
          {
            path: "research/notes/fisher-ury-interests.md",
            title: "Fisher & Ury — Positions vs. Interests",
            snippet: "…hidden risk interest…",
            score: 0.76,
          },
        ],
        top_k_used: 2,
      },
    });
    render(<SearchOverlay open onClose={vi.fn()} />);
    await user.type(screen.getByRole("searchbox"), "conflict");
    await waitFor(() => {
      expect(searchMock).toHaveBeenCalled();
    });
    // The two hit paths land in the DOM.
    expect(
      await screen.findByText(
        "research/concepts/conflict-avoidance-tells.md",
      ),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("research/notes/fisher-ury-interests.md"),
    ).toBeInTheDocument();
  });

  test("clicking a result navigates to /browse/<path> and closes the overlay", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    searchMock.mockResolvedValue({
      text: "",
      data: {
        hits: [
          {
            path: "research/concepts/conflict-avoidance-tells.md",
            title: "Conflict-Avoidance Tells",
            snippet: "…",
            score: 0.94,
          },
        ],
        top_k_used: 1,
      },
    });
    render(<SearchOverlay open onClose={onClose} />);
    await user.type(screen.getByRole("searchbox"), "conflict");
    const hit = await screen.findByText(
      "research/concepts/conflict-avoidance-tells.md",
    );
    await user.click(hit);
    expect(routerPushMock).toHaveBeenCalledWith(
      "/browse/research/concepts/conflict-avoidance-tells.md",
    );
    expect(onClose).toHaveBeenCalled();
  });

  test("global ⌘K keydown opens the overlay (exposed via `open` prop + external handler not needed for this test — uses controlled `open` toggle)", async () => {
    // The overlay is fully controlled; AppShell owns the global
    // keydown handler. Here we simply verify the overlay RESPECTS
    // `open`: rendering with ``open={false}`` shows nothing, and
    // re-rendering with ``open={true}`` surfaces the searchbox.
    const { rerender } = render(
      <SearchOverlay open={false} onClose={vi.fn()} />,
    );
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    act(() => {
      rerender(<SearchOverlay open onClose={vi.fn()} />);
    });
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
  });
});
