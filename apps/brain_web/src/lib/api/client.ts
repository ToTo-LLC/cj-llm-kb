// Typed fetch wrapper for brain_api — Plan 08 Task 2.
//
// brain_web is a static SPA served by brain_api on the same origin, so every
// HTTP call is a relative ``/api/<path>`` fetch directly to the backend — no
// more Next.js proxy layer. The per-run token lives in ``useTokenStore``
// (populated once by the bootstrap effect); we read it synchronously via the
// module accessor ``getToken()`` and attach as ``X-Brain-Token``.
//
// Contract:
//   * 2xx → decoded ``ToolResponse`` envelope.
//   * non-2xx → ``ApiError`` thrown with status + typed ``error`` code.
//   * 401/403 → treated like any other 4xx (``code = "unauthorized"`` if the
//     backend didn't supply one). The bootstrap flow — not apiFetch — handles
//     token refresh; a silent refresh here would paper over a real
//     "token file rotated mid-session" bug.

import { getToken } from "@/lib/state/token-store";

import { ApiError, type ErrorResponse, type ToolResponse } from "./types";

/**
 * Fetch ``/api<path>`` and decode the ``ToolResponse`` envelope.
 *
 * ``D`` narrows the ``data`` payload for a specific tool. Use the typed
 * bindings in ``./tools.ts`` rather than calling this directly so each call
 * site gets compile-time shape checks.
 *
 * Throws ``ApiError`` on any non-2xx status. If the error body is itself
 * unparseable (502 from an HTML error page, upstream died mid-response, etc.)
 * falls back to ``status: ?, code: "unknown"`` so UI code can still render
 * something.
 */
export async function apiFetch<D = Record<string, unknown>>(
  path: string,
  init?: RequestInit,
): Promise<ToolResponse<D>> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers["X-Brain-Token"] = token;
  }

  const response = await fetch(path, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let body: ErrorResponse;
    try {
      body = (await response.json()) as ErrorResponse;
    } catch {
      // 401 / 403 without a JSON body falls through to the ``unknown`` path
      // below — callers that care about auth failures can still read
      // ``err.status === 401`` on the thrown ApiError.
      throw new ApiError(
        response.status,
        response.status === 401 || response.status === 403
          ? "unauthorized"
          : "unknown",
        null,
        response.statusText || "request failed",
      );
    }
    throw new ApiError(response.status, body.error, body.detail, body.message);
  }

  return (await response.json()) as ToolResponse<D>;
}
