import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { Modal } from "@/components/dialogs/modal";

/**
 * Modal unit tests. We lean on shadcn's Dialog (Radix) for focus-trap, Esc,
 * backdrop click, and ARIA — so these tests assert integration, not our own
 * handlers. Radix portals outside the test container, so `screen` queries
 * still find the content (jsdom shares one document).
 */
describe("Modal", () => {
  test("renders title, eyebrow, and children when open", async () => {
    render(
      <Modal open onClose={() => {}} title="Do the thing" eyebrow="Confirm">
        <p>Body text here.</p>
      </Modal>,
    );
    // Radix assigns role="dialog" to DialogContent.
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // Title is the accessible name of the dialog.
    expect(dialog).toHaveAccessibleName("Do the thing");
    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(screen.getByText("Body text here.")).toBeInTheDocument();
  });

  test("Escape key triggers onClose (shadcn/Radix built-in)", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Modal open onClose={onClose} title="Escapable">
        <p>body</p>
      </Modal>,
    );
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("backdrop click triggers onClose (shadcn/Radix built-in)", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Modal open onClose={onClose} title="Backdroppable">
        <p>body</p>
      </Modal>,
    );
    await screen.findByRole("dialog");
    // Radix's DialogOverlay gets data-state="open" on the overlay div.
    // Click it to simulate backdrop click (Radix listens for overlay clicks).
    const overlays = document.querySelectorAll('[data-state="open"]');
    // The overlay is the element with no title/content — pick the first
    // overlay-like node. pointer-events: none on some overlays in jsdom so
    // we dispatch a direct click.
    const overlay = Array.from(overlays).find(
      (el) => el.getAttribute("aria-hidden") === "true" || el.className.includes("bg-black"),
    );
    expect(overlay).toBeTruthy();
    await user.click(overlay as Element);
    expect(onClose).toHaveBeenCalled();
  });
});
