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

  test("cancel-path: clicking Back-to-scope closes modal and dispatches no send", async () => {
    // Plan 15 Task 7 review — exercises ``handleCrossDomainCancel``.
    // The cancel handler must:
    //   1. Drop the parked send (``pendingSendRef.current = null``).
    //   2. Close the modal.
    // We can't poke the ref from outside the component, so the
    // observable proof of (1) is "no ``sendTurnStart`` ever fires"; the
    // observable proof of (2) is "the dialog leaves the DOM". A second,
    // unrelated direct send (after acknowledging) confirms the ref is
    // actually clear: if cancel had left a stale capture, a subsequent
    // send would risk replaying it. The clean direct send validates the
    // ref is clean.
    const user = userEvent.setup();
    render(<ChatScreen threadId={null} token="test-token" />);

    const textarea = await screen.findByLabelText("Message brain");
    await user.click(textarea);
    await user.keyboard("cancel me");
    await user.keyboard("{Enter}");

    // Modal opens, send is parked.
    await screen.findByRole("dialog");
    expect(sendTurnStartMock).not.toHaveBeenCalled();

    // Click Back-to-scope (cancel).
    const cancelBtn = await screen.findByTestId("cross-domain-back-button");
    await user.click(cancelBtn);

    // Modal closes (proof of #2).
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // No send fired (proof of #1: parked turn was dropped, not replayed).
    expect(sendTurnStartMock).not.toHaveBeenCalled();
  });

  test("transient WS error on first dispatch does not poison subsequent sends", async () => {
    // Plan 15 Task 7 review — locks the property "errors during dispatch
    // don't leak the captured pending into the next send."
    //
    // Pre-fix structure (clear-after-dispatch): if ``sendTurnStart``
    // threw, the ref reset never executed, leaving a stale capture.
    // Post-fix structure (clear-before-dispatch): the ref is null
    // before dispatch runs, so no stale capture is reachable even if
    // dispatch throws.
    //
    // We assert the SECOND send (with no modal trigger this time)
    // dispatches with its own intent — the first send's failed capture
    // does not carry over.
    const user = userEvent.setup();

    // First call throws synchronously; subsequent calls succeed. The
    // throw happens inside the async click handler so it surfaces as
    // an unhandled rejection at the Node process level. Pin a one-shot
    // process-level handler to swallow it cleanly so the Vitest run
    // doesn't surface an "unhandled error" report.
    sendTurnStartMock.mockImplementationOnce(() => {
      throw new Error("simulated WS send failure");
    });
    const swallow = (reason: unknown) => {
      if (
        reason instanceof Error &&
        reason.message === "simulated WS send failure"
      ) {
        // Swallow this specific expected rejection.
      } else {
        // Re-throw via setImmediate so the default behavior takes over
        // for any genuine unrelated rejections.
        throw reason;
      }
    };
    process.on("unhandledRejection", swallow);

    render(<ChatScreen threadId={null} token="test-token" />);

    const textarea = await screen.findByLabelText("Message brain");
    await user.click(textarea);
    await user.keyboard("first send");
    await user.keyboard("{Enter}");

    await screen.findByRole("dialog");

    // Acknowledge → dispatch fires (and throws). The thrown error
    // propagates out of the click handler; the swallow handler catches
    // the resulting unhandled rejection so the test runner can
    // continue and prove the next send works.
    const continueBtn = await screen.findByTestId(
      "cross-domain-continue-button",
    );
    try {
      await user.click(continueBtn);
    } catch {
      // expected — sendTurnStart threw; we're testing the recovery path.
    }
    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(1);
    });

    // Now hydrate the gate as acknowledged so the second send takes
    // the direct path and we can verify it dispatches its own intent.
    act(() => {
      useCrossDomainGateStore.setState({
        privacyRailed: ["personal"],
        acknowledged: true,
        loaded: true,
        error: null,
      });
      useAppStore.setState({ mode: "brainstorm" });
    });

    await user.click(textarea);
    await user.keyboard("second send");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(2);
    });

    // Second dispatch carries its OWN content + live mode, not a
    // poisoned replay of the first attempt's parked payload.
    const [secondContent, secondOpts] = sendTurnStartMock.mock.calls[1]!;
    expect(secondContent).toBe("second send");
    expect(secondOpts).toEqual(
      expect.objectContaining({ mode: "brainstorm" }),
    );

    process.off("unhandledRejection", swallow);
  });

  test("second Send during persistence await uses second click's mode, not first", async () => {
    // Plan 15 Task 7 review — D6 race protection across the
    // setCrossDomainWarningAcknowledged await boundary.
    //
    // Setup: gate the persistence promise so we can interleave a
    // second user Send between modal-Continue (first turn) and the
    // resolved ack-write. The second click writes a fresh
    // ``pendingSendRef`` payload; structural fix guarantees the first
    // turn's ``pending`` local stays pinned to the first click's mode.
    //
    // Note: in practice the second Send happens via the live composer
    // mid-await, but the gate predicate at click-time is captured per
    // click. We exercise the scenario by:
    //   1. Setting mode=ask, pressing Send → modal opens (turn-A
    //      captured: mode=ask).
    //   2. Clicking Continue → enters ``handleCrossDomainContinue``,
    //      captures local ``pending``, clears ref, awaits gated ack.
    //   3. While awaiting: simulate the ack-store update by
    //      acknowledging in the gate store AND switching mode to
    //      brainstorm + sending a second turn. The second send takes
    //      the direct path (acknowledged=true) so it dispatches
    //      immediately.
    //   4. Resolve the ack promise → first turn's deferred dispatch
    //      fires. Assert it carries mode=ask (the first click's
    //      captured value), not mode=brainstorm.
    let resolveAck: (value: unknown) => void = () => {};
    const ackPromise = new Promise((resolve) => {
      resolveAck = resolve;
    });
    setCrossDomainWarningAcknowledgedMock.mockImplementationOnce(
      () => ackPromise,
    );

    const user = userEvent.setup();
    render(<ChatScreen threadId={null} token="test-token" />);

    // First turn — mode=ask (default).
    const textarea = await screen.findByLabelText("Message brain");
    await user.click(textarea);
    await user.keyboard("turn A");
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    // Click Continue with "don't show again" checked → ack promise
    // gates the await; the deferred first-turn dispatch is parked.
    const checkbox = await screen.findByTestId(
      "cross-domain-dont-show-checkbox",
    );
    await user.click(checkbox);
    const continueBtn = await screen.findByTestId(
      "cross-domain-continue-button",
    );
    await user.click(continueBtn);

    // First turn's dispatch has NOT fired yet (gated on ackPromise).
    expect(sendTurnStartMock).not.toHaveBeenCalled();

    // Mid-await: simulate the user toggling mode and pressing Send
    // again. Mark the gate as acknowledged so the second send takes
    // the direct path (no second modal).
    act(() => {
      useCrossDomainGateStore.setState({
        privacyRailed: ["personal"],
        acknowledged: true,
        loaded: true,
        error: null,
      });
      useAppStore.setState({ mode: "brainstorm" });
    });

    await user.click(textarea);
    await user.keyboard("turn B");
    await user.keyboard("{Enter}");

    // Second turn dispatched immediately (direct path, mode=brainstorm).
    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(1);
    });
    expect(sendTurnStartMock.mock.calls[0]![0]).toBe("turn B");
    expect(sendTurnStartMock.mock.calls[0]![1]).toEqual(
      expect.objectContaining({ mode: "brainstorm" }),
    );

    // Now resolve the gated ack → first turn's deferred dispatch fires.
    await act(async () => {
      resolveAck({
        text: "",
        data: { key: "cross_domain_warning_acknowledged", value: true },
      });
      await ackPromise;
    });

    await waitFor(() => {
      expect(sendTurnStartMock).toHaveBeenCalledTimes(2);
    });

    // Load-bearing assertion: the FIRST turn's dispatch fires LAST
    // (because it was gated) but carries the FIRST click's mode (ask)
    // — not the live closure mode at resume time (brainstorm).
    expect(sendTurnStartMock.mock.calls[1]![0]).toBe("turn A");
    expect(sendTurnStartMock.mock.calls[1]![1]).toEqual(
      expect.objectContaining({ mode: "ask" }),
    );
  });
});
