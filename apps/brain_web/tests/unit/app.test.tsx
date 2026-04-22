import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

/**
 * Plan 08 Task 2 port: ``app/chat/page.tsx`` is a Client Component under
 * static export. Tokens come from the bootstrap context — we mock
 * ``useBootstrap`` to return a fake token so the page renders synchronously
 * without a real ``BootstrapProvider`` wiring up fetches.
 */

vi.mock("@/lib/bootstrap/bootstrap-context", () => ({
  useBootstrap: () => ({
    token: "test-token",
    isFirstRun: false,
    vaultPath: "/tmp/vault",
    loading: false,
    error: null,
    retry: vi.fn(),
  }),
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
    render(<ChatPage />);
    expect(
      screen.getByRole("heading", { name: /what are we working on/i }),
    ).toBeInTheDocument();
  });
});
