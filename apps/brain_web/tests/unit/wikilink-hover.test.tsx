import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import {
  WikilinkHover,
  WIKILINK_HOVER_ID,
} from "@/components/browse/wikilink-hover";

/**
 * WikilinkHover a11y pins (Plan 16 Task 11).
 *
 * Plan 07 Task 18 landed the popover with ``role="tooltip"``. Plan 16
 * Task 11 hardens it for screen-reader + keyboard users:
 *   - The tooltip element has a stable ``id`` (``WIKILINK_HOVER_ID``)
 *     so consumer surfaces can wire ``aria-describedby`` on the
 *     trigger anchor.
 *   - ``role="tooltip"`` is preserved.
 *   - Returns ``null`` until the ``readNote`` round-trip resolves;
 *     the component itself doesn't manage focus or aria-describedby
 *     (that's the parent surface's job — see ``Reader``'s focus
 *     handlers for the consumer pattern).
 */

const mockReadNote = vi.fn();

vi.mock("@/lib/api/tools", () => ({
  readNote: (args: unknown) => mockReadNote(args),
}));

describe("WikilinkHover", () => {
  beforeEach(() => {
    mockReadNote.mockReset();
    mockReadNote.mockResolvedValue({
      data: {
        body: "First paragraph here.\n\nSecond paragraph.",
        frontmatter: { title: "Foo", domain: "research" },
      },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test("returns null until path is set (no anchor → no render)", () => {
    const { container } = render(
      <WikilinkHover path={null} anchor={null} onOpen={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  test("rendered tooltip has role='tooltip' and the canonical WIKILINK_HOVER_ID", async () => {
    // Build a fake anchor so the component can compute its position.
    // jsdom's getBoundingClientRect returns zeros — fine for this test;
    // we only care about the tooltip's a11y attributes.
    const anchor = document.createElement("a");
    anchor.classList.add("wikilink");
    anchor.textContent = "Foo";
    document.body.appendChild(anchor);

    render(
      <WikilinkHover path="research/foo.md" anchor={anchor} onOpen={vi.fn()} />,
    );

    // Wait for the readNote async to resolve and the tooltip to mount.
    await waitFor(() =>
      expect(screen.getByRole("tooltip")).toBeInTheDocument(),
    );

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveAttribute("id", WIKILINK_HOVER_ID);
    expect(tooltip).toHaveAttribute("role", "tooltip");

    document.body.removeChild(anchor);
  });

  test("tooltip body renders title, snippet, and the ↵ to open hint", async () => {
    const anchor = document.createElement("a");
    anchor.classList.add("wikilink");
    anchor.textContent = "Foo";
    document.body.appendChild(anchor);

    render(
      <WikilinkHover path="research/foo.md" anchor={anchor} onOpen={vi.fn()} />,
    );

    await waitFor(() =>
      expect(screen.getByRole("tooltip")).toBeInTheDocument(),
    );

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent("research/foo.md");
    expect(tooltip).toHaveTextContent("Foo");
    expect(tooltip).toHaveTextContent("First paragraph here.");
    expect(tooltip).toHaveTextContent("↵ to open");

    document.body.removeChild(anchor);
  });
});
