"use client";

import { create } from "zustand";

import { configGet, configSet } from "@/lib/api/tools";
import { createChannelPubsub, type ChannelPubsub } from "./_broadcast";

/**
 * Budget store (Plan 16 Task 43 / D32(b)).
 *
 * Promotes the budget-snapshot read shape that ``panel-budget.tsx``
 * (Settings → Budget) and ``panel-domains-row.tsx`` (the per-domain
 * Budget caps subsection) used to scrape one ``configGet`` at a time
 * to a shared zustand store + selector. Mirrors the
 * ``domains-store.ts`` / ``cross-domain-gate-store.ts`` shape exactly:
 * ``refresh()`` is the single fetch + update entry point, an optimistic
 * mutator updates the store before the API round-trip resolves, and a
 * BroadcastChannel pubsub layer keeps peer tabs in sync without a
 * ``page.reload()``.
 *
 * Pre-Plan-16 the panel held its own ``useState`` per field and each
 * mount fired its own ``configGet``; opening Settings → Budget in two
 * tabs and saving from one left the other showing the old cap until
 * the user reloaded. The per-domain budget-caps subsection had the
 * same shape on a per-slug map. Plan 16 Task 43 / D32(b) closes the
 * class by wiring both reads through this store.
 *
 * What's IN the store (Config.budget surface):
 *
 *   - ``daily_usd``           — global daily spend cap (USD).
 *   - ``monthly_usd``         — global monthly spend cap (USD).
 *   - ``alert_threshold_pct`` — % of cap at which warnings fire.
 *   - ``per_domain``          — ``Record<slug, BudgetCap>`` map for
 *                                per-domain overrides (Plan 16 T28-T29).
 *
 * What's NOT in the store:
 *
 *   - ``budgetWallOpen`` (modal open flag) — already lives in
 *     ``system-store.ts`` with the rest of the per-tab UI chrome
 *     state. The modal opens on a WebSocket event, not on a config
 *     read; mixing it here would couple two different lifecycles.
 *   - Subsection form drafts (input strings, dirty flags). The
 *     Budget tab and the per-domain caps subsection each own their
 *     own ``useState`` for in-progress edits — UI-specific dirty
 *     state, not data layer.
 *
 * Lives in its own file (rather than appending to ``app-store.ts``)
 * for the same reason ``domains-store.ts`` does: mixing persisted
 * user prefs (theme/density/mode/scope/railOpen) with ephemeral cached
 * server state makes the ``persist`` middleware's ``partialize``
 * brittle every time a slice is added.
 *
 * In-flight serialization is a Promise cache (not a flag). Concurrent
 * ``refresh()`` calls get back the same Promise so any
 * ``await refresh()`` resolves once the in-flight fetch lands.
 */

// ---------- Types ----------

/** Per-domain budget cap entry — mirrors
 *  :class:`brain_core.config.schema.BudgetOverride`. Either / both
 *  caps may be ``null`` (= "no override; fall back to global"); a
 *  positive number caps spend attributed to this domain. The store
 *  carries the typed shape so callers can index ``per_domain[slug]``
 *  directly without inventing their own shape. */
export interface BudgetCap {
  daily_cap_usd: number | null;
  monthly_cap_usd: number | null;
}

export interface BudgetSnapshot {
  /** ``Config.budget.daily_usd`` — global daily cap (USD). ``null``
   *  until the first ``refresh()`` resolves or when the backend has
   *  no value set (the schema default applies). */
  daily_usd: number | null;
  /** ``Config.budget.monthly_usd`` — global monthly cap (USD).
   *  ``null`` until first ``refresh()`` resolves or unset. */
  monthly_usd: number | null;
  /** ``Config.budget.alert_threshold_pct`` — read-only in the UI
   *  (Settings displays it as a percentage of the cap; tunable only
   *  via the CLI). ``null`` until first ``refresh()``. */
  alert_threshold_pct: number | null;
  /** ``Config.budget.per_domain`` — slug → cap pair map. Empty when
   *  no per-domain overrides exist. Read by the per-domain
   *  ``BudgetCapsSubsection`` to seed its hydrate state. */
  per_domain: Record<string, BudgetCap>;
}

const EMPTY_SNAPSHOT: BudgetSnapshot = {
  daily_usd: null,
  monthly_usd: null,
  alert_threshold_pct: null,
  per_domain: {},
};

// ---------- Store shape ----------

