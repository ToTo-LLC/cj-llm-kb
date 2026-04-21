"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

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

  setTheme: (t: Theme) => void;
  setDensity: (d: Density) => void;
  setMode: (m: ChatMode) => void;
  setScope: (s: string[]) => void;
  setView: (v: ViewName) => void;
  toggleRail: () => void;
  setRailOpen: (open: boolean) => void;
  setActiveThreadId: (id: string | null) => void;
  setStreaming: (flag: boolean) => void;
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
      scope: ["research", "work"],
      view: "chat",
      railOpen: true,
      activeThreadId: null,
      streaming: false,

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
        // TODO(Task 15): when streaming is true, emit invalid-state toast
        // instead of mutating the mode. Test coverage deferred to Task 15.
        if (get().streaming) return;
        set({ mode });
      },
      setScope: (scope) => set({ scope }),
      setView: (view) => set({ view }),
      toggleRail: () => set((s) => ({ railOpen: !s.railOpen })),
      setRailOpen: (railOpen) => set({ railOpen }),
      setActiveThreadId: (activeThreadId) => set({ activeThreadId }),
      setStreaming: (streaming) => set({ streaming }),
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
