"use client";

import { create } from "zustand";

/**
 * Tiny client-only store so the Browse screen can share the
 * currently-viewed note with the right-rail ``<LinkedRail />``
 * without threading a callback through the shell. Plan 07 Task 18.
 *
 * Deliberately NOT persisted — the URL is the source of truth for
 * which note is active; this store only mirrors it after
 * ``readNote`` resolves, so the rail can show backlinks + outlinks
 * for the actual body.
 */

export interface BrowseState {
  /** Vault-relative path of the active note, or ``null`` when empty. */
  currentPath: string | null;
  /** Body of the active note (for outlink extraction). */
  currentBody: string;
  /** Slug-to-path index built from the tree for outlink resolution. */
  slugIndex: Record<string, string>;

  setCurrent: (
    path: string | null,
    body: string,
    slugIndex: Record<string, string>,
  ) => void;
}

export const useBrowseStore = create<BrowseState>((set) => ({
  currentPath: null,
  currentBody: "",
  slugIndex: {},
  setCurrent: (currentPath, currentBody, slugIndex) =>
    set({ currentPath, currentBody, slugIndex }),
}));
