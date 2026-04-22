// Thin browser WebSocket wrapper for brain_api chat streaming.
//
// ## Same-origin WebSocket (Plan 08 Task 2)
//
// brain_api now serves both the static UI and the WebSocket endpoints, so
// the browser opens the socket at ``ws://${location.host}/ws/chat/<id>`` —
// no hardcoded port, no dual-origin dance.
//
// The token is carried as a URL query parameter (``?token=<secret>``) to
// match the WS handshake auth that OriginHostMiddleware + the chat route
// expect. It lands in client-side JS memory. Accepted because:
//   - deploy is localhost-loopback only;
//   - the token rotates every time ``create_app`` runs;
//   - same-origin restrictions keep the WS URL off cross-site fetches.

import {
  SCHEMA_VERSION,
  parseServerEvent,
  type ClientMessage,
  type ServerEvent,
} from "./events";

export interface WebSocketClientOptions {
  /** Thread ID to resume. Same ID always maps to the same Python ChatThread. */
  threadId: string;
  /** Per-run token written by brain_api to ``.brain/run/token``. */
  token: string;
  /** Called for every validated server event, in wire order. */
  onEvent: (event: ServerEvent) => void;
  /** Called once after ``readyState`` flips to OPEN. */
  onOpen?: () => void;
  /** Called whenever the socket closes. ``clean`` = manual close, not drop. */
  onClose?: (clean: boolean) => void;
  /**
   * Called when the server's ``schema_version`` frame carries a version
   * that doesn't match the pinned ``SCHEMA_VERSION``. UI should prompt
   * the user to reload rather than silently accept a mismatched contract.
   */
  onSchemaVersionMismatch?: (received: string) => void;
  /** Base reconnect delay in ms. Default 500. */
  reconnectBaseMs?: number;
  /** Max reconnect delay in ms. Default 30_000. */
  reconnectMaxMs?: number;
}

/**
 * Per-thread WebSocket client with exponential-backoff reconnect.
 *
 * Intended to be owned by a single Zustand store slice / React hook —
 * open on mount, close on unmount. Re-creating the class on every
 * hook re-render is fine; only ``connect()`` opens the socket.
 *
 * Bails on policy-violation close (1008) — that's the server's signal
 * that the token is bad, and hammering reconnect would just burn CPU.
 */
export class BrainWebSocket {
  private ws: WebSocket | null = null;
  private readonly opts: WebSocketClientOptions;
  private reconnectAttempt = 0;
  private manualClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(opts: WebSocketClientOptions) {
    this.opts = opts;
  }

  /**
   * Open the socket. No-op if already open/connecting. Safe to call
   * multiple times — the class keeps at most one live socket.
   */
  connect(): void {
    if (this.ws) return;

    const wsUrl = this.buildUrl();
    this.manualClose = false;

    const ws = new WebSocket(wsUrl);
    this.ws = ws;

    ws.addEventListener("open", () => {
      this.reconnectAttempt = 0;
      this.opts.onOpen?.();
    });

    ws.addEventListener("message", (evt: MessageEvent) => {
      let parsed: ServerEvent;
      try {
        const raw =
          typeof evt.data === "string"
            ? JSON.parse(evt.data)
            : evt.data;
        parsed = parseServerEvent(raw);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("[brain-ws] failed to parse event", err, evt.data);
        return;
      }
      if (
        parsed.type === "schema_version" &&
        parsed.version !== SCHEMA_VERSION
      ) {
        // eslint-disable-next-line no-console
        console.warn(
          `[brain-ws] schema mismatch: expected ${SCHEMA_VERSION}, got ${parsed.version}`,
        );
        this.opts.onSchemaVersionMismatch?.(parsed.version);
      }
      this.opts.onEvent(parsed);
    });

    ws.addEventListener("close", (evt: CloseEvent) => {
      this.ws = null;
      this.opts.onClose?.(this.manualClose);
      // 1008 = policy violation (bad token). Don't hammer the server —
      // UI surfaces a reconnect button so the user can retry after
      // fixing setup.
      if (!this.manualClose && evt.code !== 1008) {
        this.scheduleReconnect();
      }
    });
  }

  /**
   * Queue a reconnect with exponential backoff.
   *
   * ``delay = min(max, base * 2 ** attempt)``. Caller-overridable via
   * ``reconnectBaseMs`` / ``reconnectMaxMs``. Attempts reset to 0 on
   * every successful ``open``.
   */
  private scheduleReconnect(): void {
    const base = this.opts.reconnectBaseMs ?? 500;
    const max = this.opts.reconnectMaxMs ?? 30_000;
    const delay = Math.min(max, base * Math.pow(2, this.reconnectAttempt));
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /** Serialise and send a typed client message. No-op if socket not open. */
  send(msg: ClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // eslint-disable-next-line no-console
      console.warn("[brain-ws] send called but socket not open");
      return;
    }
    this.ws.send(JSON.stringify(msg));
  }

  /**
   * Close the socket intentionally. Suppresses any pending reconnect
   * timer so a late-arriving backoff tick doesn't reopen the socket
   * after the caller asked to tear down.
   */
  close(): void {
    this.manualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close(1000, "manual close");
    this.ws = null;
  }

  /**
   * Build the same-origin WS URL.
   *
   * Because brain_api hosts both the static UI and the WebSocket endpoint,
   * the host is always ``location.host`` — no env override needed. The
   * ``wss:`` / ``ws:`` scheme is picked from ``window.location.protocol``
   * so an HTTPS front-end automatically upgrades the WS too.
   */
  private buildUrl(): string {
    const host =
      typeof window !== "undefined" ? window.location.host : "localhost:4317";
    const isHttps =
      typeof window !== "undefined" &&
      window.location.protocol === "https:";
    const scheme = isHttps ? "wss:" : "ws:";
    const threadPart = encodeURIComponent(this.opts.threadId);
    const tokenPart = encodeURIComponent(this.opts.token);
    return `${scheme}//${host}/ws/chat/${threadPart}?token=${tokenPart}`;
  }
}
