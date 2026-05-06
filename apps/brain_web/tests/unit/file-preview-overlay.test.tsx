import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { FilePreviewOverlay } from "@/components/dialogs/file-preview-overlay";

/**
 * FilePreviewOverlay (Plan 16 Task 11).
 *
 * Pins:
 *   - Closed state: dialog content not in DOM.
 *   - Open state: title (file path) + description + body content + Close
 *     button + (when ``onOpenFull`` given) "Open in Browse" button.
 *   - Description prop is DISTINCT from body content (Task 9 lesson).
 *   - Esc dismisses (Radix wrapper).
 *   - Empty body renders the "This note is empty." placeholder instead
 *     of the empty <pre>.
 *   - "Open in Browse" calls ``onOpenFull(path)`` then ``onClose``.
 */

describe("FilePreviewOverlay", () => {
  test("does not render dialog content when isOpen=false", () => {
    render(
      <FilePreviewOverlay
        isOpen={false}
        onClose={vi.fn()}
        path="research/notes/foo.md"
        body="# Foo"
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("research/notes/foo.md")).not.toBeInTheDocument();
  });

  test("renders title (path), description, body content, and Close button", async () => {
    render(
      <FilePreviewOverlay
        isOpen
        onClose={vi.fn()}
        path="research/notes/foo.md"
        body="# Foo\n\nBody content here."
      />,
    );
    await screen.findByRole("dialog");

    // Title is the file path
    expect(
      screen.getByRole("heading", { name: "research/notes/foo.md" }),
    ).toBeInTheDocument();
    // Description (visually-hidden in the Modal wrapper but in the DOM)
    expect(
      screen.getByText("Quick preview from Browse — opens read-only."),
    ).toBeInTheDocument();
    // Body content rendered in a labelled <pre>.
    const preview = screen.getByLabelText(
      "Preview of research/notes/foo.md",
    );
    expect(preview.textContent ?? "").toContain("# Foo");
    expect(preview.textContent ?? "").toContain("Body content here.");
    // Close button always present (Modal wrapper renders a sr-only
    // "Close" X-button; the footer's "Close" is the visible primary
    // dismiss). Both have the same accessible name; we only need to
    // assert at least one renders.
    expect(
      screen.getAllByRole("button", { name: /^close$/i }).length,
    ).toBeGreaterThan(0);
  });

  test("description is DISTINCT from body content (Task 9 lesson)", async () => {
    render(
      <FilePreviewOverlay
        isOpen
        onClose={vi.fn()}
        path="research/notes/foo.md"
        body="Some body text that is unrelated."
      />,
    );
    await screen.findByRole("dialog");

    // Description and body must not collide — description is a meta
    // sentence, body is the file content. Both must be present in DOM
    // and not be equal.
    const desc = screen.getByText(
      "Quick preview from Browse — opens read-only.",
    );
    const preview = screen.getByLabelText(
      "Preview of research/notes/foo.md",
    );
    expect(desc.textContent).not.toEqual(preview.textContent);
  });

  test("Esc key dismisses the dialog (Radix wrapper)", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <FilePreviewOverlay
        isOpen
        onClose={onClose}
        path="research/foo.md"
        body="x"
      />,
    );
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("empty body renders the 'This note is empty.' placeholder", async () => {
    render(
      <FilePreviewOverlay
        isOpen
        onClose={vi.fn()}
        path="research/empty.md"
        body=""
      />,
    );
    await screen.findByRole("dialog");

    expect(screen.getByText("This note is empty.")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("Preview of research/empty.md"),
    ).not.toBeInTheDocument();
  });

  test("'Open in Browse' button fires onOpenFull then onClose; hidden when no handler", async () => {
    const onClose = vi.fn();
    const onOpenFull = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <FilePreviewOverlay
        isOpen
        onClose={onClose}
        path="research/foo.md"
        body="x"
        onOpenFull={onOpenFull}
      />,
    );
    await screen.findByRole("dialog");

    const openBtn = screen.getByRole("button", { name: /open in browse/i });
    await user.click(openBtn);

    expect(onOpenFull).toHaveBeenCalledWith("research/foo.md");
    expect(onClose).toHaveBeenCalledTimes(1);

    // Re-render without onOpenFull → button is gone.
    rerender(
      <FilePreviewOverlay
        isOpen
        onClose={onClose}
        path="research/foo.md"
        body="x"
      />,
    );
    expect(
      screen.queryByRole("button", { name: /open in browse/i }),
    ).not.toBeInTheDocument();
  });
});