export interface BudgetStoreState {
  /** Most recent budget snapshot. Defaults to all-null /
   *  empty-per-domain until the first ``refresh()`` resolves. */
  snapshot: BudgetSnapshot;
  /** ``true`` once a ``refresh()`` has resolved at least once.
   *  Consumers gate first-mount auto-fetch on this — matches
   *  ``domains-store``'s ``loaded`` semantics. */
  loaded: boolean;
  /** Last error from ``refresh()`` (or from a write that the store
   *  proxies). ``null`` on success. */
  error: Error | null;

  /** Fetch the full ``Config.budget`` surface and update the snapshot.
   *  Concurrent calls share one in-flight Promise. Resolves cleanly
   *  on failure (errors land on ``error``) so callers' ``void
   *  refresh()`` never unhandled-rejects. */
  refresh: () => Promise<void>;
  /** Persist a new daily-cap value via ``brain_config_set``. Updates
   *  the store optimistically; on API failure reverts to the prior
   *  value AND records the failure on ``error`` so the caller can
   *  surface a toast. ``null`` clears the cap (= no override). */
  setDailyCap: (value: number | null) => Promise<void>;
  /** Persist a new monthly-cap value. Same optimistic-revert shape
   *  as ``setDailyCap``. */
  setMonthlyCap: (value: number | null) => Promise<void>;
  /** Replace the per-domain entry for one slug. Whole-payload semantics
   *  (mirrors ``setDomainBudget`` in ``api/tools.ts``); both caps must
   *  be sent together so a half-applied save can't leave inconsistent
   *  on-disk state. ``null`` for a cap field = "no override; fall back
   *  to global"; ``null`` for the WHOLE entry would also be valid wire-
   *  shape but isn't exposed here — callers compose
   *  ``{daily_cap_usd: null, monthly_cap_usd: null}`` and the backend
   *  prunes to "no entry" automatically. */
  setDomainCap: (slug: string, cap: BudgetCap) => Promise<void>;
  /** Test-only: reset the store to initial state + clear any
   *  in-flight promise. Used by ``beforeEach`` in unit tests. */
  _resetForTesting: () => void;
}

// ---------- In-flight serialization ----------

let inFlightPromise: Promise<void> | null = null;

// ---------- Cross-tab pubsub (Plan 16 Task 43 / D32(b)) ----------

/**
 * Wire-format payload posted to the ``"brain-budget"`` BroadcastChannel
 * on every store mutation. Peer tabs deserialize back into ``snapshot``
 * via ``_internalSet``. ``loaded`` and ``error`` are deliberately NOT
 * broadcast (per-tab transport state — see ``domains-store``'s matching
 * docstring for the same rationale).
 */
interface BudgetBroadcastPayload {
  snapshot: BudgetSnapshot;
}

export const BUDGET_BROADCAST_CHANNEL = "brain-budget";

/** Reentry guard — see ``domains-store``'s ``_isInternalUpdate``
 *  docstring. Same pattern: raised TRUE for the duration of an
 *  inbound-from-peer apply so ``post()`` skips the broadcast and the
 *  pair of tabs never ping-pongs. */
let _isInternalUpdate = false;

let _channel: ChannelPubsub<BudgetBroadcastPayload> | null = null;

function ensureChannel(): ChannelPubsub<BudgetBroadcastPayload> {
  if (_channel) return _channel;
  _channel = createChannelPubsub<BudgetBroadcastPayload>(
    BUDGET_BROADCAST_CHANNEL,
    (data) => {
      _internalSet(data);
    },
  );
  return _channel;
}

function post(data: BudgetBroadcastPayload): void {
  if (_isInternalUpdate) return;
  ensureChannel().post(data);
}

function _internalSet(data: BudgetBroadcastPayload): void {
  _isInternalUpdate = true;
  try {
    useBudgetStore.setState({ snapshot: data.snapshot });
  } finally {
    _isInternalUpdate = false;
  }
}

// ---------- Helpers ----------

/** Read a numeric value from a ``brain_config_get`` response. The
 *  backend returns ``{ key, value }`` and budget keys are always
 *  ``number | null``. Anything else is treated as "unset" (returns
 *  ``null``) — defensive against schema drift. */
function readNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

/** Read the per-domain map. The wire shape is
 *  ``Record<slug, {daily_cap_usd?, monthly_cap_usd?}>``; we normalize
 *  missing fields to ``null`` so consumers don't have to repeat the
 *  optional-chaining dance. */
