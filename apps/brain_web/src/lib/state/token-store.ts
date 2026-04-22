// Per-run API token store — Plan 08 Task 2.
//
// Zustand-backed because module-level code (``apiFetch`` in ``@/lib/api/client``
// and the WebSocket client in ``@/lib/ws/client``) needs to read the current
// token synchronously WITHOUT being a React component. The bootstrap effect
// fetches ``/api/token`` once on mount and calls ``setToken()``; every fetch +
// WebSocket connect after that picks up the value via ``getToken()``.
//
// ## Why not just React context?
//
// React context is scoped to the component tree. Modules imported for their
// side effects (``apiFetch`` is imported in Server-Action-shaped client code
// that runs outside a component body) can't read a context. A Zustand store
// exposes both a React hook (``useTokenStore``) and a vanilla getter
// (``getToken()``) — same single source of truth.

import { create } from "zustand";

interface TokenState {
  /** Per-run API token from ``/api/token``. ``null`` until bootstrap fills it. */
  token: string | null;
  /** Set the token (called by the bootstrap effect). */
  setToken: (token: string | null) => void;
}

export const useTokenStore = create<TokenState>((set) => ({
  token: null,
  setToken: (token) => set({ token }),
}));

/**
 * Module-level accessor for non-React callers.
 *
 * ``apiFetch`` and the WebSocket client live outside the React tree, so they
 * can't use the ``useTokenStore`` hook. Reading ``.getState()`` is the
 * Zustand-blessed pattern for this — always returns the current value at
 * call time, no re-render subscription.
 */
export function getToken(): string | null {
  return useTokenStore.getState().token;
}
