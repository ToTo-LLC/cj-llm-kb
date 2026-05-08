"use client";

import * as React from "react";

import {
  useDomainOverridesStore,
  EMPTY_DOMAIN_OVERRIDE_ENTRY,
  type DomainOverrideEntry as _DomainOverrideEntry,
  type DomainOverrideField as _DomainOverrideField,
} from "@/lib/state/domain-overrides-store";

/**
 * useDomainOverrides (Plan 16 Task 43 / D32(b)).
 *
 * Selector over ``useDomainOverridesStore`` (see
 * ``lib/state/domain-overrides-store.ts``) around the
 * ``Config.domain_overrides`` map. Consumers (the Settings → Domains
 * panel, the per-row override form) read from one canonical store —
 * mutating from one panel updates the other without a remount.
 *
 * Mirrors ``use-domains.ts`` and ``use-budget.ts``: thin selector +
 * first-mount auto-refresh + stable ``refresh`` callback. Per-slug
 * lookups go through ``forSlug(slug)`` which coalesces missing slugs
 * to the empty-overrides shape so callers don't have to repeat the
 * dance.
 */

export type DomainOverrideEntry = _DomainOverrideEntry;
export type DomainOverrideField = _DomainOverrideField;

export interface UseDomainOverridesResult {
  /** Most recent ``Config.domain_overrides`` map snapshot. Empty
   *  ``{}`` until the first ``refresh()`` resolves. Slugs with no
   *  overrides are NOT present in the map (the backend prunes empty
   *  entries). */
  overrides: Record<string, DomainOverrideEntry>;
  /** Look up one slug's overrides, defaulting to the empty-shape
   *  when no entry exists. Stable per-snapshot so callers can put
   *  the result in dep arrays without churn. */
  forSlug: (slug: string) => DomainOverrideEntry;
  /** ``true`` once a ``refresh()`` has resolved at least once. */
  loaded: boolean;
  /** ``true`` while the first ``refresh()`` is in flight. */
  loading: boolean;
  /** Last error from a store operation. ``null`` on success. */
  error: Error | null;
  /** Force a refetch. Stable across renders. */
  refresh: () => void;
}

export function useDomainOverrides(): UseDomainOverridesResult {
  const overrides = useDomainOverridesStore((s) => s.overrides);
  const loaded = useDomainOverridesStore((s) => s.loaded);
  const error = useDomainOverridesStore((s) => s.error);

  React.useEffect(() => {
    if (!loaded) {
      void useDomainOverridesStore.getState().refresh();
    }
  }, [loaded]);

  const loading = !loaded && error === null;

  const refresh = React.useCallback(() => {
    void useDomainOverridesStore.getState().refresh();
  }, []);

  // ``forSlug`` is recomputed when ``overrides`` changes — the
  // closure captures the current map, so a new map reference yields
  // a new callback. Callers that depend on the slug entry should
  // depend on the map directly.
  const forSlug = React.useCallback(
    (slug: string): DomainOverrideEntry =>
      overrides[slug] ?? { ...EMPTY_DOMAIN_OVERRIDE_ENTRY },
    [overrides],
  );

  return { overrides, forSlug, loaded, loading, error, refresh };
}
