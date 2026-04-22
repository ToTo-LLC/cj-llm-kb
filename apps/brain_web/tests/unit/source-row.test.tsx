import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

/**
 * SourceRow (Plan 07 Task 17) — a single inbox row.
 *
 * Each status variant (queued / classifying / integrating / failed)
 * renders distinct styling: a status pill with the right label, an
 * optional progress bar, and — for ``failed`` — an error line plus a
 * Retry button.
 */

import { SourceRow } from "@/components/inbox/source-row";
import type { IngestSource } from "@/lib/state/inbox-store";

function mkSource(extra: Partial<IngestSource> = {}): IngestSource {
  return {
    id: "s-1",
    source: "https://example.com/x",
    title: "Silent buyers — research note",
    type: "url",
    status: "queued",
    domain: "research",
    progress: 0,
    at: "2026-04-21T10:00:00Z",
    ...extra,
  };
}

describe("SourceRow", () => {
  test("queued status renders the queued label with 0% progress", () => {
    const { container } = render(
      <SourceRow source={mkSource({ status: "queued", progress: 0 })} />,
    );
    const row = screen.getByTestId("source-row");
    expect(row).toHaveAttribute("data-status", "queued");
    // Pill label visible.
    expect(screen.getByText(/^queued$/i)).toBeInTheDocument();
    // Progress bar fill width mirrors progress=0.
    const fill = container.querySelector(
      '[data-testid="source-row-progress-fill"]',
    ) as HTMLElement | null;
    expect(fill).not.toBeNull();
    expect(fill!.style.width).toBe("0%");
  });

  test("classifying status renders the classifying label with partial progress", () => {
    const { container } = render(
      <SourceRow source={mkSource({ status: "classifying", progress: 40 })} />,
    );
    expect(screen.getByTestId("source-row")).toHaveAttribute(
      "data-status",
      "classifying",
    );
    expect(screen.getByText(/^classifying$/i)).toBeInTheDocument();
    const fill = container.querySelector(
      '[data-testid="source-row-progress-fill"]',
    ) as HTMLElement | null;
    expect(fill!.style.width).toBe("40%");
  });

  test("integrating status renders distinct label with high progress", () => {
    const { container } = render(
      <SourceRow source={mkSource({ status: "integrating", progress: 85 })} />,
    );
    expect(screen.getByTestId("source-row")).toHaveAttribute(
      "data-status",
      "integrating",
    );
    expect(screen.getByText(/^integrating$/i)).toBeInTheDocument();
    const fill = container.querySelector(
      '[data-testid="source-row-progress-fill"]',
    ) as HTMLElement | null;
    expect(fill!.style.width).toBe("85%");
  });

  test("failed status renders the error line AND a Retry button", () => {
    const onRetry = vi.fn();
    render(
      <SourceRow
        source={mkSource({
          status: "failed",
          progress: 0,
          error: "Upstream classifier returned 503",
        })}
        onRetry={onRetry}
      />,
    );
    const row = screen.getByTestId("source-row");
    expect(row).toHaveAttribute("data-status", "failed");
    // Error surface + retry affordance.
    expect(
      screen.getByText(/upstream classifier returned 503/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
