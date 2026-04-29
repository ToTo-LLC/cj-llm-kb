"use client";

import * as React from "react";

import { useCrossDomainGateStore } from "@/lib/state/cross-domain-gate-store";

/**
 * useCrossDomainGate (Plan 12 Task 9 → Plan 13 Task 3 / D3).
 *
 * Selector over ``useCrossDomainGateStore`` (see
 * ``lib/state/cross-domain-gate-store.ts``) around the two ``Config``
 * fields the cross-domain modal's trigger gate needs:
 * ``privacy_railed`` (the slug list compared against scope) and
 * ``cross_domain_warning_acknowledged`` (the per-vault opt-out flag).
 *
 * Pre-Plan-13 the gate hook held local React state for both fields;
 * mutations from the Settings toggle (``panel-domains.tsx``) only
 * updated the toggle's own local state, leaving the chat-screen's
 * ``useCrossDomainGate()`` instance stale until remount or page
 * reload (cross-instance / cross-tab divergence — same shape Plan
 * 11 closure addendum named on ``useDomains`` and Plan 12 Task 5
 * fixed via ``domains-store.ts``). The Plan 13 zustand promotion
 * fixes the divergence by routing every read through one store.
 *
 * Public API preserved for back-compat with the Plan 12 Task 9
 * call site in ``chat-screen.tsx``:
 *
 *   - ``useCrossDomainGate()`` returns ``{privacyRailed, acknowledged,
 *     loading, refresh}``. Same shape as Plan 12.
 *   - ``loading`` is derived: ``true`` until the first ``refresh()``
 *     resolves (or fails). The trigger gate skips firing while
 *     loading so we never show the modal with stale defaults that
 *     disagree with disk.
 *   - ``refresh`` is a stable per-render callback that delegates to
 *     ``useCrossDomainGateStore.getState().refresh()``. Caller-side
 *     ``await refreshGate()`` semantics are preserved by the store's
 *     in-flight Promise cache.
 */

export interface CrossDomainGateState {
  /** ``Config.privacy_railed`` — slugs whose inclusion in a multi-
   *  domain scope triggers the modal. Defaults to ``["personal"]`` on
   *  fetch failure (matches the schema default). */
  privacyRailed: string[];
  /** ``Config.cross_domain_warning_acknowledged`` — when ``true`` the
   *  modal is suppressed regardless of scope. Defaults to ``false`` on
   *  fetch failure (fail open — show the modal). */
  acknowledged: boolean;
  /** ``true`` until the first ``refresh()`` resolves (or fails). The
   *  trigger gate skips firing while loading so we never show the
   *  modal with stale defaults that disagree with disk. */
  loading: boolean;
  /** Re-fetch both fields. Plan 13 Task 3: now equivalent to
   *  ``useCrossDomainGateStore.getState().refresh()`` — every peer
   *  consumer re-renders with the new data automatically. */
  refresh: () => Promise<void>;
}

export function useCrossDomainGate(): CrossDomainGateState {
  const privacyRailed = useCrossDomainGateStore((s) => s.privacyRailed);
  const acknowledged = useCrossDomainGateStore((s) => s.acknowledged);
  const loaded = useCrossDomainGateStore((s) => s.loaded);
  const error = useCrossDomainGateStore((s) => s.error);

  // First-mount auto-refresh for cold caches. The store's in-flight
  // Promise cache means concurrent first-mounts (e.g., chat-screen
  // mounting while another consumer is also subscribing) only trigger
  // one fetch. Re-runs only when ``loaded`` flips false → true (first
  // hydration) or back to false (after ``_resetForTesting``).
  React.useEffect(() => {
    if (!loaded) {
      void useCrossDomainGateStore.getState().refresh();
    }
  }, [loaded]);

  // ``loading`` is derived: still loading whenever the store hasn't
  // resolved its first refresh yet AND there's no error. Once loaded,
  // subsequent refreshes don't flip back to ``loading`` — the existing
  // values stay visible while the new fetch lands (matches the old
  // hook's behaviour after first mount).
  const loading = !loaded && error === null;

  // ``refresh`` is stable per render — store actions are stable, and
  // we just project the store's action through. Wrapping in
  // ``React.useCallback`` keeps the returned reference stable across
  // re-renders so callers can put it in dep lists without causing
  // effect-loop churn.
  const refresh = React.useCallback(async () => {
    await useCrossDomainGateStore.getState().refresh();
  }, []);

  return { privacyRailed, acknowledged, loading, refresh };
}
