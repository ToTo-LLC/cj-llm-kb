"use client";

import { create } from "zustand";

/**
 * System-UI store (Plan 07 Task 12).
 *
 * Owns app-level ephemeral state that the system overlays (`<SystemOverlays />`)
 * read: the WS connection pip, the blocking budget wall modal, the mid-turn
 * issue toast kind, the drag-to-attach dragging flag, and the toast list.
 *
 * Deliberately NOT persisted:
 *   - `connection` is driven by the live WS lifecycle (Task 14 wires it).
 *   - `budgetWallOpen` / `midTurn` come from cost / turn events (Task 15/16).
 *   - `draggingFile` is a cross-iframe / cross-tab drag flag — never survives
 *     a reload.
 *   - `toasts` includes callback references (`undo`) that can't be
 *     serialised.
 *
 * Keeping this separate from `app-store` (which IS persisted) is deliberate:
 * mixing persisted durable prefs with ephemeral event-driven state in one
 * store makes `partialize` logic fragile every time a new slice is added.
 */

export type ConnectionState = "ok" | "reconnecting" | "offline";

/**
 * Five fixed mid-turn issue kinds. Each maps to a locked copy map in
 * `components/system/mid-turn-toast.tsx`. Adding a kind means updating the
 * COPY map there AND bumping a test for it.
 */
export type MidTurnKind =
  | "rate-limit"
  | "context-full"
  | "tool-failed"
  | "invalid-state-turn"
  | "invalid-state-mode";

export interface Toast {
  /** Unique identifier used by `dismissToast`. Assigned by `pushToast`. */
  id: string;
  /** Bolded leading phrase, e.g. "Cap raised." */
  lead: string;
  /** Follow-up sentence explaining the consequence. */
  msg: string;
  /** Optional icon key (resolves to a lucide icon inside `Toasts`). */
  icon?: string;
  variant?: "default" | "success" | "warn" | "danger";
  /**
   * Optional countdown in seconds. When set the toast does NOT auto-dismiss
   * after 6s — the caller owns its lifetime (used for undo prompts, which
   * render a live countdown and fire `undo` at zero).
   */
  countdown?: number;
  /** Invoked when the user clicks the "Undo" affordance. */
  undo?: () => void;
}

export interface SystemState {
  connection: ConnectionState;
  budgetWallOpen: boolean;
  midTurn: MidTurnKind | null;
  draggingFile: boolean;
  toasts: Toast[];

  setConnection: (state: ConnectionState) => void;
  openBudgetWall: () => void;
  closeBudgetWall: () => void;
  setMidTurn: (kind: MidTurnKind | null) => void;
  setDragging: (flag: boolean) => void;
  /** Append a toast. Assigns a unique id; auto-dismisses after 6s unless a
   *  `countdown` is supplied. */
  pushToast: (toast: Omit<Toast, "id">) => void;
  /** Remove a toast by id. Safe to call with a stale id. */
  dismissToast: (id: string) => void;
}

/** Global system-UI store. Not persisted — see module docstring. */
export const useSystemStore = create<SystemState>((set, get) => ({
  connection: "ok",
  budgetWallOpen: false,
  midTurn: null,
  draggingFile: false,
  toasts: [],

  setConnection: (connection) => set({ connection }),
  openBudgetWall: () => set({ budgetWallOpen: true }),
  closeBudgetWall: () => set({ budgetWallOpen: false }),
  setMidTurn: (midTurn) => set({ midTurn }),
  setDragging: (draggingFile) => set({ draggingFile }),
  pushToast: (toast) => {
    // `Date.now()` alone collides when two toasts fire in the same tick
    // (e.g. rapid bulk-import feedback). Adding `Math.random()` keeps ids
    // unique without pulling in a uuid dep.
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }] }));
    if (!toast.countdown) {
      setTimeout(() => {
        get().dismissToast(id);
      }, 6000);
    }
  },
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
