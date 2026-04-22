import { describe, expect, test, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import ChatPage from "@/app/chat/page";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

/**
 * Task 14 replaced the placeholder /chat page with the real Chat
 * screen. With an empty transcript and no active thread the page
 * renders ``NewThreadEmpty`` — its "What are we working on?" heading
 * is the canonical smoke signal.
 */
describe("ChatPage (/chat)", () => {
  beforeEach(() => {
    localStorage.clear();
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
    useChatStore.setState({
      transcript: [],
      streaming: false,
      streamingText: "",
      currentTurn: 0,
      cumulativeTokensIn: 0,
    });
  });

  test("renders NewThreadEmpty's 'What are we working on?' heading", () => {
    render(<ChatPage />);
    expect(
      screen.getByRole("heading", { name: /what are we working on/i }),
    ).toBeInTheDocument();
  });
});
