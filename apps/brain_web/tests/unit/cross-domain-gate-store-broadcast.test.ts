/**
 * Plan 16 Task 6 / D6 — cross-domain-gate-store BroadcastChannel
 * cross-tab pubsub pin.
 *
 * Mirrors ``domains-store-broadcast.test.ts``. Pre-Plan-16 the
 * cross-domain gate store was a per-tab cache: tab A's Settings
 * toggle could flip ``Config.cross_domain_warning_acknowledged``
 * and tab B's chat-screen ``shouldFireCrossDomainModal`` would
 * still fire the modal until a manual reload. Plan 13 Task 3
 * review I3 flagged this as a hypothetical-but-known optimistic-
 * clobber race; Plan 16 D6 closes the class for both stores.
 *
 * What this file pins:
 *
 *   1. **Outbound: mutation broadcasts.** ``setAcknowledgedOptimistic``
 *      and ``refresh()`` post their resolved state to the
 *      ``"brain-cross-domain-gate"`` channel.
 *   2. **Inbound: peer payload applies without echo.** A simulated
 *      "peer tab" channel posting ``{privacyRailed, acknowledged}``
 *      updates the store WITHOUT triggering a re-broadcast (no
 *      ping-pong).
 *   3. **SSR safety.** When ``BroadcastChannel`` is undefined,
 *      store mutations don't throw.
 *   4. **100ms tab-A → tab-B latency budget.**
 */

import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";

const { configGetMock } = vi.hoisted(() => ({
  configGetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
}));

import {
  useCrossDomainGateStore,
  CROSS_DOMAIN_GATE_BROADCAST_CHANNEL,
} from "@/lib/state/cross-domain-gate-store";

function makePeerChannel(): BroadcastChannel {
  return new BroadcastChannel(CROSS_DOMAIN_GATE_BROADCAST_CHANNEL);
}

async function waitForCondition(
  predicate: () => boolean,
  timeoutMs = 100,
): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error(
        `Condition not met within ${timeoutMs}ms (predicate stayed false)`,
      );
    }
    await new Promise((r) => setTimeout(r, 5));
  }
}

beforeEach(() => {
  configGetMock.mockReset();
  useCrossDomainGateStore.getState()._resetForTesting();
});

describe("cross-domain-gate-store BroadcastChannel — outbound posts", () => {
  test("setAcknowledgedOptimistic posts the new acknowledged value", async () => {
    const peer = makePeerChannel();
    const messages: Array<{ privacyRailed: string[]; acknowledged: boolean }> =
      [];
    peer.onmessage = (e) => messages.push(e.data);

    // Seed the store so the broadcast carries a non-default
    // privacyRailed list (matches production where a refresh has
    // resolved before the toggle fires).
    useCrossDomainGateStore.setState({
      privacyRailed: ["personal", "journal"],
      acknowledged: false,
      loaded: true,
      error: null,
    });

    useCrossDomainGateStore.getState().setAcknowledgedOptimistic(true);

    await waitForCondition(() => messages.length > 0, 100);
    expect(messages).toHaveLength(1);
    expect(messages[0]!.acknowledged).toBe(true);
    expect(messages[0]!.privacyRailed).toEqual(["personal", "journal"]);

    peer.close();
  });

  test("setAcknowledgedOptimistic noop (value unchanged) does NOT post", async () => {
    useCrossDomainGateStore.setState({
      privacyRailed: ["personal"],
      acknowledged: true,
      loaded: true,
      error: null,
    });

    const peer = makePeerChannel();
    const messages: unknown[] = [];
    peer.onmessage = (e) => messages.push(e.data);

    useCrossDomainGateStore.getState().setAcknowledgedOptimistic(true);
    await new Promise((r) => setTimeout(r, 50));

    // Early-return pattern (D7 closure) — the unchanged value
    // means no ``set`` AND no ``post``. Peer tabs don't see a
    // spurious re-broadcast on every redundant toggle.
    expect(messages).toHaveLength(0);
    peer.close();
  });

  test("refresh() posts the API-resolved view on success", async () => {
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal", "journal"] },
        });
      }
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: true },
        });
      }
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: null },
      });
    });

    const peer = makePeerChannel();
    const messages: Array<{ privacyRailed: string[]; acknowledged: boolean }> =
      [];
    peer.onmessage = (e) => messages.push(e.data);

    await useCrossDomainGateStore.getState().refresh();

    await waitForCondition(() => messages.length > 0, 100);
    expect(messages).toHaveLength(1);
    expect(messages[0]!.privacyRailed).toEqual(["personal", "journal"]);
    expect(messages[0]!.acknowledged).toBe(true);

    peer.close();
  });

  test("refresh() failure does NOT post (errors are per-tab transport state)", async () => {
    configGetMock.mockRejectedValue(new Error("backend down"));

    const peer = makePeerChannel();
    const messages: unknown[] = [];
    peer.onmessage = (e) => messages.push(e.data);

    await useCrossDomainGateStore.getState().refresh();
    await new Promise((r) => setTimeout(r, 50));

    expect(messages).toHaveLength(0);
    peer.close();
  });
});

