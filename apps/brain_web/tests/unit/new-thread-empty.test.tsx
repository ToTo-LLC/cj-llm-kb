import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { NewThreadEmpty } from "@/components/chat/new-thread-empty";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

/**
 * NewThreadEmpty (Plan 07 Task 14): the empty state rendered when the
 * transcript is empty and no thread_id is present in the URL. Reads
 * mode + scope from ``app-store``; clicking a starter optimistically
 * appends a user message via ``chat-store.sendUserMessage`` (Task 15
 * wires the WS send itself).
 */

function resetAppStore() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "ask",
    scope: ["research", "work"],
    view: "chat",
    railOpen: true,
    activeThreadId: null,
    streaming: false,
  });
}

function resetChatStore() {
  useChatStore.setState({
    transcript: [],
    streaming: false,
    streamingText: "",
    currentTurn: 0,
    cumulativeTokensIn: 0,
  });
}

describe("NewThreadEmpty", () => {
  beforeEach(() => {
    localStorage.clear();
    resetAppStore();
    resetChatStore();
  });

  test("renders the three ask-mode starters verbatim", () => {
    useAppStore.setState({ mode: "ask" });
    render(<NewThreadEmpty />);
    // Exact copy from the plan's STARTERS const.
    expect(
      screen.getByText(
        "What has the vault said this year about silent-buyer patterns?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Cross-reference Fisher-Ury with the April Helios call.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Summarize concepts tagged #decision-theory · last 30 days."),
    ).toBeInTheDocument();
  });

  test("clicking a starter calls chat-store.sendUserMessage with the prompt text", async () => {
    useAppStore.setState({ mode: "brainstorm" });
    const spy = vi.fn<(text: string) => void>();
    // Patch the store so useChatStore.getState() reads the spy.
    useChatStore.setState({ sendUserMessage: spy });

    const user = userEvent.setup();
    render(<NewThreadEmpty />);
    const starter = screen.getByText(
      "Argue with me about compounding curiosity as a meta-practice.",
    );
    await user.click(starter);
    expect(spy).toHaveBeenCalledWith(
      "Argue with me about compounding curiosity as a meta-practice.",
    );
  });

  test("renders a scope chip for each domain in app-store.scope", () => {
    useAppStore.setState({ scope: ["research", "work"] });
    render(<NewThreadEmpty />);
    // Scope chips render the domain slug as visible text.
    expect(screen.getByText("research")).toBeInTheDocument();
    expect(screen.getByText("work")).toBeInTheDocument();
  });
});
