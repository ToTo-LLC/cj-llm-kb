/**
 * Plan 15 Task 7 — ``dispatchSend`` honors the click-time captured mode.
 *
 * Pre-fix: ``dispatchSend`` read ``mode`` from the live React closure.
 * If the user clicked Send (which captures the click-time mode into
 * ``pendingSendRef.current.mode``), then changed the mode toggle while
 * the cross-domain confirmation modal was open, then acknowledged the
 * modal, the dispatched ``turn_start`` would carry the POST-modal
 * mode — not the pre-modal click-time mode the user originally chose.
 *
 * Plan 15 D6 locks the captured-at-click-time semantics: ``dispatchSend``
 * must read ``mode`` from ``pendingSendRef.current.mode`` (the snapshot
 * taken at click time), not from the live closure.
 *
 * Two cases pinned here:
 *   1. Mode-changed-during-modal: send=Ask, modal opens, mode flips to
 *      Brainstorm, user acknowledges → ``sendTurnStart`` invoked with
 *      ``mode: "ask"`` (the captured value).
 *   2. Mode-unchanged-during-modal: regression guard — same flow with
 *      no mode change still works correctly (``mode: "ask"``).
 *
 * The cross-domain trigger gate is forced ON by configuring the gate
 * store with ``loaded=true``, ``acknowledged=false``, and
 * ``privacyRailed=["personal"]``, plus a scope of
 * ``["research", "personal"]`` so the trigger fires.
 */

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

// ---------- Mocks (hoisted so vi.mock factories can reach them) ----------

const { sendTurnStartMock, cancelTurnMock } = vi.hoisted(() => ({
  sendTurnStartMock: vi.fn(),
  cancelTurnMock: vi.fn(),
}));

vi.mock("@/lib/ws/hooks", () => ({
  useChatWebSocket: () => ({
    sendTurnStart: sendTurnStartMock,
    cancelTurn: cancelTurnMock,
    switchMode: vi.fn(),
    setOpenDoc: vi.fn(),
  }),
}));

const { setCrossDomainWarningAcknowledgedMock } = vi.hoisted(() => ({
  setCrossDomainWarningAcknowledgedMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  setCrossDomainWarningAcknowledged: setCrossDomainWarningAcknowledgedMock,
}));

// ---------- Imports (after mocks) ----------

import { ChatScreen } from "@/components/chat/chat-screen";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useCrossDomainGateStore } from "@/lib/state/cross-domain-gate-store";

function resetAppStore() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "ask",
    // Scope = ["research", "personal"] so ``shouldFireCrossDomainModal``
    // returns true once the gate store hydrates with privacyRailed
    // including "personal" and acknowledged=false.
    scope: ["research", "personal"],
    scopeInitialized: true,
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
    pendingAttachedSources: [],
  });
}

function primeGateStore() {
  // Mirror the on-disk values we want the trigger gate to observe:
  // ``privacy_railed=["personal"]`` and ``acknowledged=false`` →
  // trigger fires for any cross-domain scope that includes "personal".
  useCrossDomainGateStore.setState({
    privacyRailed: ["personal"],
    acknowledged: false,
    loaded: true,
    error: null,
  });
}

