import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

/**
 * BackupsPanel (Plan 07 Task 22).
 *
 * Stubbed panel — backend tools (`brain_backup_create`, `brain_backup_list`,
 * `brain_backup_restore`) are part of the Task 25 sweep. For now the panel
 * renders:
 *   - Empty-list state + "Coming soon" explainer card.
 *   - Backup-now button that is DISABLED with a tooltip explaining the
 *     pending tool wiring.
 */

import { PanelBackups } from "@/components/settings/panel-backups";

describe("PanelBackups", () => {
  test("renders an empty list placeholder", () => {
    render(<PanelBackups />);
    expect(screen.getByTestId("backups-empty")).toBeInTheDocument();
  });

  test('displays a "Coming soon" card', () => {
    render(<PanelBackups />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  });

  test("backup-now button is disabled + has a tooltip/title", () => {
    render(<PanelBackups />);
    const btn = screen.getByRole("button", { name: /back up now/i });
    expect(btn).toBeDisabled();
    // Tooltip-like hint — either title attr or aria-describedby.
    expect(btn).toHaveAttribute("title");
  });
});
