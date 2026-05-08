"use client";

import * as React from "react";

import {
  useBudgetStore,
  type BudgetSnapshot as _BudgetSnapshot,
  type BudgetCap as _BudgetCap,
} from "@/lib/state/budget-store";

/**
 * useBudget (Plan 16 Task 43 / D32(b)).
 *
 * Selector over ``useBudgetStore`` (see ``lib/state/budget-store.ts``)
 * around the ``Config.budget`` surface. Every consumer (Settings →
 * Budget tab, the per-domain Budget caps subsection, future cost-pip
 * displays) reads from one canonical store — one consumer mutates,
 * all peers re-render.
 *
 * Mirrors ``use-domains.ts``'s shape: thin selector + first-mount
 * auto-refresh + stable ``refresh`` callback. Consumers that only
 * need a couple fields should select directly off
 * ``useBudgetStore((s) => s.snapshot.daily_usd)`` for narrower
 * subscriptions.
 */

export type BudgetSnapshot = _BudgetSnapshot;
export type BudgetCap = _BudgetCap;

export interface UseBudgetResult {
  /** Most recent ``Config.budget`` snapshot. Defaults to all-null
   *  until the first ``refresh()`` resolves. */
  snapshot: BudgetSnapshot;
  /** ``true`` once a ``refresh()`` has resolved at least once. */
  loaded: boolean;
  /** ``true`` while the first ``refresh()`` is in flight (mirrors
   *  ``use-domains``'s derived ``loading`` flag — once hydrated, a
   *  subsequent in-flight refresh does NOT flip back to loading). */
  loading: boolean;
  /** Last error from a store operation. ``null`` on success. */
  error: Error | null;
  /** Force a refetch. Stable across renders. */
  refresh: () => void;
}

export function useBudget(): UseBudgetResult {
  const snapshot = useBudgetStore((s) => s.snapshot);
  const loaded = useBudgetStore((s) => s.loaded);
  const error = useBudgetStore((s) => s.error);

  // First-mount auto-refresh for cold caches. The store's in-flight
  // Promise cache means concurrent first-mounts trigger one fetch.
  React.useEffect(() => {
    if (!loaded) {
      void useBudgetStore.getState().refresh();
    }
  }, [loaded]);

  const loading = !loaded && error === null;

  const refresh = React.useCallback(() => {
    void useBudgetStore.getState().refresh();
  }, []);

  return { snapshot, loaded, loading, error, refresh };
}
