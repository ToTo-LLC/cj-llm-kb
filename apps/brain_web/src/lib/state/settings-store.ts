"use client";

import { create } from "zustand";

import type { AutonomyCategory } from "@/lib/api/tools";

/**
 * Settings-store (Plan 07 Task 22 → Plan 16 Task 40 / D30 step 4 of 4).
 *
 * Plan 16 Task 38 reshaped the underlying ``Config.autonomous`` field
 * from the legacy flat ``AutonomousConfig`` (5 booleans:
 * ``ingest`` / ``entities`` / ``concepts`` / ``index_rewrites`` /
 * ``draft``) to ``dict[str, AutonomyCategoryFlags]`` keyed by domain
 * slug, where each :class:`AutonomyCategoryFlags` carries 5 per-category
 * booleans (``new_files`` / ``edits`` / ``index_entries`` / ``concepts``
 * / ``draft``). Plan 16 Task 40 lands the matching frontend shape: a
 * per-domain × per-category grid in Settings → Autonomy, backed by the
 * new ``setDomainAutonomy(slug, category, value)`` API.
 *
 * Per-panel dirty tracking + a cached snapshot of the autonomous
 * setting set. Most panels fit fine in local ``useState`` — the store
 * only needs to hold state that's shared across surfaces:
 *
 *   - ``autonomous`` — mirrors ``Config.autonomous`` so the
 *     Settings → Autonomy panel and any future inbox / pending-rail
 *     surface that wants to reflect "is autonomy on for this domain?"
 *     can converge on the same truth after any one of them writes.
 *
 *   - ``dirtyPanels`` — a Set of panel ids with unsaved form state. The
 *     Settings sidebar can light up a breadcrumb dot; useful later when
 *     we add an "unsaved changes" guard on navigation.
 *
 * Not persisted. Settings are authoritative in the config tool; the
 * store is a UI cache, not a source of truth.
 *
 * **Migration note (Task 40).** The legacy ``AutonomousCategory`` type
 * (``"ingest" | "entities" | "concepts" | "index_rewrites" | "draft"``)
 * and the flat ``Record<AutonomousCategory, boolean | null>`` autonomous
 * shape are GONE — Plan 16 Task 39 removed the static
 * ``autonomous.<flag>`` keys from the backend allowlist, so reads /
 * writes against those keys would fail at the API gate today. Inbox's
 * legacy ``AutonomousIngestToggle`` and Pending's mount-time read of
 * five flat keys (``pending-rail.tsx``) reach for the OLD wire shape
 * and are pre-existing carry-forward debt outside this task's scope —
 * the schema gate will surface those when a follow-up plan lifts them.
 */

/** Per-domain autonomy state — every category may be ``true`` (auto-
 *  apply matching patches in this domain), ``false`` (stage for
 *  approval), or ``undefined`` (not yet hydrated / no entry, treated as
 *  ``false`` by the gate). */
export type AutonomyDomainFlags = Partial<Record<AutonomyCategory, boolean>>;

export type SettingsPanelId =
  | "general"
  | "providers"
  | "budget"
  | "autonomous"
  | "integrations"
  | "domains"
  | "brain-md"
  | "backups";

export interface SettingsState {
  /** Latest-known per-domain × per-category autonomy snapshot. Keyed by
   *  domain slug. Empty object until first ``hydrateAutonomous()`` lands
   *  (the panel mounts with an empty grid; every cell falls back to
   *  ``false`` until the API resolves). */
  autonomous: Record<string, AutonomyDomainFlags>;
  /** Panels with unsaved form state. */
  dirtyPanels: Set<SettingsPanelId>;

  /** Replace the full autonomous snapshot — used by the panel's mount-
   *  time hydrate after reading ``configGet({key:"autonomous"})``. */
  hydrateAutonomous: (
    snapshot: Record<string, AutonomyDomainFlags>,
  ) => void;
  /** Set a single ``(slug, category)`` flag in local state. Optimistic
   *  — caller is responsible for the API round-trip + revert on
   *  failure (matches the ``setActiveDomainOptimistic`` / domain-rail
   *  pattern). */
  setDomainAutonomy: (
    slug: string,
    category: AutonomyCategory,
    value: boolean,
  ) => void;
  /** Drop every flag for a single slug — wires the per-row Reset
   *  button. Optimistic; caller fires N-flag-clear API calls in
   *  parallel. */
  resetDomainAutonomy: (slug: string) => void;
  /** Drop every entry across every slug — wires the panel's "Disable
   *  all autonomy" footer button. Optimistic; caller fires the
   *  per-(slug,category) clear API calls. */
  disableAllAutonomy: () => void;
  markDirty: (panel: SettingsPanelId) => void;
  markClean: (panel: SettingsPanelId) => void;
  reset: () => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  autonomous: {},
  dirtyPanels: new Set<SettingsPanelId>(),

  hydrateAutonomous: (snapshot) =>
    set(() => ({
      // Defensive shallow-copy of the inner records so a caller that
      // mutates the source object after dispatch can't corrupt the
      // store snapshot. The category objects themselves are plain
      // booleans, so a one-level deep clone is enough.
      autonomous: Object.fromEntries(
        Object.entries(snapshot).map(([slug, flags]) => [slug, { ...flags }]),
      ),
    })),

  setDomainAutonomy: (slug, category, value) =>
    set((s) => ({
      autonomous: {
        ...s.autonomous,
        [slug]: { ...(s.autonomous[slug] ?? {}), [category]: value },
      },
    })),

  resetDomainAutonomy: (slug) =>
    set((s) => {
      // Drop the slug entry entirely — equivalent to "every flag false"
      // (the gate treats missing entries the same as all-False).
      const { [slug]: _omit, ...rest } = s.autonomous;
      return { autonomous: rest };
    }),

  disableAllAutonomy: () => set({ autonomous: {} }),

  markDirty: (panel) =>
    set((s) => {
      const next = new Set(s.dirtyPanels);
      next.add(panel);
      return { dirtyPanels: next };
    }),
  markClean: (panel) =>
    set((s) => {
      const next = new Set(s.dirtyPanels);
      next.delete(panel);
      return { dirtyPanels: next };
    }),
  reset: () =>
    set({
      autonomous: {},
      dirtyPanels: new Set<SettingsPanelId>(),
    }),
}));
