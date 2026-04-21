import { describe, expect, test, beforeEach, afterEach, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import { useSystemStore } from "@/lib/state/system-store";

/**
 * System-store (Plan 07 Task 12): owns app-level system UI state —
 *   connection pip, budget-wall modal, mid-turn toast kind, drag-to-attach
 *   dragging flag, and the toast list (with auto-dismiss after 6s when no
 *   countdown is specified).
 *
 * NO persist middleware — system state is transient per session.
 */

function resetStore() {
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    toasts: [],
  });
}

describe("useSystemStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("setConnection transitions the connection state", () => {
    const { setConnection } = useSystemStore.getState();
    expect(useSystemStore.getState().connection).toBe("ok");
    setConnection("reconnecting");
    expect(useSystemStore.getState().connection).toBe("reconnecting");
    setConnection("offline");
    expect(useSystemStore.getState().connection).toBe("offline");
    setConnection("ok");
    expect(useSystemStore.getState().connection).toBe("ok");
  });

  test("openBudgetWall and closeBudgetWall flip the flag", () => {
    const { openBudgetWall, closeBudgetWall } = useSystemStore.getState();
    expect(useSystemStore.getState().budgetWallOpen).toBe(false);
    openBudgetWall();
    expect(useSystemStore.getState().budgetWallOpen).toBe(true);
    closeBudgetWall();
    expect(useSystemStore.getState().budgetWallOpen).toBe(false);
  });

  test("setMidTurn cycles through kinds and clears to null", () => {
    const { setMidTurn } = useSystemStore.getState();
    expect(useSystemStore.getState().midTurn).toBeNull();
    setMidTurn("rate-limit");
    expect(useSystemStore.getState().midTurn).toBe("rate-limit");
    setMidTurn("tool-failed");
    expect(useSystemStore.getState().midTurn).toBe("tool-failed");
    setMidTurn(null);
    expect(useSystemStore.getState().midTurn).toBeNull();
  });

  test("setDragging toggles the drag flag", () => {
    const { setDragging } = useSystemStore.getState();
    expect(useSystemStore.getState().draggingFile).toBe(false);
    setDragging(true);
    expect(useSystemStore.getState().draggingFile).toBe(true);
    setDragging(false);
    expect(useSystemStore.getState().draggingFile).toBe(false);
  });

  test("pushToast appends a toast; auto-dismiss removes it after 6s when no countdown", () => {
    vi.useFakeTimers();
    try {
      const { pushToast } = useSystemStore.getState();
      pushToast({ lead: "Cap raised.", msg: "Today's cap is now $15.00" });
      // Unique id assigned and toast appears immediately.
      let state = useSystemStore.getState();
      expect(state.toasts).toHaveLength(1);
      const [toast] = state.toasts;
      expect(toast.lead).toBe("Cap raised.");
      expect(toast.msg).toBe("Today's cap is now $15.00");
      expect(typeof toast.id).toBe("string");

      // Advance ~5.9s — still present.
      vi.advanceTimersByTime(5900);
      expect(useSystemStore.getState().toasts).toHaveLength(1);

      // Advance past the 6s threshold — auto-dismiss fires.
      vi.advanceTimersByTime(200);
      expect(useSystemStore.getState().toasts).toHaveLength(0);

      // A toast WITH countdown does NOT auto-dismiss at 6s (caller owns lifetime).
      pushToast({ lead: "Hold on.", msg: "Undo-able for 8s", countdown: 8 });
      expect(useSystemStore.getState().toasts).toHaveLength(1);
      vi.advanceTimersByTime(10_000);
      expect(useSystemStore.getState().toasts).toHaveLength(1);

      // Explicit dismiss removes it.
      const id = useSystemStore.getState().toasts[0].id;
      useSystemStore.getState().dismissToast(id);
      expect(useSystemStore.getState().toasts).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });
});

// After-suite safety net: restore real timers if a test left them faked.
afterEach(() => {
  vi.useRealTimers();
});
