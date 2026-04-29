"use client";

import { create } from "zustand";

import { configGet } from "@/lib/api/tools";

/**
 * Cross-domain gate store (Plan 13 Task 3 / D3).
 *
 * Promotes the two ``Config`` fields the cross-domain confirmation
 * modal's trigger gate needs — ``privacy_railed`` (the slug list the
 * trigger compares scope against) and ``cross_domain_warning_acknowledged``
 * (the per-vault opt-out flag) — from per-hook React state to a
 * shared zustand store + selector.
 *
 * Pre-Plan-13 the gate hook held local React state for both fields and
 * each consumer's ``refresh()`` only re-fetched its own copy. The
 * Settings toggle in ``panel-domains.tsx`` mutates ``acknowledged``
 * via ``setCrossDomainWarningAcknowledged`` but the chat-screen's
 * ``useCrossDomainGate()`` instance never saw the change without a
 * remount or page reload (cross-instance / cross-tab divergence —
 * same shape Plan 11 closure addendum named on ``useDomains`` and
 * Plan 12 Task 5 fixed via ``domains-store.ts``).
 *
 * The new store surface mirrors ``domains-store.ts``: ``refresh()``
 * is the single source of truth for fetch + update;
 * ``setAcknowledgedOptimistic`` is the only direct mutator (UX
 * affordance for the Settings toggle so peer consumers re-render
 * before the API round-trip resolves). Direct ``setPrivacyRailed``
 * is deliberately absent so callers go through the API
 * (``setPrivacyRailed()`` → ``refresh()``).
 *
 * Lives in its own file (rather than appending to ``app-store.ts``
 * or extending ``domains-store.ts``) per D3: separate concerns,
 * separate stores. ``domains-store.ts``'s docstring pins the same
 * rationale — mixing persisted user prefs with ephemeral cached
 * server state makes the persist middleware brittle.
 *
 * In-flight serialization is a Promise cache (not a flag), matching
 * ``domains-store.ts``. Concurrent ``refresh()`` calls share one
 * Promise so any ``await refresh()`` resolves once the in-flight
 * fetch lands. A flag-with-discard would drop the second caller's
 * await semantics.
 *
 * Failure handling: errors from ``configGet`` resolve to safe
 * defaults (``privacyRailed=["personal"]`` + ``acknowledged=false``)
 * to fail open — if the backend can't tell us whether the user has
 * acknowledged, default to "show the modal" (safer than silently
 * skipping it).
 */

// ---------- Store shape ----------

export interface CrossDomainGateStoreState {
  /** ``Config.privacy_railed`` — slugs whose inclusion in a multi-
   *  domain scope triggers the cross-domain modal. ``["personal"]``
   *  until the first ``refresh()`` resolves (matches the schema
   *  default). */
  privacyRailed: string[];
  /** ``Config.cross_domain_warning_acknowledged`` — when ``true``
   *  the modal is suppressed regardless of scope. ``false`` until
   *  the first ``refresh()`` resolves (fail open — show the modal). */
  acknowledged: boolean;
  /** ``true`` once a ``refresh()`` has resolved at least once.
   *  Consumers use this to gate first-mount auto-fetch and skip the
   *  trigger-fire check while the gate is hydrating (don't fire the
   *  modal off stale defaults that disagree with disk). */
  loaded: boolean;
  /** Last error from ``refresh()``. ``null`` on success. Surfaces
   *  for callers that want to differentiate "still loading" from
   *  "load failed and we fell back to safe defaults". */
  error: Error | null;

  /** Fetch ``privacy_railed`` + ``cross_domain_warning_acknowledged``
   *  via two ``brain_config_get`` calls and update store fields.
   *  Concurrent calls share a single in-flight Promise (see module
   *  docstring). Always re-fetches — callers who need rate-limiting
   *  wrap themselves. Resolves cleanly even on API failure: errors
   *  are recorded as ``error`` state and the fields fall back to
   *  safe defaults (``["personal"]`` + ``false``). */
  refresh: () => Promise<void>;
  /** Update ``acknowledged`` immediately for snappy UI — used by the
   *  Settings toggle (Plan 13 Task 3) after the user flips it but
   *  before the API round-trip resolves. The next ``refresh()``
   *  reconciles whatever the API ultimately returns. Fire-and-forget;
   *  the caller owns the API call. */
  setAcknowledgedOptimistic: (value: boolean) => void;
  /** Test-only: reset the store to initial state + clear any
   *  in-flight promise. Used by ``beforeEach`` in unit tests so
   *  cases don't leak through the singleton store. */
  _resetForTesting: () => void;
}

// ---------- In-flight serialization ----------

/**
 * Module-private Promise cache. Concurrent ``refresh()`` calls share
 * one Promise so any ``await refresh()`` resolves once the in-flight
 * fetch lands — preserves the call-site semantics callers had under
 * the old per-hook React state. Lives at module scope (not in store
 * state) for the same reason ``domains-store.ts`` keeps it there:
 * an in-flight Promise isn't a state — it's a coordination primitive.
 */
let inFlightPromise: Promise<void> | null = null;

// ---------- Store ----------

export const useCrossDomainGateStore = create<CrossDomainGateStoreState>(
  (set) => ({
    privacyRailed: ["personal"],
    acknowledged: false,
    loaded: false,
    error: null,

    refresh: () => {
      if (inFlightPromise) return inFlightPromise;
      inFlightPromise = (async () => {
        try {
          const [railRes, ackRes] = await Promise.all([
            configGet({ key: "privacy_railed" }),
            configGet({ key: "cross_domain_warning_acknowledged" }),
          ]);
          const rail = railRes.data?.value;
          const ack = ackRes.data?.value;
          set({
            privacyRailed: Array.isArray(rail)
              ? (rail as string[])
              : ["personal"],
            acknowledged: typeof ack === "boolean" ? ack : false,
            loaded: true,
            error: null,
          });
        } catch (err) {
          // Fail open — default to show-the-modal so the user is never
          // silently skipped past the confirmation due to a transient
          // backend hiccup. Resolve-always semantics matches the
          // ``domains-store`` pattern: callers' ``void refresh()``
          // never raises an unhandled rejection.
          const error = err instanceof Error ? err : new Error(String(err));
          set({
            privacyRailed: ["personal"],
            acknowledged: false,
            loaded: true,
            error,
          });
        } finally {
          // Drop the cache so the next call re-fetches. Done in a
          // ``finally`` so success AND failure both clear — otherwise
          // a failed refresh would block all subsequent retries for
          // the lifetime of the page.
          inFlightPromise = null;
        }
      })();
      return inFlightPromise;
    },

    setAcknowledgedOptimistic: (value) => {
      set((state) => {
        if (state.acknowledged === value) return state;
        return { ...state, acknowledged: value };
      });
    },

    _resetForTesting: () => {
      inFlightPromise = null;
      set({
        privacyRailed: ["personal"],
        acknowledged: false,
        loaded: false,
        error: null,
      });
    },
  }),
);
