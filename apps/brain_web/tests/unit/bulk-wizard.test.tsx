import { describe, expect, test, beforeEach, afterEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, act } from "@testing-library/react";

/**
 * Plan 25 T4 — per-phase progress UI in the bulk-import wizard.
 *
 * Five exercises:
 *   1. Walk-phase interstitial renders spinner + "Scanning folder..." +
 *      folder path + helper text.
 *   2. Apply-phase progress bar shows "Importing N of M files" with the
 *      correct percentage width.
 *   3. Apply-phase ETA reads "Estimated time remaining: ~Xm" with the
 *      Math.ceil((M - N) × 10 / 60) value.
 *   4. Phase transition: idle → walking renders the interstitial; phase
 *      flipped back to ``idle`` unmounts it (verifies the gate, which
 *      stands in for the fade animation contract).
 *   5. Walk elapsed counter advances when timers tick — we use
 *      ``vi.useFakeTimers`` because the elapsed display is timer-driven.
 *
 * The store is reset between tests so phase + walk timestamps don't
 * leak. We don't mock the API tool layer here because these tests
 * exercise the UI surface; the bulk-store.test.ts file already covers
 * the API contract for ``pickFolder`` / ``startApply``.
 */

import { WalkInterstitial } from "@/components/bulk/walk-interstitial";
import { StepApply } from "@/components/bulk/step-apply";
import { useBulkStore, type BulkFile } from "@/lib/state/bulk-store";

function mkFile(id: number, extra: Partial<BulkFile> = {}): BulkFile {
  return {
    id,
    name: `file-${id}.md`,
    type: "text",
    size: "4.2 KB",
    classified: "research",
    confidence: 0.92,
    include: true,
    ...extra,
  };
}

function resetStore(): void {
  useBulkStore.setState({
    step: 1,
    folder: null,
    domain: "auto",
    cap: 20,
    files: [],
    applying: false,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
    phase: "idle",
    walkPath: null,
    walkStartedAt: null,
    applyStartedAt: null,
  });
}

describe("bulk-wizard per-phase progress UI (Plan 25 T4)", () => {
  beforeEach(() => {
    resetStore();
  });

  afterEach(() => {
    // Some tests opt into fake timers — restore real timers between
    // runs so a leak doesn't poison the next test's render.
    vi.useRealTimers();
  });

  test("walk phase renders spinner + 'Scanning folder...' + folder path + helper text", () => {
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
    });

    render(<WalkInterstitial />);

    // Heading microcopy verbatim per plan-doc spec.
    expect(screen.getByText("Scanning folder...")).toBeInTheDocument();
    // Helper text microcopy verbatim.
    expect(
      screen.getByText("This may take a moment for large folders."),
    ).toBeInTheDocument();
    // Folder path rendered into the path display.
    expect(screen.getByTestId("walk-path")).toHaveTextContent(
      "/Users/test/research",
    );
    // Spinner is the Lucide Loader2 with the ``animate-spin`` class.
    const spinner = screen.getByTestId("walk-spinner");
    expect(spinner).toBeInTheDocument();
    expect(spinner.classList.contains("animate-spin")).toBe(true);
  });

  test("apply phase progress bar shows 'Importing N of M files' + percentage width", () => {
    useBulkStore.setState({
      step: 4,
      files: Array.from({ length: 342 }, (_, i) => mkFile(i + 1)),
      applying: true,
      applyIdx: 27,
      cancelled: false,
      done: false,
      phase: "applying",
      applyStartedAt: Date.now(),
    });

    render(<StepApply />);

    expect(screen.getByTestId("apply-headline")).toHaveTextContent(
      "Importing 27 of 342 files",
    );
    // Math.round(27 / 342 * 100) = 8
    const progress = screen.getByTestId("apply-progress");
    const fill = progress.firstElementChild as HTMLElement;
    expect(fill.style.width).toBe("8%");
    expect(progress.getAttribute("aria-valuenow")).toBe("27");
    expect(progress.getAttribute("aria-valuemax")).toBe("342");
  });

  test("apply phase ETA shows 'Estimated time remaining: ~Xm' with Math.ceil rounding", () => {
    useBulkStore.setState({
      step: 4,
      files: Array.from({ length: 100 }, (_, i) => mkFile(i + 1)),
      applying: true,
      applyIdx: 50,
      cancelled: false,
      done: false,
      phase: "applying",
      applyStartedAt: Date.now(),
    });

    render(<StepApply />);

    // Remaining = 50; seconds = 500; minutes = ceil(500/60) = 9.
    expect(screen.getByTestId("apply-eta")).toHaveTextContent(
      "Estimated time remaining: ~9m",
    );
  });

  test("phase gate: walking renders interstitial; idle unmounts it", () => {
    // Initially idle — component should render nothing.
    const { rerender, container } = render(<WalkInterstitial />);
    expect(container.firstChild).toBeNull();

    // Transition to walking — interstitial renders.
    act(() => {
      useBulkStore.setState({
        phase: "walking",
        walkPath: "/Users/test/x",
        walkStartedAt: Date.now(),
      });
    });
    rerender(<WalkInterstitial />);
    expect(screen.getByTestId("walk-interstitial")).toBeInTheDocument();

    // Transition back to idle — interstitial unmounts. This stands in
    // for the fade-out contract: the component's render gate is the
    // single source of truth; CSS transition runs on the element-level
    // ``transition-opacity`` utility.
    act(() => {
      useBulkStore.setState({
        phase: "idle",
        walkPath: null,
        walkStartedAt: null,
      });
    });
    rerender(<WalkInterstitial />);
    expect(screen.queryByTestId("walk-interstitial")).not.toBeInTheDocument();
  });

  test("walk elapsed counter advances when timers tick", () => {
    vi.useFakeTimers();
    const start = Date.now();
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: start,
    });

    render(<WalkInterstitial />);

    // At t=0 the elapsed reads "0s".
    expect(screen.getByTestId("walk-elapsed")).toHaveTextContent("Elapsed: 0s");

    // Advance 12s — the setInterval(1000) fires 12 times. Each tick
    // calls setTick which re-renders; Date.now() reads the fake
    // timer's now value.
    act(() => {
      vi.advanceTimersByTime(12_000);
    });
    expect(screen.getByTestId("walk-elapsed")).toHaveTextContent("Elapsed: 12s");

    // Advance to >60s to verify the m/s split.
    act(() => {
      vi.advanceTimersByTime(50_000);
    });
    // 62s total → "1m 02s"
    expect(screen.getByTestId("walk-elapsed")).toHaveTextContent(
      "Elapsed: 1m 02s",
    );
  });
});
