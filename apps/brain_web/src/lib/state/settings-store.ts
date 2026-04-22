"use client";

import { create } from "zustand";

/**
 * Settings-store (Plan 07 Task 22).
 *
 * Per-panel dirty tracking + a cached snapshot of the autonomous toggle
 * set. Most panels fit fine in local ``useState`` — the store only needs
 * to hold state that's shared across surfaces:
 *
 *   - ``autonomous`` — mirrors ``autonomous.*`` config values so the
 *     Settings → Autonomous panel, Inbox's ``AutonomousIngestToggle``,
 *     and Pending's ``AutonomousToggle`` can converge on the same
 *     truth after any one of them writes.
 *
 *   - ``dirtyPanels`` — a Set of panel ids with unsaved form state. The
 *     Settings sidebar can light up a breadcrumb dot; useful later when
 *     we add an "unsaved changes" guard on navigation.
 *
 * Not persisted. Settings are authoritative in the config tool; the
 * store is a UI cache, not a source of truth.
 */

export type AutonomousCategory =
  | "ingest"
  | "entities"
  | "concepts"
  | "index_rewrites"
  | "draft";

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
  /** Latest-known ``autonomous.*`` boolean values. ``null`` = not yet
   *  loaded from the server. */
  autonomous: Record<AutonomousCategory, boolean | null>;
  /** Panels with unsaved form state. */
  dirtyPanels: Set<SettingsPanelId>;

  setAutonomous: (key: AutonomousCategory, value: boolean) => void;
  setManyAutonomous: (
    values: Partial<Record<AutonomousCategory, boolean>>,
  ) => void;
  markDirty: (panel: SettingsPanelId) => void;
  markClean: (panel: SettingsPanelId) => void;
  reset: () => void;
}

const initialAutonomous: Record<AutonomousCategory, boolean | null> = {
  ingest: null,
  entities: null,
  concepts: null,
  index_rewrites: null,
  draft: null,
};

export const useSettingsStore = create<SettingsState>((set) => ({
  autonomous: { ...initialAutonomous },
  dirtyPanels: new Set<SettingsPanelId>(),

  setAutonomous: (key, value) =>
    set((s) => ({ autonomous: { ...s.autonomous, [key]: value } })),
  setManyAutonomous: (values) =>
    set((s) => ({ autonomous: { ...s.autonomous, ...values } })),
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
      autonomous: { ...initialAutonomous },
      dirtyPanels: new Set<SettingsPanelId>(),
    }),
}));
