import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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
    scope: ["research", "work"],
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
    expect(screen.getByRole("button", { name: /toggle theme/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /toggle rail/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toBeInTheDocument();
  });

  test("left-nav items render as links with correct hrefs", () => {
    render(<LeftNav />);
    expect(screen.getByRole("link", { name: /chat/i })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /inbox/i })).toHaveAttribute("href", "/inbox");
    expect(screen.getByRole("link", { name: /browse/i })).toHaveAttribute("href", "/browse");
    expect(screen.getByRole("link", { name: /pending/i })).toHaveAttribute("href", "/pending");
    expect(screen.getByRole("link", { name: /bulk/i })).toHaveAttribute("href", "/bulk");
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute("href", "/settings");
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
    await user.click(screen.getByRole("button", { name: /toggle rail/i }));
    expect(useAppStore.getState().railOpen).toBe(false);
    await user.click(screen.getByRole("button", { name: /toggle rail/i }));
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
    render(<Topbar />);
    // Closed initially — no list.
    expect(screen.queryByRole("checkbox", { name: /research/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /scope/i }));
    // Open: the 3 stub domains are visible.
    expect(await screen.findByRole("checkbox", { name: /research/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /work/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /personal/i })).toBeInTheDocument();
  });
});

// Keep RightRail referenced so the import is used and tree-shaking lint stays happy.
void RightRail;
