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

/**
 * Plan 25 T4 — per-phase progress UI.
 *
 * The wizard has two long-running phases that need visible feedback:
 *
 *   - **Walking** (Step 1 — pick folder): backend ``BulkImporter.plan()``
 *     walks the folder + classifies files. Can take 10–30s for thousands
 *     of files. Backend doesn't stream during walk so we render a spinner +
 *     folder path + elapsed time. ``walkPath`` and ``walkStartedAt`` are
 *     set when the dry-run kicks; both reset when the walk completes
 *     (success or error).
 *   - **Applying** (Step 4 — apply): JS-driven serial ingest loop already
 *     emits REAL per-file progress via ``applyIdx``. T4 adds ``applyStartedAt``
 *     for an ETA estimate ("Estimated time remaining: ~Xm") computed from
 *     a rolling 10s/file napkin assumption.
 *
 * Per D11 (timer-based pseudo-progress): we deliberately keep the apply
 * loop's REAL progress (already accurate) and only synthesize state for
 * the walk phase where the backend doesn't stream.
 */
export type BulkPhase = "idle" | "walking" | "applying" | "complete" | "error";

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
  // Plan 25 T4 — phase tracking
  phase: BulkPhase;
  walkPath: string | null;
  walkStartedAt: number | null;
  applyStartedAt: number | null;
  // Plan 26 T4 — per-file filename display during apply phase. The
  // apply loop writes the current file's relative path here before each
  // ``await ingest()`` so the UI can render "Current: <path>" under the
  // progress bar. Cleared on complete/error/finally (D11).
  currentFile: string | null;

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
  // Plan 25 T4 — phase actions
  beginWalk: (path: string) => void;
  endWalk: (ok: boolean) => void;
  // Plan 26 T4 — per-file filename display
  setCurrentFile: (name: string | null) => void;
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
  | "phase"
  | "walkPath"
  | "walkStartedAt"
  | "applyStartedAt"
  | "currentFile"
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
  phase: "idle",
  walkPath: null,
  walkStartedAt: null,
  applyStartedAt: null,
  currentFile: null,
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
      // Plan 25 T4 — walk completed successfully; clear walk state
      phase: "idle",
      walkPath: null,
      walkStartedAt: null,
    });
  },

  // Plan 25 T4 — begin/end walk lifecycle. The walk phase has no streaming
  // progress signal from the backend; the UI renders a spinner + folder
  // path + elapsed time off ``walkStartedAt``. ``endWalk(false)`` clears
  // walk state without advancing the step (toast in the caller surfaces
  // the error).
  beginWalk: (path) => {
    set({
      phase: "walking",
      walkPath: path,
      walkStartedAt: Date.now(),
    });
  },

  endWalk: (ok) => {
    if (ok) {
      // pickFolder() already cleared walk state. Defensive: if a caller
      // didn't reach pickFolder(), still drop us back to idle.
      set({ phase: "idle", walkPath: null, walkStartedAt: null });
    } else {
      // Plan 26 T4 (D11) — error state-machine transition clears
      // ``currentFile`` alongside walk markers so the lingering
      // apply-phase microcopy doesn't leak into the error screen.
      set({
        phase: "error",
        walkPath: null,
        walkStartedAt: null,
        currentFile: null,
      });
    }
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
      // Plan 25 T4 — apply phase markers for ETA computation
      phase: "applying",
      applyStartedAt: Date.now(),
      // Plan 26 T4 — start each apply session with no current-file
      // microcopy; the first iteration sets it before its ingest call.
      currentFile: null,
    });

    // Plan 26 T4 (D11) — outer try/finally guarantees ``currentFile``
    // clears at apply-phase exit regardless of how the loop terminates
    // (normal completion, cancel, or an unexpected synchronous throw
    // from one of the ``set()`` calls). This is the third clear-site.
    try {
      for (let i = 0; i < queue.length; i++) {
        if (get().cancelled) break;
        const file = queue[i];
        // Plan 26 T4 — surface the in-flight filename to the UI before
        // awaiting the ingest. The store's ``currentFile`` drives the
        // ``apply-current-file`` microcopy under the progress bar.
        get().setCurrentFile(file.name);
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
    } finally {
      // Plan 26 T4 (D11) — complete state-machine transition clears
      // ``currentFile`` alongside ``phase: "complete"``. Setting it in
      // the finally block (rather than after the loop) ensures the
      // clear fires even if a caller cancels via an exception path.
      set({
        applying: false,
        done: true,
        phase: "complete",
        currentFile: null,
      });
    }
  },

  cancel: () => set({ cancelled: true }),

  reset: () => set({ ...INITIAL }),

  // Plan 26 T4 — setter for the current-file filename microcopy. Called
  // by the apply loop before each ``await ingest()`` and cleared in the
  // outer finally (D11 third clear-site). Tests also drive this
  // directly to render the apply-current-file element in isolation.
  setCurrentFile: (name) => set({ currentFile: name }),
}));
