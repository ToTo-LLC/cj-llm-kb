import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * BudgetWall (Plan 07 Task 12): blocking modal shown when the daily spend cap
 * is hit. Shows a cost breakdown by mode (pure presentational — data comes
 * from props), a "heaviest turn" hint, and a model-switch hint. Footer has
 * two buttons:
 *   - "Wait it out" → just closes.
 *   - "Raise cap by $5 for today" → calls `budgetOverride({amount_usd: 5,
 *     duration_hours: 24})`, then pushes a toast via system-store.
 *
 * Cost data flows in via props. For Task 12 we do NOT wire React Query —
 * that's Task 16 / 21. Rendering without props falls back to built-in
 * `mockData` so snapshot-free tests can exercise the component.
 */

// Mock the tools API — budgetOverride is the only binding we call here.
const { budgetOverrideMock } = vi.hoisted(() => ({
  budgetOverrideMock: vi.fn(),
}));
vi.mock("@/lib/api/tools", () => ({
  budgetOverride: budgetOverrideMock,
}));

import { BudgetWall } from "@/components/system/budget-wall";
import { useSystemStore } from "@/lib/state/system-store";

function resetSystemStore() {
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    toasts: [],
  });
}

const costBreakdown = {
  costToday: 2.82,
  budget: 3.0,
  byMode: {
    ask: 1.04,
    brainstorm: 0.38,
    draft: 0.92,
    ingest: 0.48,
  },
  heaviestTurn: {
    title: "Cross-link April stall-pattern calls",
    toolCalls: 12,
    tokens: 48_000,
    cost: 0.31,
  },
};

describe("BudgetWall", () => {
  beforeEach(() => {
    resetSystemStore();
    budgetOverrideMock.mockReset();
  });

  test("renders the cost breakdown from props (eyebrow, totals, heaviest turn)", async () => {
    render(
      <BudgetWall
        open
        onClose={() => {}}
        data={costBreakdown}
      />,
    );
    await screen.findByRole("dialog");

    // Eyebrow + title both present.
    expect(screen.getByText(/daily spend cap hit/i)).toBeInTheDocument();
    expect(screen.getByText(/\$2\.82/)).toBeInTheDocument();
    expect(screen.getByText(/\$3\.00/)).toBeInTheDocument();

    // Breakdown rows (mode labels + dollar amounts).
    expect(screen.getByText(/ask turns/i)).toBeInTheDocument();
    expect(screen.getByText(/brainstorm turns/i)).toBeInTheDocument();
    expect(screen.getByText(/draft turns/i)).toBeInTheDocument();
    expect(screen.getByText(/\$1\.04/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.38/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.92/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.48/)).toBeInTheDocument();

    // Heaviest turn details.
    expect(screen.getByText(/cross-link april stall-pattern calls/i)).toBeInTheDocument();

    // Model-switch hint — "current" marker on Sonnet.
    expect(screen.getByText(/claude sonnet/i)).toBeInTheDocument();
    expect(screen.getByText(/haiku/i)).toBeInTheDocument();
  });

  test("'Raise cap by $5 for today' button calls budgetOverride and pushes a toast", async () => {
    const user = userEvent.setup();
    budgetOverrideMock.mockResolvedValue({
      text: "Cap raised.",
      data: {
        amount_usd: 5,
        duration_hours: 24,
        expires_at: "2026-04-22T00:00:00Z",
      },
    });
    const onClose = vi.fn();
    render(
      <BudgetWall open onClose={onClose} data={costBreakdown} />,
    );
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /raise cap by \$5 for today/i }));

    expect(budgetOverrideMock).toHaveBeenCalledTimes(1);
    expect(budgetOverrideMock).toHaveBeenCalledWith({
      amount_usd: 5,
      duration_hours: 24,
    });

    // Wait a microtask for the promise to resolve, then assert toast + close.
    await Promise.resolve();
    await Promise.resolve();

    expect(onClose).toHaveBeenCalled();
    const toasts = useSystemStore.getState().toasts;
    expect(toasts.length).toBeGreaterThanOrEqual(1);
    const latest = toasts[toasts.length - 1];
    expect(latest.lead).toMatch(/cap raised/i);
  });

  test("Wait it out' closes the dialog", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <BudgetWall open onClose={onClose} data={costBreakdown} />,
    );
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: /wait it out/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
