// EventSource wrapper for /api/bulk/walk-progress — Plan 26 T3.
//
// brain_api exposes the walk-phase SSE stream at
// ``GET /api/bulk/walk-progress?path=<folder>&token=<hex>`` (see
// ``packages/brain_api/src/brain_api/endpoints/bulk_walk_progress.py``).
// The browser ``EventSource`` constructor accepts neither custom headers
// nor cookies on a cross-origin connection — same constraint the chat
// WebSocket lives with — so the per-run app token rides in the query
// string. We read it synchronously from the token-store via
// ``getToken()`` at subscribe time; callers don't need to pass it in.
//
// Wire format (per ``brain_core.ingest.walk_events``):
//   * ``data: <json>\n\n`` records, one per event.
//   * ``<json>`` is the discriminated-union ``WalkEvent`` with
//     ``type ∈ {walk_started, walk_progress, walk_complete, walk_error}``.
//
// Lifecycle (per D7 in the plan-doc):
//   * Caller invokes ``subscribeWalkProgress(path, token, callbacks)``.
//   * Returns a ``() => void`` close handle. Callers MUST invoke it on
//     unmount / completion / error to release the EventSource.
//   * Graceful degradation (per D3): EventSource transport-level errors
//     BEFORE the first event arrives surface via ``onConnectionError``
//     so the caller can fall back to timer-driven pseudo-progress.
//     Transport errors AFTER the first event are surfaced via
//     ``onConnectionError`` as well — caller decides whether to
//     fall back or treat as terminal.
//
// Zero new npm deps (per D14) — native ``EventSource`` only.

export type WalkStartedEvent = {
  type: "walk_started";
  path: string;
};

export type WalkProgressEvent = {
  type: "walk_progress";
  files_seen: number;
  current_path: string;
};

export type WalkCompleteEvent = {
  type: "walk_complete";
  total_count: number;
  plan_id: string;
};

export type WalkErrorEvent = {
  type: "walk_error";
  error_message: string;
  error_code: "permission_denied" | "path_not_found" | "internal_error";
};

export type WalkEvent =
  | WalkStartedEvent
  | WalkProgressEvent
  | WalkCompleteEvent
  | WalkErrorEvent;

export interface WalkProgressCallbacks {
  /** ``walk_started`` — the walk has begun; UI can leave the "connecting" state. */
  onStarted?: (event: WalkStartedEvent) => void;
  /** ``walk_progress`` — periodic progress (every 50 files seen). */
  onProgress?: (event: WalkProgressEvent) => void;
  /** ``walk_complete`` — terminal success; carries final count + plan_id. */
  onComplete?: (event: WalkCompleteEvent) => void;
  /**
   * ``walk_error`` — APPLICATION-level walk failure (permission, missing
   * path, internal). This is a structured event on the wire — distinct
   * from a transport-level connection failure.
   */
  onError?: (event: WalkErrorEvent) => void;
  /**
   * Transport-level EventSource failure (network drop, server died,
   * 5xx during streaming, browser ``EventSource.onerror``). The caller
   * uses receipt of this signal to decide between graceful-degradation
   * fallback (if no events have arrived yet) and a terminal "scan
   * failed" state (if some events arrived first).
   */
  onConnectionError?: () => void;
}

/**
 * Subscribe to the SSE walk-progress stream. Returns a close handle.
 *
 * The handle is idempotent — calling it twice is safe. It calls
 * :js:`EventSource.close()` and clears local listeners so the
 * callbacks do not fire after teardown even if a late frame arrives
 * (rare but possible — the browser buffers the previous tick of
 * received bytes during teardown).
 */
export function subscribeWalkProgress(
  path: string,
  token: string,
  callbacks: WalkProgressCallbacks,
): () => void {
  // Construct the URL with both query parameters URL-encoded. The
  // backend pulls them out of FastAPI's ``Query(...)`` machinery so
  // standard ``encodeURIComponent`` is sufficient.
  const url =
    `/api/bulk/walk-progress?path=${encodeURIComponent(path)}` +
    `&token=${encodeURIComponent(token)}`;

  // Use the global ``EventSource`` so tests can swap in a mock by
  // assigning to ``global.EventSource``. ``new EventSource(url)`` opens
  // the connection synchronously (the GET fires on the next tick).
  const eventSource = new EventSource(url);

  let closed = false;
  let receivedFirst = false;

  const close = (): void => {
    if (closed) return;
    closed = true;
    // Clear handlers before close() so late onerror dispatches during
    // teardown don't fire onConnectionError again.
    eventSource.onmessage = null;
    eventSource.onerror = null;
    eventSource.close();
  };

  eventSource.onmessage = (event: MessageEvent): void => {
    if (closed) return;
    let payload: WalkEvent;
    try {
      payload = JSON.parse(event.data) as WalkEvent;
    } catch {
      // Malformed frame — treat as a connection-level error so the
      // caller can decide whether to fall back to the timer. We do
      // NOT close the EventSource here: a single garbled frame is
      // recoverable, and the browser will keep delivering subsequent
      // frames.
      callbacks.onConnectionError?.();
      return;
    }

    receivedFirst = true;

    switch (payload.type) {
      case "walk_started":
        callbacks.onStarted?.(payload);
        return;
      case "walk_progress":
        callbacks.onProgress?.(payload);
        return;
      case "walk_complete":
        callbacks.onComplete?.(payload);
        // Terminal event — close the stream so we don't hold the
        // connection open waiting for frames that will never arrive.
        close();
        return;
      case "walk_error":
        callbacks.onError?.(payload);
        // Terminal event — same reasoning as walk_complete.
        close();
        return;
      default: {
        // Unknown discriminator — surface as a connection error so the
        // caller can recover. ``never`` cast keeps the exhaustiveness
        // check honest if a new event type is added to ``WalkEvent``
        // without updating this switch.
        const _exhaustive: never = payload;
        void _exhaustive;
        callbacks.onConnectionError?.();
        return;
      }
    }
  };

  eventSource.onerror = (): void => {
    if (closed) return;
    // Whether or not we've received the first event, surface the
    // connection error so the caller decides how to react (timer
    // fallback vs terminal). EventSource auto-reconnects by default;
    // we close explicitly to give the caller full control.
    void receivedFirst;
    callbacks.onConnectionError?.();
    close();
  };

  return close;
}
