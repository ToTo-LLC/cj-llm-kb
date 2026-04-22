import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { Message } from "@/components/chat/message";
import type { ChatMessage } from "@/lib/state/chat-store";

/**
 * Message component visual contract (Plan 07 Task 14).
 *
 * Ported from the v3 design:
 *   - avatar + role label
 *   - assistant messages show a mode chip ("Ask" / "Brainstorm" / "Draft")
 *   - timestamp + cost in the role strip ("· $0.004")
 *   - body rendered via ``renderBody`` (tests for that parser live in
 *     rendering.test.tsx — here we just smoke-check).
 *
 * Streaming cases are covered via the chat-store reducers + transcript
 * integration; Message itself is a pure render of its props.
 */

function makeMsg(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    role: "brain",
    ts: "09:12",
    body: "A short answer.",
    mode: "ask",
    cost: 0.004,
    ...overrides,
  };
}

describe("Message", () => {
  test("user role renders 'You' with the body text (no mode chip, no msg-actions)", () => {
    render(<Message msg={makeMsg({ role: "user", body: "a question" })} />);
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(screen.getByText("a question")).toBeInTheDocument();
    // user messages never render the Ask/Brainstorm/Draft chip
    expect(screen.queryByText("Ask")).not.toBeInTheDocument();
    expect(screen.queryByText("Brainstorm")).not.toBeInTheDocument();
    expect(screen.queryByText("Draft")).not.toBeInTheDocument();
    // no assistant msg-actions on user rows
    expect(screen.queryByRole("button", { name: /Copy/i })).not.toBeInTheDocument();
  });

  test("assistant role renders 'brain' + a mode chip with the mode label", () => {
    render(<Message msg={makeMsg({ mode: "brainstorm" })} />);
    expect(screen.getByText("brain")).toBeInTheDocument();
    // Mode label is shown as a capitalized chip (matches v3).
    expect(screen.getByText("Brainstorm")).toBeInTheDocument();
  });

  test("timestamp renders verbatim (backend pre-formats it)", () => {
    render(<Message msg={makeMsg({ ts: "14:32" })} />);
    expect(screen.getByText("14:32")).toBeInTheDocument();
  });

  test("cost renders in the $X.XXX format (3-decimal)", () => {
    render(<Message msg={makeMsg({ cost: 0.02 })} />);
    // 0.02 -> "$0.020" (toFixed(3))
    expect(screen.getByText(/\$0\.020/)).toBeInTheDocument();
  });
});
