import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * PanelBudget (Plan 17 Task 3) — migrated to budget-store.
 *
 * Pins four behaviours after the refactor from inline configGet/configSet
 * to the shared budget-store:
 *
 *   1. Alert threshold renders from the store snapshot.
 *   2. Daily input hydrates from the store once ``loaded`` is true.
 *   3. Clicking Save calls ``useBudgetStore.getState().setDailyCap(n)``.
 *   4. An invalid (non-numeric) input shows a danger toast without
 *      reaching the store.
 *
 * Mocks: ``useBudget`` hook + ``useBudgetStore`` static access. The
 * system-store is NOT mocked — we read its ``toasts`` array directly to
 * verify toast pushes (mirrors budget-wall.test.tsx).
 */

// ---- Hoisted mock factories ----

const { useBudgetMock, setDailyCapMock } = vi.hoisted(() => ({
  useBudgetMock: vi.fn(),
  setDailyCapMock: vi.fn(),
}));

vi.mock("@/lib/hooks/use-budget", () => ({
  useBudget: useBudgetMock,
}));

vi.mock("@/lib/state/budget-store", () => ({
  useBudgetStore: Object.assign(
    // Selector calls (not used in the migrated component — it calls
    // useBudget() for reads and useBudgetStore.getState() for writes).
    vi.fn(),
    {
      getState: vi.fn(() => ({
        setDailyCap: setDailyCapMock,
      })),
    },
  ),
}));

// ---- Imports (after mocks) ----

import { PanelBudget } from "@/components/settings/panel-budget";
import { useSystemStore } from "@/lib/state/system-store";

// ---- Helpers ----

function resetSystemStore() {
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    toasts: [],
  });
}

/** Default useBudget return when the store is loaded with a full snapshot. */
function mockBudgetLoaded(overrides: {
  daily_usd?: number | null;
  alert_threshold_pct?: number | null;
} = {}) {
  useBudgetMock.mockReturnValue({
    snapshot: {
      daily_usd: overrides.daily_usd ?? null,
      monthly_usd: null,
      alert_threshold_pct: overrides.alert_threshold_pct ?? null,
      per_domain: {},
    },
    loaded: true,
    loading: false,
    error: null,
    refresh: vi.fn(),
  });
}

/** Default useBudget return when the store has not yet loaded. */
function mockBudgetNotLoaded() {
  useBudgetMock.mockReturnValue({
    snapshot: {
      daily_usd: null,
      monthly_usd: null,
      alert_threshold_pct: null,
      per_domain: {},
    },
    loaded: false,
    loading: true,
    error: null,
    refresh: vi.fn(),
  });
}

// ---- Tests ----

beforeEach(() => {
  useBudgetMock.mockReset();
  setDailyCapMock.mockReset();
  resetSystemStore();
});

describe("PanelBudget — threshold display", () => {
  test("renders the alert threshold from the store snapshot", () => {
    mockBudgetLoaded({ alert_threshold_pct: 80 });
    render(<PanelBudget />);

    // "80% of cap" should appear in the alerting section.
    expect(screen.getByText(/80%/)).toBeInTheDocument();
    expect(screen.getByText(/of cap/)).toBeInTheDocument();
  });

  test("renders em-dash when alert_threshold_pct is null", () => {
    mockBudgetLoaded({ alert_threshold_pct: null });
    render(<PanelBudget />);

    expect(screen.getByText(/—.*of cap/)).toBeInTheDocument();
  });
});

describe("PanelBudget — daily input hydration", () => {
  test("hydrates the daily input from the store when loaded is true", async () => {
    mockBudgetLoaded({ daily_usd: 5 });
    render(<PanelBudget />);

    // useEffect fires after mount; waitFor handles the microtask flush.
    await waitFor(() => {
      const input = screen.getByLabelText(/daily cap/i) as HTMLInputElement;
      expect(input.value).toBe("5");
    });
  });

  test("leaves the daily input empty when store is not yet loaded", () => {
    mockBudgetNotLoaded();
    render(<PanelBudget />);

    const input = screen.getByLabelText(/daily cap/i) as HTMLInputElement;
    expect(input.value).toBe("");
  });
});

