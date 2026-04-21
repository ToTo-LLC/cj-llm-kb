import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { MidTurnToast } from "@/components/system/mid-turn-toast";

/**
 * MidTurnToast (Plan 07 Task 12): non-blocking banner rendered when a chat
 * turn hits a recoverable or soft-invalid state. Five fixed kinds — each has
 * a locked copy (lead + msg) taken verbatim from the v3 design / plan.
 *
 * Tests assert the COPY MAP is wired correctly (never rewrite these strings
 * without a plan update) and that dismiss + retry callbacks fire exactly
 * once on click.
 */

describe("MidTurnToast", () => {
  test("rate-limit copy (warn tone)", () => {
    render(<MidTurnToast kind="rate-limit" />);
    expect(screen.getByText(/rate limit\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/anthropic slowed us down\. retrying in 8s — or retry now\./i),
    ).toBeInTheDocument();
  });

  test("context-full copy (warn tone)", () => {
    render(<MidTurnToast kind="context-full" />);
    expect(screen.getByText(/context full\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/compact the thread to keep going, or start a fresh one\./i),
    ).toBeInTheDocument();
  });

  test("tool-failed copy (danger tone)", () => {
    render(<MidTurnToast kind="tool-failed" />);
    expect(screen.getByText(/tool failed\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/a tool couldn't complete — the vault path may not be reachable\./i),
    ).toBeInTheDocument();
  });

  test("invalid-state-turn copy", () => {
    render(<MidTurnToast kind="invalid-state-turn" />);
    expect(screen.getByText(/finish this turn first\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/wait for it to complete, or cancel to start fresh\./i),
    ).toBeInTheDocument();
  });

  test("invalid-state-mode copy", () => {
    render(<MidTurnToast kind="invalid-state-mode" />);
    expect(screen.getByText(/can't switch mid-turn\./i)).toBeInTheDocument();
    expect(
      screen.getByText(/mode change takes effect on the next turn\./i),
    ).toBeInTheDocument();
  });

  test("dismiss and retry callbacks fire on click", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    const onRetry = vi.fn();
    render(
      <MidTurnToast
        kind="rate-limit"
        onDismiss={onDismiss}
        onRetry={onRetry}
      />,
    );
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onDismiss).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
