/**
 * Plan 13 Task 3 — useCrossDomainGateStore (zustand) contract.
 *
 * Pins the store's surface so the hook rewrite (Plan 13 Task 3) and
 * the Settings toggle (CrossDomainWarningToggle in panel-domains.tsx)
 * can rely on a stable cross-instance reactivity model:
 *
 *   1. Fresh store has the documented zero-state.
 *   2. ``refresh()`` resolves and the store reflects the response,
 *      including ``loaded === true``.
 *   3. ``setAcknowledgedOptimistic`` propagates to peer consumers
 *      via the zustand subscription model (no manual reload — the
 *      whole point of Plan 13 Task 3 / D3).
 *   4. Concurrent ``refresh()`` calls share a single in-flight
 *      Promise (no double-fetch).
 *   5. ``shouldFireCrossDomainModal`` table reads from the store-
 *      backed gate selector consistently (mirrors Plan 12 Task 9).
 *
 * Implementation choice (per plan): in-flight serialization via
 * Promise cache (not a flag). Concurrent ``refresh()`` calls receive
 * the same Promise so any ``await refresh()`` resolves once the in-
 * flight fetch lands. A flag-with-discard would drop the second
 * caller's await semantics. Mirrors ``domains-store.ts``.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

const { configGetMock } = vi.hoisted(() => ({
  configGetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
}));

import { useCrossDomainGateStore } from "@/lib/state/cross-domain-gate-store";
import { useCrossDomainGate } from "@/lib/hooks/use-cross-domain-gate";
import { shouldFireCrossDomainModal } from "@/components/dialogs/cross-domain-modal";

beforeEach(() => {
  configGetMock.mockReset();
  // Drop any state from a prior test so the singleton store starts
  // clean for each case. ``_resetForTesting`` also clears the
  // module-private in-flight Promise.
  useCrossDomainGateStore.getState()._resetForTesting();
});

describe("useCrossDomainGateStore — fresh state", () => {
  test("returns the documented zero-state on first read", () => {
    const s = useCrossDomainGateStore.getState();
    // Defaults match the schema: privacy_railed defaults to ["personal"]
    // and acknowledged defaults to false (fail open — show the modal
    // when in doubt). ``loaded`` flips true only after the first
    // refresh resolves so consumers can gate first-mount auto-fetch.
    expect(s.privacyRailed).toEqual(["personal"]);
    expect(s.acknowledged).toBe(false);
    expect(s.loaded).toBe(false);
    expect(s.error).toBeNull();
  });
});

describe("useCrossDomainGateStore — refresh()", () => {
  test("hydrates store fields from successful configGet responses", async () => {
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

    await useCrossDomainGateStore.getState().refresh();

    const s = useCrossDomainGateStore.getState();
    expect(s.privacyRailed).toEqual(["personal", "journal"]);
    expect(s.acknowledged).toBe(true);
    expect(s.loaded).toBe(true);
    expect(s.error).toBeNull();
    // Two configGet calls — one per field.
    expect(configGetMock).toHaveBeenCalledTimes(2);
  });

  test("falls back to safe defaults + records error on failure", async () => {
    configGetMock.mockRejectedValue(new Error("backend down"));

    // ``refresh()`` resolves cleanly even on failure — the hook's
    // first-mount auto-refresh fires ``void refresh()`` and we don't
    // want a transient backend hiccup to surface as an unhandled
    // rejection.
    await useCrossDomainGateStore.getState().refresh();

    const s = useCrossDomainGateStore.getState();
    // Fail open: defaults to "show the modal" so the user is never
    // silently skipped past the confirmation due to a transient
    // backend hiccup.
    expect(s.privacyRailed).toEqual(["personal"]);
    expect(s.acknowledged).toBe(false);
    // ``loaded`` flips true even on failure — the gate's trigger
    // logic uses safe defaults and the Settings toggle becomes
    // interactive (otherwise a permanent backend hiccup would
    // disable the toggle forever).
    expect(s.loaded).toBe(true);
    expect(s.error).toBeInstanceOf(Error);
    expect(s.error?.message).toBe("backend down");
  });

  test("subsequent refresh after failure retries (in-flight promise cleared)", async () => {
    // Failure clears the in-flight promise so the next call doesn't
    // get back the cached one. This is critical: without the
    // ``finally``-clear, a transient failure would block all future
    // refreshes for the lifetime of the page.
    configGetMock.mockRejectedValueOnce(new Error("transient"));
    configGetMock.mockRejectedValueOnce(new Error("transient"));
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
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

    await useCrossDomainGateStore.getState().refresh();
    expect(useCrossDomainGateStore.getState().error?.message).toBe("transient");
    await useCrossDomainGateStore.getState().refresh();
    expect(useCrossDomainGateStore.getState().acknowledged).toBe(true);
    expect(useCrossDomainGateStore.getState().error).toBeNull();
  });
});

describe("useCrossDomainGateStore — in-flight serialization (Promise cache)", () => {
  test("concurrent refresh() calls share one fetch + same Promise", async () => {
    // Resolve the configGet mock manually so we can launch two
    // refreshes against explicitly-pending promises. Track each
    // pending resolver so we can settle both ``Promise.all`` legs
    // (one per ``configGet`` key — privacy_railed +
    // cross_domain_warning_acknowledged).
    const resolvers: Array<(val: unknown) => void> = [];
    configGetMock.mockImplementation(
      (args: { key: string }) =>
        new Promise((resolve) => {
          resolvers.push((val) =>
            resolve({ text: "", data: { key: args.key, value: val } }),
          );
        }),
    );

    const a = useCrossDomainGateStore.getState().refresh();
    const b = useCrossDomainGateStore.getState().refresh();

    // Same Promise reference — caller B got back the in-flight cache
    // entry rather than triggering a fresh round of configGet calls.
    expect(a).toBe(b);
    // First refresh fires both configGet calls (Promise.all internally);
    // the second refresh shares the same in-flight promise so total
    // configGet calls === 2 (one per key, fired by the FIRST refresh).
    expect(configGetMock).toHaveBeenCalledTimes(2);

    // Resolve both pending fetches — Promise.all completes only when
    // both legs settle, so we have to release each.
    expect(resolvers).toHaveLength(2);
    resolvers[0]!(["personal"]);
    resolvers[1]!(false);
    await Promise.all([a, b]);

    expect(useCrossDomainGateStore.getState().loaded).toBe(true);
    // Even after both awaiters complete, the call count stays at 2.
    expect(configGetMock).toHaveBeenCalledTimes(2);
  });

  test("refresh() after previous resolves triggers a new fetch", async () => {
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: false },
      });
    });

    await useCrossDomainGateStore.getState().refresh();
    await useCrossDomainGateStore.getState().refresh();
    // Two distinct refreshes (sequential, not concurrent) → 4 total
    // configGet calls (2 per refresh, one per key).
    expect(configGetMock).toHaveBeenCalledTimes(4);
  });
});

describe("useCrossDomainGateStore — setAcknowledgedOptimistic", () => {
  test("propagates to peer consumers via zustand subscription (cross-instance pubsub)", async () => {
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: false },
        });
      }
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: null },
      });
    });

    // Two independent ``useCrossDomainGate()`` consumers. In jsdom
    // this is the analogue of the chat-screen and the Settings
    // toggle subscribing simultaneously — they should both see the
    // optimistic update without any manual remount or reload.
    const consumerA = renderHook(() => useCrossDomainGate());
    const consumerB = renderHook(() => useCrossDomainGate());

    await waitFor(() => {
      expect(consumerA.result.current.loading).toBe(false);
      expect(consumerB.result.current.loading).toBe(false);
    });
    expect(consumerA.result.current.acknowledged).toBe(false);
    expect(consumerB.result.current.acknowledged).toBe(false);

    // Consumer A's "code" calls setAcknowledgedOptimistic — both
    // consumers re-render with the new value. This is the exact
    // cross-instance bug Plan 12 Task 9 review flagged and Plan 13
    // Task 3 fixes. Without the store promotion, consumer B would
    // still report ``acknowledged=false`` until a remount or page
    // reload.
    act(() => {
      useCrossDomainGateStore.getState().setAcknowledgedOptimistic(true);
    });
    expect(consumerA.result.current.acknowledged).toBe(true);
    expect(consumerB.result.current.acknowledged).toBe(true);

    // Reverse direction: consumer B's "code" flips back. Consumer A
    // tracks the change without a remount — bidirectional pubsub.
    act(() => {
      useCrossDomainGateStore.getState().setAcknowledgedOptimistic(false);
    });
    expect(consumerA.result.current.acknowledged).toBe(false);
    expect(consumerB.result.current.acknowledged).toBe(false);
  });

  test("noop when value already matches acknowledged (no peer re-render)", () => {
    useCrossDomainGateStore.setState({ acknowledged: true, loaded: true });
    // Subscribe so we can detect any unnecessary re-render.
    let renders = 0;
    const unsub = useCrossDomainGateStore.subscribe(() => {
      renders += 1;
    });
    useCrossDomainGateStore.getState().setAcknowledgedOptimistic(true);
    expect(renders).toBe(0);
    unsub();
  });
});

describe("useCrossDomainGate() hook — auto-refresh on cold cache", () => {
  test("first mount triggers refresh() when loaded=false", async () => {
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: false },
        });
      }
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: null },
      });
    });

    const { result } = renderHook(() => useCrossDomainGate());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.privacyRailed).toEqual(["personal"]);
    expect(result.current.acknowledged).toBe(false);
    // 2 calls — one per configGet key.
    expect(configGetMock).toHaveBeenCalledTimes(2);
  });

  test("two mounts on cold cache share one fetch (in-flight cache)", async () => {
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: false },
        });
      }
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: null },
      });
    });

    const a = renderHook(() => useCrossDomainGate());
    const b = renderHook(() => useCrossDomainGate());
    await waitFor(() => {
      expect(a.result.current.loading).toBe(false);
      expect(b.result.current.loading).toBe(false);
    });
    // Even though both consumers' first-mount effect fires
    // ``refresh()``, the store's in-flight Promise cache means the
    // network is hit exactly once per key (2 total calls, not 4).
    expect(configGetMock).toHaveBeenCalledTimes(2);
  });
});

describe("shouldFireCrossDomainModal — store-backed selector parity", () => {
  // Mirrors the Plan 12 Task 9 trigger logic table; the helper now
  // reads from the store-backed selector via ``useCrossDomainGate()``,
  // but the pure trigger function still takes (scope, privacyRailed,
  // acknowledged) so this table just exercises the predicate against
  // the store-shape values.
  test.each([
    [["research", "personal"], ["personal"], false, true, "cross-domain into railed"],
    [["research", "personal"], ["personal"], true, false, "acknowledged short-circuits"],
    [["research", "work"], ["personal"], false, false, "no rail in scope"],
    [["personal"], ["personal"], false, false, "single-domain railed (consent implicit)"],
  ])(
    "scope=%j railed=%j ack=%j → fires=%j (%s)",
    (scope, railed, ack, expected) => {
      expect(
        shouldFireCrossDomainModal(
          scope as readonly string[],
          railed as readonly string[],
          ack as boolean,
        ),
      ).toBe(expected);
    },
  );
});
