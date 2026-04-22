import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * AutonomousPanel (Plan 07 Task 22).
 *
 * Five per-category toggles — `autonomous.ingest`, `autonomous.entities`,
 * `autonomous.concepts`, `autonomous.index_rewrites`, `autonomous.draft`.
 *
 * - index_rewrites row has a danger class / icon.
 * - Initial value per toggle is read via `configGet(<key>)` on mount.
 * - Flipping a toggle calls `configSet(<key>, bool)`.
 */

const { configGetMock, configSetMock } = vi.hoisted(() => ({
  configGetMock: vi.fn(),
  configSetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
  configSet: configSetMock,
}));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: vi.fn() }),
    { getState: () => ({ pushToast: vi.fn() }) },
  ),
}));

import { PanelAutonomous } from "@/components/settings/panel-autonomous";

beforeEach(() => {
  configGetMock.mockReset();
  configSetMock.mockReset();
  configGetMock.mockResolvedValue({
    text: "",
    data: { key: "autonomous.ingest", value: false },
  });
  configSetMock.mockResolvedValue({ text: "", data: {} });
});

describe("PanelAutonomous", () => {
  test("renders all 5 category toggles", () => {
    render(<PanelAutonomous />);
    const categories = [
      "autonomous.ingest",
      "autonomous.entities",
      "autonomous.concepts",
      "autonomous.index_rewrites",
      "autonomous.draft",
    ];
    for (const key of categories) {
      expect(screen.getByRole("switch", { name: key })).toBeInTheDocument();
    }
  });

  test("index_rewrites row has a danger class / attribute", () => {
    render(<PanelAutonomous />);
    const danger = screen.getByTestId("autonomous-row-index_rewrites");
    expect(danger).toHaveAttribute("data-danger", "true");
  });

  test("toggling a switch calls configSet with `autonomous.<cat>`", async () => {
    const user = userEvent.setup();
    render(<PanelAutonomous />);
    const toggle = screen.getByRole("switch", { name: "autonomous.ingest" });
    await user.click(toggle);
    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalled();
    });
    const call = configSetMock.mock.calls[0]![0] as { key: string; value: unknown };
    expect(call.key).toBe("autonomous.ingest");
    expect(typeof call.value).toBe("boolean");
  });

  test("reading initial state calls configGet per key on mount", async () => {
    render(<PanelAutonomous />);
    await waitFor(() => {
      expect(configGetMock).toHaveBeenCalled();
    });
    const calls = configGetMock.mock.calls.map((c) => (c[0] as { key: string }).key);
    // At least one call per category.
    expect(calls).toEqual(
      expect.arrayContaining([
        "autonomous.ingest",
        "autonomous.entities",
        "autonomous.concepts",
        "autonomous.index_rewrites",
        "autonomous.draft",
      ]),
    );
  });
});
