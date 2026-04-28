"use client";

import * as React from "react";

import { configGet } from "@/lib/api/tools";

/**
 * useCrossDomainGate (Plan 12 Task 9).
 *
 * Lightweight hook that reads the two ``Config`` fields the cross-domain
 * confirmation modal's trigger gate needs: ``privacy_railed`` (the slug
 * list the trigger compares scope against) and
 * ``cross_domain_warning_acknowledged`` (the per-vault opt-out flag).
 *
 * Kept as its own hook (rather than extending ``useDomainsStore``)
 * because:
 *   - Both fields are tiny — one bool + one short slug list. Promoting
 *     to the shared zustand store would require a wider config-slice
 *     contract that's Plan 13+ territory (D14 candidate-cut for this
 *     plan was "no broader Config-slice promotion").
 *   - The modal trigger needs them at scope-finalization time, not on
 *     every render. A first-mount fetch + a reload-on-Settings-toggle
 *     pubsub is cheaper than a store-state + cross-component sub.
 *   - Settings-side mutation (the toggle in ``panel-domains.tsx``)
 *     re-fetches via ``refresh()`` after the API resolves so the
 *     modal sees the new value on the next trigger fire without a
 *     reload.
 *
 * The hook fires one ``brain_config_get`` per field on mount and
 * returns ``{privacyRailed, acknowledged, loading, refresh}``. Errors
 * are swallowed into safe defaults (``["personal"]`` + ``false``) to
 * fail open — if the backend can't tell us whether the user has
 * acknowledged, default to "show the modal" (safer than silently
 * skipping it).
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
  /** ``true`` until the first fetch resolves (or fails). The trigger
   *  gate skips firing while loading so we never show the modal with
   *  stale defaults that disagree with disk. */
  loading: boolean;
  /** Re-fetch both fields. Call after a Settings toggle change so the
   *  next trigger fire sees the new value. */
  refresh: () => Promise<void>;
}

export function useCrossDomainGate(): CrossDomainGateState {
  const [privacyRailed, setPrivacyRailed] = React.useState<string[]>([
    "personal",
  ]);
  const [acknowledged, setAcknowledged] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    try {
      const [railRes, ackRes] = await Promise.all([
        configGet({ key: "privacy_railed" }),
        configGet({ key: "cross_domain_warning_acknowledged" }),
      ]);
      const rail = railRes.data?.value;
      const ack = ackRes.data?.value;
      setPrivacyRailed(Array.isArray(rail) ? (rail as string[]) : ["personal"]);
      setAcknowledged(typeof ack === "boolean" ? ack : false);
    } catch {
      // Fail open — default to show-the-modal so the user is never
      // silently skipped past the confirmation due to a transient
      // backend hiccup.
      setPrivacyRailed(["personal"]);
      setAcknowledged(false);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  return { privacyRailed, acknowledged, loading, refresh };
}
