import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * Shell unit tests. We mock `next/navigation` so hooks used inside the shell
 * (usePathname for view-sensitive chrome) behave deterministically.
 */
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

// Plan 10 Task 7: stub useDomains() so the scope picker doesn't trigger
// a live ``listDomains`` fetch in the unit-test environment. The hook's
// real behaviour (singleton cache + refresh) is exercised in
// ``use-domains.test.ts``; this test just needs the topbar to render
// the v0.1 default triple.
vi.mock("@/lib/hooks/use-domains", () => ({
  useDomains: () => ({
    domains: [
      { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
      { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
      { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
    ],
    activeDomain: "research",
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
  invalidateDomainsCache: vi.fn(),
}));

// Plan 11 Task 8: topbar reads ``vaultPath`` from the bootstrap context
// to key its per-vault first-mount-hydration flag. Stub a stable path
// here so the hydration effect runs deterministically.
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

import { Topbar } from "@/components/shell/topbar";
import { LeftNav } from "@/components/shell/left-nav";
import { RightRail } from "@/components/shell/right-rail";
import { AppShell } from "@/components/shell/app-shell";
import { useAppStore } from "@/lib/state/app-store";

function resetStore() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "ask",
    // Plan 11 Task 8: scope starts empty + scopeInitialized=false so
    // the topbar's first-mount hydration effect can fire on each test
    // mount. Tests that need a pre-hydrated scope opt in by setting
    // ``scopeInitialized: true`` and ``scope: [...]`` explicitly.
    scope: [],
    scopeInitialized: false,
    view: "chat",
    railOpen: true,
    activeThreadId: null,
    streaming: false,
  });
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.density;
}

describe("Shell components", () => {
  beforeEach(() => {
    localStorage.clear();
    usePathnameMock.mockReturnValue("/chat");
    resetStore();
  });

  test("topbar renders app title and key controls", () => {
    render(<Topbar />);
    // App title (banner-level label "brain").
    const banner = screen.getByRole("banner");
    expect(banner).toHaveTextContent(/brain/i);
    // Phase 2E iconified the topbar's right-side controls. The aria-labels
    // are intentionally action-prefixed ("Switch to light theme" / "Toggle
    // right rail") so screen-reader users hear what the icon-only button
    // does, not just what it represents.
    expect(
      screen.getByRole("button", { name: /switch to (light|dark) theme/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /toggle right rail/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument();
  });

  test("left-nav items render as links with correct hrefs", () => {
    render(<LeftNav />);
    expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /inbox/i })).toHaveAttribute("href", "/inbox");
    expect(screen.getByRole("link", { name: /browse/i })).toHaveAttribute("href", "/browse");
    expect(screen.getByRole("link", { name: /pending/i })).toHaveAttribute("href", "/pending");
    expect(screen.getByRole("link", { name: /bulk/i })).toHaveAttribute("href", "/bulk");
    // Plan 07 Task 22: nav links deep-link into /settings/general so a
    // click avoids the redirect round-trip through /settings.
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute(
      "href",
      "/settings/general",
    );
    expect(screen.getByRole("link", { name: /setup/i })).toHaveAttribute("href", "/setup");
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
  });

  test("rail toggle flips railOpen in the store", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>main content</div>
      </AppShell>,
    );
    expect(useAppStore.getState().railOpen).toBe(true);
    await user.click(screen.getByRole("button", { name: /toggle right rail/i }));
    expect(useAppStore.getState().railOpen).toBe(false);
    await user.click(screen.getByRole("button", { name: /toggle right rail/i }));
    expect(useAppStore.getState().railOpen).toBe(true);
  });

  test("mode switcher shows only on chat view", () => {
    // Chat view: mode switcher present.
    usePathnameMock.mockReturnValue("/chat");
    const { unmount } = render(<Topbar />);
    expect(screen.getByRole("group", { name: /chat mode/i })).toBeInTheDocument();
    unmount();

    // Browse view: hidden.
    usePathnameMock.mockReturnValue("/browse");
    render(<Topbar />);
    expect(screen.queryByRole("group", { name: /chat mode/i })).not.toBeInTheDocument();
  });

  test("scope picker opens a popover listing domains", async () => {
    const user = userEvent.setup();
    // Pre-hydrate so the popover renders with a deterministic scope —
    // the hydration effect would also resolve to ["research"] but
    // forcing it here keeps the test about the popover itself.
    useAppStore.setState({ scope: ["research"], scopeInitialized: true });
    render(<Topbar />);
    // Closed initially — no list.
    expect(screen.queryByRole("checkbox", { name: /research/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /scope/i }));
    // Open: the 3 stub domains are visible.
    expect(await screen.findByRole("checkbox", { name: /research/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /work/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /personal/i })).toBeInTheDocument();
  });

  // ---------- Plan 11 Task 8 — first-mount scope hydration ----------

  test("first-mount: hydrates scope from activeDomain when scopeInitialized=false", async () => {
    // Fresh store: scope=[], scopeInitialized=false. The mocked
    // useDomains returns activeDomain="research" — topbar should set
    // scope to ["research"] and flip the flag.
    expect(useAppStore.getState().scope).toEqual([]);
    expect(useAppStore.getState().scopeInitialized).toBe(false);

    render(<Topbar />);

    await waitFor(() =>
      expect(useAppStore.getState().scopeInitialized).toBe(true),
    );
    expect(useAppStore.getState().scope).toEqual(["research"]);
    // Per-vault localStorage key was written.
    expect(localStorage.getItem("brain.scopeInitialized./test/vault")).toBe(
      "true",
    );
  });

  test("subsequent mount: scopeInitialized=true honors user-set scope", async () => {
    // Simulate "user already hydrated, then edited to two domains".
    useAppStore.setState({
      scope: ["research", "work"],
      scopeInitialized: true,
    });
    localStorage.setItem("brain.scopeInitialized./test/vault", "true");

    render(<Topbar />);

    // Hydration effect must NOT fire — scope stays as the user left it.
    // Use a small wait to make sure no async setState clobbers it.
    await new Promise((r) => setTimeout(r, 10));
    expect(useAppStore.getState().scope).toEqual(["research", "work"]);
  });
});

// Keep RightRail referenced so the import is used and tree-shaking lint stays happy.
void RightRail;
