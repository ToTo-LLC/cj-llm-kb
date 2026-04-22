import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { ToolCall } from "@/components/chat/tool-call";
import type { ToolCallData } from "@/lib/state/chat-store";

/**
 * ToolCall is a collapsible card. Plan 07 Task 14.
 *
 * Head: tool name + args one-liner + caret.
 * Body (on expand): each ``call.result.hits`` renders score + path + snippet.
 *   - score truncated to 2 decimals (matches v3: ``h.score.toFixed(2)``)
 *   - path rendered monospace
 *   - snippet dim
 *
 * Default collapsed — hits stay off-screen until the user clicks.
 */

function makeCall(overrides: Partial<ToolCallData> = {}): ToolCallData {
  return {
    id: "tc-1",
    tool: "brain_search",
    args: { query: "silent-buyer", top_k: 3 },
    result: {
      hits: [
        {
          path: "research/buyers.md",
          snippet: "A silent buyer seldom says no outright.",
          score: 0.873,
        },
      ],
    },
    ...overrides,
  };
}

describe("ToolCall", () => {
  test("is collapsed by default; hit details are hidden", () => {
    render(<ToolCall call={makeCall()} />);
    // Head shows the tool name and args one-liner.
    expect(screen.getByText("brain_search")).toBeInTheDocument();
    // "query" appears in the args one-liner at minimum.
    expect(screen.getByText(/query/)).toBeInTheDocument();
    // Hit snippet is NOT visible while collapsed.
    expect(
      screen.queryByText(/silent buyer seldom says no outright/),
    ).not.toBeInTheDocument();
  });

  test("clicking the head expands and reveals the hits", async () => {
    const user = userEvent.setup();
    render(<ToolCall call={makeCall()} />);
    const head = screen.getByRole("button", { name: /brain_search/i });
    await user.click(head);
    expect(
      screen.getByText(/silent buyer seldom says no outright/),
    ).toBeInTheDocument();
  });

  test("expanded hit renders score (2 decimals), path (monospace), and snippet", async () => {
    const user = userEvent.setup();
    render(<ToolCall call={makeCall()} />);
    await user.click(screen.getByRole("button", { name: /brain_search/i }));

    // Score rendered to 2 decimals — 0.873 becomes "0.87".
    expect(screen.getByText("0.87")).toBeInTheDocument();
    // Path renders monospace. We query by text and then check its class.
    const pathEl = screen.getByText("research/buyers.md");
    expect(pathEl).toBeInTheDocument();
    expect(pathEl.className).toMatch(/(mono|font-mono)/);
    // Snippet renders (dim styling is a class assertion only).
    expect(
      screen.getByText("A silent buyer seldom says no outright."),
    ).toBeInTheDocument();
  });
});
