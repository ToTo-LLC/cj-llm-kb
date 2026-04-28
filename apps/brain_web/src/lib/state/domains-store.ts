"use client";

import { create } from "zustand";

import { listDomains } from "@/lib/api/tools";
import { ACCENT_SWATCHES } from "@/components/settings/domain-form";

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
   *  Consumers use this to gate first-mount auto-fetch. */
  domainsLoaded: boolean;
  /** Last error from ``refresh()``. ``null`` on success. */
  error: Error | null;

  /** Fetch ``brain_list_domains`` and update ``domains`` /
   *  ``activeDomain`` / ``domainsLoaded``. Concurrent calls share a
   *  single in-flight Promise (see module docstring). Always re-fetches
   *  — callers who need rate-limiting wrap themselves. */
  refresh: () => Promise<void>;
  /** Update ``activeDomain`` immediately for snappy UI — used by the
   *  active-domain dropdown (Plan 12 Task 8) after the user picks a
   *  new value but before the API round-trip resolves. The next
   *  ``refresh()`` reconciles whatever the API returns. Fire-and-
   *  forget; the caller owns the API call. */
  setActiveDomainOptimistic: (slug: string) => void;
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

// ---------- Store ----------

export const useDomainsStore = create<DomainsState>((set, get) => ({
  domains: [],
  activeDomain: "",
  domainsLoaded: false,
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
          domainsLoaded: true,
          error: null,
        });
      })
      .catch((err: unknown) => {
        const error = err instanceof Error ? err : new Error(String(err));
        set({ error });
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
  },

  _resetForTesting: () => {
    inFlightPromise = null;
    set({
      domains: [],
      activeDomain: "",
      domainsLoaded: false,
      error: null,
    });
  },
}));
