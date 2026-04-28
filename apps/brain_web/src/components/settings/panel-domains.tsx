"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, Edit2, Lock, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ACCENT_SWATCHES, DomainForm } from "@/components/settings/domain-form";
import {
  DomainOverrideForm,
  type DomainOverrideValues,
} from "@/components/settings/domain-override-form";
import { useDomains } from "@/lib/hooks/use-domains";
import { useDomainsStore } from "@/lib/state/domains-store";
import {
  brainDeleteDomain,
  configGet,
  setActiveDomain,
  setCrossDomainWarningAcknowledged,
  setPrivacyRailed,
} from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelDomains (Plan 07 Task 22 → Plan 10 Task 6 → Plan 11 Task 7 →
 * Plan 13 Task 2).
 *
 * - List renders from the zustand ``useDomainsStore`` (Plan 12 Task 5)
 *   via the ``useDomains()`` selector. Plan 13 Task 2 dropped the
 *   parallel local ``domains: string[]`` state that previously
 *   hydrated from a separate ``listDomains()`` call: single source of
 *   truth, peer-consumer pubsub, no drift. Each row shows a colour
 *   swatch, the slug, a privacy-rail checkbox, and an expand caret.
 *   Rename opens the existing RenameDomainDialog via dialogs-store
 *   with an ``onRenamed`` callback so the list refreshes after a
 *   successful rename. Delete opens TypedConfirmDialog and on confirm
 *   calls ``brain_delete_domain``.
 *
 * - Personal's privacy-rail checkbox is ``disabled`` AND ``checked``
 *   with a tooltip "personal is required and cannot be un-railed" per
 *   Plan 11 D11. The Config validator enforces this on persist; the
 *   UI mirrors it so the user gets immediate feedback.
 *
 * - Personal also has NO delete button (Plan 10 D5).
 *
 * - Plan 11 Task 7: each row is expandable to a ``<DomainOverrideForm>``
 *   showing the five optional override fields (classify_model,
 *   default_model, temperature, max_output_tokens, autonomous_mode).
 *   Override values are read once on expand (cheap — Config snapshot
 *   from ``brain_config_get`` is a defaults-backed dump) and re-fetched
 *   after every successful save.
 */

const PROTECTED_DOMAINS = new Set<string>(["personal"]);

// Built-in domain dots use the brand-skin's semantic ``--dom-*`` tokens so
// the colors match the topbar's scope-picker dots, the chat pane's domain
// chips, and every other place these three domains surface. The values are
// CSS variable references (resolved by the active theme — light vs dark
// flips them automatically).
//
// User-created domains beyond these three pick from ACCENT_SWATCHES (kept
// in sync with the form's swatch list).
const BUILTIN_DOMAIN_ACCENT: Record<string, string> = {
  research: "var(--dom-research)",
  work: "var(--dom-work)",
  personal: "var(--dom-personal)",
};

const EMPTY_OVERRIDE: DomainOverrideValues = {
  classify_model: null,
  default_model: null,
  temperature: null,
  max_output_tokens: null,
  autonomous_mode: null,
};

/** Read ``Config.domain_overrides`` for a single slug.
 *
 * ``brain_config_get`` returns the full Config snapshot under any
 * key; reading ``domain_overrides`` gives us a ``dict[str,
 * DomainOverride]`` shape we can index by slug. A missing slug = no
 * override (returns ``EMPTY_OVERRIDE``). */
async function readOverridesFor(slug: string): Promise<DomainOverrideValues> {
  try {
    const r = await configGet({ key: "domain_overrides" });
    const all = (r.data?.value ?? {}) as Record<string, Partial<DomainOverrideValues>>;
    const entry = all[slug] ?? {};
    return {
      classify_model: entry.classify_model ?? null,
      default_model: entry.default_model ?? null,
      temperature: entry.temperature ?? null,
      max_output_tokens: entry.max_output_tokens ?? null,
      autonomous_mode: entry.autonomous_mode ?? null,
    };
  } catch {
    return EMPTY_OVERRIDE;
  }
}