describe("cross-domain-gate-store BroadcastChannel — inbound peer apply (no echo)", () => {
  test("inbound peer post updates the store within 100ms", async () => {
    const observer = makePeerChannel();
    const observed: Array<{ privacyRailed: string[]; acknowledged: boolean }> =
      [];
    observer.onmessage = (e) => observed.push(e.data);

    const peer = makePeerChannel();
    const payload = {
      privacyRailed: ["personal", "journal"],
      acknowledged: true,
    };
    peer.postMessage(payload);

    await waitForCondition(
      () => useCrossDomainGateStore.getState().acknowledged === true,
      100,
    );

    const s = useCrossDomainGateStore.getState();
    expect(s.privacyRailed).toEqual(["personal", "journal"]);
    expect(s.acknowledged).toBe(true);

    // No echo: the store applied the peer payload via
    // ``_internalSet`` and did NOT re-broadcast. ``observer`` (a
    // distinct channel) sees ONE message — the peer's original —
    // and NOT a second echo from the store.
    await new Promise((r) => setTimeout(r, 50));
    expect(observed).toHaveLength(1);
    expect(observed[0]!.acknowledged).toBe(true);

    peer.close();
    observer.close();
  });

  test("inbound apply does NOT touch loaded or error fields", async () => {
    useCrossDomainGateStore.setState({
      privacyRailed: ["personal"],
      acknowledged: false,
      loaded: false,
      error: new Error("prior failure"),
    });

    const peer = makePeerChannel();
    peer.postMessage({
      privacyRailed: ["personal", "journal"],
      acknowledged: true,
    });

    await waitForCondition(
      () => useCrossDomainGateStore.getState().acknowledged === true,
      100,
    );

    const s = useCrossDomainGateStore.getState();
    expect(s.privacyRailed).toEqual(["personal", "journal"]);
    expect(s.acknowledged).toBe(true);
    // Untouched per the broadcast-payload contract.
    expect(s.loaded).toBe(false);
    expect(s.error?.message).toBe("prior failure");

    peer.close();
  });
});

describe("cross-domain-gate-store BroadcastChannel — SSR / unsupported environments", () => {
  let savedBC: typeof BroadcastChannel | undefined;

  beforeEach(() => {
    savedBC = globalThis.BroadcastChannel;
  });

  afterEach(() => {
    if (savedBC) {
      (globalThis as unknown as { BroadcastChannel: typeof BroadcastChannel })
        .BroadcastChannel = savedBC;
    }
  });

  test("store mutations don't throw when BroadcastChannel is undefined", () => {
    // Order matters: delete BC first, then reset (which triggers
    // ``ensureChannel()`` against the now-undefined global) — see
    // ``domains-store-broadcast.test.ts``'s matching docstring.
    delete (globalThis as { BroadcastChannel?: typeof BroadcastChannel })
      .BroadcastChannel;
    useCrossDomainGateStore.getState()._resetForTesting();

    // The store has acknowledged=false initially, so set to true
    // exercises the ``post`` path (early-return only fires when
    // value is unchanged).
    expect(() => {
      useCrossDomainGateStore.getState().setAcknowledgedOptimistic(true);
    }).not.toThrow();

    expect(useCrossDomainGateStore.getState().acknowledged).toBe(true);
  });
});

describe("cross-domain-gate-store BroadcastChannel — channel name distinctness", () => {
  test("channel name does NOT collide with domains-store's channel", async () => {
    // Defense-in-depth: post to ``brain-domains`` and confirm the
    // cross-domain gate store ignores it. Without distinct channel
    // names, a domains-store payload would be deserialized as a
    // cross-domain-gate payload and corrupt store state.
    const wrongChannel = new BroadcastChannel("brain-domains");
    wrongChannel.postMessage({
      // Shape that LOOKS plausible but isn't this store's payload.
      domains: [{ slug: "research" }],
      activeDomain: "research",
    });

    await new Promise((r) => setTimeout(r, 50));

    // Cross-domain gate store stays at its zero-state because the
    // wrong channel doesn't reach it.
    const s = useCrossDomainGateStore.getState();
    expect(s.privacyRailed).toEqual(["personal"]);
    expect(s.acknowledged).toBe(false);
    expect(s.loaded).toBe(false);

    wrongChannel.close();
  });
});
