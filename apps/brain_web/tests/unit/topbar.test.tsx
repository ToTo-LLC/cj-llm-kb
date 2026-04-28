/**
 * Plan 11 Task 8 — Topbar first-mount scope hydration edge cases.
 *
 * The happy path (``activeDomain`` is in ``liveDomains`` → scope flips
 * to ``[activeDomain]``) is covered in ``shell.test.tsx`` alongside the
 * other topbar chrome tests. This file pins the two messier branches
 * that need their own ``useDomains`` stubs:
 *
 *   1. Fallback: ``activeDomain`` is NOT in the live domain list
 *      (rare race — user changed Config.active_domain in another
 *      window then deleted that domain before this mount finished
 *      hydrating). Topbar falls back to the first non-``personal``
 *      slug and logs a console warning.
 *
 *   2. Vault-path-keyed isolation: switching ``vaultPath`` mid-session
 *      (e.g. via Settings) re-runs first-mount hydration without
 *      anyone clearing localStorage, because the new vault's
 *      ``brain.scopeInitialized.<vault>`` key is unset.
 *
 *   3. Skip when activeDomain is empty: the backend pre-dates Task 6
 *      (or the response is still loading) — topbar must NOT flip the
 *      flag with an empty scope. The hydration effect waits.
 */

import { describe, expect, test, beforeEach, afterEach, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

const { usePathnameMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn(() => "/chat"),
}));
vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock,
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// Per-test mutable stub: tests reach into ``useDomainsStub`` to swap
// the activeDomain / domains shape before render. Mirrors the pattern
// in shell.test.tsx but exposed as a mutable object so individual
// tests can drive the hydration branches independently.
const useDomainsStub = {
  domains: [
    { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
    { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
    { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
  ] as Array<{
    slug: string;
    label: string;
    accent: string;
    configured: boolean;
    on_disk: boolean;
  }>,
  activeDomain: "research",
  loading: false,
  error: null as Error | null,
  refresh: vi.fn(),
};
vi.mock("@/lib/hooks/use-domains", () => ({
  useDomains: () => useDomainsStub,
  invalidateDomainsCache: vi.fn(),
}));

const bootstrapStub = {
  token: "test-token",
  isFirstRun: false as boolean | null,
  vaultPath: "/test/vault" as string | null,
  loading: false,
  error: null as string | null,
  retry: vi.fn(),
};
vi.mock("@/lib/bootstrap/bootstrap-context", () => ({
  useBootstrap: () => bootstrapStub,
}));

import { Topbar } from "@/components/shell/topbar";
import { useAppStore } from "@/lib/state/app-store";

function resetStore() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "ask",
    scope: [],
    scopeInitialized: false,
    view: "chat",
    railOpen: true,
    activeThreadId: null,
    streaming: false,
  });
}

describe("Topbar — Plan 11 Task 8 first-mount scope hydration", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    resetStore();
    // Reset stubs to the happy-path defaults — individual tests
    // override.
    useDomainsStub.domains = [
      { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
      { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
      { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
    ];
    useDomainsStub.activeDomain = "research";
    bootstrapStub.vaultPath = "/test/vault";
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  test("fallback: activeDomain not in live list → first non-personal slug + console.warn", async () => {
    // active_domain references a slug that's no longer in the live list.
    useDomainsStub.activeDomain = "ghost";

    render(<Topbar />);

    await waitFor(() =>
      expect(useAppStore.getState().scopeInitialized).toBe(true),
    );
    // First non-"personal" slug is "research".
    expect(useAppStore.getState().scope).toEqual(["research"]);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0]![0]).toContain('"ghost"');
    expect(warnSpy.mock.calls[0]![0]).toContain('"research"');
  });

  test("fallback: every live slug is personal → falls back to first slug, warns", async () => {
    // Theoretically impossible per Config validators (Config.domains
    // requires at least one non-personal slug in normal operation),
    // but the topbar's fallback path must still produce a non-empty
    // scope rather than an empty array. Pin the behaviour so a future
    // refactor doesn't silently regress.
    useDomainsStub.domains = [
      { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
    ];
    useDomainsStub.activeDomain = "ghost";

    render(<Topbar />);

    await waitFor(() =>
      expect(useAppStore.getState().scopeInitialized).toBe(true),
    );
    expect(useAppStore.getState().scope).toEqual(["personal"]);
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });

  test("waits when activeDomain is empty (backend pre-Task-6 / still loading)", async () => {
    useDomainsStub.activeDomain = "";

    render(<Topbar />);

    // Give effects a chance to flush. The flag must NOT flip because
    // we have no signal for what to hydrate to.
    await new Promise((r) => setTimeout(r, 25));
    expect(useAppStore.getState().scopeInitialized).toBe(false);
    expect(useAppStore.getState().scope).toEqual([]);
  });

  test("vault-path-keyed: different vaults each get their own first-mount hydration", async () => {
    // Vault A's flag is already set in localStorage from a previous
    // session — topbar should NOT re-hydrate when vaultPath="/vault/a".
    localStorage.setItem("brain.scopeInitialized./vault/a", "true");
    bootstrapStub.vaultPath = "/vault/a";
    useAppStore.setState({ scope: ["work"], scopeInitialized: false });

    const { unmount } = render(<Topbar />);
    await waitFor(() =>
      expect(useAppStore.getState().scopeInitialized).toBe(true),
    );
    // Mirror flipped via loadScopeInitializedFor (the durable record
    // existed). User's persisted scope ["work"] is preserved — the
    // hydration effect bails on the scopeInitialized=true gate.
    expect(useAppStore.getState().scope).toEqual(["work"]);
    unmount();

    // Now switch to vault B (no durable flag). Reset the in-memory
    // mirror to simulate the post-rehydrate state, and re-mount.
    bootstrapStub.vaultPath = "/vault/b";
    useAppStore.setState({ scope: [], scopeInitialized: false });

    render(<Topbar />);

    await waitFor(() =>
      expect(useAppStore.getState().scopeInitialized).toBe(true),
    );
    // Vault B had no durable flag → hydration ran and set scope from
    // the mocked activeDomain ("research").
    expect(useAppStore.getState().scope).toEqual(["research"]);
    expect(localStorage.getItem("brain.scopeInitialized./vault/b")).toBe(
      "true",
    );
  });
});
