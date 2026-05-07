/**
 * Plan 16 Task 42 — Topbar scope picker "Set as default" action.
 *
 * Pins three contracts on the per-row star button rendered next to each
 * non-active domain in the scope picker popover:
 *
 *   1. Click → ``setActiveDomain(slug)`` is invoked with the row's slug;
 *      on success a "success"-variant toast is dispatched announcing the
 *      change.
 *   2. Click → optimistic update flips ``useDomainsStore.activeDomain``
 *      AHEAD of the API resolution, so the star indicator on the
 *      previously active row immediately moves to the newly chosen one
 *      (peer-consumer re-render parity with ``panel-domains-active``).
 *   3. API failure path → the optimistic update is reverted AND a
 *      "danger"-variant toast surfaces. The star indicator returns to
 *      the previously active row.
 *
 * The button is hover-revealed in CSS but jsdom evaluates the DOM
 * regardless of pointer state — clicking it works in tests even when
 * sighted users would need to hover first. Accessibility note: the
 * action is keyboard-accessible (it's a real ``<button>`` with an
 * ``aria-label`` so screen-reader users can tab to it without needing
 * the hover affordance).
 *
 * The mocking pattern mirrors ``settings-domains.test.tsx`` (selector
 * + ``getState`` shaped stub for ``useSystemStore``) and
 * ``topbar.test.tsx`` (mutable ``useDomainsStub`` + ``bootstrapStub``
 * for the topbar's hydration deps).
 */

import {
  describe,
  expect,
  test,
  beforeEach,
  afterEach,
  vi,
} from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const useDomainsStub = {
  domains: [
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
    {
      slug: "personal",
      label: "Personal",
      accent: "var(--dom-personal)",
      configured: true,
      on_disk: true,
    },
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

vi.mock("@/lib/bootstrap/bootstrap-context", () => ({
  useBootstrap: () => ({
    token: "test-token",
    isFirstRun: false,
    vaultPath: "/test/vault",
    loading: false,
    error: null,
    retry: vi.fn(),
  }),
}));

const { setActiveDomainMock } = vi.hoisted(() => ({
  setActiveDomainMock: vi.fn(),
}));
vi.mock("@/lib/api/tools", () => ({
  setActiveDomain: setActiveDomainMock,
}));

const { pushToastStub } = vi.hoisted(() => ({ pushToastStub: vi.fn() }));
vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: typeof pushToastStub }) => unknown) =>
      selector({ pushToast: pushToastStub }),
    { getState: () => ({ pushToast: pushToastStub }) },
  ),
}));

import { Topbar } from "@/components/shell/topbar";
import { useAppStore } from "@/lib/state/app-store";
import { useDomainsStore } from "@/lib/state/domains-store";

function resetStores() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "ask",
    scope: ["research"],
    scopeInitialized: true,
    view: "chat",
    railOpen: true,
    activeThreadId: null,
    streaming: false,
  });
  // Seed the real domains-store so the optimistic-update assertion has
  // something concrete to flip. ``setActiveDomainOptimistic`` reads from
  // and writes to this store; mocking ``useDomains`` only stubs the
  // *hook* used for rendering, not the store action invoked from the
  // click handler.
  useDomainsStore.setState({
    domains: useDomainsStub.domains,
    activeDomain: "research",
    loaded: true,
    error: null,
  });
}

describe("Topbar scope picker — Plan 16 Task 42 'Set as default'", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStores();
    setActiveDomainMock.mockReset();
    pushToastStub.mockReset();
    useDomainsStub.activeDomain = "research";
  });

  afterEach(() => {
    // Clean up any toast timers scheduled by the real system-store. We
    // mocked the hook, but the store action's setTimeout (6s auto-
    // dismiss) doesn't run here — defensive belt-and-braces.
    vi.useRealTimers();
  });

  test("clicking the star on a non-default row calls setActiveDomain + success toast", async () => {
    const user = userEvent.setup();
    setActiveDomainMock.mockResolvedValue({
      text: "",
      data: { key: "active_domain", value: "work" },
    });

    render(<Topbar />);
    await user.click(screen.getByRole("button", { name: /scope/i }));

    // The "research" row IS the current default — its star is the
    // non-interactive indicator (``Default`` label). The "work" row's
    // star IS interactive (``Set Work as default``).
    const setDefaultBtn = await screen.findByRole("button", {
      name: /set work as default/i,
    });
    await user.click(setDefaultBtn);

    await waitFor(() => {
      expect(setActiveDomainMock).toHaveBeenCalledWith("work");
    });

    await waitFor(() => {
      expect(pushToastStub).toHaveBeenCalledWith(
        expect.objectContaining({ variant: "success" }),
      );
    });
  });

  test("optimistic update: activeDomain flips before API resolves", async () => {
    const user = userEvent.setup();
    // Hold the API promise so we can assert state mid-flight.
    let resolveApi: (v: unknown) => void = () => {};
    setActiveDomainMock.mockImplementation(
      () =>
        new Promise((res) => {
          resolveApi = res;
        }),
    );

    render(<Topbar />);
    await user.click(screen.getByRole("button", { name: /scope/i }));
    await user.click(
      await screen.findByRole("button", { name: /set work as default/i }),
    );

    // Optimistic update has fired; activeDomain is "work" even though
    // the API is still pending.
    expect(useDomainsStore.getState().activeDomain).toBe("work");

    // Resolve the API and let the success toast dispatch.
    act(() => {
      resolveApi({ text: "", data: { key: "active_domain", value: "work" } });
    });
    await waitFor(() => {
      expect(pushToastStub).toHaveBeenCalledWith(
        expect.objectContaining({ variant: "success" }),
      );
    });
  });

  test("API failure: revert + danger toast", async () => {
    const user = userEvent.setup();
    setActiveDomainMock.mockRejectedValue(new Error("network sad"));

    render(<Topbar />);
    await user.click(screen.getByRole("button", { name: /scope/i }));
    await user.click(
      await screen.findByRole("button", { name: /set work as default/i }),
    );

    // After the rejection settles, optimistic update reverts to the
    // pre-click value ("research") AND a danger toast lands.
    await waitFor(() => {
      expect(useDomainsStore.getState().activeDomain).toBe("research");
    });
    expect(pushToastStub).toHaveBeenCalledWith(
      expect.objectContaining({ variant: "danger" }),
    );
  });

  test("clicking the star does NOT toggle the row's visibility checkbox", async () => {
    const user = userEvent.setup();
    setActiveDomainMock.mockResolvedValue({
      text: "",
      data: { key: "active_domain", value: "work" },
    });

    render(<Topbar />);
    await user.click(screen.getByRole("button", { name: /scope/i }));
    const beforeScope = useAppStore.getState().scope;
    await user.click(
      await screen.findByRole("button", { name: /set work as default/i }),
    );
    // The visibility scope is unchanged — the click was consumed by the
    // star button, not the wrapping label/checkbox.
    expect(useAppStore.getState().scope).toEqual(beforeScope);
  });

  test("the active row exposes a non-interactive 'Default' indicator (no Set-as-default button)", async () => {
    const user = userEvent.setup();
    render(<Topbar />);
    await user.click(screen.getByRole("button", { name: /scope/i }));
    // Wait for the popover to render.
    await screen.findByRole("checkbox", { name: /research/i });
    // The active row ("research") has NO "Set Research as default"
    // button — the indicator there is the static "Default" marker.
    expect(
      screen.queryByRole("button", { name: /set research as default/i }),
    ).not.toBeInTheDocument();
  });
});
