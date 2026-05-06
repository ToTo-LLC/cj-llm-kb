import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { Message } from "@/components/chat/message";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import type { ChatMessage } from "@/lib/state/chat-store";

/**
 * Per-message Fork — Plan 16 Task 11 a11y pin.
 *
 * The chat-sub-header already renders a Fork button (``aria-label="Fork"``,
 * ``title="Fork"``); each assistant message bubble ALSO renders a Fork
 * button via ``MsgActions``. Plan 16 Task 11 disambiguates the per-
 * message variant with ``aria-label="Fork from this message"`` so screen
 * readers can tell the two apart.
 *
 * Pins:
 *   - Assistant message bubble has a button with
 *     ``aria-label="Fork from this message"``.
 *   - User messages do NOT render that button.
 *   - Click → ``dialogs-store.open({ kind: "fork", threadId, turnIndex })``.
 *     The ``turnIndex`` flows from the Transcript through ``Message`` →
 *     ``MsgActions``.
 */

const openDialogMock = vi.fn();

vi.mock("@/lib/state/dialogs-store", () => ({
  useDialogsStore: Object.assign(
    (
      selector: (s: { open: typeof openDialogMock; close: () => void }) =>
        unknown,
    ) => selector({ open: openDialogMock, close: vi.fn() }),
    { getState: () => ({ open: openDialogMock, close: vi.fn() }) },
  ),
}));

function makeMsg(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    role: "brain",
    ts: "09:12",
    body: "an assistant reply",
    mode: "ask",
    cost: 0.001,
    ...overrides,
  };
}

describe("per-message Fork (MsgActions)", () => {
  beforeEach(() => {
    openDialogMock.mockReset();
    useAppStore.setState({
      activeThreadId: "thread-abc",
      mode: "ask",
      scope: ["research"],
    });
    useChatStore.setState({
      transcript: [],
      streaming: false,
      streamingText: "",
      pendingAttachedSources: [],
    });
  });

  test("assistant message renders a 'Fork from this message' button", () => {
    render(<Message msg={makeMsg()} turnIndex={2} />);
    const btn = screen.getByRole("button", { name: /fork from this message/i });
    expect(btn).toBeInTheDocument();
    // The button label disambiguates from the chat-sub-header Fork
    // (which uses aria-label="Fork"). Both share the visible "Fork"
    // text — only the aria-label distinguishes them for AT users.
    expect(btn).toHaveAttribute("aria-label", "Fork from this message");
  });

  test("user message does NOT render the per-message Fork button", () => {
    render(<Message msg={makeMsg({ role: "user" })} turnIndex={0} />);
    expect(
      screen.queryByRole("button", { name: /fork from this message/i }),
    ).not.toBeInTheDocument();
  });

  test("clicking the per-message Fork opens the fork dialog with correct turnIndex", async () => {
    const user = userEvent.setup();
    render(<Message msg={makeMsg({ body: "the long body" })} turnIndex={3} />);

    await user.click(
      screen.getByRole("button", { name: /fork from this message/i }),
    );

    expect(openDialogMock).toHaveBeenCalledTimes(1);
    const arg = openDialogMock.mock.calls[0][0];
    expect(arg.kind).toBe("fork");
    expect(arg.threadId).toBe("thread-abc");
    expect(arg.turnIndex).toBe(3);
    // ``summary`` is sliced from the message body (≤220 chars).
    expect(arg.summary).toContain("the long body");
  });

  test("Fork is a no-op without an active thread (silent)", async () => {
    useAppStore.setState({ activeThreadId: null });
    const user = userEvent.setup();
    render(<Message msg={makeMsg()} turnIndex={1} />);

    await user.click(
      screen.getByRole("button", { name: /fork from this message/i }),
    );

    // No openDialog call — Fork only makes sense once the source
    // thread is persisted server-side.
    expect(openDialogMock).not.toHaveBeenCalled();
  });
});
