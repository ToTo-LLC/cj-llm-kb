/**
 * File upload (Plan 07 Task 17).
 *
 * ``uploadFile(file)`` is the browser-side entry point for drag-drop
 * and file-picker ingestion. It POSTs a multipart form to the Task 17
 * proxy route ``/api/proxy/upload``; the route reads the file body on
 * the server, attaches the per-run token, and forwards the raw text to
 * ``brain_ingest``.
 *
 * Binary files (PDF, images, zip, ...) are out of scope for day-one —
 * the proxy route rejects them with 415 and we translate that into a
 * typed error here so the caller can surface a "PDFs coming soon" toast
 * without parsing the error body itself. Task 25 sweep will plumb a
 * proper binary upload variant (base64 or temp-file handoff).
 */

import { ApiError } from "@/lib/api/types";

/** Successful upload response — echoes the patch id from ``brain_ingest``. */
export interface UploadResult {
  patch_id: string | null;
  applied: boolean;
  domain: string | null;
  [extra: string]: unknown;
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

  const response = await fetch("/api/proxy/upload", {
    method: "POST",
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
  return (envelope.data ?? {
    patch_id: null,
    applied: false,
    domain: null,
  }) as UploadResult;
}
