"use client";

import { create } from "zustand";

import { listDomains } from "@/lib/api/tools";
import { ACCENT_SWATCHES } from "@/components/settings/domain-form";
import { createChannelPubsub, type ChannelPubsub } from "./_broadcast";

/**
 * Domains store (Plan 12 Task 5).
 *
 * Promotes ``useDomains()`` from a module-level singleton cache to a
 * real zustand store + selector so every consumer (topbar, browse,
 * settings panel, setup wizard, future active-domain dropdown) sees
 * the same canonical view of ``brain_list_domains`` and re-renders
 * automatically when one consumer mutates it.
 *
 * Pre-Plan-12 the cache lived in module state; mutations called
 * ``invalidateDomainsCache()``, which dropped the next-fetch promise
 * but left every already-mounted hook's local React state untouched
 * (cross-instance divergence — see ``tasks/lessons.md`` Plan 11
 * closure addendum). The Playwright e2e worked around it with
 * ``page.reload()`` between mutation and cross-surface verification.
 *
 * The new store surface is intentionally narrow: ``refresh()`` is the
 * single source of truth for fetch + update; ``setActiveDomainOptimistic``
 * is the only direct mutator (UX affordance for the active-domain
 * dropdown — Plan 12 Task 8). Direct ``setDomains`` is deliberately
 * absent so callers go through the API.
 *
 * Lives in its own file (rather than appending to ``app-store.ts``)
 * because mixing persisted user prefs (theme/density/mode/scope/
 * railOpen, ``app-store.ts``) with ephemeral cached server state
 * (this file) makes the ``persist`` middleware's ``partialize``
 * brittle every time a slice is added. ``system-store.ts``'s docstring
 * pins the same rationale.
 *
 * In-flight serialization is a Promise cache (not a flag). Concurrent
 * ``refresh()`` calls get back the same Promise so any ``await
 * useDomainsStore.getState().refresh()`` resolves once the in-flight
 * fetch lands. A flag-with-discard would drop the second caller's
 * await semantics.
 */

// ---------- Types (re-exported from lib/hooks/use-domains for back-compat) ----------

export interface DomainEntry {
  slug: string;
  /** Humanised name for chrome — Title Case with separators replaced. */
  label: string;
  /** CSS color value — built-ins use a ``--dom-{slug}`` variable, user-
   *  added domains rotate through ``ACCENT_SWATCHES``. */
  accent: string;
  /** Listed in ``Config.domains``. */
  configured: boolean;
  /** A folder by this slug exists at the vault root. */
  on_disk: boolean;
}

const BUILTIN_SLUGS = new Set(["research", "work", "personal"]);

export function humaniseDomain(slug: string): string {
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part[0]!.toUpperCase() + part.slice(1))
    .join(" ");
}

function accentFor(slug: string, userIndex: number): string {
  if (BUILTIN_SLUGS.has(slug)) {
    return `var(--dom-${slug})`;
  }
  return ACCENT_SWATCHES[userIndex % ACCENT_SWATCHES.length] ?? "#6A8CAA";
}

interface RawListDomainsEntry {
  slug: string;
  configured: boolean;
  on_disk: boolean;
}

interface DomainsPayload {
  entries: DomainEntry[];
  /** ``Config.active_domain`` from the backend (Plan 11 Task 6).
   *  Empty string when the backend pre-dates Task 6 — callers must
   *  guard. */
  activeDomain: string;
}

/**
 * Wire-format payload posted to the ``"brain-domains"``
 * BroadcastChannel on every store mutation (Plan 16 Task 6 / D6).
 * Peer tabs deserialize this back into ``{domains, activeDomain}``
 * via ``_internalSet`` so consumers see the same canonical view of
 * ``brain_list_domains`` without a ``page.reload()``.
 *
 * ``loaded`` is intentionally NOT broadcast: a peer's freshness
 * latch is its own (a peer that just mounted should still trigger
 * its own first-mount ``refresh()`` even after receiving an
 * inbound payload — receiving an inbound payload doesn't mean THIS
 * tab has confirmed the data with the backend itself). Same shape
 * for ``error``: it's a per-tab transport state, not a shared one.
 */
interface DomainsBroadcastPayload {
  domains: DomainEntry[];
  activeDomain: string;
}

function payloadFromResponse(
  data:
    | {
        domains?: string[];
        entries?: RawListDomainsEntry[];
        active_domain?: string;
      }
    | null
    | undefined,
): DomainsPayload {
  if (!data) return { entries: [], activeDomain: "" };
  const raw: RawListDomainsEntry[] =
    data.entries && Array.isArray(data.entries)
      ? data.entries
      : (data.domains ?? []).map((slug) => ({
          slug,
          configured: true,
          on_disk: true,
        }));

  let userIdx = 0;
  const entries = raw.map((r) => {
    const isBuiltin = BUILTIN_SLUGS.has(r.slug);
    const accent = accentFor(r.slug, isBuiltin ? 0 : userIdx);
    if (!isBuiltin) userIdx += 1;
    return {
      slug: r.slug,
      label: humaniseDomain(r.slug),
      accent,
      configured: r.configured,
      on_disk: r.on_disk,
    };
  });
  return { entries, activeDomain: data.active_domain ?? "" };
}

