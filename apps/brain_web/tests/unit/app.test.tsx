import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

/**
 * Task 15 made ``app/chat/page.tsx`` a server component that reads the
 * per-run API token on the server, redirects to ``/setup`` when the
 * token is missing, and passes token + ``threadId={null}`` to the
 * client ``<ChatScreen />``. To keep this smoke test around without a
 * real vault we mock ``readToken`` to return a fake token, await the
 * async page function, and render the resulting element with
 * Testing Library — same behaviour Next.js exercises in production.
 */

vi.mock("@/lib/auth/token", () => ({
  readToken: vi.fn(async () => "test-token"),
}));

// WebSocket is unused by the empty transcript path but the ChatScreen
// hook still constructs one. Stub the global so jsdom doesn't blow up.
class NoopWebSocket {
  static readonly OPEN = 1;
  readyState = 0;
  addEventListener(): void {}
  removeEventListener(): void {}
  send(): void {}
  close(): void {}
  constructor(_: string) {}
}

describe("ChatPage (/chat)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("WebSocket", NoopWebSocket);
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
      pendingAttachedSources: [],
    });
  });

  test("renders NewThreadEmpty's 'What are we working on?' heading", async () => {
    const { default: ChatPage } = await import("@/app/chat/page");
    const element = await ChatPage();
    render(element);
    expect(
      screen.getByRole("heading", { name: /what are we working on/i }),
    ).toBeInTheDocument();
  });
});
