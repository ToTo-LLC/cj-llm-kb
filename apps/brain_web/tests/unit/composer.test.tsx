import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { Composer } from "@/components/chat/composer";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";

/**
 * Composer (Plan 07 Task 15). Reads `mode`, `scope`, `streaming`, and
 * `cumulativeTokensIn` from the relevant stores; reads
 * `pendingAttachedSources` from chat-store. Emits onSend / onCancel /
 * onDetach callbacks; the hook layer wires those to the WS.
 *
 * Every test resets the two stores so cross-test state doesn't leak.
 */

function resetStores() {
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
}

describe("Composer", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStores();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("placeholder switches with mode", () => {
    useAppStore.setState({ mode: "ask" });
    const { rerender } = render(
      <Composer onSend={() => {}} onCancel={() => {}} onDetach={() => {}} />,
    );
    expect(screen.getByRole("textbox")).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/ask the vault/i),
    );

    useAppStore.setState({ mode: "brainstorm" });
    rerender(
      <Composer onSend={() => {}} onCancel={() => {}} onDetach={() => {}} />,
    );
    expect(screen.getByRole("textbox")).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/half-formed idea/i),
    );

    useAppStore.setState({ mode: "draft" });
    rerender(
      <Composer onSend={() => {}} onCancel={() => {}} onDetach={() => {}} />,
    );
    expect(screen.getByRole("textbox")).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/collaborate inline/i),
    );
  });

  test("Enter submits and clears; Shift+Enter inserts a newline", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <Composer onSend={onSend} onCancel={() => {}} onDetach={() => {}} />,
    );
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.click(textarea);
    await user.keyboard("hello world");
    await user.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("hello world");
    // Textarea is cleared on successful send.
    expect(textarea.value).toBe("");
  });

  test("Shift+Enter inserts a newline without submitting", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <Composer onSend={onSend} onCancel={() => {}} onDetach={() => {}} />,
    );
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.click(textarea);
    await user.keyboard("line one");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.keyboard("line two");

    expect(onSend).not.toHaveBeenCalled();
    expect(textarea.value).toBe("line one\nline two");
  });

  test("send button is disabled when text is empty", () => {
    render(
      <Composer onSend={() => {}} onCancel={() => {}} onDetach={() => {}} />,
    );
    const sendBtn = screen.getByRole("button", { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  test("during streaming: cancel button replaces send and fires onCancel", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <Composer
        onSend={() => {}}
        onCancel={onCancel}
        onDetach={() => {}}
        streaming
      />,
    );
    // Send is not present while streaming; cancel IS.
    expect(screen.queryByRole("button", { name: /send/i })).toBeNull();
    const cancelBtn = screen.getByRole("button", { name: /cancel/i });
    await user.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  test("context meter reads cumulativeTokensIn / 200_000 as a percentage", () => {
    useChatStore.setState({ cumulativeTokensIn: 20_000 });
    render(
      <Composer onSend={() => {}} onCancel={() => {}} onDetach={() => {}} />,
    );
    // 20k / 200k = 10%.
    expect(screen.getByText(/≈10%/)).toBeInTheDocument();
  });
});
