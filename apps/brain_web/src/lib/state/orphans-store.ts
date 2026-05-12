"use client";

import { create } from "zustand";

import {
  deleteOrphan,
  listOrphans,
  restoreOrphan,
  type DeleteOrphanData,
  type OrphanEntry,
  type RestoreOrphanData,
} from "@/lib/api/tools";

/**
 * Orphans store (Plan 22 T13).
 *
 * Peer to :func:`useWatchedFoldersStore`. The Settings → Orphans panel
 * (T13) and the topbar status indicator (T14) both read the same
 * canonical view of ``brain_list_orphans`` so they re-render in lock-
 * step when one consumer mutates the underlying vault (restore /
 * delete).
 *
 * Mirrors the watched-folders store's shape:
 *
 *   - ``refresh()`` is the single source of truth for fetch + update;
 *     resolve-always semantics record errors on store state rather
 *     than rejecting.
 *   - ``removeOrphanOptimistic()`` is the only direct mutator (UX
 *     affordance for restore / delete so peer subscribers update
 *     before the backend round-trip resolves).
 *   - ``restoreOrphan()`` / ``deleteOrphan()`` use resolve-rejects
 *     semantics so the caller awaits to drive the per-row spinner +
 *     toast lifecycle.
 *
 * Cross-store invariant (mockup hand-off note): when a folder is
 * unwatched, its orphans REMAIN (D2: orphan-marking is the orphans-
 * store's responsibility, not the watched-folders store's). This store
 * MUST NOT auto-filter rows on watched-folder mutations — refresh is
 * always read from disk via ``brain_list_orphans``.
 *
 * In-flight serialization is a Promise cache (not a flag), matching
 * ``watched-folders-store.ts`` / ``domains-store.ts``'s pattern:
 * concurrent ``refresh()`` calls share one Promise so any
 * ``await refresh()`` resolves once the in-flight fetch lands.
 */

// ---------- Store shape ----------

export interface OrphansState {
  /** Most recent ``brain_list_orphans`` response. ``[]`` until first
   *  ``refresh()`` lands. */
  orphans: OrphanEntry[];
  /** ``true`` once a ``refresh()`` has resolved at least once.
   *  Consumers gate first-mount auto-fetch on this so the panel's
   *  loading shimmer drops at the right moment. */
  loaded: boolean;
  /** Last error from ``refresh()``. ``null`` on success. Drives the
   *  inline error banner in the Settings panel (mirrors the
   *  ``useWatchedFoldersStore.error`` precedent / Plan 16 T4 D4 pattern). */
  error: Error | null;

  /** Fetch ``brain_list_orphans`` and update ``orphans`` /
   *  ``loaded`` / ``error``. Concurrent calls share a single in-flight
   *  Promise (see module docstring). Always re-fetches — callers who
   *  need rate-limiting wrap themselves. Resolve-always semantics:
   *  failures are recorded on ``error`` state, the returned Promise
   *  resolves cleanly. */
  refresh: () => Promise<void>;
  /** Drop an orphan row from ``orphans`` immediately for snappy UI —
   *  used by the Settings → Orphans restore + delete handlers after the
   *  user has confirmed the action but before the API round-trip
   *  resolves. No API call, no fetch — just a synchronous state update
   *  so peer subscribers re-render without waiting on the network.
   *  Caller owns the API call AND the rollback (``refresh()`` to
   *  restore the row on failure). No-op when ``note_path`` is not in
   *  ``orphans``. */
  removeOrphanOptimistic: (notePath: string) => void;
  /** Resolve-rejects semantics (unlike ``refresh``): the caller awaits
   *  the result to drive the per-row spinner + toast lifecycle. On
   *  success: returns the backend's ``RestoreOrphanData`` AND triggers
   *  a follow-up ``refresh()`` so any orphan counts elsewhere
   *  (Settings → Watched folders' ``orphan_count`` column, topbar
   *  indicator) reconcile with the canonical backend list. On failure:
   *  rejects with the original error so the caller can push a danger
   *  toast — the store does NOT swallow the error onto ``error`` state
   *  (which is reserved for ``refresh()`` failures the inline error
   *  banner reads). */
  restoreOrphan: (notePath: string) => Promise<RestoreOrphanData>;
  /** Resolve-rejects semantics, same lifecycle as ``restoreOrphan``.
   *  Always passes ``typed_confirm: true`` to the backend — the UI
   *  guards typed-confirm at the modal layer; this helper is the
   *  post-confirm execution path. The backend still raises
   *  :class:`PermissionError` if a caller bypasses the modal and omits
   *  the flag — surfaces as :class:`ApiError`. */
  deleteOrphan: (notePath: string) => Promise<DeleteOrphanData>;
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

export const useOrphansStore = create<OrphansState>((set) => ({
  orphans: [],
  loaded: false,
  error: null,

  refresh: () => {
    if (inFlightPromise) return inFlightPromise;
    // Resolve-always semantics: failures land on ``error`` state and
    // the returned Promise resolves cleanly. The panel's first-mount
    // auto-refresh fires ``void refresh()`` and we don't want a
    // transient backend hiccup to surface as an unhandled rejection.
    // Callers who need failure information read ``store.error``.
    inFlightPromise = listOrphans()
      .then((r) => {
        const orphans = r.data?.orphans ?? [];
        set({ orphans, loaded: true, error: null });
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

  removeOrphanOptimistic: (notePath) => {
    set((s) => ({
      orphans: s.orphans.filter((o) => o.note_path !== notePath),
    }));
  },

  restoreOrphan: async (notePath) => {
    // Resolve-rejects semantics (per JSDoc): the caller awaits to
    // drive the per-row spinner + toast lifecycle. We do NOT mutate
    // ``error`` on failure — that's the ``refresh()`` banner's
    // reserved channel. The follow-up ``refresh()`` is fire-and-
    // forget (``void``) so the toast lands without waiting on the
    // re-walk; if the refresh fails it lands on the banner per
    // existing semantics.
    const response = await restoreOrphan({ note_path: notePath });
    if (!response.data) {
      // Defensive: backend always emits ``data`` on success per the
      // T5 pin, but the response envelope's TS shape allows
      // ``undefined``. Map to a plain Error so the caller's catch
      // arm gets a consistent shape.
      throw new Error("brain_restore_orphan returned no data");
    }
    void useOrphansStore.getState().refresh();
    return response.data;
  },

  deleteOrphan: async (notePath) => {
    // Always pass ``typed_confirm: true`` — the UI guards typed-confirm
    // at the modal layer (TypedConfirmDialog with slug / "delete N
    // notes" phrase). The backend still raises PermissionError if a
    // caller bypasses the modal and omits the flag — that bubbles up
    // as an ApiError to the caller's catch arm.
    const response = await deleteOrphan({
      note_path: notePath,
      typed_confirm: true,
    });
    if (!response.data) {
      throw new Error("brain_delete_orphan returned no data");
    }
    void useOrphansStore.getState().refresh();
    return response.data;
  },

  _resetForTesting: () => {
    inFlightPromise = null;
    set({ orphans: [], loaded: false, error: null });
  },
}));
