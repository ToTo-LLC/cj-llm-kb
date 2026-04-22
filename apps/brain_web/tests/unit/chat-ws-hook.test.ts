import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { useChatWebSocket } from "@/lib/ws/hooks";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useSystemStore } from "@/lib/state/system-store";
import type { ServerEvent } from "@/lib/ws/events";

/**
 * useChatWebSocket (Plan 07 Task 15): the per-thread hook that owns the
 * BrainWebSocket lifecycle and exposes four send methods —
 *   sendTurnStart / cancelTurn / switchMode / setOpenDoc.
 *
 * The hook guards against sending mid-stream client messages that the
 * backend would reject with invalid_state: a second turn_start while
 * streaming, or a switch_mode while streaming. Both raise a mid-turn
 * toast (invalid-state-turn / invalid-state-mode) instead of reaching
 * the wire. The app-store reducer also guards setMode — tested
 * separately in app-store tests.
 *
 * BrainWebSocket is mocked so tests can inspect .send() and fire onOpen
 * / onEvent / onClose without standing up a socket.
 */

type Listener = (evt: Record<string, unknown>) => void;

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  static instances: MockWebSocket[] = [];
  static reset(): void {
    MockWebSocket.instances = [];
  }

  readonly url: string;
  readyState = MockWebSocket.CONNECTING;
  send = vi.fn<(data: string) => void>();
  close = vi.fn<(code?: number, reason?: string) => void>(
    (_code?: number, _reason?: string) => {
      this.readyState = MockWebSocket.CLOSED;
    },
  );
  private readonly listeners: Record<string, Listener[]> = {};

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: Listener): void {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener];
  }

  removeEventListener(): void {
    // no-op
  }

  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    (this.listeners.open ?? []).forEach((fn) => fn({}));
  }

  simulateMessage(data: unknown): void {
    (this.listeners.message ?? []).forEach((fn) =>
      fn({ data: JSON.stringify(data) }),
    );
  }

  simulateClose(code = 1000): void {
    this.readyState = MockWebSocket.CLOSED;
    (this.listeners.close ?? []).forEach((fn) => fn({ code }));
  }
}

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
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    toasts: [],
  });
}

beforeEach(() => {
  MockWebSocket.reset();
  vi.stubGlobal("WebSocket", MockWebSocket);
  resetStores();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function openSocket(): MockWebSocket {
  const mock = MockWebSocket.instances[0];
  if (!mock) throw new Error("expected a mock WebSocket to be created");
  mock.simulateOpen();
  return mock;
}

describe("useChatWebSocket — send methods + invalid-state guards", () => {
  test("sendTurnStart sends a turn_start frame with content + mode + attached_sources", () => {
    const { result } = renderHook(() =>
      useChatWebSocket("thread-1", "tok-abc"),
    );
    const mock = openSocket();

    act(() => {
      result.current.sendTurnStart("hello vault", {
        mode: "brainstorm",
        attachedSources: ["src-1", "src-2"],
      });
    });

    expect(mock.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(mock.send.mock.calls[0]![0])).toEqual({
      type: "turn_start",
      content: "hello vault",
      mode: "brainstorm",
      attached_sources: ["src-1", "src-2"],
    });
    // Optimistic user-message append so the transcript reflects the send.
    const transcript = useChatStore.getState().transcript;
    expect(transcript.at(-1)?.body).toBe("hello vault");
  });

  test("cancelTurn sends a cancel_turn frame", () => {
    const { result } = renderHook(() =>
      useChatWebSocket("thread-1", "tok-abc"),
    );
    const mock = openSocket();

    act(() => {
      result.current.cancelTurn();
    });

    expect(mock.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(mock.send.mock.calls[0]![0])).toEqual({
      type: "cancel_turn",
    });
  });

  test("second sendTurnStart during streaming raises invalid-state-turn instead of sending", () => {
    const { result } = renderHook(() =>
      useChatWebSocket("thread-1", "tok-abc"),
    );
    const mock = openSocket();

    // Start the first turn — backend-side streaming begins when turn_start
    // comes back. We simulate that via the reducer.
    act(() => {
      result.current.sendTurnStart("first turn");
    });
    expect(mock.send).toHaveBeenCalledTimes(1);

    // Streaming flag flips on (backend would send turn_start back).
    act(() => {
      useChatStore.getState().onTurnStart({ type: "turn_start", turn_number: 1 });
    });
    expect(useChatStore.getState().streaming).toBe(true);

    // A second attempt must NOT reach the socket; mid-turn toast fires.
    act(() => {
      result.current.sendTurnStart("second turn");
    });
    expect(mock.send).toHaveBeenCalledTimes(1);
    expect(useSystemStore.getState().midTurn).toBe("invalid-state-turn");
  });

  test("switchMode during streaming raises invalid-state-mode and does not send", () => {
    const { result } = renderHook(() =>
      useChatWebSocket("thread-1", "tok-abc"),
    );
    const mock = openSocket();

    // Put the chat in a streaming state.
    act(() => {
      useChatStore.getState().onTurnStart({ type: "turn_start", turn_number: 1 });
    });
    expect(useChatStore.getState().streaming).toBe(true);

    act(() => {
      result.current.switchMode("draft");
    });
    // Nothing went on the wire; mid-turn toast fired; mode unchanged.
    expect(mock.send).not.toHaveBeenCalled();
    expect(useSystemStore.getState().midTurn).toBe("invalid-state-mode");
    expect(useAppStore.getState().mode).toBe("ask");
  });

  test("switchMode between turns sends switch_mode and updates app-store mode", () => {
    const { result } = renderHook(() =>
      useChatWebSocket("thread-1", "tok-abc"),
    );
    const mock = openSocket();

    // Not streaming; switch mode is legal.
    act(() => {
      result.current.switchMode("draft");
    });

    expect(mock.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(mock.send.mock.calls[0]![0])).toEqual({
      type: "switch_mode",
      mode: "draft",
    });
    expect(useAppStore.getState().mode).toBe("draft");
  });

  test("pendingAttachedSources are propagated with sendTurnStart and cleared on successful send", () => {
    useChatStore.getState().addAttachedSource("research/paper-1.md");
    useChatStore.getState().addAttachedSource("research/paper-2.md");
    expect(useChatStore.getState().pendingAttachedSources).toEqual([
      "research/paper-1.md",
      "research/paper-2.md",
    ]);

    const { result } = renderHook(() =>
      useChatWebSocket("thread-1", "tok-abc"),
    );
    const mock = openSocket();

    act(() => {
      result.current.sendTurnStart("use my sources", {
        attachedSources: useChatStore.getState().pendingAttachedSources,
      });
    });

    expect(mock.send).toHaveBeenCalledTimes(1);
    const sent = JSON.parse(mock.send.mock.calls[0]![0]) as ServerEvent & {
      attached_sources: string[];
    };
    expect(sent.attached_sources).toEqual([
      "research/paper-1.md",
      "research/paper-2.md",
    ]);
    // The hook clears attached sources after a successful send so the
    // next turn doesn't re-send them.
    expect(useChatStore.getState().pendingAttachedSources).toEqual([]);
  });
});
