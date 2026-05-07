import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import axe from "axe-core";

/**
 * PanelAutonomous (Plan 16 Task 40 / D30 step 4 of 4 — REWRITE).
 *
 * Per-domain × per-category grid surface. Replaces the Plan 07 Task 22
 * flat 5-row toggle scaffold (which read against the OLD
 * ``autonomous.<flag>`` keys; Plan 16 Task 39 dropped those from the
 * backend allowlist).
 *
 * Coverage:
 *   1. Renders one row per domain + 5 category columns + Reset button.
 *   2. Toggling a Switch fires ``setDomainAutonomy(slug, cat, value)``
 *      via ``brain_config_set`` with the dotted key
 *      ``autonomous.<slug>.<category>``.
 *   3. Reset button fires per-category ``setDomainAutonomy(_, _, false)``
 *      for every flag currently true.
 *   4. "Disable all autonomy" footer button does the same across every
 *      slug.
 *   5. Empty-state when no domains.
 *   6. Mount-time ``configGet({key:"autonomous"})`` hydrate.
 *   7. axe-core: 0 violations on populated state.
 *   8. Switch aria-labels uniquely identify (slug, category).
 */

const { configGetMock, configSetMock, listDomainsMock } = vi.hoisted(() => ({
  configGetMock: vi.fn(),
  configSetMock: vi.fn(),
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/api/tools")>();
  return {
    ...actual,
    configGet: configGetMock,
    configSet: configSetMock,
    listDomains: listDomainsMock,
    // ``setDomainAutonomy`` calls ``configSet`` via the module's own
    // closure, so the configSet mock above WON'T be visible to its
    // internal call site. Re-route the helper through the mock here so
    // assertions on ``configSetMock`` see every panel write.
    setDomainAutonomy: (
      slug: string,
      category: string,
      value: boolean,
    ) => configSetMock({ key: `autonomous.${slug}.${category}`, value }),
  };
});

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: vi.fn() }),
    { getState: () => ({ pushToast: vi.fn() }) },
  ),
}));

import { PanelAutonomous } from "@/components/settings/panel-autonomous";
import { useDomainsStore } from "@/lib/state/domains-store";
import { useSettingsStore } from "@/lib/state/settings-store";

beforeEach(() => {
  configGetMock.mockReset();
  configSetMock.mockReset();
  listDomainsMock.mockReset();
  // Default snapshot: empty autonomous; populated 2-domain list.
  configGetMock.mockResolvedValue({
    text: "",
    data: { key: "autonomous", value: {} },
  });
  configSetMock.mockResolvedValue({ text: "", data: {} });
  listDomainsMock.mockResolvedValue({
    text: "",
    data: {
      domains: ["research", "personal"],
      entries: [
        { slug: "research", configured: true, on_disk: true },
        { slug: "personal", configured: true, on_disk: true },
      ],
      active_domain: "research",
    },
  });
  // Ensure stores start at a known-clean state.
  useDomainsStore.getState()._resetForTesting();
  useSettingsStore.getState().reset();
});

