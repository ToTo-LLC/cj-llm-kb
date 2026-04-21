// Catch-all proxy to brain_api.
//
// Responsibilities:
// 1. Read the per-run token from disk (server-side only).
// 2. Forward the incoming request to `http://127.0.0.1:4317/<path>` with
//    `X-Brain-Token` + `Origin: http://localhost:4316` headers attached.
// 3. Strip sensitive headers from the upstream response before returning it
//    to the browser — the token MUST NOT leak to client-side JS.
//
// Missing-token contract: return `503 { error: "setup_required" }` so the
// setup wizard (Task 13) can detect first-run and launch its flow.
import { NextRequest, NextResponse } from "next/server";

import { readToken } from "@/lib/auth/token";

const API_BASE = process.env.BRAIN_API_URL || "http://127.0.0.1:4317";
const FRONTEND_ORIGIN =
  process.env.BRAIN_WEB_ORIGIN || "http://localhost:4316";

// Response headers the upstream API sets that must be removed before we hand
// the response back to the browser. Matched case-insensitively.
const STRIPPED_RESPONSE_HEADERS = new Set<string>([
  "x-brain-token",
  "server",
]);

// Request headers that must be dropped before forwarding. `host` must be
// dropped because Node's `fetch` sets it from the target URL; keeping the
// frontend's host would mismatch the upstream's expected Origin/Host pairing.
// `connection` is a hop-by-hop header.
const STRIPPED_REQUEST_HEADERS: readonly string[] = ["host", "connection"];

async function proxy(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await context.params;
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

  const urlSuffix = "/" + path.join("/") + (req.nextUrl.search || "");
  const targetUrl = API_BASE + urlSuffix;

  const headers = new Headers(req.headers);
  headers.set("X-Brain-Token", token);
  headers.set("Origin", FRONTEND_ORIGIN);
  for (const name of STRIPPED_REQUEST_HEADERS) {
    headers.delete(name);
  }

  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;

  const upstream = await fetch(targetUrl, {
    method,
    headers,
    body,
    redirect: "manual",
  });

  const outHeaders = new Headers();
  for (const [name, value] of upstream.headers) {
    if (!STRIPPED_RESPONSE_HEADERS.has(name.toLowerCase())) {
      outHeaders.set(name, value);
    }
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: outHeaders,
  });
}

export {
  proxy as DELETE,
  proxy as GET,
  proxy as PATCH,
  proxy as POST,
  proxy as PUT,
};
