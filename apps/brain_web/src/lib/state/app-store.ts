"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import { useSystemStore } from "./system-store";

// ---------- Types ----------

export type ViewName =
  | "chat"
  | "inbox"
  | "browse"
  | "pending"
  | "bulk"
  | "settings"
  | "setup";
export type ChatMode = "ask" | "brainstorm" | "draft";
export type Theme = "dark" | "light";
export type Density = "comfortable" | "compact";

export interface AppState {
  theme: Theme;
  density: Density;
  mode: ChatMode;
  scope: string[]; // domain slugs
  view: ViewName; // URL-derived; do NOT persist (URL is source of truth).
  railOpen: boolean;
  activeThreadId: string | null; // URL-derived; do NOT persist.
  streaming: boolean; // set by chat stream lifecycle (Task 15). Not persisted.
  /**
   * Plan 11 Task 8 / D8 — has the topbar already hydrated ``scope`` from
   * ``Config.active_domain`` for the current vault?
   *
   * In-memory mirror of the per-vault ``brain.scopeInitialized.<vault>``
   * localStorage flag. Kept here so React effects can subscribe and bail
   * without poking ``localStorage`` on every render. The actual durable
   * record is the localStorage key — this slot is rehydrated from it via
   * ``loadScopeInitializedFor()`` once ``vaultPath`` is known.
   *
   * Deliberately NOT in the persisted ``brain-app`` payload: the flag
   * MUST scope to the active vault (D8: switching vaults re-runs first-
   * mount hydration), which is impossible to express through the single
   * persist key without per-vault forks of the whole store.
   */
  scopeInitialized: boolean;

  setTheme: (t: Theme) => void;
  setDensity: (d: Density) => void;
  setMode: (m: ChatMode) => void;
  setScope: (s: string[]) => void;
  setView: (v: ViewName) => void;
  toggleRail: () => void;
  setRailOpen: (open: boolean) => void;
  setActiveThreadId: (id: string | null) => void;
  setStreaming: (flag: boolean) => void;
  /** Mark first-mount scope hydration done for ``vaultPath``. Writes the
   *  per-vault localStorage flag and flips the in-memory mirror. */
  markScopeInitialized: (vaultPath: string) => void;
  /** Read the per-vault flag from localStorage and mirror it into the
   *  store. Idempotent; safe to call from a useEffect on every mount. */
  loadScopeInitializedFor: (vaultPath: string) => void;
}

// ---------- localStorage helpers (per-vault scopeInitialized) ----------

/**
 * localStorage key shape for the first-mount-hydration flag. Keying by
 * vault path means two vaults at e.g. ``~/Documents/brain`` vs
 * ``~/Documents/brain-work`` each get their own first-load hydration —
 * no cross-talk, no explicit reset needed when the user changes vault.
 */
function scopeInitKey(vaultPath: string): string {
  return `brain.scopeInitialized.${vaultPath}`;
}

/** SSR-safe read of the per-vault flag. Returns ``false`` on the
 *  server, on a fresh localStorage, or on parse failure. */
export function readScopeInitialized(vaultPath: string): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    return localStorage.getItem(scopeInitKey(vaultPath)) === "true";
  } catch {
    return false;
  }
}

/** SSR-safe write of the per-vault flag. */
export function writeScopeInitialized(vaultPath: string): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(scopeInitKey(vaultPath), "true");
  } catch {
    // Quota / private-mode failures are non-fatal — the in-memory
    // mirror still flips, so the current session won't re-hydrate.
  }
}

// ---------- Helpers ----------

/** Apply theme + density to the <html> element. SSR-safe no-op on the server. */
function applyHtmlDataset(theme: Theme, density: Density) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.density = density;
}

// ---------- Store ----------

/**
 * Global UI state. Shared across every screen. Persisted fields only: theme,
 * density, mode, scope, railOpen. `view` and `activeThreadId` are derived from
 * the URL at render time, and `streaming` is ephemeral chat-stream state.
 */
export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      density: "comfortable",
      mode: "ask",
      // Plan 11 Task 8: default to empty until first-mount hydration
      // resolves. Topbar fills this from ``activeDomain`` once the
      // ``brain_list_domains`` response lands. Pre-Task-8 callers
      // shouldn't observe the empty state — it's a single tick before
      // hydration runs.
      scope: [],
      view: "chat",
      railOpen: true,
      activeThreadId: null,
      streaming: false,
      scopeInitialized: false,

      setTheme: (theme) => {
        if (typeof document !== "undefined") {
          document.documentElement.dataset.theme = theme;
        }
        set({ theme });
      },
      setDensity: (density) => {
        if (typeof document !== "undefined") {
          document.documentElement.dataset.density = density;
        }
        set({ density });
      },
      setMode: (mode) => {
        // Double guard (see plan Task 15): reducer AND WS hook both
        // short-circuit when the chat is streaming. A mid-turn mode
        // switch would desync with the server's ChatThread.mode; surface
        // the "invalid-state-mode" toast instead so the user can retry
        // between turns. The WS hook also guards this path — see
        // ``lib/ws/hooks.ts#useChatWebSocket``.
        if (get().streaming) {
          useSystemStore.getState().setMidTurn("invalid-state-mode");
          return;
        }
        set({ mode });
      },
      setScope: (scope) => set({ scope }),
      setView: (view) => set({ view }),
      toggleRail: () => set((s) => ({ railOpen: !s.railOpen })),
      setRailOpen: (railOpen) => set({ railOpen }),
      setActiveThreadId: (activeThreadId) => set({ activeThreadId }),
      setStreaming: (streaming) => set({ streaming }),
      markScopeInitialized: (vaultPath) => {
        writeScopeInitialized(vaultPath);
        set({ scopeInitialized: true });
      },
      loadScopeInitializedFor: (vaultPath) => {
        // Idempotent: only flip the in-memory mirror when the
        // localStorage flag is set AND the slot is currently false.
        // The reverse direction (mirror=true, storage=false) means
        // the user manually cleared localStorage — leave the mirror
        // alone for the rest of this session; a reload re-reads.
        const stored = readScopeInitialized(vaultPath);
        if (stored && !get().scopeInitialized) {
          set({ scopeInitialized: true });
        }
      },
    }),
    {
      name: "brain-app",
      storage: createJSONStorage(() => localStorage),
      // URL is source of truth for `view` + `activeThreadId`; streaming is
      // ephemeral. Persist only durable UI preferences.
      partialize: (s) => ({
        theme: s.theme,
        density: s.density,
        mode: s.mode,
        scope: s.scope,
        railOpen: s.railOpen,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          applyHtmlDataset(state.theme, state.density);
        }
      },
    },
  ),
);