describe("PanelAutonomous (Task 40)", () => {
  test("renders the empty-state when domains are empty", async () => {
    listDomainsMock.mockResolvedValueOnce({
      text: "",
      data: { domains: [], entries: [], active_domain: "" },
    });
    render(<PanelAutonomous />);
    await waitFor(() => {
      expect(screen.getByTestId("autonomy-empty-state")).toBeInTheDocument();
    });
    // No grid in the empty-state branch.
    expect(screen.queryByTestId("autonomy-grid")).not.toBeInTheDocument();
  });

  test("renders one row per domain with 5 category switches", async () => {
    render(<PanelAutonomous />);
    await waitFor(() => {
      expect(screen.getByTestId("autonomy-grid")).toBeInTheDocument();
    });
    // Header row carries the 5 category column labels.
    const grid = screen.getByTestId("autonomy-grid");
    expect(within(grid).getByText("New files")).toBeInTheDocument();
    expect(within(grid).getByText("Edits")).toBeInTheDocument();
    expect(within(grid).getByText("Index entries")).toBeInTheDocument();
    expect(within(grid).getByText("Concepts")).toBeInTheDocument();
    expect(within(grid).getByText("Draft")).toBeInTheDocument();

    // One row per seeded domain.
    expect(screen.getByTestId("autonomy-row-research")).toBeInTheDocument();
    expect(screen.getByTestId("autonomy-row-personal")).toBeInTheDocument();

    // 5 switches per row × 2 rows = 10 switches total.
    const switches = within(grid).getAllByRole("switch");
    expect(switches).toHaveLength(10);
  });

  test("each switch has a unique aria-label encoding (slug, category)", async () => {
    render(<PanelAutonomous />);
    await waitFor(() => {
      expect(screen.getByTestId("autonomy-grid")).toBeInTheDocument();
    });
    const cases: ReadonlyArray<[string, string]> = [
      ["research", "new files"],
      ["research", "edits"],
      ["research", "index entries"],
      ["research", "concepts"],
      ["research", "draft"],
      ["personal", "new files"],
      ["personal", "edits"],
    ];
    for (const [slug, category] of cases) {
      const sw = screen.getByRole("switch", {
        name: new RegExp(
          `Auto-apply ${category} patches in ${slug}`,
          "i",
        ),
      });
      expect(sw).toBeInTheDocument();
    }
  });

  test("hydrates initial state from a single configGet call", async () => {
    configGetMock.mockResolvedValueOnce({
      text: "",
      data: {
        key: "autonomous",
        value: {
          research: { new_files: true, edits: true },
          personal: { draft: true },
        },
      },
    });
    render(<PanelAutonomous />);
    // Wait for the mount-time fetch to land + grid to render.
    await waitFor(() => {
      expect(screen.getByTestId("autonomy-grid")).toBeInTheDocument();
    });
    // ``configGet`` called exactly once (panel) — mount fetch.
    await waitFor(() => {
      expect(configGetMock).toHaveBeenCalledWith({ key: "autonomous" });
    });
    // Verify hydrated state landed in the store.
    await waitFor(() => {
      const state = useSettingsStore.getState().autonomous;
      expect(state.research?.new_files).toBe(true);
      expect(state.research?.edits).toBe(true);
      expect(state.personal?.draft).toBe(true);
    });
  });

  test("toggling a switch fires configSet with autonomous.<slug>.<category>", async () => {
    const user = userEvent.setup();
    render(<PanelAutonomous />);
    await waitFor(() => {
      expect(screen.getByTestId("autonomy-grid")).toBeInTheDocument();
    });
    const sw = screen.getByTestId("autonomy-switch-research-new_files");
    await user.click(sw);
    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalled();
    });
    const call = configSetMock.mock.calls[0]![0] as {
      key: string;
      value: unknown;
    };
    expect(call.key).toBe("autonomous.research.new_files");
    expect(call.value).toBe(true);
  });

  test("Reset row clears every previously-true flag for that slug", async () => {
    configGetMock.mockResolvedValueOnce({
      text: "",
      data: {
        key: "autonomous",
        value: {
          research: { new_files: true, edits: true, draft: true },
        },
      },
    });
    const user = userEvent.setup();
    render(<PanelAutonomous />);
    await waitFor(() => {
      // Wait for hydrate to land.
      const state = useSettingsStore.getState().autonomous;
      expect(state.research?.new_files).toBe(true);
    });
    const reset = screen.getByTestId("autonomy-reset-research");
    await user.click(reset);
    await waitFor(() => {
      // 3 flags were true → 3 setDomainAutonomy(_, _, false) calls.
      expect(configSetMock).toHaveBeenCalledTimes(3);
    });
    const calls = configSetMock.mock.calls.map(
      (c) => c[0] as { key: string; value: unknown },
    );
    const keys = new Set(calls.map((c) => c.key));
    expect(keys).toEqual(
      new Set([
        "autonomous.research.new_files",
        "autonomous.research.edits",
        "autonomous.research.draft",
      ]),
    );
    for (const c of calls) expect(c.value).toBe(false);
  });

  test("Disable-all clears every flag across every domain", async () => {
    configGetMock.mockResolvedValueOnce({
      text: "",
      data: {
        key: "autonomous",
        value: {
          research: { new_files: true, edits: true },
          personal: { draft: true },
        },
      },
    });
    const user = userEvent.setup();
    render(<PanelAutonomous />);
    await waitFor(() => {
      const state = useSettingsStore.getState().autonomous;
      expect(state.research?.new_files).toBe(true);
      expect(state.personal?.draft).toBe(true);
    });
    const disableAll = screen.getByTestId("autonomy-disable-all");
    await user.click(disableAll);
    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalledTimes(3);
    });
    const calls = configSetMock.mock.calls.map(
      (c) => c[0] as { key: string; value: unknown },
    );
    const keys = new Set(calls.map((c) => c.key));
    expect(keys).toEqual(
      new Set([
        "autonomous.research.new_files",
        "autonomous.research.edits",
        "autonomous.personal.draft",
      ]),
    );
    for (const c of calls) expect(c.value).toBe(false);
  });

  test("axe-core: 0 violations on populated state", async () => {
    configGetMock.mockResolvedValueOnce({
      text: "",
      data: {
        key: "autonomous",
        value: { research: { new_files: true } },
      },
    });
    const { container } = render(<PanelAutonomous />);
    await waitFor(() => {
      expect(screen.getByTestId("autonomy-grid")).toBeInTheDocument();
    });
    // axe-core runs against the rendered container. Mirror the
    // top-level e2e gate's filter: WCAG 2.1 A + AA + WCAG 2.2 AA. Color-
    // contrast is disabled in jsdom because computed styles aren't
    // resolved (CSS variables read as empty); the e2e populated-state
    // case (a11y-populated.spec.ts) carries that rule against a real
    // browser.
    const results = await axe.run(container, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag22aa"] },
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });
});
