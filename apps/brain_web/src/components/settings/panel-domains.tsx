"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, Edit2, Lock, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { invalidateDomainsCache } from "@/lib/hooks/use-domains";
import { useDomainsStore } from "@/lib/state/domains-store";
import {
  brainDeleteDomain,
  configGet,
  listDomains,
  setActiveDomain,
  setPrivacyRailed,
} from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelDomains (Plan 07 Task 22 → Plan 10 Task 6 → Plan 11 Task 7).
 *
 * - List renders from ``listDomains``. Each row shows a colour swatch,
 *   the slug, a privacy-rail checkbox, and an expand caret. Rename
 *   opens the existing RenameDomainDialog via dialogs-store with an
 *   ``onRenamed`` callback so the list refreshes after a successful
 *   rename. Delete opens TypedConfirmDialog and on confirm calls
 *   ``brain_delete_domain``.
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

  const [domains, setDomains] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());
  const [overrides, setOverrides] = React.useState<
    Record<string, DomainOverrideValues>
  >({});
  const [railed, setRailed] = React.useState<string[]>(["personal"]);

  const refresh = React.useCallback(async () => {
    // Plan 10 Task 7: blow the module-level cache so other live
    // surfaces (topbar scope picker, Browse file tree) re-fetch on
    // their next mount. The list call below populates a fresh cache
    // for the panel itself.
    invalidateDomainsCache();
    try {
      const [domainsRes, railList] = await Promise.all([
        listDomains(),
        readPrivacyRailed(),
      ]);
      setDomains(domainsRes.data?.domains ?? []);
      setRailed(railList);
    } catch {
      pushToast({
        lead: "Load failed.",
        msg: "Could not list domains.",
        variant: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [pushToast]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

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
      invalidateDomainsCache();
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
          // Plan 10 Task 7: invalidate the cache so the topbar +
          // browse pick up the deletion on their next read.
          invalidateDomainsCache();
          setDomains((prev) => prev.filter((s) => s !== slug));
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
              {domains.map((slug, idx) => {
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
