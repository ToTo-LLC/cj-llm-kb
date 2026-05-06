/**
 * Plan 16 Task 6 / D6 — domains-store BroadcastChannel cross-tab
 * pubsub pin.
 *
 * Pre-Plan-16 the store was a per-tab cache: tab A could mutate
 * ``Config.active_domain`` and tab B's topbar/Settings would still
 * show the stale value until a manual reload. Plan 13 Task 3 review
 * I3 flagged this as a hypothetical-but-known optimistic-clobber
 * race; Plan 16 D6 closes the class by adding a thin module-private
 * pubsub layer to BOTH ``domains-store.ts`` AND
 * ``cross-domain-gate-store.ts``.
 *
 * What this file pins:
 *
 *   1. **Outbound: mutation broadcasts.** ``setActiveDomainOptimistic``,
 *      ``removeDomainOptimistic``, and ``refresh()`` all post their
 *      resolved state to the ``"brain-domains"`` channel.
 *   2. **Inbound: peer payload applies without echo.** A simulated
 *      "peer tab" channel posting ``{domains, activeDomain}`` updates
 *      the store WITHOUT triggering a re-broadcast (no ping-pong).
 *   3. **SSR safety.** When ``BroadcastChannel`` is undefined
 *      (Node SSR), the helper returns no-ops and store mutations
 *      don't throw.
 *   4. **100ms tab-A → tab-B latency budget.** Per the plan's
 *      success criterion, peer updates surface within 100ms.
 *
 * Test architecture: jsdom 25 ships a working BroadcastChannel
 * implementation that follows the spec (sender does NOT receive its
 * own postMessage). We simulate "tab B" by constructing a separate
 * ``new BroadcastChannel("brain-domains")`` in test code and
 * posting through it; the store (the simulated "tab A") receives
 * via its own internal channel and applies via ``_internalSet``.
 *
 * The reverse direction (store-mutation → peer-channel-receive) is
 * also tested: a separate BroadcastChannel instance with the same
 * name receives the store's outbound posts.
 */

import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";

const { listDomainsMock } = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
}));

import {
  useDomainsStore,
  DOMAINS_BROADCAST_CHANNEL,
  type DomainEntry,
} from "@/lib/state/domains-store";

/** Helper: a peer-tab channel for posting INTO the store and for
 *  observing OUTBOUND store posts. The store's own channel is held
 *  privately inside ``domains-store.ts``; this is the test seam. */
function makePeerChannel(): BroadcastChannel {
  return new BroadcastChannel(DOMAINS_BROADCAST_CHANNEL);
}

/** Wait for a condition to be observed within ``timeoutMs``. Used
 *  for the 100ms latency budget assertions. Polls every 5ms; if the
 *  condition fires earlier, returns immediately. */
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
  listDomainsMock.mockReset();
  // ``_resetForTesting`` clears the store + the in-flight Promise +
  // closes any held BroadcastChannel so the next ``post`` in the
  // store rebuilds a fresh channel bound to the current jsdom realm.
  useDomainsStore.getState()._resetForTesting();
});

