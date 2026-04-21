import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { DropOverlay } from "@/components/system/drop-overlay";

/**
 * DropOverlay (Plan 07 Task 12): fullscreen overlay rendered during a file
 * drag. When not visible, the overlay MUST be non-interactive. We assert via
 * `aria-hidden="true"` because the overlay stays in the DOM (so the visible
 * -> hidden transition can animate later) and pointer-events are gated by
 * Tailwind utility + `aria-hidden`. Testing note: using `aria-hidden` is the
 * cleanest single idiom that implies both "screen-reader: ignore" and
 * (visually) "pointer-events-none" per our CSS in globals.
 */

describe("DropOverlay", () => {
  test("renders the 'Drop to attach' card with file-type chips when visible", () => {
    render(<DropOverlay visible />);
    expect(screen.getByText(/drop to attach/i)).toBeInTheDocument();
    expect(
      screen.getByText(/brain will ingest and summarize before filing\./i),
    ).toBeInTheDocument();
    // Four chips, per v3 design.
    expect(screen.getByText(/^pdf$/i)).toBeInTheDocument();
    expect(screen.getByText(/txt · md/i)).toBeInTheDocument();
    expect(screen.getByText(/^eml$/i)).toBeInTheDocument();
    expect(screen.getByText(/^url$/i)).toBeInTheDocument();
    const root = screen.getByTestId("drop-overlay");
    expect(root).toHaveAttribute("aria-hidden", "false");
  });

  test("hidden state marks overlay aria-hidden=true so it's non-interactive", () => {
    render(<DropOverlay visible={false} />);
    const root = screen.getByTestId("drop-overlay");
    expect(root).toHaveAttribute("aria-hidden", "true");
    // Tailwind utility `pointer-events-none` enforces non-interactivity too.
    expect(root.className).toMatch(/pointer-events-none/);
  });
});
