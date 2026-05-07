"use client";

import * as React from "react";
import { RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  AUTONOMY_CATEGORIES,
  type AutonomyCategory,
  configGet,
  setDomainAutonomy as apiSetDomainAutonomy,
} from "@/lib/api/tools";
import { useDomains } from "@/lib/hooks/use-domains";
import {
  type AutonomyDomainFlags,
  useSettingsStore,
} from "@/lib/state/settings-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelAutonomous (Plan 07 Task 22 → Plan 16 Task 40 / D30 step 4 of 4).
 *
 * Per-domain × per-category grid surface for Settings → Autonomy.
 *
 *   - Rows: domains in :class:`Config.domains` order (the topbar /
 *     browse / settings-domains all read the same source via
 *     ``useDomains()``).
 *   - Columns: 5 :class:`AutonomyCategoryFlags` fields — three are
 *     PatchSet member-field names (``new_files``, ``edits``,
 *     ``index_entries``); two are PatchCategory values (``concepts``,
 *     ``draft``). HYBRID surface per T37 §1.
 *   - Each cell is a `<Switch>` bound to
 *     ``autonomous[<slug>][<category>]`` (defaults to ``false`` when
 *     unset — CLAUDE.md principle #3 keeps everything off out-of-the-
 *     box).
 *   - Per-row "Reset" icon button clears all 5 flags for that domain.
 *   - Footer "Disable all autonomy" button clears the whole snapshot.
 *
 * Reads the initial snapshot via ``configGet({key:"autonomous"})`` on
 * mount (one call returns the full ``dict[str, AutonomyCategoryFlags]``
 * blob). Writes via :func:`setDomainAutonomy` —
 * ``brain_config_set`` with the dotted key
 * ``autonomous.<slug>.<category>``. The wildcard handler
 * (``_apply_autonomous_per_domain``) auto-creates the per-slug entry
 * on first set; setting every flag in an entry to ``false`` causes the
 * backend to prune the slug entry entirely (the gate treats a missing
 * slug the same as an explicit all-False entry, so the prune is
 * semantically a no-op).
 *
 * a11y shape:
 *   - ``role="grid"`` on the wrapping element with an aria-label.
 *   - ``<th scope="col">`` headers + per-row ``<th scope="row">`` slug
 *     so screen readers announce "Research, New files, switch, off".
 *   - Each Switch has
 *     ``aria-label="Auto-apply <category> patches in <slug>"`` for the
 *     unique-text gate (axe-core's image-of-text + region rules).
 *   - Tab order is row-major: domain A's 5 cells + Reset, then
 *     domain B's, etc.
 *   - Footer button is ``variant="destructive"`` for the visual cue
 *     but does NOT confirm via modal — clearing the autonomy dict is
 *     purely additive in safety (the gate falls back to "stage
 *     everything" with empty autonomy state), so the destructive
 *     confirm pattern from delete-domain isn't warranted.
 *
 * Surface-failure semantics: the panel renders an empty-state hint
 * when ``Config.domains`` is empty (the user hasn't added any domains
 * yet). When the API hydrate fails, the local state stays at the
 * defaults (all-False) and a danger toast surfaces; the panel still
 * renders so the user can interact.
 */

const CATEGORY_LABELS: Record<AutonomyCategory, string> = {
  new_files: "New files",
  edits: "Edits",
  index_entries: "Index entries",
  concepts: "Concepts",
  draft: "Draft",
};

/** Built-in domain accent dots — same mapping as panel-domains.tsx. */
const BUILTIN_DOMAIN_ACCENT: Record<string, string> = {
  research: "var(--dom-research)",
  work: "var(--dom-work)",
  personal: "var(--dom-personal)",
};

/** Read the full ``Config.autonomous`` snapshot via
 *  ``brain_config_get``. The backend returns the persisted-shape dict
 *  (``{ <slug>: { <category>: bool, ... } }``) — we coerce defensively
 *  in case a malformed entry slips through.
 */
async function readAutonomousSnapshot(): Promise<Record<string, AutonomyDomainFlags>> {
  const r = await configGet({ key: "autonomous" });
  const v = r.data?.value;
  if (!v || typeof v !== "object" || Array.isArray(v)) return {};
  const snapshot: Record<string, AutonomyDomainFlags> = {};
  for (const [slug, raw] of Object.entries(v as Record<string, unknown>)) {
    if (!raw || typeof raw !== "object") continue;
    const flags: AutonomyDomainFlags = {};
    for (const cat of AUTONOMY_CATEGORIES) {
      const val = (raw as Record<string, unknown>)[cat];
      if (typeof val === "boolean") flags[cat] = val;
    }
    snapshot[slug] = flags;
  }
  return snapshot;
}

export function PanelAutonomous(): React.ReactElement {
  const { domains, loading: domainsLoading } = useDomains();
  const autonomous = useSettingsStore((s) => s.autonomous);
  const hydrateAutonomous = useSettingsStore((s) => s.hydrateAutonomous);
  const setDomainAutonomy = useSettingsStore((s) => s.setDomainAutonomy);
  const resetDomainAutonomy = useSettingsStore((s) => s.resetDomainAutonomy);
  const disableAllAutonomy = useSettingsStore((s) => s.disableAllAutonomy);
  const pushToast = useSystemStore((s) => s.pushToast);

  // Mount-time hydrate. One ``configGet`` call returns the full
  // ``Config.autonomous`` dict — much cheaper than a per-(slug,category)
  // round-trip.
  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const snap = await readAutonomousSnapshot();
        if (!cancelled) hydrateAutonomous(snap);
      } catch {
        // Silent — leaves the store at defaults (all-False). The user
        // can still interact; the next write attempt will surface its
        // own failure toast if the backend really is down.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hydrateAutonomous]);

  /** Toggle a single ``(slug, category)`` flag. Optimistic — flip the
   *  store, fire the API, revert on failure. Mirrors the panel-domains
   *  ``togglePrivacyRail`` pattern. */
  const onToggle = async (
    slug: string,
    category: AutonomyCategory,
    next: boolean,
  ) => {
    const prev = autonomous[slug]?.[category] ?? false;
    setDomainAutonomy(slug, category, next);
    try {
      await apiSetDomainAutonomy(slug, category, next);
      pushToast({
        lead: next ? "Autonomy on." : "Autonomy off.",
        msg: `${slug} ${CATEGORY_LABELS[category].toLowerCase()} → ${
          next ? "auto-apply" : "stage for review"
        }.`,
        variant: "success",
      });
    } catch (err) {
      setDomainAutonomy(slug, category, prev);
      pushToast({
        lead: "Couldn't save autonomy flag.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  /** Clear every flag for a single slug. Issues N parallel API calls
   *  (one per category that's currently true) — the snapshot only
   *  carries explicitly-set flags, so this is at most 5 calls. The
   *  backend's apply-helper prunes the entry when every flag is false. */
  const onResetRow = async (slug: string) => {
    const previousFlags = { ...(autonomous[slug] ?? {}) };
    // Optimistic — drop the entry locally first.
    resetDomainAutonomy(slug);
    const trueCategories = AUTONOMY_CATEGORIES.filter(
      (cat) => previousFlags[cat] === true,
    );
    if (trueCategories.length === 0) {
      // Nothing to clear server-side — just feedback.
      pushToast({
        lead: "Autonomy reset.",
        msg: `No flags were set for ${slug}.`,
        variant: "success",
      });
      return;
    }
    try {
      await Promise.all(
        trueCategories.map((cat) => apiSetDomainAutonomy(slug, cat, false)),
      );
      pushToast({
        lead: "Autonomy reset.",
        msg: `Cleared ${trueCategories.length} flag${trueCategories.length === 1 ? "" : "s"} for ${slug}.`,
        variant: "success",
      });
    } catch (err) {
      // Revert optimistic update — re-hydrate from the canonical
      // snapshot so we don't half-restore.
      try {
        const snap = await readAutonomousSnapshot();
        hydrateAutonomous(snap);
      } catch {
        /* If rehydrate also fails, the toast below is the user's
           signal — leave the store at all-False rather than echoing
           the failed state. */
      }
      pushToast({
        lead: "Couldn't reset autonomy.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  /** Clear every flag across every slug. Same shape as ``onResetRow``
   *  but iterates the whole snapshot. */
  const onDisableAll = async () => {
    const snapshot = autonomous;
    const writes: Promise<unknown>[] = [];
    for (const [slug, flags] of Object.entries(snapshot)) {
      for (const cat of AUTONOMY_CATEGORIES) {
        if (flags[cat] === true) {
          writes.push(apiSetDomainAutonomy(slug, cat, false));
        }
      }
    }
    // Optimistic — drop the whole snapshot locally first.
    disableAllAutonomy();
    if (writes.length === 0) {
      pushToast({
        lead: "Autonomy disabled.",
        msg: "No flags were set.",
        variant: "success",
      });
      return;
    }
    try {
      await Promise.all(writes);
      pushToast({
        lead: "Autonomy disabled.",
        msg: `Cleared ${writes.length} flag${writes.length === 1 ? "" : "s"} across every domain.`,
        variant: "success",
      });
    } catch (err) {
      // Revert via re-hydrate.
      try {
        const snap = await readAutonomousSnapshot();
        hydrateAutonomous(snap);
      } catch {
        /* see onResetRow rationale */
      }
      pushToast({
        lead: "Couldn't disable all autonomy.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
          Autonomy
        </h2>
        <p className="mb-4 text-[11px] text-[var(--text-muted)]">
          Per-domain auto-apply controls. When a flag is on, patches
          matching that category in that domain auto-apply without
          review. Scope guard, domain routing, and budget caps are all
          still enforced. Out-of-the-box every flag is off.
        </p>

        {domainsLoading ? (
          <div className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-xs text-[var(--text-dim)]">
            Loading domains…
          </div>
        ) : domains.length === 0 ? (
          <p
            data-testid="autonomy-empty-state"
            className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-4 text-xs text-[var(--text-muted)]"
          >
            Add a domain in Settings → Domains to configure autonomy.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border border-[var(--hairline)] bg-[var(--surface-1)]">
            <table
              data-testid="autonomy-grid"
              className="w-full border-collapse"
              role="grid"
              aria-label="Per-domain autonomy controls"
            >
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-[var(--surface-2)]">
                  <th
                    scope="col"
                    className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-dim)]"
                  >
                    Domain
                  </th>
                  {AUTONOMY_CATEGORIES.map((cat) => (
                    <th
                      key={cat}
                      scope="col"
                      className="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-[var(--text-dim)]"
                    >
                      {CATEGORY_LABELS[cat]}
                    </th>
                  ))}
                  <th scope="col" className="px-3 py-2">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {domains.map((entry) => {
                  const slug = entry.slug;
                  const accent = BUILTIN_DOMAIN_ACCENT[slug] ?? entry.accent;
                  const flags = autonomous[slug] ?? {};
                  return (
                    <tr
                      key={slug}
                      data-testid={`autonomy-row-${slug}`}
                      className="border-b border-[var(--hairline)] last:border-0"
                    >
                      <th
                        scope="row"
                        className="px-3 py-2 text-left font-normal"
                      >
                        <span className="inline-flex items-center gap-2">
                          <span
                            aria-hidden="true"
                            className="h-3 w-3 rounded-full border border-[var(--hairline)]"
                            style={{ background: accent }}
                          />
                          <span className="font-mono text-sm text-[var(--text)]">
                            {slug}
                          </span>
                        </span>
                      </th>
                      {AUTONOMY_CATEGORIES.map((cat) => {
                        const checked = flags[cat] ?? false;
                        return (
                          <td
                            key={cat}
                            className="px-3 py-2 text-center align-middle"
                          >
                            <Switch
                              checked={checked}
                              onCheckedChange={(v) =>
                                void onToggle(slug, cat, Boolean(v))
                              }
                              data-testid={`autonomy-switch-${slug}-${cat}`}
                              aria-label={`Auto-apply ${CATEGORY_LABELS[cat].toLowerCase()} patches in ${slug}`}
                            />
                          </td>
                        );
                      })}
                      <td className="px-3 py-2 text-right align-middle">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => void onResetRow(slug)}
                          aria-label={`Reset ${slug} autonomy`}
                          data-testid={`autonomy-reset-${slug}`}
                          className="h-7 w-7 p-0"
                        >
                          <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {domains.length > 0 && (
          <div className="mt-3 flex justify-end">
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => void onDisableAll()}
              data-testid="autonomy-disable-all"
              aria-label="Disable all autonomy"
            >
              Disable all autonomy
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
