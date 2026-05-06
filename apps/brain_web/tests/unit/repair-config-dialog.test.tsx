import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { RepairConfigDialog } from "@/components/dialogs/repair-config-dialog";

/**
 * RepairConfigDialog (Plan 16 Task 9 — SCAFFOLD).
 *
 * Pins:
 *   - Closed state: dialog does NOT render.
 *   - Open state: title "Repair config" + description + Run repair + Cancel.
 *   - Run repair button calls onRunRepair (when provided) THEN onClose.
 *   - Cancel button calls onClose.
 *   - Esc dismisses (Radix wrapper behavior — verified via onClose firing).
 *   - onRunRepair omitted: Run repair still cleanly closes.
 *
 * Full implementation (telemetry read-out, per-step controls,
 * ``Config.config_version``) lands at Task 33; this scaffold only needs to
 * satisfy the a11y-populated.spec.ts gate AND prove the prop contract.
 */

describe("RepairConfigDialog", () => {
  test("does not render dialog content when isOpen=false", () => {
    render(<RepairConfigDialog isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /repair config/i }),
    ).not.toBeInTheDocument();
  });

  test("renders title, description, and both buttons when isOpen=true", async () => {
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    expect(
      screen.getByRole("heading", { name: /repair config/i }),
    ).toBeInTheDocument();
    // Description text appears in the body — Radix mirrors it into
    // ``aria-describedby``-targeted DialogDescription as well.
    expect(
      screen.getByText(
        /If your .* is corrupted, brain falls back to .* then defaults\./i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /run repair/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^cancel$/i }),
    ).toBeInTheDocument();
  });

  test("Run repair button fires onRunRepair then onClose", async () => {
    const onRunRepair = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <RepairConfigDialog
        isOpen
        onClose={onClose}
        onRunRepair={onRunRepair}
      />,
    );
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /run repair/i }));

    expect(onRunRepair).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Run repair without onRunRepair handler still closes the dialog", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /run repair/i }));

    // No throw, no console error — onClose is the one observable.
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Cancel button fires onClose only (does not call onRunRepair)", async () => {
    const onRunRepair = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <RepairConfigDialog
        isOpen
        onClose={onClose}
        onRunRepair={onRunRepair}
      />,
    );
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onRunRepair).not.toHaveBeenCalled();
  });

  test("Esc key dismisses the dialog (Radix wrapper behavior)", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
