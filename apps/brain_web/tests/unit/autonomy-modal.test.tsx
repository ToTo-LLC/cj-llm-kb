import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { AutonomyModal } from "@/components/dialogs/autonomy-modal";

/**
 * AutonomyModal (Plan 16 Task 10 — SCAFFOLD).
 *
 * Pins:
 *   - Closed state: dialog does NOT render.
 *   - Open state: title "Autonomy mode" + description + Global +
 *     3 category Switches (New files / Edits / Index entries) + Done.
 *   - Description prop ≠ body content (Task 9 lesson — distinct prose).
 *   - Default value (no ``value`` passed): all switches off.
 *   - Per-category Switches disabled when Global is off; toggling
 *     Global to true enables them and fires onChange.
 *   - Toggling a per-category Switch (with Global on) fires onChange
 *     with the patched ``AutonomyValue``.
 *   - Done button calls onClose.
 *   - Esc dismisses the dialog (Radix wrapper behavior).
 *
 * Full per-domain enforcement + schema redesign land at Tasks 37–40.
 * This file only locks the scaffold's prop contract + microcopy +
 * disabled-state behavior so the a11y-populated gate stays valid
 * through the upgrade.
 */

describe("AutonomyModal", () => {
  test("does not render dialog content when isOpen=false", () => {
    render(<AutonomyModal isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /autonomy mode/i }),
    ).not.toBeInTheDocument();
  });

  test("renders title, description, body, 4 switches, and Done when open", async () => {
    render(<AutonomyModal isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    // Title.
    expect(
      screen.getByRole("heading", { name: /^autonomy mode$/i }),
    ).toBeInTheDocument();
    // Description text rendered via Modal's DialogDescription. Pin the
    // description prose (the Radix ``aria-describedby`` target).
    expect(
      screen.getByText(
        /Let brain make changes without asking\. Toggle each category for fine-grained control\./i,
      ),
    ).toBeInTheDocument();
    // Body content is DISTINCT from the description (Task 9 lesson) —
    // the body's leading paragraph names the safety rails that still
    // apply. Pinning here prevents the duplicate-description regression
    // from re-emerging.
    expect(
      screen.getByText(
        /Scope, domain, and budget guards still enforce every patch/i,
      ),
    ).toBeInTheDocument();

    // 4 Switches: 1 global + 3 categories. Match by aria-label since
    // the Switch primitive renders as a button; visible label is the
    // <span> text inside the wrapper.
    expect(
      screen.getByRole("switch", { name: /global autonomy/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /^new files$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /edits to existing notes/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /^index entries$/i }),
    ).toBeInTheDocument();

    // Done CTA.
    expect(
      screen.getByRole("button", { name: /^done$/i }),
    ).toBeInTheDocument();
  });

  test("default value: all switches off and per-category disabled", async () => {
    render(<AutonomyModal isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    // All 4 switches start unchecked (Radix exposes via aria-checked).
    const global = screen.getByRole("switch", { name: /global autonomy/i });
    const newFiles = screen.getByRole("switch", { name: /^new files$/i });
    const edits = screen.getByRole("switch", { name: /edits to existing notes/i });
    const index = screen.getByRole("switch", { name: /^index entries$/i });

    for (const sw of [global, newFiles, edits, index]) {
      expect(sw).toHaveAttribute("aria-checked", "false");
    }
    // Per-category switches disabled when Global is off.
    expect(newFiles).toBeDisabled();
    expect(edits).toBeDisabled();
    expect(index).toBeDisabled();
    // Global itself is always interactive.
    expect(global).not.toBeDisabled();
  });

  test("toggling Global fires onChange and enables per-category switches", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<AutonomyModal isOpen onClose={vi.fn()} onChange={onChange} />);
    await screen.findByRole("dialog");

    const global = screen.getByRole("switch", { name: /global autonomy/i });
    await user.click(global);

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith({
      global: true,
      newFiles: false,
      edits: false,
      indexEntries: false,
    });

    // Per-category switches now interactive.
    const newFiles = screen.getByRole("switch", { name: /^new files$/i });
    expect(newFiles).not.toBeDisabled();

    // Toggle a per-category switch — onChange fires with the patched value.
    await user.click(newFiles);
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith({
      global: true,
      newFiles: true,
      edits: false,
      indexEntries: false,
    });
  });

  test("seeded value renders all switches checked and enabled", async () => {
    render(
      <AutonomyModal
        isOpen
        onClose={vi.fn()}
        value={{
          global: true,
          newFiles: true,
          edits: true,
          indexEntries: true,
        }}
      />,
    );
    await screen.findByRole("dialog");

    for (const name of [
      /global autonomy/i,
      /^new files$/i,
      /edits to existing notes/i,
      /^index entries$/i,
    ]) {
      const sw = screen.getByRole("switch", { name });
      expect(sw).toHaveAttribute("aria-checked", "true");
      expect(sw).not.toBeDisabled();
    }
  });

  test("Done button calls onClose", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<AutonomyModal isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^done$/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Esc key dismisses the dialog (Radix wrapper behavior)", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<AutonomyModal isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
