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

/** Kind of source — drives the leading icon + badge.
 *
 * Plan 24 T5: added ``docx`` + ``pptx`` to match the backend's
 * ``SourceType`` enum expansion (Plan 24 T0). Generic Microsoft Word
 * documents and PowerPoint slide decks now ingest via dedicated handlers
 * with their own ``source_type`` value emitted by the backend; the
 * Inbox row picks the matching Lucide icon from ``TypeIcon`` below.
 */
export type IngestType =
  | "url"
  | "pdf"
  | "text"
  | "email"
  | "docx"
  | "pptx"
  | "file";

/**
 * Drop-zone accept list (Plan 24 T5) — the canonical mapping from
 * supported MIME type to the file extensions that file pickers and
 * drag-drop callers should advertise. Each entry mirrors the
 * react-dropzone ``Accept`` shape (MIME → extensions[]) even though
 * the current ``DropZone`` uses a hand-rolled drag handler; keeping
 * the same shape future-proofs the constant for a react-dropzone
 * swap and lets us serialize it into a native ``<input accept=...>``
 * value with a single helper.
 *
 * Order: text-ish formats first, then PDFs, then Office Open XML
 * (docx / pptx) added by Plan 24 T5. The backend's upload endpoint
 * is the source of truth for what's actually accepted server-side;
 * this list is the FRONTEND advertisement and feeds the native file
 * picker's filter dropdown.
 */
export const INGEST_ACCEPT: Readonly<Record<string, readonly string[]>> = {
  // Plain text + structured text formats the existing pipeline handles.
  "text/plain": [".txt"],
  "text/markdown": [".md", ".markdown"],
  "application/json": [".json"],
  "application/xml": [".xml"],
  "application/x-yaml": [".yaml", ".yml"],
  // Email exports (.eml).
  "message/rfc822": [".eml"],
  // PDFs.
  "application/pdf": [".pdf"],
  // Plan 24 T5 — Office Open XML formats.
  // .docx — Microsoft Word.
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
    ".docx",
  ],
  // .pptx — Microsoft PowerPoint.
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
    ".pptx",
  ],
};

/**
 * Serialize ``INGEST_ACCEPT`` into the string a native
 * ``<input type="file" accept=...>`` expects: a comma-separated list
 * of MIME types AND extensions. Browsers accept either form; we emit
 * BOTH so the picker behaves correctly across Safari, Chrome, and Edge
 * (Safari historically struggles with MIME-only accept strings for
 * Office Open XML files).
 */
export function ingestAcceptAttribute(): string {
  const parts: string[] = [];
  for (const [mime, exts] of Object.entries(INGEST_ACCEPT)) {
    parts.push(mime);
    for (const ext of exts) parts.push(ext);
  }
  return parts.join(",");
}

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

export const useInboxStore = create<InboxState>((set, get) => ({
  sources: [],
  activeTab: "progress",

  loadRecent: async () => {
    const res = await recentIngests({});
    const data = (res.data ?? { ingests: [] }) as {
      ingests: Array<{
        source: string;
        source_type: string;
        domain: string | null;
        status: string;
        classified_at: string;
        cost_usd: number;
        patch_id?: string;
        error?: string;
        [extra: string]: unknown;
      }>;
    };
    const items = (data.ingests ?? []).map(
      (it, idx): IngestSource => ({
        id: it.patch_id ?? `ingest-${it.classified_at}-${idx}`,
        source: it.source,
        title: (it.title as string) ?? inferTitle(it.source), // title not emitted by backend — Task 25 sweep
        // Plan 24 T5.5: read backend field name ``source_type`` (NOT
        // ``type``). The typed shape on line 202 declares the field
        // correctly as ``source_type``; the pre-T5.5 code at this read
        // site spelled it ``it.type``, which was always ``undefined``
        // → fall-through to ``inferType(it.source)``. That produced a
        // generic ``url``/``text`` IngestType regardless of the actual
        // backend SourceType, and downstream the Inbox row's
        // ``TypeIcon`` rendered the generic ``FileIcon`` instead of
        // the dedicated ``FileText`` / ``Presentation`` glyph for
        // docx / pptx (Plan 24 T5 added those branches). The fix is
        // a 1-token rename to match the backend's emitted field name.
        type: (it.source_type as IngestType) ?? inferType(it.source),
        // Backend emits status as `string`; cast narrows to the IngestStatus literal union.
        status: (it.status as IngestStatus) ?? "done",
        domain: it.domain ?? null,
        progress:
          typeof it.progress === "number"
            ? (it.progress as number)
            : it.status === "done"
              ? 100
              : 0,
        at: it.classified_at,
        error: it.error,
        // Backend always emits cost_usd (0.0 for cached / zero-token rows).
        // Plan 19 T3 (D4) resolved the UX question downstream in <SourceRow>:
        // the badge is suppressed when ``cost === 0``. The store still
        // forwards the raw value so consumers can distinguish 0 from
        // undefined if a future surface needs to.
        cost: it.cost_usd,
      }),
    );
    // Plan 16 Task 1 (D1): id-keyed merge that preserves in-flight
    // optimistic rows whose id is not in the server response. Without
    // this, a slow ``loadRecent`` resolution races optimistic
    // ``addOptimistic`` calls — the unconditional ``set({ sources: items })``
    // overwrites the just-inserted optimistic row with the (typically
    // empty) server list. Only ``queued`` rows are preserved: they're
    // the in-flight optimistic adds. ``complete`` / ``failed`` rows
    // came from the server originally and re-appear in ``items`` if
    // still recent. Optimistic-preserved rows lead the merged array
    // since ``addOptimistic`` prepends — preserves prepend semantics.
    const serverIds = new Set(items.map((i) => i.id));
    const current = get().sources;
    const optimisticPreserved = current.filter(
      (s) => !serverIds.has(s.id) && s.status === "queued",
    );
    set({ sources: [...optimisticPreserved, ...items] });
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
