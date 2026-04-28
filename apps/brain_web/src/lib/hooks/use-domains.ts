"use client";

import * as React from "react";

import {
  useDomainsStore,
  humaniseDomain as _humaniseDomain,
  type DomainEntry as _DomainEntry,
} from "@/lib/state/domains-store";

/**
 * useDomains (Plan 10 Task 7 → Plan 12 Task 5).
 *
 * Selector over ``useDomainsStore`` (see ``lib/state/domains-store.ts``)
 * around the ``brain_list_domains`` tool. Every consumer (topbar
 * scope picker, browse file tree, settings panel, setup wizard,
 * future active-domain dropdown) shares the same canonical store —
 * one consumer mutates, all peers re-render.
 *
 * Pre-Plan-12 the cache lived in module state and each hook instance
 * held its own React state, so panel-side mutations + ``invalidate
 * DomainsCache()`` only re-fetched on the next mount of each peer
 * (cross-instance divergence). The Plan 12 zustand promotion fixes
 * this by routing every read through one store.
 *
 * Public API preserved for back-compat:
 *
 *   - ``useDomains()`` returns ``{domains, activeDomain, loading,
 *     error, refresh}``. Same shape as Plan 10 / Plan 11.
 *   - ``invalidateDomainsCache()`` is a thin alias for
 *     ``useDomainsStore.getState().refresh()`` so existing call sites
 *     in panel-domains.tsx work unchanged. Marked deprecated; new
 *     code should call ``refresh()`` (or
 *     ``useDomainsStore.getState().refresh()``) directly.
 *   - ``humaniseDomain`` re-exported from the store module.
 *   - ``_setDomainsCacheForTesting`` retained as a test seam routed
 *     through the store's ``_resetForTesting`` action.
 *
 * The domain list returned here is the *union* of ``Config.domains``
 * + on-disk slugs (matching ``brain_list_domains``'s response).
 */

// Re-export the type so existing imports (``import type { DomainEntry }
// from "@/lib/hooks/use-domains"``) keep working. Tests + components
// alike read the alias from this module.
export type DomainEntry = _DomainEntry;

export const humaniseDomain = _humaniseDomain;

/**
 * @deprecated Plan 12 Task 5 — call
 * ``useDomainsStore.getState().refresh()`` directly. This alias
 * remains so existing call sites (panel-domains.tsx mutation helpers)
 * keep working without churn; remove once all callers migrate.
 */
export function invalidateDomainsCache(): void {
  // Fire-and-forget — same semantics as the pre-Plan-12 helper. The
  // returned Promise from ``refresh()`` is intentionally dropped so
  // callers in event handlers (panel-domains.tsx) don't need to
  // ``await`` it. The store's in-flight Promise cache prevents
  // duplicate fetches if multiple mutations land in the same tick.
  void useDomainsStore.getState().refresh();
}

/** Reset the store to its initial state. Used by tests. */
export function _setDomainsCacheForTesting(
  entries: DomainEntry[] | null,
  activeDomain = "",
): void {
  if (entries === null) {
    useDomainsStore.getState()._resetForTesting();
    return;
  }
  // Tests that pre-seed the cache need ``domainsLoaded=true`` so the
  // first-mount auto-refresh in ``useDomains()`` skips the fetch.
  // Setting state directly here (rather than going through
  // ``refresh()``) keeps the test deterministic — no listDomains
  // mock interaction required for tests that just want a known
  // starting point.
  useDomainsStore.setState({
    domains: entries,
    activeDomain,
    domainsLoaded: true,
    error: null,
  });
}

export interface UseDomainsResult {
  domains: DomainEntry[];
  /**
   * ``Config.active_domain`` from the most recent ``brain_list_domains``
   * response (Plan 11 Task 6). Empty string until the first fetch
   * resolves, or when the backend pre-dates Task 6. The topbar uses this
   * to hydrate ``app-store.scope`` once per vault on first mount
   * (Plan 11 Task 8 / D8).
   */
  activeDomain: string;
  loading: boolean;
  error: Error | null;
  /** Force-refetch. Plan 12 Task 5: now equivalent to
   *  ``useDomainsStore.getState().refresh()`` — every peer consumer
   *  re-renders with the new data automatically. */
  refresh: () => void;
}

export function useDomains(): UseDomainsResult {
  const domains = useDomainsStore((s) => s.domains);
  const activeDomain = useDomainsStore((s) => s.activeDomain);
  const domainsLoaded = useDomainsStore((s) => s.domainsLoaded);
  const error = useDomainsStore((s) => s.error);

  // First-mount auto-refresh for cold caches. The store's in-flight
  // Promise cache means concurrent first-mounts (e.g., topbar +
  // browse mounting in the same render tree) only trigger one fetch.
  // Re-runs only when ``domainsLoaded`` flips false → true (first
  // hydration) or back to false (after ``_resetForTesting``).
  React.useEffect(() => {
    if (!domainsLoaded) {
      void useDomainsStore.getState().refresh();
    }
  }, [domainsLoaded]);

  // ``loading`` is derived: still loading whenever the store hasn't
  // hydrated yet AND there's no error. Once hydrated, subsequent
  // refreshes don't flip back to ``loading`` — the existing data
  // stays visible while the new fetch lands (matches the old hook's
  // behaviour after first mount).
  const loading = !domainsLoaded && error === null;

  // ``refresh`` is stable per render — store actions are stable, and
  // we just project the store's action through. Wrapping in
  // ``React.useCallback`` keeps the returned reference stable across
  // re-renders so callers can put it in dep lists without causing
  // effect-loop churn.
  const refresh = React.useCallback(() => {
    void useDomainsStore.getState().refresh();
  }, []);

  return { domains, activeDomain, loading, error, refresh };
}
