/**
 * Plan 12 Task 5 — useDomainsStore (zustand) contract.
 *
 * Pins the store's surface so the hook rewrite (Plan 12 Task 5) and
 * the active-domain dropdown (Plan 12 Task 8) can rely on a stable
 * cross-instance reactivity model:
 *
 *   1. Fresh store has the documented zero-state.
 *   2. ``refresh()`` resolves and the store reflects the response,
 *      including ``domainsLoaded === true``.
 *   3. ``setActiveDomainOptimistic`` propagates to peer consumers
 *      via the zustand subscription model (no manual reload — the
 *      whole point of Task 5).
 *   4. Concurrent ``refresh()`` calls share a single in-flight
 *      Promise (no double-fetch).
 *
 * Implementation choice (per plan): in-flight serialization via
 * Promise cache (not a flag). Concurrent ``refresh()`` calls receive
 * the same Promise so any ``await refresh()`` resolves once the in-
 * flight fetch lands. A flag-with-discard would drop the second
 * caller's await semantics.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

const { listDomainsMock } = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
}));

import { useDomainsStore } from "@/lib/state/domains-store";
import { useDomains } from "@/lib/hooks/use-domains";

beforeEach(() => {
  listDomainsMock.mockReset();
  // Drop any state from a prior test so the singleton store starts
  // clean for each case. ``_resetForTesting`` also clears the
  // module-private in-flight Promise.
  useDomainsStore.getState()._resetForTesting();
});

describe("useDomainsStore — fresh state", () => {
  test("returns the documented zero-state on first read", () => {
    const s = useDomainsStore.getState();
    expect(s.domains).toEqual([]);
    expect(s.activeDomain).toBe("");
    expect(s.domainsLoaded).toBe(false);
    expect(s.error).toBeNull();
  });
});

describe("useDomainsStore — refresh()", () => {
  test("hydrates store fields from a successful listDomains response", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        domains: ["personal", "research", "work"],
        entries: [
          { slug: "personal", configured: true, on_disk: true },
          { slug: "research", configured: true, on_disk: true },
          { slug: "work", configured: true, on_disk: true },
        ],
        active_domain: "research",
      },
    });

    await useDomainsStore.getState().refresh();

    const s = useDomainsStore.getState();
    expect(s.domains.map((d) => d.slug)).toEqual([
      "personal",
      "research",
      "work",
    ]);
    expect(s.activeDomain).toBe("research");
    expect(s.domainsLoaded).toBe(true);
    expect(s.error).toBeNull();
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });

  test("records error on failed listDomains call (resolve-always semantics)", async () => {
    listDomainsMock.mockRejectedValue(new Error("boom"));

    // ``refresh()`` resolves cleanly even on failure — the hook's
    // first-mount auto-refresh fires ``void refresh()`` and we don't
    // want a transient backend hiccup to surface as an unhandled
    // rejection. Callers read ``store.error`` for failure state.
    await useDomainsStore.getState().refresh();

    const s = useDomainsStore.getState();
    expect(s.error).toBeInstanceOf(Error);
    expect(s.error?.message).toBe("boom");
    // ``domainsLoaded`` stays false on failure — the auto-refresh in
    // useDomains() doesn't loop because the effect's only dep is
    // ``domainsLoaded``, which doesn't flip. (A retry requires either
    // an explicit ``refresh()`` from a button or a state mutation
    // that re-mounts the consumer.)
    expect(s.domainsLoaded).toBe(false);
  });

  test("subsequent refresh after error retries (in-flight promise cleared)", async () => {
    // Failure clears the in-flight promise so the next call doesn't
    // get back the cached one. This is critical: without the
    // ``finally``-clear, a transient failure would block all future
    // refreshes for the lifetime of the page.
    listDomainsMock.mockRejectedValueOnce(new Error("transient"));
    listDomainsMock.mockResolvedValueOnce({
      text: "",
      data: {
        entries: [{ slug: "research", configured: true, on_disk: true }],
        active_domain: "research",
      },
    });

    await useDomainsStore.getState().refresh();
    expect(useDomainsStore.getState().error?.message).toBe("transient");
    await useDomainsStore.getState().refresh();
    expect(useDomainsStore.getState().domainsLoaded).toBe(true);
    expect(useDomainsStore.getState().error).toBeNull();
    expect(useDomainsStore.getState().domains.map((d) => d.slug)).toEqual([
      "research",
    ]);
  });
});

describe("useDomainsStore — in-flight serialization (Promise cache)", () => {
  test("concurrent refresh() calls share one fetch + same Promise", async () => {
    // Resolve the listDomains mock manually so we can launch two
    // refreshes against an explicitly-pending promise.
    let resolveFetch: (val: unknown) => void = () => {};
    listDomainsMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const a = useDomainsStore.getState().refresh();
    const b = useDomainsStore.getState().refresh();

    // Same Promise reference — caller B got back the in-flight cache
    // entry rather than a fresh listDomains call.
    expect(a).toBe(b);
    expect(listDomainsMock).toHaveBeenCalledTimes(1);

    // Resolve the underlying fetch; both awaiters complete.
    resolveFetch({
      text: "",
      data: {
        entries: [{ slug: "research", configured: true, on_disk: true }],
        active_domain: "research",
      },
    });
    await Promise.all([a, b]);

    expect(useDomainsStore.getState().domainsLoaded).toBe(true);
    // Even after both awaiters complete, the call count stays at 1.
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });

  test("refresh() after previous resolves triggers a new fetch", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        entries: [{ slug: "research", configured: true, on_disk: true }],
        active_domain: "research",
      },
    });

    await useDomainsStore.getState().refresh();
    await useDomainsStore.getState().refresh();
    // Two distinct refreshes (sequential, not concurrent) → two fetches.
    expect(listDomainsMock).toHaveBeenCalledTimes(2);
  });
});

describe("useDomainsStore — setActiveDomainOptimistic", () => {
  test("propagates to peer consumers via zustand subscription", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        entries: [
          { slug: "research", configured: true, on_disk: true },
          { slug: "work", configured: true, on_disk: true },
        ],
        active_domain: "research",
      },
    });

    // Two independent ``useDomains()`` consumers. In jsdom this is
    // the analogue of two React components mounting in the same
    // app — they should both see the optimistic update without any
    // manual remount or reload.
    const consumerA = renderHook(() => useDomains());
    const consumerB = renderHook(() => useDomains());

    await waitFor(() => {
      expect(consumerA.result.current.loading).toBe(false);
      expect(consumerB.result.current.loading).toBe(false);
    });
    expect(consumerA.result.current.activeDomain).toBe("research");
    expect(consumerB.result.current.activeDomain).toBe("research");

    // Consumer A's "code" calls setActiveDomainOptimistic — both
    // consumers re-render with the new value. This is the exact
    // cross-instance bug Plan 11 closure addendum identified and
    // Plan 12 Task 5 fixes.
    act(() => {
      useDomainsStore.getState().setActiveDomainOptimistic("work");
    });
    expect(consumerA.result.current.activeDomain).toBe("work");
    expect(consumerB.result.current.activeDomain).toBe("work");
  });

  test("noop when slug already matches activeDomain", () => {
    useDomainsStore.setState({ activeDomain: "research" });
    // Subscribe so we can detect any unnecessary re-render.
    let renders = 0;
    const unsub = useDomainsStore.subscribe(() => {
      renders += 1;
    });
    useDomainsStore.getState().setActiveDomainOptimistic("research");
    expect(renders).toBe(0);
    unsub();
  });
});

describe("useDomains() hook — auto-refresh on cold cache", () => {
  test("first mount triggers refresh() when domainsLoaded=false", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        entries: [{ slug: "research", configured: true, on_disk: true }],
        active_domain: "research",
      },
    });

    const { result } = renderHook(() => useDomains());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.activeDomain).toBe("research");
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });

  test("two mounts on cold cache share one fetch (in-flight cache)", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        entries: [{ slug: "research", configured: true, on_disk: true }],
        active_domain: "research",
      },
    });

    const a = renderHook(() => useDomains());
    const b = renderHook(() => useDomains());
    await waitFor(() => {
      expect(a.result.current.loading).toBe(false);
      expect(b.result.current.loading).toBe(false);
    });
    // Even though both consumers' first-mount effect fires
    // ``refresh()``, the store's in-flight Promise cache means the
    // network is hit exactly once.
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });
});
