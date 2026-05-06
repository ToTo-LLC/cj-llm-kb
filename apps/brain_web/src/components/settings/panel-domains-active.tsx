"use client";

import * as React from "react";

import { setActiveDomain } from "@/lib/api/tools";
import { ApiError } from "@/lib/api/types";
import { useDomainsStore } from "@/lib/state/domains-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * ActiveDomainSelector (Plan 12 D3 / Task 8 → extracted Plan 16 Task 8 / D8).
 *
 * Surfaces ``Config.active_domain`` as a top-of-panel dropdown so users
 * never need to hand-edit ``config.json`` to change the persisted scope
 * default. Selection flow:
 *
 *   1. Optimistic update via ``useDomainsStore.setActiveDomainOptimistic``
 *      so peer subscribers (topbar scope chip, browse scope filter,
 *      future surfaces) re-render immediately. This is the load-bearing
 *      Plan 12 Task 5 contract — without zustand promotion the chip
 *      would stay stale until next page-load.
 *   2. Fire ``brain_config_set({key:"active_domain", value:slug})`` via
 *      the typed helper. Backend cross-field validator
 *      (``_check_active_domain_membership``) raises ``ValueError`` if
 *      ``slug`` isn't in ``Config.domains`` — defensive against the
 *      race where another tab concurrently deletes the slug between
 *      the dropdown rendering and the user picking it. Dropdown
 *      options are populated from the same ``domains`` list so the
 *      validator can't realistically fire on the user's own pick;
 *      the guard exists for that cross-tab race only.
 *   3. On failure, revert the optimistic update by re-pushing the
 *      previous value through ``setActiveDomainOptimistic`` and toast
 *      a "danger" variant pointing the user at picking a different
 *      domain. The next ``refresh()`` reconciles whatever the API
 *      ultimately returned.
 *
 * Native ``<select>`` (not shadcn ``<Select>``) deliberately:
 *   - Browser-managed keyboard nav + screen-reader announcements out
 *     of the box. No portal / pointer-capture jsdom pitfalls in tests.
 *   - The dropdown lists flat slug strings; shadcn's richer custom
 *     popper isn't needed for a single-column slug list.
 *   - Mirrors ``DomainOverrideForm``'s native ``<select>`` for
 *     ``classify_model``/``default_model`` choices — consistent inside
 *     the Settings → Domains panel.
 *
 * Plan 16 Task 8 (D8): factored out of ``panel-domains.tsx`` into its
 * own file as part of the orchestrator + 3-children split. The
 * component owns its own store reads + persistence call — no props
 * needed; the orchestrator just renders ``<PanelDomainsActive />``.
 */
export function PanelDomainsActive(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  // Read directly off the store rather than ``useDomains()`` so we get
  // the live optimistic-update view AND avoid the hook's first-mount
  // auto-refresh side effect (``PanelDomains``'s own ``refresh()``
  // already populates the store on mount).
  const domains = useDomainsStore((s) => s.domains);
  const activeDomain = useDomainsStore((s) => s.activeDomain);

  const onChange = async (event: React.ChangeEvent<HTMLSelectElement>) => {
    const next = event.target.value;
    if (!next || next === activeDomain) return;
    const previous = activeDomain;
    // Plan 15 Task 6 (D5): toast payload is built inside catch but
    // dispatched OUTSIDE the catch block (defensive scoping — pushToast
    // is a zustand setter that shouldn't realistically throw, but keeping
    // it out of the catch means a bug there can't swallow the optimistic
    // rollback or shadow the original error). Plan 12 Task 8 review I2.
    let pendingToast: { lead: string; msg: string; variant: "danger" } | null =
      null;

    // 1. Optimistic update — peer consumers re-render now.
    useDomainsStore.getState().setActiveDomainOptimistic(next);
    try {
      // 2. Persist via brain_config_set wrapper.
      await setActiveDomain(next);
      pushToast({
        lead: "Active domain updated.",
        msg: `Default scope is now ${next}.`,
        variant: "success",
      });
    } catch (err) {
      // 3. Revert the optimistic update — peer consumers see ``previous``
      //    again. Done first so the UI snaps back even if anything below
      //    were to throw.
      useDomainsStore.getState().setActiveDomainOptimistic(previous);

      // 4. Classify the error to pick a CTA that matches reality
      //    (Plan 15 Task 6 / D5; Plan 12 Task 8 review I1).
      //
      //    - ``ApiError`` with ``status === 400`` is a validator error:
      //      the cross-field ``_check_active_domain_membership`` raises
      //      ``ValueError`` ("active_domain X not in Config.domains
      //      [..]") which the brain_api error layer renders as a flat
      //      400 envelope (``code: "invalid_input"``). The user-actionable
      //      next step is to pick a different domain.
      //    - Anything else (network error / fetch reject / 5xx) is a
      //      transport error — the user's choice was fine; the wire
      //      blew up. The next step is to retry.
      const isValidatorError = err instanceof ApiError && err.status === 400;
      const detail = err instanceof Error ? err.message : "Unknown error.";
      const cta = isValidatorError
        ? "Pick a different domain."
        : "Try again.";
      pendingToast = {
        lead: "Couldn't update active domain.",
        msg: `${detail} ${cta}`,
        variant: "danger",
      };
    }

    // 5. Dispatch the danger toast outside the catch block.
    if (pendingToast) {
      pushToast(pendingToast);
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-3">
      <label
        htmlFor="active-domain-selector"
        className="text-xs font-semibold text-[var(--text)]"
      >
        Active domain
      </label>
      <p className="text-[11px] text-[var(--text-muted)]">
        The default scope for new chats, ingest calls, and any tool
        that does not override the domain explicitly. Persists to
        Config.active_domain.
      </p>
      <select
        id="active-domain-selector"
        data-testid="active-domain-selector"
        value={activeDomain}
        onChange={(e) => void onChange(e)}
        disabled={domains.length === 0}
        className="h-9 rounded-md border border-[var(--hairline)] bg-[var(--surface-0)] px-2 text-sm text-[var(--text)] focus:outline-none focus:ring-1 focus:ring-[var(--ring,_currentColor)] disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Active domain"
      >
        {/* Empty placeholder option for the cold-cache / pre-Task-6
            backend case where ``activeDomain`` is "". Hidden once any
            real value is selected so the dropdown can never re-pick
            the empty value through the keyboard. */}
        {activeDomain === "" && (
          <option value="" disabled hidden>
            — none selected —
          </option>
        )}
        {domains.map((d) => (
          <option key={d.slug} value={d.slug}>
            {d.slug}
          </option>
        ))}
      </select>
    </div>
  );
}
