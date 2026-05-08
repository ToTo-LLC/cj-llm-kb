/**
 * Plan 16 Task 43 / D32(b) — useBudgetStore (zustand) contract.
 *
 * Pins the budget-store surface so the Settings → Budget tab and the
 * per-domain Budget caps subsection (and any future cost-pip displays)
 * can rely on a stable cross-instance reactivity model:
 *
 *   1. Fresh store has the documented zero-state.
 *   2. ``refresh()`` populates from four parallel ``configGet`` reads;
 *      failure lands on ``error`` without flipping ``loaded``.
 *   3. Optimistic mutators (``setDailyCap`` / ``setMonthlyCap`` /
 *      ``setDomainCap``) update the snapshot before the round-trip
 *      resolves; on failure they revert AND surface the error.
 *   4. Concurrent ``refresh()`` calls share one in-flight Promise.
 *   5. Outbound: every mutation broadcasts to peer tabs via the
 *      ``"brain-budget"`` BroadcastChannel.
 *   6. Inbound: peer payloads apply via ``_internalSet`` and do NOT
 *      re-broadcast (no ping-pong).
 *
 * Mirrors the canonical ``domains-store-broadcast.test.ts`` +
 * ``use-domains-store.test.ts`` shape exactly.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";

const { configGetMock, configSetMock } = vi.hoisted(() => ({
  configGetMock: vi.fn(),
  configSetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
  configSet: configSetMock,
}));

import {
  useBudgetStore,
  BUDGET_BROADCAST_CHANNEL,
  type BudgetSnapshot,
} from "@/lib/state/budget-store";

/** Helper: simulate a peer-tab BroadcastChannel for posting INTO the
 *  store and observing OUTBOUND store posts. The store's own channel
 *  is held privately; this is the test seam (matches
 *  ``domains-store-broadcast.test.ts`` precisely). */
function makePeerChannel(): BroadcastChannel {
  return new BroadcastChannel(BUDGET_BROADCAST_CHANNEL);
}

/** Wait for a condition within ``timeoutMs``. Polls every 5ms; returns
 *  immediately on success. Used for the broadcast-latency assertions. */
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

/** Default ``configGet`` mock for the four parallel keys ``refresh()``
 *  reads. Specific tests override per-key by reading the ``key`` arg. */
function mockBudgetGets(snapshot: Partial<BudgetSnapshot>): void {
  configGetMock.mockImplementation((args: { key: string }) => {
    switch (args.key) {
      case "budget.daily_usd":
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: snapshot.daily_usd ?? null },
        });
      case "budget.monthly_usd":
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: snapshot.monthly_usd ?? null },
        });
      case "budget.alert_threshold_pct":
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: snapshot.alert_threshold_pct ?? null },
        });
      case "budget.per_domain":
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: snapshot.per_domain ?? {} },
        });
      default:
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: null },
        });
    }
  });
}

beforeEach(() => {
  configGetMock.mockReset();
  configSetMock.mockReset();
  // ``_resetForTesting`` clears the store + the in-flight Promise +
  // closes any held BroadcastChannel so the next ``post`` rebuilds a
  // fresh channel bound to the current jsdom realm.
  useBudgetStore.getState()._resetForTesting();
});

describe("useBudgetStore — fresh state", () => {
  test("returns the documented zero-state on first read", () => {
    const s = useBudgetStore.getState();
    expect(s.snapshot.daily_usd).toBeNull();
    expect(s.snapshot.monthly_usd).toBeNull();
    expect(s.snapshot.alert_threshold_pct).toBeNull();
    expect(s.snapshot.per_domain).toEqual({});
    expect(s.loaded).toBe(false);
    expect(s.error).toBeNull();
  });
});