describe("domains-store BroadcastChannel — outbound posts (mutation broadcasts)", () => {
  test("setActiveDomainOptimistic posts the new active domain to peers", async () => {
    const peer = makePeerChannel();
    const messages: Array<{ domains: DomainEntry[]; activeDomain: string }> = [];
    peer.onmessage = (e) => messages.push(e.data);

    // Seed the store with a couple of domains so the broadcast
    // payload's ``domains`` field is non-empty (matches the
    // production shape where a refresh has resolved before the
    // optimistic mutation fires).
    useDomainsStore.setState({
      domains: [
        { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
        { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
      ],
      activeDomain: "research",
      loaded: true,
      error: null,
    });

    useDomainsStore.getState().setActiveDomainOptimistic("work");

    // Within the 100ms latency budget the peer channel observes the
    // new active domain. (jsdom's BroadcastChannel delivers via
    // microtask-then-macrotask; a few ms is the typical floor.)
    await waitForCondition(() => messages.length > 0, 100);
    expect(messages).toHaveLength(1);
    expect(messages[0]!.activeDomain).toBe("work");
    expect(messages[0]!.domains.map((d) => d.slug)).toEqual([
      "research",
      "work",
    ]);

    peer.close();
  });

  test("removeDomainOptimistic posts the post-filter domains list", async () => {
    const peer = makePeerChannel();
    const messages: Array<{ domains: DomainEntry[]; activeDomain: string }> = [];
    peer.onmessage = (e) => messages.push(e.data);

    useDomainsStore.setState({
      domains: [
        { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
        { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
        { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
      ],
      activeDomain: "research",
      loaded: true,
      error: null,
    });

    useDomainsStore.getState().removeDomainOptimistic("work");

    await waitForCondition(() => messages.length > 0, 100);
    expect(messages).toHaveLength(1);
    // Broadcast carries the AFTER-filter list so peer tabs see the
    // row drop without computing the diff themselves.
    expect(messages[0]!.domains.map((d) => d.slug)).toEqual([
      "research",
      "personal",
    ]);
    expect(messages[0]!.activeDomain).toBe("research");

    peer.close();
  });

  test("refresh() posts the API-resolved view on success", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        entries: [
          { slug: "research", configured: true, on_disk: true },
          { slug: "work", configured: true, on_disk: true },
        ],
        active_domain: "work",
      },
    });

    const peer = makePeerChannel();
    const messages: Array<{ domains: DomainEntry[]; activeDomain: string }> = [];
    peer.onmessage = (e) => messages.push(e.data);

    await useDomainsStore.getState().refresh();

    await waitForCondition(() => messages.length > 0, 100);
    expect(messages).toHaveLength(1);
    expect(messages[0]!.activeDomain).toBe("work");
    expect(messages[0]!.domains.map((d) => d.slug)).toEqual([
      "research",
      "work",
    ]);

    peer.close();
  });

  test("refresh() failure does NOT post (errors are per-tab transport state)", async () => {
    listDomainsMock.mockRejectedValue(new Error("boom"));

    const peer = makePeerChannel();
    const messages: unknown[] = [];
    peer.onmessage = (e) => messages.push(e.data);

    await useDomainsStore.getState().refresh();
    // Brief wait to give any spurious post a chance to fire.
    await new Promise((r) => setTimeout(r, 50));

    expect(messages).toHaveLength(0);
    peer.close();
  });
});

describe("domains-store BroadcastChannel — inbound peer apply (no echo)", () => {
  test("inbound peer post updates the store within 100ms", async () => {
    // Track outbound posts so we can assert the inbound apply does
    // NOT echo. ``observer`` is a SECOND peer channel; its onmessage
    // fires for any post EXCEPT its own — including the store's
    // outbound posts AND our peer's outbound post.
    const observer = makePeerChannel();
    const observed: Array<{ domains: DomainEntry[]; activeDomain: string }> = [];
    observer.onmessage = (e) => observed.push(e.data);

    const peer = makePeerChannel();
    const payload = {
      domains: [
        {
          slug: "research",
          label: "Research",
          accent: "var(--dom-research)",
          configured: true,
          on_disk: true,
        },
      ],
      activeDomain: "research",
    };
    peer.postMessage(payload);

    // The store's onmessage fires asynchronously — wait until the
    // store reflects the inbound payload. 100ms latency budget per
    // the plan's success criterion.
    await waitForCondition(
      () => useDomainsStore.getState().activeDomain === "research",
      100,
    );

    const s = useDomainsStore.getState();
    expect(s.domains.map((d) => d.slug)).toEqual(["research"]);
    expect(s.activeDomain).toBe("research");

    // Critical: the store applied the peer payload via ``_internalSet``
    // and did NOT re-broadcast. ``observer`` (a third channel) sees
    // ONE message — the peer's original — and NOT a second echo from
    // the store. Without the ``_isInternalUpdate`` guard, two tabs
    // would ping-pong forever.
    await new Promise((r) => setTimeout(r, 50));
    // ``observed`` sees exactly the peer's post (channels don't see
    // their own posts, but observer is distinct from peer so it does).
    // It must NOT see a re-broadcast from the store.
    expect(observed).toHaveLength(1);
    expect(observed[0]!.activeDomain).toBe("research");

    peer.close();
    observer.close();
  });

  test("inbound apply does NOT touch loaded or error fields", async () => {
    // ``loaded`` and ``error`` are intentionally per-tab transport
    // state; the broadcast payload doesn't carry them. Pin that an
    // inbound apply never accidentally flips ``loaded`` or clears
    // ``error``.
    useDomainsStore.setState({
      domains: [],
      activeDomain: "",
      loaded: false,
      error: new Error("prior failure"),
    });

    const peer = makePeerChannel();
    peer.postMessage({
      domains: [
        {
          slug: "work",
          label: "Work",
          accent: "var(--dom-work)",
          configured: true,
          on_disk: true,
        },
      ],
      activeDomain: "work",
    });

    await waitForCondition(
      () => useDomainsStore.getState().activeDomain === "work",
      100,
    );

    const s = useDomainsStore.getState();
    expect(s.domains.map((d) => d.slug)).toEqual(["work"]);
    expect(s.activeDomain).toBe("work");
    // Untouched: receiving an inbound payload doesn't mean THIS tab
    // has confirmed the data with the backend itself.
    expect(s.loaded).toBe(false);
    expect(s.error?.message).toBe("prior failure");

    peer.close();
  });
});

describe("domains-store BroadcastChannel — SSR / unsupported environments", () => {
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

  test("store mutations don't throw when BroadcastChannel is undefined", async () => {
    // Simulate Node SSR: drop the global BroadcastChannel BEFORE the
    // store rebuilds its internal channel. The helper's ``typeof
    // BroadcastChannel === "undefined"`` guard then returns a no-op
    // pubsub so store mutations stay silent but don't throw.
    //
    // Order matters: delete BC first, then reset (which triggers
    // ``ensureChannel()`` against the now-undefined global). Without
    // this ordering the cached channel from the previous test would
    // still be live and the SSR path wouldn't actually be exercised.
    delete (globalThis as { BroadcastChannel?: typeof BroadcastChannel })
      .BroadcastChannel;
    useDomainsStore.getState()._resetForTesting();

    // ``setActiveDomainOptimistic`` would normally call ``post()``;
    // with BroadcastChannel undefined the helper returns no-ops and
    // ``post()`` is silent. The state update itself still happens.
    expect(() => {
      useDomainsStore.getState().setActiveDomainOptimistic("research");
    }).not.toThrow();

    // The store's own state update succeeded even without
    // BroadcastChannel.
    expect(useDomainsStore.getState().activeDomain).toBe("research");
  });
});
