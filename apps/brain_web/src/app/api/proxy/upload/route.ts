// Multipart file upload proxy (Plan 07 Task 17).
//
// The catch-all proxy at ``/api/proxy/[...path]`` forwards JSON bodies
// unchanged — that works for every other tool. This route carves out a
// dedicated multipart path because Next's App Router already parses the
// request body to a ``FormData`` when we call ``.formData()``, and we
// need to extract the uploaded ``File`` here to (a) validate the MIME
// type (text only for day-one) and (b) re-shape the call for
// ``brain_ingest``, which takes a ``source: string`` (URL, path, or raw
// text) rather than multipart data.
//
// Contract:
//   * 503 if the per-run token can't be read (setup wizard).
//   * 400 if the form body has no ``file`` part.
//   * 415 if the file's MIME type isn't in the text allow-list. The
//     frontend reads this status to surface "PDFs coming soon."
//   * Otherwise: forward the file body as ``{ source: <text> }`` to
//     ``brain_ingest`` with ``X-Brain-Token`` + ``Origin`` headers and
//     return the upstream response verbatim.
//
// PDFs / binaries: deferred to the Task 25 sweep or Plan 09. The plan
// calls out this limitation explicitly; the 415 surface is what makes
// the deferral user-visible.

import { NextRequest, NextResponse } from "next/server";

import { readToken } from "@/lib/auth/token";

const API_BASE = process.env.BRAIN_API_URL || "http://127.0.0.1:4317";
const FRONTEND_ORIGIN =
  process.env.BRAIN_WEB_ORIGIN || "http://localhost:4316";

/** MIME patterns the backend can ingest today (text source). */
const TEXT_MIME_PATTERNS: readonly RegExp[] = [
  /^text\//,
  /^application\/json$/,
  /^application\/markdown$/,
  /^application\/xml$/,
  /^application\/(x-)?yaml$/,
];

function isTextMimeType(type: string): boolean {
  if (!type) return false;
  return TEXT_MIME_PATTERNS.some((re) => re.test(type));
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const token = await readToken();
  if (!token) {
    return NextResponse.json(
      {
        error: "setup_required",
        message: "brain_api token not found. Is brain_api running?",
      },
      { status: 503 },
    );
  }

  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json(
      { error: "invalid_input", message: "Expected multipart/form-data body." },
      { status: 400 },
    );
  }

  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "invalid_input", message: "Missing 'file' field." },
      { status: 400 },
    );
  }

  if (!isTextMimeType(file.type)) {
    return NextResponse.json(
      {
        error: "unsupported_media_type",
        message:
          "Only text files are supported for upload today. PDFs coming soon.",
        detail: { received: file.type || "application/octet-stream" },
      },
      { status: 415 },
    );
  }

  const content = await file.text();

  const upstream = await fetch(`${API_BASE}/api/tools/brain_ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Brain-Token": token,
      Origin: FRONTEND_ORIGIN,
    },
    body: JSON.stringify({ source: content }),
  });

  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/json",
    },
  });
}
