"use client";

import { create } from "zustand";

import {
  listWatchedFolders,
  resyncFolder,
  type ResyncFolderData,
  type WatchedFolderEntry,
} from "@/lib/api/tools";

/**
 * Watched-folders store (Plan 22 T12).
 *
 * Mirrors the ``useDomainsStore`` shape (Plan 12 T5 / Plan 13 T2) so
 * the Settings panel, the topbar status indicator (T14), and the
 * Orphans panel (T13) all read the same canonical view of
 * ``brain_list_watched_folders`` and re-render automatically when one
 * consumer mutates the underlying config (unwatch, resync, watch).
 *
 * v1 (Plan 22 T12) does NOT add a BroadcastChannel for cross-tab pubsub
 * — every peer consumer in this realm is in the same tab today
 * (Settings panel + topbar indicator + Orphans panel render in one
 * shell). When Plan 23 lands the future-cross-tab story (or when a
 * second realm starts reading watched-folder state), promoting this
 * store to the ``domains-store`` cross-tab shape is a tracked candidate.
 *
 * The store surface is intentionally narrow — ``refresh()`` is the
 * single source of truth for fetch + update; ``removeFolderOptimistic``
 * is the only direct mutator (UX affordance for the Settings unwatch
 * action so peer subscribers update before the backend round-trip
 * resolves). Direct ``setFolders`` is deliberately absent so callers go
 * through the API.
 *
 * In-flight serialization is a Promise cache (not a flag), matching
 * ``domains-store.ts``'s pattern: concurrent ``refresh()`` calls share
 * one Promise so any ``await refresh()`` resolves once the in-flight
 * fetch lands.
 */

// ---------- Store shape ----------

export interface WatchedFoldersState {
  /** Most recent ``brain_list_watched_folders`` response. ``[]`` until
   *  first ``refresh()`` lands. */
  folders: WatchedFolderEntry[];
  /** ``true`` once a ``refresh()`` has resolved at least once.
   *  Consumers gate first-mount auto-fetch on this so the panel's
   *  loading shimmer drops at the right moment. */
  loaded: boolean;
  /** Last error from ``refresh()``. ``null`` on success. Drives the
   *  inline error banner in the Settings panel (mirrors the
   *  ``useDomainsStore.error`` precedent / Plan 16 T4 D4 pattern). */
  error: Error | null;

  /** Fetch ``brain_list_watched_folders`` and update ``folders`` /
   *  ``loaded`` / ``error``. Concurrent calls share a single in-flight
   *  Promise (see module docstring). Always re-fetches — callers who
   *  need rate-limiting wrap themselves. Resolve-always semantics:
   *  failures are recorded on ``error`` state, the returned Promise
   *  resolves cleanly. */
  refresh: () => Promise<void>;
  /** Drop a folder row from ``folders`` immediately for snappy UI —
   *  used by the Settings → Watched folders unwatch handler (T12)
   *  after the user confirms the unwatch but before the API round-trip
   *  resolves. No API call, no fetch — just a synchronous state update
   *  so peer subscribers re-render without waiting on the network.
   *  Caller owns the API call AND the rollback (``refresh()`` to
   *  restore the row on failure). No-op when ``path`` is not in
   *  ``folders``. */
  removeFolderOptimistic: (path: string) => void;
  /** Resolve-rejects semantics (unlike ``refresh``): the caller awaits
   *  the result to drive the per-row spinner + toast lifecycle. On
   *  success: returns the backend's ``ResyncFolderData`` AND triggers
   *  a follow-up ``refresh()`` so any row stats invalidated by the
   *  resync (file_count, orphan_count, last_sync) reconcile with the
   *  canonical backend list. On failure: rejects with the original
   *  error so the caller can push a danger toast — the store does NOT
   *  swallow the error onto ``error`` state (which is reserved for
   *  ``refresh()`` failures that the inline error banner reads).
   *  Plan 22 T12 fix-up — replaces the earlier "Coming soon" tooltip
   *  with a fully-wired action. */
  resyncFolder: (folder: string) => Promise<ResyncFolderData>;
  /** Test-only: reset the store to initial state + clear any in-flight
   *  promise. Used by ``beforeEach`` in unit tests so cases don't leak
   *  through the singleton store. */
  _resetForTesting: () => void;
}

// ---------- In-flight serialization ----------

/**
 * Module-private Promise cache. Concurrent ``refresh()`` calls share
 * one Promise so any ``await refresh()`` resolves once the in-flight
 * fetch lands — preserves call-site semantics. Lives at module scope
 * (not in store state) because zustand's ``set`` is for state
 * subscribers care about; an in-flight Promise isn't user-observable
 * state, it's a coordination primitive.
 */
let inFlightPromise: Promise<void> | null = null;

// ---------- Store ----------

export const useWatchedFoldersStore = create<WatchedFoldersState>(
  (set) => ({
    folders: [],
    loaded: false,
    error: null,

    refresh: () => {
      if (inFlightPromise) return inFlightPromise;
      // Resolve-always semantics: failures land on ``error`` state and
      // the returned Promise resolves cleanly. The panel's first-mount
      // auto-refresh fires ``void refresh()`` and we don't want a
      // transient backend hiccup to surface as an unhandled rejection.
      // Callers who need failure information read ``store.error``.
      inFlightPromise = listWatchedFolders()
        .then((r) => {
          const folders = r.data?.folders ?? [];
          set({ folders, loaded: true, error: null });
        })
        .catch((err: unknown) => {
          const error = err instanceof Error ? err : new Error(String(err));
          set({ error });
        })
        .finally(() => {
          // Drop the cache so the next call re-fetches. Done in
          // ``finally`` so success AND failure both clear — otherwise a
          // failed refresh would block all subsequent retries.
          inFlightPromise = null;
        });
      return inFlightPromise;
    },

    removeFolderOptimistic: (path) => {
      set((s) => ({ folders: s.folders.filter((f) => f.path !== path) }));
    },

    resyncFolder: async (folder) => {
      // Resolve-rejects semantics (per JSDoc): the caller awaits to
      // drive the per-row spinner + toast lifecycle. We do NOT mutate
      // ``error`` on failure — that's the ``refresh()`` banner's
      // reserved channel. The follow-up ``refresh()`` is fire-and-
      // forget (``void``) so the toast lands without waiting on a
      // potentially slow stats walk; if the refresh fails it lands on
      // the banner per existing semantics.
      const response = await resyncFolder({ folder });
      if (!response.data) {
        // Defensive: backend always emits ``data`` on success per the
        // T5 pin, but the response envelope's TS shape allows
        // ``undefined``. Map to a plain Error so the caller's catch
        // arm gets a consistent shape.
        throw new Error("brain_resync_folder returned no data");
      }
      void useWatchedFoldersStore.getState().refresh();
      return response.data;
    },

    _resetForTesting: () => {
      inFlightPromise = null;
      set({ folders: [], loaded: false, error: null });
    },
  }),
);
