/**
 * Plan 16 Task 4 (D4) — useDomainsStore.removeDomainOptimistic.
 *
 * Pins the contract for the optimistic-delete action used by the
 * Settings → Domains delete handler:
 *
 *   1. ``removeDomainOptimistic(slug)`` drops the slug from
 *      ``state.domains`` synchronously — no API call, no fetch,
 *      mirrors ``setActiveDomainOptimistic``'s in-store-only pattern.
 *   2. A subsequent ``refresh()`` reconciles with the canonical
 *      server list — used by the panel-domains delete handler on
 *      API failure to restore the optimistically-removed row.
 *   3. ``removeDomainOptimistic`` for a slug NOT in the store is a
 *      silent no-op (no error, no state change). The handler can
 *      always call it safely without having to introspect the store.
 *
 * The action exists specifically for Plan 13 Task 2 review I1 (the
 * earlier deferred recommendation) — without it, the UI delay
 * between confirm-click and ``refresh()`` resolution is the entire
 * end-to-end round-trip latency. With it, the delete feels
 * instantaneous and the network call is the rollback path, not the
 * happy path.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";

const { listDomainsMock } = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
}));

import { useDomainsStore } from "@/lib/state/domains-store";

beforeEach(() => {
  listDomainsMock.mockReset();
  // Lesson from Plan 16 Task 3: reset via the store's exported
  // ``_resetForTesting`` (rather than ``setState``) so the module-
  // private in-flight Promise is also cleared. Without that clear,
  // a prior test's pending promise can short-circuit subsequent
  // ``refresh()`` calls and break the assertion order.
  useDomainsStore.getState()._resetForTesting();
});

/** Seed the store directly with a known three-domain list. Bypasses
 *  the ``refresh()`` round-trip so tests don't depend on the mock
 *  for setup — the contract under test is the optimistic action,
 *  not the fetch hydration (covered by ``use-domains-store.test.ts``). */
function seedThree() {
  useDomainsStore.setState({
    domains: [
      {
        slug: "personal",
        label: "Personal",
        accent: "var(--dom-personal)",
        configured: true,
        on_disk: true,
      },
      {
        slug: "research",
        label: "Research",
        accent: "var(--dom-research)",
        configured: true,
        on_disk: true,
      },
      {
        slug: "work",
        label: "Work",
        accent: "var(--dom-work)",
        configured: true,
        on_disk: true,
      },
    ],
    activeDomain: "research",
    loaded: true,
    error: null,
  });
}

describe("useDomainsStore.removeDomainOptimistic", () => {
  test("removes the matching slug synchronously", () => {
    seedThree();
    expect(useDomainsStore.getState().domains.map((d) => d.slug)).toEqual([
      "personal",
      "research",
      "work",
    ]);

    useDomainsStore.getState().removeDomainOptimistic("personal");

    const after = useDomainsStore.getState();
    expect(after.domains.map((d) => d.slug)).toEqual(["research", "work"]);
    // Other store fields are untouched — the action is in-store-only.
    expect(after.activeDomain).toBe("research");
    expect(after.loaded).toBe(true);
    expect(after.error).toBeNull();
    // No fetch was triggered — confirms the action is purely in-store.
    expect(listDomainsMock).not.toHaveBeenCalled();
  });

  test("subsequent refresh() restores the row from the server list", async () => {
    seedThree();
    useDomainsStore.getState().removeDomainOptimistic("personal");
    expect(useDomainsStore.getState().domains.map((d) => d.slug)).toEqual([
      "research",
      "work",
    ]);

    // The server still has all three (eg. the delete API call failed
    // and the panel-domains handler is calling refresh() to rollback).
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        entries: [
          { slug: "personal", configured: true, on_disk: true },
          { slug: "research", configured: true, on_disk: true },
          { slug: "work", configured: true, on_disk: true },
        ],
        active_domain: "research",
      },
    });

    await useDomainsStore.getState().refresh();

    // Row restored — the optimistic remove was a UI-only mutation
    // and refresh() reconciles with whatever the backend has.
    expect(useDomainsStore.getState().domains.map((d) => d.slug)).toEqual([
      "personal",
      "research",
      "work",
    ]);
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });

  test("unknown slug is a silent no-op", () => {
    seedThree();
    const before = useDomainsStore.getState().domains;

    // The handler can call this without introspecting the store —
    // unknown slug must not throw or mutate state.
    expect(() => {
      useDomainsStore.getState().removeDomainOptimistic("does-not-exist");
    }).not.toThrow();

    const after = useDomainsStore.getState().domains;
    expect(after.map((d) => d.slug)).toEqual(["personal", "research", "work"]);
    // Reference equality is NOT required by the contract (zustand's
    // ``set`` returns a new object whether or not the filter changes
    // anything); only value equality is asserted. This keeps the
    // test from coupling to the implementation choice.
    expect(after).toEqual(before);
  });
});
