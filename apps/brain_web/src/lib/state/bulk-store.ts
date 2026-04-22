"use client";

import { create } from "zustand";

import { ingest } from "@/lib/api/tools";

/**
 * Bulk-store (Plan 07 Task 21).
 *
 * Drives the 4-step bulk-import flow:
 *   1. Pick folder   — populate ``folder`` + ``files`` from the dry-run tool.
 *   2. Target domain — one-shot ``domain`` + ``cap`` selection.
 *   3. Dry-run review — per-file ``include`` + ``setRoute`` edits.
 *   4. Apply         — serial ``ingest`` loop, honouring ``cancel``.
 *
 * The store owns UI state only. Every write round-trips through the typed
 * tools API so the vault remains the source of truth. The apply loop is a
 * ``for await`` over the included + non-skipped files; each ingest result
 * lands in ``results.applied``, each failure in ``results.failed``, and
 * every ``skip`` reason lands in ``results.quarantined`` up front.
 *
 * Testing trade-off: the true filesystem folder-picker requires an
 * Electron wrapper (Plan 08 roadmap). The web-only ``<input webkitdirectory>``
 * path-picker reads metadata locally then ships the user-typed path to the
 * backend for the real read. The "Use a path" text flow is the canonical
 * ingest path in Task 21 — documented in ``step-pick-folder.tsx``.
 */

export interface BulkFile {
  id: number;
  name: string;
  type: "pdf" | "text" | "doc" | "img" | "email" | "url" | "sys";
  size: string;
  classified: string | null;
  confidence: number | null;
  include: boolean;
  duplicate?: boolean;
  uncertain?: boolean;
  flagged?: "personal";
  skip?: string;
}

export interface BulkFolder {
  path: string;
  fileCount: number;
  picked: string;
}

export interface BulkResults {
  applied: string[];
  failed: string[];
  quarantined: string[];
}

export interface BulkState {
  step: 1 | 2 | 3 | 4;
  folder: BulkFolder | null;
  domain: "auto" | string;
  cap: number;
  files: BulkFile[];
  applying: boolean;
  applyIdx: number;
  cancelled: boolean;
  done: boolean;
  results: BulkResults;

  // actions
  pickFolder: (path: string, files: BulkFile[]) => void;
  setStep: (step: 1 | 2 | 3 | 4) => void;
  setDomain: (domain: "auto" | string) => void;
  setCap: (n: number) => void;
  toggleInclude: (id: number) => void;
  toggleIncludeAll: (next: boolean) => void;
  setRoute: (id: number, dom: string) => void;
  startApply: () => Promise<void>;
  cancel: () => void;
  reset: () => void;
}

const INITIAL: Pick<
  BulkState,
  | "step"
  | "folder"
  | "domain"
  | "cap"
  | "files"
  | "applying"
  | "applyIdx"
  | "cancelled"
  | "done"
  | "results"
> = {
  step: 1,
  folder: null,
  domain: "auto",
  cap: 20,
  files: [],
  applying: false,
  applyIdx: 0,
  cancelled: false,
  done: false,
  results: { applied: [], failed: [], quarantined: [] },
};

function nowPicked(): string {
  return "just now";
}

export const useBulkStore = create<BulkState>((set, get) => ({
  ...INITIAL,

  pickFolder: (path, files) => {
    set({
      step: 2,
      folder: { path, fileCount: files.length, picked: nowPicked() },
      files,
      cap: Math.min(20, files.length || 20),
      applying: false,
      applyIdx: 0,
      cancelled: false,
      done: false,
      results: { applied: [], failed: [], quarantined: [] },
    });
  },

  setStep: (step) => set({ step }),

  setDomain: (domain) => set({ domain }),

  setCap: (n) => {
    const folder = get().folder;
    const ceiling = folder?.fileCount ?? n;
    const clamped = Math.max(1, Math.min(ceiling, Math.floor(n) || 1));
    set({ cap: clamped });
  },

  toggleInclude: (id) => {
    set((s) => ({
      files: s.files.map((f) =>
        f.id === id ? { ...f, include: !f.include } : f,
      ),
    }));
  },

  toggleIncludeAll: (next) => {
    set((s) => ({
      files: s.files.map((f) => (f.skip ? f : { ...f, include: next })),
    }));
  },

  setRoute: (id, dom) => {
    set((s) => ({
      files: s.files.map((f) =>
        f.id === id ? { ...f, classified: dom, confidence: 1 } : f,
      ),
    }));
  },

  startApply: async () => {
    // Snapshot queue at start so include edits mid-loop don't shift indices.
    const state = get();
    const skipped = state.files.filter((f) => f.skip).map((f) => f.name);
    const queue = state.files.filter((f) => f.include && !f.skip);

    set({
      step: 4,
      applying: true,
      applyIdx: 0,
      cancelled: false,
      done: false,
      results: { applied: [], failed: [], quarantined: skipped },
    });

    for (let i = 0; i < queue.length; i++) {
      if (get().cancelled) break;
      const file = queue[i];
      try {
        await ingest({
          source: file.name,
          domain_override:
            file.classified && file.classified !== "auto"
              ? file.classified
              : undefined,
        });
        set((s) => ({
          applyIdx: i + 1,
          results: {
            ...s.results,
            applied: [...s.results.applied, file.name],
          },
        }));
      } catch {
        set((s) => ({
          applyIdx: i + 1,
          results: {
            ...s.results,
            failed: [...s.results.failed, file.name],
          },
        }));
      }
    }

    set({ applying: false, done: true });
  },

  cancel: () => set({ cancelled: true }),

  reset: () => set({ ...INITIAL }),
}));
