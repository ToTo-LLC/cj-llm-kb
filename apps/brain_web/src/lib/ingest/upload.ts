/**
 * File upload (Plan 07 Task 17, updated Plan 08 Task 2).
 *
 * ``uploadFile(file)`` is the browser-side entry point for drag-drop
 * and file-picker ingestion. It POSTs a multipart form to the same-origin
 * ``/api/upload`` endpoint served by brain_api; the backend validates the
 * MIME type + size and forwards the text body to ``brain_ingest``.
 *
 * Plan 08 pivot: the old Next.js proxy route at ``/api/proxy/upload`` is
 * gone — brain_api is now both the API + UI host, so we call it directly.
 * The per-run token is attached via ``X-Brain-Token`` read from the Zustand
 * token store (populated by the bootstrap effect on mount).
 *
 * Binary files (PDF, images, zip, ...) are still out of scope for day-one —
 * the backend rejects them with 415 and we translate that into a typed error
 * here so the caller can surface a "PDFs coming soon" toast without parsing
 * the error body itself. Task 25 sweep will plumb a proper binary upload
 * variant.
 */

import { ApiError } from "@/lib/api/types";
import { getToken } from "@/lib/state/token-store";

/**
 * Successful upload response — echoes the patch id from ``brain_ingest``.
 *
 * Plan 19 T2 narrow: the backend's ``UploadResponse`` (Pydantic
 * ``BaseModel`` at ``packages/brain_api/src/brain_api/endpoints/upload.py:91``)
 * declares ``{patch_id: str}`` — a single non-nullable field. The previous
 * TS shape declared ``applied`` + ``domain`` which the backend never
 * emits, plus a permissive ``patch_id: string | null`` (backend's is
 * non-null). Two live consumers (``drop-zone.tsx``,
 * ``app-shell.tsx``) read ``res.domain`` and silently wrote
 * ``undefined``/``null`` into the inbox row's ``domain`` field on
 * every successful upload. T2 narrows TS to backend reality; the
 * inbox row's actual classified ``domain`` is filled in by
 * ``inbox-store``'s ``recentIngests`` poll once the staged patch
 * resolves backend-side.
 */
export interface UploadResult {
  patch_id: string;
}

/**
 * MIME types we consider ``text`` for upload purposes. Anything else
 * lands in the binary bucket and is rejected with a typed error.
 *
 * The allow-list is deliberately narrow — the backend's tolerant
 * mimetype sniffing lives behind the proxy; we stay conservative here
 * to make the "PDFs coming soon" surface actionable.
 */
const TEXT_MIME_PATTERNS: readonly RegExp[] = [
  /^text\//,
  /^application\/json$/,
  /^application\/markdown$/,
  /^application\/xml$/,
  /^application\/(x-)?yaml$/,
];

export function isTextMimeType(type: string): boolean {
  if (!type) return false;
  return TEXT_MIME_PATTERNS.some((re) => re.test(type));
}

/**
 * Upload a single file. Resolves with the backend's ingest result on
 * 2xx; throws ``ApiError`` on any non-2xx — ``status === 415`` signals
 * the binary-rejection path so callers can render a tailored toast.
 */
export async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["X-Brain-Token"] = token;

  const response = await fetch("/api/upload", {
    method: "POST",
    headers,
    body: form,
  });

  if (!response.ok) {
    let body: { error?: string; message?: string; detail?: unknown } = {};
    try {
      body = (await response.json()) as typeof body;
    } catch {
      // fallthrough — empty body
    }
    throw new ApiError(
      response.status,
      body.error ?? "upload_failed",
      (body.detail as Record<string, unknown> | null) ?? null,
      body.message ?? response.statusText ?? "upload failed",
    );
  }

  const envelope = (await response.json()) as {
    data?: UploadResult | null;
    text?: string;
  };
  // Plan 19 T2: backend's ``response_model=UploadResponse`` guarantees a
  // ``{patch_id: str}`` body on 2xx; the previous fallback that filled
  // ``{patch_id: null, applied: false, domain: null}`` was dead code under
  // the current backend contract (audited 2026-05-11; see plan doc
  // ``T1 audit findings``). Treat a missing/empty ``data`` as a contract
  // violation rather than papering over it.
  const data = envelope.data;
  if (!data || typeof data.patch_id !== "string" || data.patch_id === "") {
    throw new ApiError(
      response.status,
      "upload_envelope_invalid",
      null,
      "upload succeeded but server did not return a patch_id",
    );
  }
  return { patch_id: data.patch_id };
}
