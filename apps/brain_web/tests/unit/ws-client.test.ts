import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { BrainWebSocket } from "@/lib/ws/client";
import { SCHEMA_VERSION, type ServerEvent } from "@/lib/ws/events";

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
    // no-op for tests
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

beforeEach(() => {
  MockWebSocket.reset();
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BrainWebSocket", () => {
  test("connect() opens WS with the expected URL + token + thread_id", () => {
    const events: ServerEvent[] = [];
    const ws = new BrainWebSocket({
      threadId: "thread abc/1",
      token: "tok?n&special",
      onEvent: (e) => events.push(e),
    });
    ws.connect();

    expect(MockWebSocket.instances).toHaveLength(1);
    const url = MockWebSocket.instances[0]!.url;
    expect(url.startsWith("ws://")).toBe(true);
    // Plan 08 Task 2: same-origin — host comes from ``window.location.host``.
    // In jsdom's default environment that's ``localhost:3000``.
    expect(url).toContain(window.location.host);
    expect(url).toContain("/ws/chat/");
    // Thread + token must be URL-encoded.
    expect(url).toContain(encodeURIComponent("thread abc/1"));
    expect(url).toContain(`token=${encodeURIComponent("tok?n&special")}`);
  });

  test("schema_version mismatch triggers the mismatch callback", () => {
    const mismatches: string[] = [];
    const events: ServerEvent[] = [];
    const ws = new BrainWebSocket({
      threadId: "t1",
      token: "tok",
      onEvent: (e) => events.push(e),
      onSchemaVersionMismatch: (v) => mismatches.push(v),
    });
    ws.connect();
    const mock = MockWebSocket.instances[0]!;
    mock.simulateOpen();

    // Pinned version "2" vs server saying "3" -> mismatch fires.
    mock.simulateMessage({ type: "schema_version", version: "3" });
    expect(mismatches).toEqual(["3"]);

    // Matching version -> mismatch NOT called.
    mock.simulateMessage({ type: "schema_version", version: SCHEMA_VERSION });
    expect(mismatches).toEqual(["3"]);

    // Every parsed event still fans out to onEvent (mismatch is advisory).
    expect(events.filter((e) => e.type === "schema_version")).toHaveLength(2);
  });

  test("send() serialises typed client messages", () => {
    const ws = new BrainWebSocket({
      threadId: "t1",
      token: "tok",
      onEvent: () => {},
    });
    ws.connect();
    const mock = MockWebSocket.instances[0]!;
    mock.simulateOpen();

    ws.send({ type: "cancel_turn" });
    ws.send({ type: "switch_mode", mode: "draft" });

    expect(mock.send).toHaveBeenCalledTimes(2);
    expect(JSON.parse(mock.send.mock.calls[0]![0])).toEqual({
      type: "cancel_turn",
    });
    expect(JSON.parse(mock.send.mock.calls[1]![0])).toEqual({
      type: "switch_mode",
      mode: "draft",
    });
  });

  test("close() suppresses reconnect and does not reopen on late timer", () => {
    vi.useFakeTimers();
    const closeSignals: boolean[] = [];
    const ws = new BrainWebSocket({
      threadId: "t1",
      token: "tok",
      onEvent: () => {},
      onClose: (clean) => closeSignals.push(clean),
      reconnectBaseMs: 10,
      reconnectMaxMs: 1000,
    });
    ws.connect();
    const first = MockWebSocket.instances[0]!;
    first.simulateOpen();

    // Simulate an abnormal drop so a reconnect would normally be scheduled.
    first.simulateClose(1006);
    expect(closeSignals).toEqual([false]);

    // Now the user tears down — pending reconnect must NOT fire.
    ws.close();

    // Advance past the backoff window; no new MockWebSocket should appear.
    vi.advanceTimersByTime(5_000);
    expect(MockWebSocket.instances).toHaveLength(1);

    // Re-calling close is idempotent and doesn't throw.
    expect(() => ws.close()).not.toThrow();
  });
});