// ---------- Store shape ----------

export interface DomainsState {
  /** Most recent ``brain_list_domains`` response, hydrated into the
   *  consumer-friendly shape. ``[]`` until first ``refresh()`` lands. */
  domains: DomainEntry[];
  /** ``Config.active_domain`` from the most recent response.
   *  Empty string until first ``refresh()`` lands or when the backend
   *  pre-dates Plan 11 Task 6. */
  activeDomain: string;
  /** ``true`` once a ``refresh()`` has resolved at least once.
   *  Consumers use this to gate first-mount auto-fetch. Renamed from
   *  ``domainsLoaded`` in Plan 16 Task 5 / D5 to align with
   *  ``cross-domain-gate-store``'s ``loaded`` field naming. */
  loaded: boolean;
  /** Last error from ``refresh()``. ``null`` on success. */
  error: Error | null;

  /** Fetch ``brain_list_domains`` and update ``domains`` /
   *  ``activeDomain`` / ``loaded``. Concurrent calls share a
   *  single in-flight Promise (see module docstring). Always re-fetches
   *  — callers who need rate-limiting wrap themselves. */
  refresh: () => Promise<void>;
  /** Update ``activeDomain`` immediately for snappy UI — used by the
   *  active-domain dropdown (Plan 12 Task 8) after the user picks a
   *  new value but before the API round-trip resolves. The next
   *  ``refresh()`` reconciles whatever the API returns. Fire-and-
   *  forget; the caller owns the API call. */
  setActiveDomainOptimistic: (slug: string) => void;
  /** Drop a domain row from ``domains`` immediately for snappy UI —
   *  used by the Settings → Domains delete handler (Plan 16 Task 4 /
   *  D4) after the user confirms a delete but before the API round-
   *  trip resolves. Mirrors ``setActiveDomainOptimistic``'s in-store-
   *  only pattern: no API call, no fetch, just a synchronous state
   *  update so peer subscribers (topbar scope chip, active-domain
   *  dropdown, browse) re-render without waiting on the network.
   *  Caller owns the API call AND the rollback (``refresh()`` to
   *  restore the row on failure). No-op when ``slug`` is not in
   *  ``domains``. */
  removeDomainOptimistic: (slug: string) => void;
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
 * the old module-state cache.
 *
 * Lives at module scope (not in store state) because zustand's
 * ``set`` is for state subscribers care about; an in-flight Promise
 * isn't a state — it's a coordination primitive. Putting it in store
 * state would force every consumer that selects ``domains`` to also
 * re-render when the in-flight Promise reference changes.
 */
let inFlightPromise: Promise<void> | null = null;

// ---------- Cross-tab pubsub (Plan 16 Task 6 / D6) ----------

/**
 * BroadcastChannel name for cross-tab pubsub of domains-store
 * mutations. MUST be distinct from ``cross-domain-gate-store``'s
 * channel name (``"brain-cross-domain-gate"``) so the two stores
 * don't cross-contaminate. Exported for tests so the pin tests can
 * simulate a peer tab without reaching into the store internals.
 */
export const DOMAINS_BROADCAST_CHANNEL = "brain-domains";

/**
 * Reentry guard: when the inbound BroadcastChannel handler calls
 * ``_internalSet`` to apply a peer payload, the actions that the
 * application normally calls (``refresh``, ``setActiveDomainOptimistic``,
 * ``removeDomainOptimistic``) MUST NOT post that change back to the
 * channel — otherwise tab A → tab B → tab A → … would ping-pong
 * forever. The flag is set TRUE by ``_internalSet`` for the duration
 * of the inbound apply; ``post()`` (the wrapper below) checks it and
 * skips the broadcast when set. Lives at module scope (not in store
 * state) because it's a coordination primitive, not user-observable
 * state.
 */
let _isInternalUpdate = false;

/**
 * Lazily-constructed channel pubsub. Constructed on first ``post()``
 * via ``ensureChannel()`` so:
 *
 *   - SSR import doesn't pay for a BroadcastChannel construction it
 *     can't use (the helper's SSR guard already returns a no-op, but
 *     deferring construction keeps module init hot path minimal).
 *   - ``_resetForTesting`` can drop the reference and the next ``post``
 *     will rebuild it — useful when a test wants to simulate a fresh
 *     module load without re-importing.
 *
 * Lives at module scope because the channel binding is a singleton
 * per module realm (matches BroadcastChannel's tab-singleton shape).
 */
let _channel: ChannelPubsub<DomainsBroadcastPayload> | null = null;

function ensureChannel(): ChannelPubsub<DomainsBroadcastPayload> {
  if (_channel) return _channel;
  _channel = createChannelPubsub<DomainsBroadcastPayload>(
    DOMAINS_BROADCAST_CHANNEL,
    (data) => {
      // Inbound: apply WITHOUT re-broadcasting. ``_internalSet``
      // raises ``_isInternalUpdate`` for the duration of the apply
      // so any internal call to ``post()`` from inside the apply
      // block (none today, but defensive) is silenced.
      _internalSet(data);
    },
  );
  return _channel;
}

function post(data: DomainsBroadcastPayload): void {
  if (_isInternalUpdate) return;
  ensureChannel().post(data);
}

/**
 * Apply an inbound peer-tab payload to the local store WITHOUT
 * re-broadcasting. The reentry guard flag is raised for the duration
 * of the ``setState`` so any call to ``post()`` from inside (defensive
 * — there shouldn't be any) is silenced. ``loaded`` and ``error`` are
 * deliberately untouched: see ``DomainsBroadcastPayload`` rationale.
 */
function _internalSet(data: DomainsBroadcastPayload): void {
  _isInternalUpdate = true;
  try {
    useDomainsStore.setState({
      domains: data.domains,
      activeDomain: data.activeDomain,
    });
  } finally {
    _isInternalUpdate = false;
  }
}

// ---------- Store ----------

export const useDomainsStore = create<DomainsState>((set, get) => ({
  domains: [],
  activeDomain: "",
  loaded: false,
  error: null,

  refresh: () => {
    if (inFlightPromise) return inFlightPromise;
    // Resolve-always semantics: failures are recorded as ``error``
    // state and the returned Promise resolves cleanly. The hook's
    // first-mount auto-refresh fires ``void refresh()`` and we don't
    // want a transient backend hiccup to surface as an unhandled
    // rejection in every component tree that mounts the topbar.
    // Callers who need failure information read ``store.error``.
    inFlightPromise = listDomains()
      .then((r) => {
        const payload = payloadFromResponse(r.data ?? null);
        set({
          domains: payload.entries,
          activeDomain: payload.activeDomain,
          loaded: true,
          error: null,
        });
        // Plan 16 Task 6 / D6: broadcast the resolved-from-API view
        // to peer tabs. ``post()`` short-circuits when the apply is
        // an inbound peer payload (``_isInternalUpdate``) so this
        // never echoes.
        post({
          domains: payload.entries,
          activeDomain: payload.activeDomain,
        });
      })
      .catch((err: unknown) => {
        const error = err instanceof Error ? err : new Error(String(err));
        set({ error });
        // Errors are intentionally NOT broadcast: per-tab transport
        // state, not shared-vault state.
      })
      .finally(() => {
        // Drop the cache so the next call re-fetches. Done in a
        // ``finally`` so success AND failure both clear — otherwise a
        // failed refresh would block all subsequent retries.
        inFlightPromise = null;
      });
    return inFlightPromise;
  },

  setActiveDomainOptimistic: (slug) => {
    if (get().activeDomain === slug) return;
    set({ activeDomain: slug });
    // Plan 16 Task 6 / D6: peer tabs see the optimistic active-domain
    // change without waiting for the API round-trip + ``refresh()``.
    post({ domains: get().domains, activeDomain: slug });
  },

  removeDomainOptimistic: (slug) => {
    set((s) => ({ domains: s.domains.filter((d) => d.slug !== slug) }));
    // Plan 16 Task 6 / D6: peer tabs see the row drop without waiting
    // for the API round-trip + ``refresh()``. Read ``get()`` AFTER
    // ``set`` so the broadcast carries the post-filter state.
    post({ domains: get().domains, activeDomain: get().activeDomain });
  },

  _resetForTesting: () => {
    inFlightPromise = null;
    // Tear down the channel so the next ``ensureChannel()`` rebuilds
    // it bound to whatever ``BroadcastChannel`` the test environment
    // currently has installed (e.g. a mock swapped in between cases,
    // or a re-stubbed global after an SSR-guard test). Then re-arm
    // it eagerly so inbound peer posts deliver to the test's store
    // even before any outbound mutation triggers a lazy build.
    if (_channel) {
      _channel.close();
      _channel = null;
    }
    _isInternalUpdate = false;
    set({
      domains: [],
      activeDomain: "",
      loaded: false,
      error: null,
    });
    // Re-arm AFTER state reset so any race with a peer's still-in-
    // flight post lands on the freshly-zeroed store, not on stale
    // pre-reset state. SSR-safe via the helper's guard.
    ensureChannel();
  },
}));

// Eagerly construct the channel at module load so peer tabs can
// deliver inbound updates even before this tab has called ``post()``
// for the first time. Without this, tab B (which only ever READS
// from the store, e.g. a topbar that doesn't mutate) would never
// see tab A's mutations because B's channel wouldn't exist until
// B itself called ``post()``. SSR-safe via the helper's
// ``typeof BroadcastChannel === "undefined"`` guard.
ensureChannel();
