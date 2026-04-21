// Shared types for the typed API client (Plan 07 Task 9).
//
// These mirror the FastAPI envelopes in ``brain_api.responses``:
//   - ToolResponse  -> every 2xx from ``POST /api/tools/{name}``
//   - ErrorResponse -> every 4xx/5xx from any route (flat envelope, Task 15)
//
// The frontend NEVER decodes error bodies into domain data; any non-2xx is
// surfaced as ``ApiError`` so callers get one exception type to catch.

/**
 * Successful tool-call envelope. ``text`` is the human-readable summary
 * (fed into the chat transcript when the LLM invokes the tool); ``data``
 * is the structured payload (rendered in UI panels).
 *
 * ``data`` is typed as a generic so each per-tool binding can narrow it
 * to the shape that specific tool returns. Defaults to a loose
 * ``Record<string, unknown>`` for callers that don't care about the
 * specific payload shape.
 */
export interface ToolResponse<D = Record<string, unknown>> {
  text: string;
  data: D | null;
}

/**
 * Flat error envelope emitted by ``brain_api.errors``. Matches the
 * Pydantic ``ErrorResponse`` model — every 4xx/5xx from the API takes
 * exactly this shape.
 */
export interface ErrorResponse {
  error: string;
  message: string;
  detail: Record<string, unknown> | null;
}

/**
 * Rich error type thrown by ``apiFetch`` on any non-2xx response.
 *
 * Preserves the HTTP status, the typed ``error`` code, and the optional
 * ``detail`` bag (Pydantic validation errors land in
 * ``detail.errors`` for 400s, for example). UI code can pattern-match on
 * ``code`` + ``status`` to show specific messages without re-parsing the
 * raw response.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly detail: Record<string, unknown> | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