describe("PanelBudget — Save button", () => {
  test("calls setDailyCap with the numeric value when Save is clicked", async () => {
    const user = userEvent.setup();
    mockBudgetLoaded({ daily_usd: 5 });
    setDailyCapMock.mockResolvedValue(undefined);

    render(<PanelBudget />);

    // Wait for hydration.
    await waitFor(() => {
      const input = screen.getByLabelText(/daily cap/i) as HTMLInputElement;
      expect(input.value).toBe("5");
    });

    // Clear and type a new value.
    const input = screen.getByLabelText(/daily cap/i);
    await user.clear(input);
    await user.type(input, "10");

    // Click the enabled Save button (first one — daily section).
    const saveButtons = screen.getAllByRole("button", { name: /save/i });
    const enabledSave = saveButtons.find(
      (btn) => !(btn as HTMLButtonElement).disabled,
    )!;
    await user.click(enabledSave);

    expect(setDailyCapMock).toHaveBeenCalledTimes(1);
    expect(setDailyCapMock).toHaveBeenCalledWith(10);
  });

  test("shows a success toast after a successful save", async () => {
    const user = userEvent.setup();
    mockBudgetLoaded({ daily_usd: 3 });
    setDailyCapMock.mockResolvedValue(undefined);

    render(<PanelBudget />);

    await waitFor(() => {
      expect(
        (screen.getByLabelText(/daily cap/i) as HTMLInputElement).value,
      ).toBe("3");
    });

    const saveButtons = screen.getAllByRole("button", { name: /save/i });
    const enabledSave = saveButtons.find(
      (btn) => !(btn as HTMLButtonElement).disabled,
    )!;
    await user.click(enabledSave);

    // Flush async resolution.
    await Promise.resolve();
    await Promise.resolve();

    const toasts = useSystemStore.getState().toasts;
    expect(toasts.length).toBeGreaterThanOrEqual(1);
    const latest = toasts[toasts.length - 1]!;
    expect(latest.lead).toMatch(/daily cap saved/i);
    expect(latest.variant).toBe("success");
  });
});

describe("PanelBudget — invalid input", () => {
  test("shows a danger toast without calling setDailyCap for a negative value (store not yet loaded)", async () => {
    const user = userEvent.setup();
    mockBudgetNotLoaded();

    render(<PanelBudget />);

    // HTML type="number" inputs produce "" for non-numeric text in jsdom
    // (Number("") === 0 — valid), so the only DOM-reachable invalid path
    // is a negative number. The `min="0"` attribute is advisory in HTML;
    // jsdom does not enforce it, so we can type "-1" and expect the guard
    // to catch it.
    const input = screen.getByLabelText(/daily cap/i);
    await user.type(input, "-1");

    const saveButtons = screen.getAllByRole("button", { name: /save/i });
    const enabledSave = saveButtons.find(
      (btn) => !(btn as HTMLButtonElement).disabled,
    )!;
    await user.click(enabledSave);

    expect(setDailyCapMock).not.toHaveBeenCalled();

    const toasts = useSystemStore.getState().toasts;
    expect(toasts.length).toBeGreaterThanOrEqual(1);
    const latest = toasts[toasts.length - 1]!;
    expect(latest.lead).toMatch(/invalid cap/i);
    expect(latest.variant).toBe("danger");
  });

  test("shows a danger toast and does NOT call setDailyCap for a negative value", async () => {
    const user = userEvent.setup();
    mockBudgetLoaded({ daily_usd: 5 });

    render(<PanelBudget />);

    await waitFor(() => {
      expect(
        (screen.getByLabelText(/daily cap/i) as HTMLInputElement).value,
      ).toBe("5");
    });

    const input = screen.getByLabelText(/daily cap/i);
    await user.clear(input);
    await user.type(input, "-1");

    const saveButtons = screen.getAllByRole("button", { name: /save/i });
    const enabledSave = saveButtons.find(
      (btn) => !(btn as HTMLButtonElement).disabled,
    )!;
    await user.click(enabledSave);

    expect(setDailyCapMock).not.toHaveBeenCalled();

    const toasts = useSystemStore.getState().toasts;
    const latest = toasts[toasts.length - 1]!;
    expect(latest.lead).toMatch(/invalid cap/i);
    expect(latest.variant).toBe("danger");
  });
});
