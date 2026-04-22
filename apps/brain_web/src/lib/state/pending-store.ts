"use client";

import { create } from "zustand";

import {
  applyPatch,
  getPendingPatch,
  listPendingPatches,
  rejectPatch,
} from "@/lib/api/tools";

/**
 * Pending-store (Plan 07 Task 16).
 *
 * Holds the approval-queue metadata list, the current selection, the
 * fetched body for that selection, and the active filter chip. The body
 * is fetched ON DEMAND via ``brain_get_pending_patch`` — the list tool
 * deliberately returns envelopes only (Plan 04 hard rule: never leak
 * staged content on list).
 *
 * The store is the seam between the typed tools API and the pending
 * screen + rail. It owns only UI state; every mutation round-trips
 * through the API so the vault stays the source of truth. Each action
 * is async and awaits its API call before updating state — callers can
 * await the returned promise to sequence UI feedback (e.g. toast on
 * success).
 */

export interface PatchEnvelope {
  patch_id: string;
  target_path: string;
  reason: string;
  created_at: string;
  tool: string;
  // The envelope may carry extra fields (source_thread, mode, domain on
  // the frontend-synthesized side). Leaving the index-signature open
  // matches the shape of the typed tools API.
  [extra: string]: unknown;
}

export interface PatchDetail {
  envelope: Record<string, unknown>;
  patchset: Record<string, unknown>;
}

export type PendingFilter =
  | "all"
  | "notes"
  | "ingested"
  | "entities"
  | "concepts"
  | "index_rewrites"
  | "draft";

export interface PendingState {
  patches: PatchEnvelope[];
  selectedId: string | null;
  selectedDetail: PatchDetail | null;
  filter: PendingFilter;

  loadPending: () => Promise<void>;
  select: (id: string) => Promise<void>;
  approve: (id: string) => Promise<void>;
  reject: (id: string, reason: string) => Promise<void>;
  setFilter: (f: PendingFilter) => void;
}

export const usePendingStore = create<PendingState>((set, get) => ({
  patches: [],
  selectedId: null,
  selectedDetail: null,
  filter: "all",

  loadPending: async () => {
    const res = await listPendingPatches({});
    const data = (res.data ?? { patches: [] }) as { patches: PatchEnvelope[] };
    set({ patches: data.patches ?? [] });
  },

  select: async (id) => {
    set({ selectedId: id, selectedDetail: null });
    const res = await getPendingPatch({ patch_id: id });
    const detail = (res.data ?? null) as PatchDetail | null;
    // Guard against a stale response when the user clicked a different
    // card while this request was in flight.
    if (get().selectedId !== id) return;
    set({ selectedDetail: detail });
  },

  approve: async (id) => {
    await applyPatch({ patch_id: id });
    set((s) => ({
      patches: s.patches.filter((p) => p.patch_id !== id),
      selectedId: s.selectedId === id ? null : s.selectedId,
      selectedDetail: s.selectedId === id ? null : s.selectedDetail,
    }));
  },

  reject: async (id, reason) => {
    await rejectPatch({ patch_id: id, reason });
    set((s) => ({
      patches: s.patches.filter((p) => p.patch_id !== id),
      selectedId: s.selectedId === id ? null : s.selectedId,
      selectedDetail: s.selectedId === id ? null : s.selectedDetail,
    }));
  },

  setFilter: (filter) => set({ filter }),
}));
