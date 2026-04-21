import { describe, expect, test, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";

import { useAppStore } from "@/lib/state/app-store";

/**
 * Zustand `persist` middleware auto-hydrates from `localStorage` on first
 * import. Tests below need a known baseline, so each test:
 *   1. Clears localStorage + html dataset.
 *   2. Resets the store to its initial state via the private `_reset` hook.
 */

function resetStore() {
  // Known-good defaults; keep in sync with the store itself.
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

describe("useAppStore", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStore();
  });

  test("has sensible defaults", () => {
    const s = useAppStore.getState();
    expect(s.theme).toBe("dark");
    expect(s.density).toBe("comfortable");
    expect(s.mode).toBe("ask");
    expect(s.scope).toEqual(["research", "work"]);
    expect(s.view).toBe("chat");
    expect(s.railOpen).toBe(true);
    expect(s.activeThreadId).toBeNull();
    expect(s.streaming).toBe(false);
  });

  test("setTheme writes to <html data-theme> and persists", () => {
    useAppStore.getState().setTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(useAppStore.getState().theme).toBe("light");

    // Persist payload under the configured storage key.
    const raw = localStorage.getItem("brain-app");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.state.theme).toBe("light");
  });

  test("setScope replaces the list (scope toggle)", () => {
    const { setScope } = useAppStore.getState();
    setScope(["research"]);
    expect(useAppStore.getState().scope).toEqual(["research"]);

    setScope(["research", "work", "personal"]);
    expect(useAppStore.getState().scope).toEqual(["research", "work", "personal"]);

    setScope([]);
    expect(useAppStore.getState().scope).toEqual([]);
  });

  test("partialize excludes `view` and `activeThreadId` from persistence", () => {
    const { setActiveThreadId } = useAppStore.getState();
    // Mutate non-persisted fields.
    useAppStore.setState({ view: "browse" });
    setActiveThreadId("thread-42");
    // Persist another field to force a write.
    useAppStore.getState().toggleRail();

    const raw = localStorage.getItem("brain-app");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.state).not.toHaveProperty("view");
    expect(parsed.state).not.toHaveProperty("activeThreadId");
    expect(parsed.state).not.toHaveProperty("streaming");
    // Sanity: persisted fields ARE present.
    expect(parsed.state).toHaveProperty("theme");
    expect(parsed.state).toHaveProperty("density");
    expect(parsed.state).toHaveProperty("mode");
    expect(parsed.state).toHaveProperty("scope");
    expect(parsed.state).toHaveProperty("railOpen");
  });
});