async function readPrivacyRailed(): Promise<string[]> {
  try {
    const r = await configGet({ key: "privacy_railed" });
    const v = r.data?.value;
    return Array.isArray(v) ? (v as string[]) : ["personal"];
  } catch {
    return ["personal"];
  }
}

async function readCrossDomainAcknowledged(): Promise<boolean> {
  try {
    const r = await configGet({ key: "cross_domain_warning_acknowledged" });
    const v = r.data?.value;
    return typeof v === "boolean" ? v : false;
  } catch {
    return false;
  }
}

/**
 * CrossDomainWarningToggle (Plan 12 D8 / Task 9).
 *
 * Surfaces ``Config.cross_domain_warning_acknowledged`` as a toggle
 * inside Settings → Domains. The UI sense is INVERTED relative to the
 * underlying field — toggle ON means "show the warning" (modal active,
 * ``cross_domain_warning_acknowledged === false``); toggle OFF means
 * the user has acknowledged the warning and the modal is suppressed.
 *
 * Microcopy is locked by ``docs/design/cross-domain-modal/microcopy.md``
 * (Task 7 § "Settings toggle text"). The helper text below the switch
 * swaps between two strings depending on the current toggle state so
 * the user always sees the right framing for what's about to happen.
 *
 * Pattern matches ``ActiveDomainSelector``: optimistic local-state
 * update for snappy UI, API helper call (Plan 12 Task 9
 * ``setCrossDomainWarningAcknowledged``), revert on failure with a
 * danger-variant toast surfacing the structured error.
 */
