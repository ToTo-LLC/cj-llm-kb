"use client";

import { create } from "zustand";

import { recentIngests } from "@/lib/api/tools";

/**
 * Inbox-store (Plan 07 Task 17).
 *
 * Holds the list of ingest sources that drive the inbox screen + its
 * three-tab filter (In progress / Needs attention / Recent), plus
 * optimistic in-flight rows inserted by drag-drop / paste / file-picker
 * uploads. The store talks to the typed tools API (``recentIngests``)
 * but never to the WS directly — Task 14 already routes ``ingest_*``
 * events through ``useChatWebSocket``, and Task 25 will wire per-row
 * status streaming once the backend emits it.
 *
 * The shape deliberately mirrors the ``IngestSource`` row rendered by
 * ``<SourceRow />``. The tab filter is applied at the component layer
 * (simple array filter) so the store can stay dumb.
 */

/**
 * Seven discrete statuses the pipeline flows through. ``queued`` is the
 * optimistic entry state; ``done`` and ``failed`` are terminal. Anything
 * in between is rendered by the in-progress tab.
 */
export type IngestStatus =
  | "queued"
  | "extracting"
  | "classifying"
  | "summarizing"
  | "integrating"
  | "done"
  | "failed";

/** Kind of source — drives the leading icon + badge. */
export type IngestType = "url" | "pdf" | "text" | "email" | "file";

/** The three inbox tabs. */
export type InboxTab = "progress" | "failed" | "recent";

export interface IngestSource {
  /** Stable row id — server-assigned ``patch_id`` once known, otherwise a
   *  locally-minted optimistic id. */
  id: string;
  /** Opaque source locator — a URL, file name, or short excerpt. */
  source: string;
  /** Human-readable title. May equal ``source`` for now; Task 25 sweep
   *  pulls the real title from the summary step. */
  title: string;
  type: IngestType;
  status: IngestStatus;
  /** Vault domain the source was filed under. ``null`` until classified. */
  domain: string | null;
  /** 0–100 bar fill percentage. */
  progress: number;
  /** ISO-8601 timestamp for the last status transition. */
  at: string;
  /** Short error message — only set when ``status === "failed"``. */
  error?: string;
  /** USD cost of the ingest run — only set when ``status === "done"``. */
  cost?: number;
  [extra: string]: unknown;
}

/** Args accepted by ``addOptimistic``. Status / progress default to the
 *  ``queued``-at-0% starter row. */
export interface OptimisticSource {
  id: string;
  source: string;
  title: string;
  type: IngestType;
}

/** Args accepted by ``updateStatus``. */
export interface StatusUpdate {
  status: IngestStatus;
  progress?: number;
  domain?: string | null;
  error?: string;
  cost?: number;
}

export interface InboxState {
  sources: IngestSource[];
  activeTab: InboxTab;

  loadRecent: () => Promise<void>;
  setTab: (tab: InboxTab) => void;
  addOptimistic: (source: OptimisticSource) => void;
  updateStatus: (id: string, patch: StatusUpdate) => void;
}

/**
 * Best-effort type inference from a source string. URLs detect by
 * ``http(s)://`` prefix; everything else falls back to ``text`` since
 * the current ingest pipeline only accepts URLs, paths, or raw text.
 * File-type inference for drag-drop uploads lives in ``uploadFile`` —
 * the caller supplies the typed ``OptimisticSource`` there directly.
 */
function inferType(source: string): IngestType {
  const trimmed = source.trim();
  if (/^https?:\/\//i.test(trimmed)) return "url";
  return "text";
}

function inferTitle(source: string): string {
  const trimmed = source.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    try {
      const u = new URL(trimmed);
      return u.hostname + u.pathname;
    } catch {
      return trimmed;
    }
  }
  // Keep the first line for plain-text snippets — avoids a 4KB blob
  // dominating the row title.
  const firstLine = trimmed.split(/\r?\n/)[0] ?? "";
  return firstLine.length > 80 ? firstLine.slice(0, 77) + "…" : firstLine;
}

export const useInboxStore = create<InboxState>((set) => ({
  sources: [],
  activeTab: "progress",

  loadRecent: async () => {
    const res = await recentIngests({});
    const data = (res.data ?? { items: [] }) as {
      items: Array<{
        source: string;
        domain: string | null;
        status: string;
        at: string;
        [extra: string]: unknown;
      }>;
    };
    const items = (data.items ?? []).map(
      (it, idx): IngestSource => ({
        id: (it.patch_id as string) ?? `ingest-${it.at}-${idx}`,
        source: it.source,
        title: (it.title as string) ?? inferTitle(it.source),
        type: (it.type as IngestType) ?? inferType(it.source),
        status: (it.status as IngestStatus) ?? "done",
        domain: it.domain ?? null,
        progress:
          typeof it.progress === "number"
            ? (it.progress as number)
            : it.status === "done"
              ? 100
              : 0,
        at: it.at,
        error: (it.error as string | undefined) ?? undefined,
        cost: (it.cost as number | undefined) ?? undefined,
      }),
    );
    set({ sources: items });
  },

  setTab: (activeTab) => set({ activeTab }),

  addOptimistic: (source) => {
    set((s) => ({
      sources: [
        {
          id: source.id,
          source: source.source,
          title: source.title,
          type: source.type,
          status: "queued",
          domain: null,
          progress: 0,
          at: new Date().toISOString(),
        },
        ...s.sources,
      ],
    }));
  },

  updateStatus: (id, patch) => {
    set((s) => ({
      sources: s.sources.map((row) =>
        row.id === id
          ? {
              ...row,
              status: patch.status,
              progress:
                typeof patch.progress === "number"
                  ? patch.progress
                  : row.progress,
              domain: patch.domain === undefined ? row.domain : patch.domain,
              error: patch.error ?? row.error,
              cost: patch.cost ?? row.cost,
              at: new Date().toISOString(),
            }
          : row,
      ),
    }));
  },
}));
