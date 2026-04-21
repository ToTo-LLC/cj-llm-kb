// Typed fetch wrapper for the Next.js → brain_api proxy.
//
// ALL HTTP traffic flows through the Task 8 catch-all route at
// ``/api/proxy/*`` — that route reads the per-run token server-side and
// attaches it as ``X-Brain-Token`` before forwarding to
// ``http://127.0.0.1:4317``. The browser never sees the token; the
// client side here just issues same-origin fetches and trusts the
// proxy to authenticate.
//
// Every non-2xx response throws ``ApiError`` — callers never have to
// check ``response.ok``.

import { ApiError, type ErrorResponse, type ToolResponse } from "./types";

/**
 * Fetch ``/api/proxy<path>`` and decode the ``ToolResponse`` envelope.
 *
 * ``D`` narrows the ``data`` payload for a specific tool. Use the
 * typed bindings in ``./tools.ts`` rather than calling this directly
 * so each call site gets compile-time shape checks.
 *
 * Throws ``ApiError`` on any non-2xx status. If the error body is
 * itself unparseable (upstream died mid-response, 502 from an HTML
 * error page, etc.) falls back to ``status: ?, code: "unknown"`` so
 * UI code can still render something.
 */
export async function apiFetch<D = Record<string, unknown>>(
  path: string,
  init?: RequestInit,
): Promise<ToolResponse<D>> {
  const response = await fetch("/api/proxy" + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let body: ErrorResponse;
    try {
      body = (await response.json()) as ErrorResponse;
    } catch {
      throw new ApiError(
        response.status,
        "unknown",
        null,
        response.statusText || "request failed",
      );
    }
    throw new ApiError(response.status, body.error, body.detail, body.message);
  }

  return (await response.json()) as ToolResponse<D>;
}