describe("useBudgetStore — refresh()", () => {
  test("hydrates snapshot from four parallel configGet reads", async () => {
    mockBudgetGets({
      daily_usd: 5,
      monthly_usd: 100,
      alert_threshold_pct: 80,
      per_domain: {
        research: { daily_cap_usd: 2, monthly_cap_usd: 40 },
      },
    });

    await useBudgetStore.getState().refresh();

    const s = useBudgetStore.getState();
    expect(s.snapshot.daily_usd).toBe(5);
    expect(s.snapshot.monthly_usd).toBe(100);
    expect(s.snapshot.alert_threshold_pct).toBe(80);
    expect(s.snapshot.per_domain).toEqual({
      research: { daily_cap_usd: 2, monthly_cap_usd: 40 },
    });
    expect(s.loaded).toBe(true);
    expect(s.error).toBeNull();
    // Four reads in parallel — one per Config.budget leaf.
    expect(configGetMock).toHaveBeenCalledTimes(4);
  });

  test("normalizes missing per_domain fields to null", async () => {
    // The wire shape may omit one of the cap fields; the helper coerces
    // missing fields to ``null`` so consumers don't have to repeat
    // optional-chaining.
    mockBudgetGets({
      per_domain: {
        // ``daily_cap_usd`` omitted — should be normalized to null.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        partial: { monthly_cap_usd: 30 } as any,
      },
    });

    await useBudgetStore.getState().refresh();

    expect(useBudgetStore.getState().snapshot.per_domain.partial).toEqual({
      daily_cap_usd: null,
      monthly_cap_usd: 30,
    });
  });

  test("records error on failed configGet (resolve-always semantics)", async () => {
    configGetMock.mockRejectedValue(new Error("network down"));

    // ``refresh()`` resolves cleanly even on failure — see
    // ``use-domains-store.test.ts`` for the same shape rationale.
    await useBudgetStore.getState().refresh();

    const s = useBudgetStore.getState();
    expect(s.error).toBeInstanceOf(Error);
    expect(s.error?.message).toBe("network down");
    expect(s.loaded).toBe(false);
  });

  test("concurrent refresh() calls share one in-flight Promise", async () => {
    // Each refresh() fans out into four parallel configGet calls.
    // We need ALL four to be unblockable at once so the in-flight
    // Promise can resolve. Capture every per-call resolver and resolve
    // them together at the end of the test.
    const resolvers: Array<(val: unknown) => void> = [];
    configGetMock.mockImplementation(
      (args: { key: string }) =>
        new Promise((resolve) => {
          resolvers.push((val) =>
            resolve(
              val ?? { text: "", data: { key: args.key, value: null } },
            ),
          );
        }),
    );

    const a = useBudgetStore.getState().refresh();
    const b = useBudgetStore.getState().refresh();

    // Same Promise reference — caller B got the in-flight cache entry.
    expect(a).toBe(b);
    // The fan-out fires exactly once across two concurrent refreshes:
    // four configGet calls (one per Config.budget leaf), not eight.
    expect(configGetMock).toHaveBeenCalledTimes(4);

    // Unblock all four parallel reads; both awaiters complete from the
    // same Promise.
    for (const resolve of resolvers) resolve(null);
    await Promise.all([a, b]);
    expect(configGetMock).toHaveBeenCalledTimes(4);
  });
});