function readPerDomain(value: unknown): Record<string, BudgetCap> {
  if (value === null || typeof value !== "object") return {};
  const raw = value as Record<string, Partial<BudgetCap>>;
  const out: Record<string, BudgetCap> = {};
  for (const [slug, entry] of Object.entries(raw)) {
    out[slug] = {
      daily_cap_usd: entry?.daily_cap_usd ?? null,
      monthly_cap_usd: entry?.monthly_cap_usd ?? null,
    };
  }
  return out;
}

// ---------- Store ----------

export const useBudgetStore = create<BudgetStoreState>((set, get) => ({
  snapshot: EMPTY_SNAPSHOT,
  loaded: false,
  error: null,

  refresh: () => {
    if (inFlightPromise) return inFlightPromise;
    inFlightPromise = (async () => {
      try {
        // Four parallel fetches — the schema doesn't expose a single
        // ``budget`` aggregate read, and the wildcard handler returns
        // each leaf separately. ``Promise.all`` keeps the round-trip
        // count flat at one tick.
        const [dailyRes, monthlyRes, thresholdRes, perDomainRes] =
          await Promise.all([
            configGet({ key: "budget.daily_usd" }),
            configGet({ key: "budget.monthly_usd" }),
            configGet({ key: "budget.alert_threshold_pct" }),
            configGet({ key: "budget.per_domain" }),
          ]);
        const next: BudgetSnapshot = {
          daily_usd: readNumber(dailyRes.data?.value),
          monthly_usd: readNumber(monthlyRes.data?.value),
          alert_threshold_pct: readNumber(thresholdRes.data?.value),
          per_domain: readPerDomain(perDomainRes.data?.value),
        };
        set({ snapshot: next, loaded: true, error: null });
        post({ snapshot: next });
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        set({ error });
        // Errors are intentionally NOT broadcast: per-tab transport
        // state, not shared-vault state.
      } finally {
        inFlightPromise = null;
      }
    })();
    return inFlightPromise;
  },

  setDailyCap: async (value) => {
    const before = get().snapshot;
    // 1. Optimistic update — peer subscribers re-render immediately.
    const optimistic: BudgetSnapshot = { ...before, daily_usd: value };
    set({ snapshot: optimistic, error: null });
    post({ snapshot: optimistic });
    try {
      await configSet({ key: "budget.daily_usd", value });
    } catch (err) {
      // 2. Revert + surface the failure on ``error``. Re-broadcast
      //    the reverted view so peer tabs that saw the optimistic
      //    update also revert.
      const error = err instanceof Error ? err : new Error(String(err));
      set({ snapshot: before, error });
      post({ snapshot: before });
      throw error;
    }
  },

  setMonthlyCap: async (value) => {
    const before = get().snapshot;
    const optimistic: BudgetSnapshot = { ...before, monthly_usd: value };
    set({ snapshot: optimistic, error: null });
    post({ snapshot: optimistic });
    try {
      await configSet({ key: "budget.monthly_usd", value });
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      set({ snapshot: before, error });
      post({ snapshot: before });
      throw error;
    }
  },

  setDomainCap: async (slug, cap) => {
    const before = get().snapshot;
    const nextPerDomain = { ...before.per_domain, [slug]: cap };
    const optimistic: BudgetSnapshot = {
      ...before,
      per_domain: nextPerDomain,
    };
    set({ snapshot: optimistic, error: null });
    post({ snapshot: optimistic });
    try {
      // Whole-payload write — mirrors ``setDomainBudget`` in
      // ``api/tools.ts``. The backend prunes to "no entry" when both
      // caps are null, but we still post the pair so a partial-update
      // can't leave inconsistent on-disk state.
      await configSet({ key: `budget.per_domain.${slug}`, value: cap });
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      set({ snapshot: before, error });
      post({ snapshot: before });
      throw error;
    }
  },

  _resetForTesting: () => {
    inFlightPromise = null;
    if (_channel) {
      _channel.close();
      _channel = null;
    }
    _isInternalUpdate = false;
    set({
      snapshot: EMPTY_SNAPSHOT,
      loaded: false,
      error: null,
    });
    ensureChannel();
  },
}));

// Eagerly construct the channel at module load so peer tabs can
// deliver inbound updates even before this tab has called ``post()``
// for the first time. SSR-safe via the helper's
// ``typeof BroadcastChannel === "undefined"`` guard.
ensureChannel();