describe("ChatScreen — dispatchSend honors pendingSendRef.mode (Plan 15 D6 / Task 7)", () => {
  beforeEach(() => {
    sendTurnStartMock.mockReset();
    cancelTurnMock.mockReset();
    setCrossDomainWarningAcknowledgedMock.mockReset();
    setCrossDomainWarningAcknowledgedMock.mockResolvedValue({
      text: "",
      data: { key: "cross_domain_warning_acknowledged", value: true },
    });

    useCrossDomainGateStore.getState()._resetForTesting();
    resetAppStore();
    resetChatStore();
    primeGateStore();
  });

  afterEach(() => {
    // Defensive: reset to keep stores from bleeding into other suites
    // sharing the same singletons.
    useCrossDomainGateStore.getState()._resetForTesting();
    resetAppStore();
    resetChatStore();
  });

  test("mode changed between modal-show and modal-acknowledge: dispatched mode = click-time captured value", async () => {
    const user = userEvent.setup();

    // threadId=null forces the new-thread path → cross-domain modal
    // gate is eligible to fire.
    render(<ChatScreen threadId={null} token="test-token" />);

    // Initial mode is "ask" (set by resetAppStore). User types and
    // presses Enter to submit; click-time capture happens here.
    const textarea = await screen.findByLabelText("Message brain");
    await user.click(textarea);
    await user.keyboard("hello brain");
    await user.keyboard("{Enter}");

    // Modal should be open; sendTurnStart NOT yet called (parked).
    await screen.findByRole("dialog");
    expect(sendTurnStartMock).not.toHaveBeenCalled();

    // User flips mode to "brainstorm" via the app store while modal
    // is still open. The chat-screen's ``mode`` selector now reads
    // "brainstorm" via the live closure on the next render. Wrap in
    // ``act`` to flush the resulting re-render before we click
    // Continue (otherwise React Testing Library yells about missing
    // act() wrapping around the cross-component state update).
    act(() => {
      useAppStore.setState({ mode: "brainstorm" });
    });

    // User acknowledges (Continue without "don't show again").
    const continueBtn = await screen.findByTestId(
      "cross-domain-continue-button",
    );
    await user.click(continueBtn);

    // Assert: send was dispatched with the CAPTURED mode ("ask"), not
    // the live-closure mode ("brainstorm"). This is the load-bearing
    // assertion for D6.
    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(1);
    });
    const [content, opts] = sendTurnStartMock.mock.calls[0]!;
    expect(content).toBe("hello brain");
    expect(opts).toEqual(
      expect.objectContaining({
        mode: "ask",
      }),
    );
  });

  test("mode unchanged through modal acknowledge: dispatched mode = click-time mode (regression guard)", async () => {
    const user = userEvent.setup();

    render(<ChatScreen threadId={null} token="test-token" />);

    const textarea = await screen.findByLabelText("Message brain");
    await user.click(textarea);
    await user.keyboard("regression check");
    await user.keyboard("{Enter}");

    await screen.findByRole("dialog");
    expect(sendTurnStartMock).not.toHaveBeenCalled();

    // No mode change this time — user simply acknowledges.
    const continueBtn = await screen.findByTestId(
      "cross-domain-continue-button",
    );
    await user.click(continueBtn);

    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(1);
    });
    const [content, opts] = sendTurnStartMock.mock.calls[0]!;
    expect(content).toBe("regression check");
    expect(opts).toEqual(
      expect.objectContaining({
        mode: "ask",
      }),
    );
  });

  test("non-modal direct send path: dispatched mode = live mode (no ref captured)", async () => {
    // Disable the trigger gate by acknowledging — modal won't fire,
    // and ``handleSend`` calls ``dispatchSend`` directly. Exercises
    // the fallback branch where ``pendingSendRef.current`` is null
    // so ``dispatchSend`` falls back to live closure ``mode``.
    useCrossDomainGateStore.setState({
      privacyRailed: ["personal"],
      acknowledged: true,
      loaded: true,
      error: null,
    });

    const user = userEvent.setup();
    render(<ChatScreen threadId={null} token="test-token" />);

    // Set mode = "draft" before sending so the live closure carries
    // a non-default value.
    act(() => {
      useAppStore.setState({ mode: "draft" });
    });

    const textarea = await screen.findByLabelText("Message brain");
    await user.click(textarea);
    await user.keyboard("direct path");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(1);
    });
    const [content, opts] = sendTurnStartMock.mock.calls[0]!;
    expect(content).toBe("direct path");
    expect(opts).toEqual(
      expect.objectContaining({
        mode: "draft",
      }),
    );
  });
});