describe("useBudgetStore — optimistic mutations", () => {
  test("setDailyCap optimistically updates then persists", async () => {
    useBudgetStore.setState({
      snapshot: {
        daily_usd: 1,
        monthly_usd: 50,
        alert_threshold_pct: 80,
        per_domain: {},
      },
      loaded: true,
    });
    configSetMock.mockResolvedValue({
      text: "",
      data: { key: "budget.daily_usd", value: 7 },
    });

    await useBudgetStore.getState().setDailyCap(7);

    expect(useBudgetStore.getState().snapshot.daily_usd).toBe(7);
    // Other fields untouched.
    expect(useBudgetStore.getState().snapshot.monthly_usd).toBe(50);
    expect(configSetMock).toHaveBeenCalledWith({
      key: "budget.daily_usd",
      value: 7,
    });
  });

  test("setDailyCap reverts + surfaces error on configSet failure", async () => {
    useBudgetStore.setState({
      snapshot: {
        daily_usd: 1,
        monthly_usd: 50,
        alert_threshold_pct: 80,
        per_domain: {},
      },
      loaded: true,
    });
    configSetMock.mockRejectedValue(new Error("validation failed"));

    await expect(useBudgetStore.getState().setDailyCap(99)).rejects.toThrow(
      "validation failed",
    );

    // Revert: snapshot restored to the prior value.
    expect(useBudgetStore.getState().snapshot.daily_usd).toBe(1);
    expect(useBudgetStore.getState().error?.message).toBe("validation failed");
  });

  test("setDomainCap writes the whole-payload key for the slug", async () => {
    useBudgetStore.setState({
      snapshot: {
        daily_usd: null,
        monthly_usd: null,
        alert_threshold_pct: null,
        per_domain: {},
      },
      loaded: true,
    });
    configSetMock.mockResolvedValue({
      text: "",
      data: { key: "budget.per_domain.research", value: null },
    });

    await useBudgetStore.getState().setDomainCap("research", {
      daily_cap_usd: 2,
      monthly_cap_usd: 40,
    });

    expect(useBudgetStore.getState().snapshot.per_domain.research).toEqual({
      daily_cap_usd: 2,
      monthly_cap_usd: 40,
    });
    // Whole-payload write keyed by slug — mirrors setDomainBudget in
    // api/tools.ts. Both cap fields are sent together so a partial
    // update can't leave inconsistent on-disk state.
    expect(configSetMock).toHaveBeenCalledWith({
      key: "budget.per_domain.research",
      value: { daily_cap_usd: 2, monthly_cap_usd: 40 },
    });
  });
});

describe("useBudgetStore — BroadcastChannel outbound posts", () => {
  test("setDailyCap posts the optimistic snapshot to peers", async () => {
    useBudgetStore.setState({
      snapshot: {
        daily_usd: 1,
        monthly_usd: 50,
        alert_threshold_pct: 80,
        per_domain: {},
      },
      loaded: true,
    });
    configSetMock.mockResolvedValue({
      text: "",
      data: { key: "budget.daily_usd", value: 7 },
    });

    const peer = makePeerChannel();
    const messages: Array<{ snapshot: BudgetSnapshot }> = [];
    peer.onmessage = (e) => messages.push(e.data);

    await useBudgetStore.getState().setDailyCap(7);

    await waitForCondition(() => messages.length > 0, 100);
    expect(messages[0]!.snapshot.daily_usd).toBe(7);

    peer.close();
  });

  test("refresh() failure does NOT post (errors are per-tab transport state)", async () => {
    configGetMock.mockRejectedValue(new Error("boom"));

    const peer = makePeerChannel();
    const messages: unknown[] = [];
    peer.onmessage = (e) => messages.push(e.data);

    await useBudgetStore.getState().refresh();
    await new Promise((r) => setTimeout(r, 50));

    expect(messages).toHaveLength(0);
    peer.close();
  });
});

describe("useBudgetStore — BroadcastChannel inbound apply (no echo)", () => {
  test("inbound peer post updates the store within 100ms without re-broadcasting", async () => {
    // ``observer`` is a SECOND peer channel; its onmessage fires for
    // any post EXCEPT its own. If the store re-broadcast on inbound
    // apply (ping-pong), observer would see TWO messages.
    const observer = makePeerChannel();
    const observed: Array<{ snapshot: BudgetSnapshot }> = [];
    observer.onmessage = (e) => observed.push(e.data);

    const peer = makePeerChannel();
    const payload: { snapshot: BudgetSnapshot } = {
      snapshot: {
        daily_usd: 12,
        monthly_usd: 240,
        alert_threshold_pct: 75,
        per_domain: {},
      },
    };
    peer.postMessage(payload);

    await waitForCondition(
      () => useBudgetStore.getState().snapshot.daily_usd === 12,
      100,
    );

    expect(useBudgetStore.getState().snapshot.monthly_usd).toBe(240);

    // The store applied via ``_internalSet`` and did NOT re-broadcast.
    // ``observed`` sees exactly the peer's post (channels don't see
    // their own posts, but observer is distinct from peer so it does).
    await new Promise((r) => setTimeout(r, 50));
    expect(observed).toHaveLength(1);
    expect(observed[0]!.snapshot.daily_usd).toBe(12);

    peer.close();
    observer.close();
  });
});