function CrossDomainWarningToggle(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  // ``acknowledged`` mirrors ``Config.cross_domain_warning_acknowledged``;
  // ``showWarning`` is its inverse — what the toggle visually represents.
  const [acknowledged, setAcknowledged] = React.useState<boolean>(false);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      const v = await readCrossDomainAcknowledged();
      if (!cancelled) {
        setAcknowledged(v);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const showWarning = !acknowledged;

  const onCheckedChange = async (next: boolean) => {
    // ``next`` is the new toggle state (UI sense). Translate to the
    // field sense: toggle ON → show warning → acknowledged=false;
    // toggle OFF → suppress warning → acknowledged=true.
    const previousAck = acknowledged;
    const newAck = !next;
    if (newAck === previousAck) return;

    setAcknowledged(newAck);
    try {
      await setCrossDomainWarningAcknowledged(newAck);
      pushToast({
        lead: next ? "Cross-domain warning on." : "Cross-domain warning off.",
        msg: next
          ? "brain will confirm before mixing private domains."
          : "Mixed-scope chats will start without a prompt.",
        variant: "success",
      });
    } catch (err) {
      setAcknowledged(previousAck);
      pushToast({
        lead: "Couldn't update cross-domain warning.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-3"
      data-testid="cross-domain-warning-toggle-container"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-xs font-semibold text-[var(--text)]">
            Cross-domain warning
          </span>
          <label
            htmlFor="cross-domain-warning-toggle"
            className="text-[11px] text-[var(--text-muted)]"
          >
            Show cross-domain warning
          </label>
        </div>
        <Switch
          id="cross-domain-warning-toggle"
          data-testid="cross-domain-warning-toggle"
          checked={showWarning}
          disabled={loading}
          onCheckedChange={(v) => void onCheckedChange(Boolean(v))}
          aria-label="Show cross-domain warning"
        />
      </div>
      <p className="text-[11px] text-[var(--text-muted)]">
        {showWarning
          ? "Before starting a chat that mixes a private domain (like personal) with another domain, brain will ask you to confirm."
          : "The confirmation is off. Mixed-scope chats including private domains will start without a prompt. Turn this back on if you want the check back."}
      </p>
    </div>
  );
}

/**
 * ActiveDomainSelector (Plan 12 D3 / Task 8).
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
 */
function ActiveDomainSelector(): React.ReactElement {
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
      // 3. Revert and surface the structured error. The cross-field
      //    validator raises a plain ``ValueError`` whose ``message``
      //    is the user-actionable string ("active_domain X not in
      //    Config.domains [..]") — surface verbatim with a CTA.
      useDomainsStore.getState().setActiveDomainOptimistic(previous);
      const detail =
        err instanceof Error ? err.message : "Unknown error.";
      pushToast({
        lead: "Couldn't update active domain.",
        msg: `${detail} Pick a different domain.`,
        variant: "danger",
      });
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

export function PanelDomains(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const openDialog = useDialogsStore((s) => s.open);

  // Plan 13 Task 2 (D2): single source of truth for the domain list is
  // the zustand store. Plan 12 Task 5 promoted ``useDomains()`` to a
  // store-backed selector; this panel now reads through that selector
  // instead of maintaining a parallel ``domains: string[]`` local
  // state hydrated from a separate ``listDomains()`` call. The two
  // read paths previously landed at the same backend so they stayed
  // coincidentally aligned, but the seam was drift-prone (see Plan 12
  // Task 5 + Task 8 reviews and ``tasks/lessons.md``).
  const { domains: domainEntries, loading: domainsLoading } = useDomains();
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());
  const [overrides, setOverrides] = React.useState<
    Record<string, DomainOverrideValues>
  >({});
  const [railed, setRailed] = React.useState<string[]>(["personal"]);
  // ``railedLoading`` gates the loading shimmer alongside the store's
  // own ``domainsLoading``. Combined the panel renders the shimmer
  // until both fetches resolve once.
  const [railedLoading, setRailedLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    // Plan 13 Task 2: domains-list refresh routes through the zustand
    // store so every peer consumer (topbar scope chip, browse,
    // active-domain dropdown, etc.) re-renders with the new list
    // without a remount. Privacy-rail still goes through configGet —
    // it isn't part of the store's scope.
    try {
      const [, railList] = await Promise.all([
        useDomainsStore.getState().refresh(),
        readPrivacyRailed(),
      ]);
      setRailed(railList);
    } catch {
      pushToast({
        lead: "Load failed.",
        msg: "Could not list domains.",
        variant: "danger",
      });
    } finally {
      setRailedLoading(false);
    }
  }, [pushToast]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  // Render the placeholder until both the store-backed domains list
  // AND the privacy-rail fetch have resolved at least once. Either
  // alone leaves a partial UI that flashes incorrect state.
  const loading = domainsLoading || railedLoading;

  /** Re-fetch the override values for a single slug — used after each
   *  ``DomainOverrideForm`` save so the form re-hydrates from the
   *  authoritative Config snapshot. */
  const refreshOverrides = React.useCallback(async (slug: string) => {
    const vals = await readOverridesFor(slug);
    setOverrides((prev) => ({ ...prev, [slug]: vals }));
  }, []);

  const toggleExpanded = (slug: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
      } else {
        next.add(slug);
        // Lazy-load override values on first expand. If we already
        // have them in state from a previous expand, skip the fetch.
        if (overrides[slug] === undefined) {
          void refreshOverrides(slug);
        }
      }
      return next;
    });
  };

  const togglePrivacyRail = async (slug: string, checked: boolean) => {
    // ``personal`` is structurally required — guard at the UI layer
    // even though the checkbox is ``disabled`` (defense in depth, in
    // case a future styling change re-enables it accidentally).
    if (slug === "personal" && !checked) {
      pushToast({
        lead: "Can't un-rail personal.",
        msg: "personal is required in privacy_railed and cannot be removed.",
        variant: "danger",
      });
      return;
    }
    const prev = railed;
    const next = checked
      ? Array.from(new Set([...railed, slug]))
      : railed.filter((s) => s !== slug);
    // Optimistic update — revert on failure.
    setRailed(next);
    try {
      await setPrivacyRailed(next);
      // Plan 13 Task 2: privacy-rail mutations don't change the
      // domain list itself but downstream surfaces (e.g. browse) do
      // re-render off the store; trigger a refresh so any cached
      // configured/on-disk flags re-fetch.
      void useDomainsStore.getState().refresh();
      pushToast({
        lead: checked ? "Privacy-rail on." : "Privacy-rail off.",
        msg: `${slug} ${checked ? "added to" : "removed from"} privacy rail.`,
        variant: "success",
      });
    } catch (err) {
      setRailed(prev);
      pushToast({
        lead: "Couldn't update privacy rail.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  const handleRename = (slug: string) => {
    openDialog({
      kind: "rename-domain",
      domain: { id: slug, name: slug, count: 0 },
      // Plan 10 Task 6: refresh the panel list after the dialog
      // commits the rename. Without this hook the row would still
      // show the old slug until the user navigated away and back.
      onRenamed: () => {
        void refresh();
      },
    });
  };

  const handleDelete = (slug: string) => {
    openDialog({
      kind: "typed-confirm",
      title: `Delete ${slug}?`,
      body: `This moves the ${slug}/ folder to .brain/trash/. Backups (if enabled) retain a copy; brain_undo_last fully reverses the move.`,
      word: slug, // per plan: typed-match on the slug itself
      danger: true,
      onConfirm: async () => {
        try {
          // Plan 11 Task 7: if the slug is currently in the privacy
          // rail, drop it from the rail FIRST so the post-delete
          // state is consistent. Otherwise the
          // ``_check_privacy_railed_subset_of_domains`` validator
          // would refuse the next ``save_config`` (railed slug
          // referencing a deleted domain). Personal is delete-
          // protected upstream so we never hit "personal is required"
          // here.
          if (railed.includes(slug)) {
            const newRail = railed.filter((s) => s !== slug);
            await setPrivacyRailed(newRail);
            setRailed(newRail);
          }
          const res = await brainDeleteDomain({ slug, typed_confirm: true });
          // Plan 13 Task 2: route through the zustand store so every
          // peer consumer (topbar scope chip, browse, active-domain
          // dropdown, etc.) re-renders with the new list. The store
          // refresh re-fetches ``brain_list_domains`` once and
          // broadcasts to every subscriber — including this panel
          // (which now reads ``domains`` off the store via
          // ``useDomains()``) so the deleted row falls out of the
          // rendered list automatically.
          void useDomainsStore.getState().refresh();
          // Drop any stale override state for the deleted slug.
          setOverrides((prev) => {
            const { [slug]: _omit, ...rest } = prev;
            return rest;
          });
          const moved = res.data?.files_moved ?? 0;
          pushToast({
            lead: "Domain deleted.",
            msg: `${slug}/ moved to trash (${moved} files). Undo via brain_undo_last.`,
            variant: "success",
          });
        } catch (err) {
          pushToast({
            lead: "Couldn't delete domain.",
            msg: err instanceof Error ? err.message : "Unknown error.",
            variant: "danger",
          });
        }
      },
    });
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex flex-col gap-6">
        {/* Plan 12 Task 8 (D3): active-domain dropdown lives above the
            per-domain rows so users never need to hand-edit
            ``config.json`` to change the persisted scope default. */}
        <ActiveDomainSelector />

        {/* Plan 12 Task 9 (D8): cross-domain confirmation toggle —
            below the active-domain dropdown, above the per-domain
            rows. UI sense is INVERTED relative to the underlying
            ``Config.cross_domain_warning_acknowledged`` field; see
            the component docstring for the mapping. */}
        <CrossDomainWarningToggle />

        <section>
          <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
            Domains
          </h2>
          <p className="mb-3 text-[11px] text-[var(--text-muted)]">
            Each domain is a top-level folder in your vault. The scope
            selector + every ingest call targets a single domain. Domains
            in the privacy rail are excluded from default and wildcard
            queries — explicit inclusion is required for read access.
            Personal is structurally required and cannot be un-railed.
          </p>

          {loading ? (
            <div className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-xs text-[var(--text-dim)]">
              Loading domains…
            </div>
          ) : (
            <ul
              className="flex flex-col gap-1 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)]"
              role="list"
            >
              {domainEntries.map((entry, idx) => {
                const slug = entry.slug;
                const protectedDomain = PROTECTED_DOMAINS.has(slug);
                const builtinAccent = BUILTIN_DOMAIN_ACCENT[slug];
                const accent =
                  builtinAccent ??
                  ACCENT_SWATCHES[idx % ACCENT_SWATCHES.length] ??
                  "#6A8CAA";
                const isExpanded = expanded.has(slug);
                const isRailed = railed.includes(slug);
                const railCheckboxId = `privacy-rail-${slug}`;
                return (
                  <li
                    key={slug}
                    data-testid="domain-row"
                    className="flex flex-col border-b border-[var(--hairline)] last:border-0"
                  >
                    <div className="flex items-center gap-3 px-3 py-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleExpanded(slug)}
                        aria-label={
                          isExpanded
                            ? `Collapse ${slug} overrides`
                            : `Expand ${slug} overrides`
                        }
                        aria-expanded={isExpanded}
                        aria-controls={`override-panel-${slug}`}
                        className="h-7 w-7 p-0"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </Button>
                      <span
                        aria-hidden="true"
                        className="h-4 w-4 rounded-full border border-[var(--hairline)]"
                        style={{ background: accent }}
                      />
                      <span className="font-mono text-sm text-[var(--text)]">
                        {slug}
                      </span>

                      {protectedDomain && (
                        <span
                          data-testid="personal-privacy-badge"
                          className="inline-flex items-center gap-1 rounded-full border border-[var(--hairline-strong)] px-2 py-0.5 text-[10px] font-medium"
                          style={{
                            background: "var(--dom-personal-soft)",
                            color: "var(--dom-personal)",
                          }}
                        >
                          <Lock className="h-2.5 w-2.5" />
                          Privacy-railed
                        </span>
                      )}

                      <div className="ml-auto flex items-center gap-3">
                        {/* Privacy-rail checkbox per row. Personal is
                            disabled-and-checked; tooltip explains
                            why. */}
                        {protectedDomain ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="inline-flex items-center gap-1.5">
                                <Checkbox
                                  id={railCheckboxId}
                                  checked={true}
                                  disabled={true}
                                  data-testid={`privacy-rail-checkbox-${slug}`}
                                  aria-labelledby={`privacy-rail-label-${slug}`}
                                />
                                <label
                                  id={`privacy-rail-label-${slug}`}
                                  htmlFor={railCheckboxId}
                                  className="text-[11px] text-[var(--text-muted)]"
                                >
                                  Privacy-railed
                                </label>
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              personal is required and cannot be un-railed.
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <Checkbox
                              id={railCheckboxId}
                              checked={isRailed}
                              onCheckedChange={(v) =>
                                void togglePrivacyRail(slug, Boolean(v))
                              }
                              data-testid={`privacy-rail-checkbox-${slug}`}
                              aria-labelledby={`privacy-rail-label-${slug}`}
                            />
                            <label
                              id={`privacy-rail-label-${slug}`}
                              htmlFor={railCheckboxId}
                              className="text-[11px] text-[var(--text-muted)]"
                            >
                              Privacy-railed
                            </label>
                          </span>
                        )}

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRename(slug)}
                          aria-label={`Rename ${slug}`}
                          className="h-7 gap-1 px-2 text-xs"
                        >
                          <Edit2 className="h-3 w-3" />
                          Rename
                        </Button>
                        {!protectedDomain && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(slug)}
                            aria-label={`Delete ${slug}`}
                            className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
                          >
                            <Trash2 className="h-3 w-3" />
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>

                    {isExpanded && (
                      <div
                        id={`override-panel-${slug}`}
                        className="border-t border-[var(--hairline)] bg-[var(--surface-0)] px-3 py-3"
                      >
                        <DomainOverrideForm
                          slug={slug}
                          initialValues={overrides[slug] ?? EMPTY_OVERRIDE}
                          onChanged={() => void refreshOverrides(slug)}
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
            Add domain
          </h2>
          <DomainForm onAdded={() => void refresh()} />
        </section>
      </div>
    </TooltipProvider>
  );
}
