"""brain_api auth primitives — token generation, filesystem IO, middleware.

Task 7 lands the token-file primitives. Task 8 adds Origin/Host middleware;
Task 9 adds the FastAPI dependency that enforces X-Brain-Token on write routes.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, Request, WebSocket
from starlette.types import ASGIApp, Receive, Scope, Send

from brain_api.context import AppContext, get_ctx
from brain_api.errors import ApiError

_TOKEN_FILENAME = "api-secret.txt"

# Methods that don't mutate state — Origin check bypassed (except on WS upgrade,
# which uses GET at the HTTP layer but IS state-changing at the protocol level).
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Accepted hostnames for Host header (any port) and Origin parsing.
# Issue #33: ``"::1"`` is the IPv6 loopback address. The Host-header parser
# in ``OriginHostMiddleware`` strips the surrounding ``[...]`` so the
# membership check sees ``::1`` (not ``[::1]``) — see ``_extract_hostname``.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _extract_hostname(host_header: str) -> str:
    """Extract the hostname (without port) from a ``Host`` header value.

    Handles three shapes:
    - ``localhost`` → ``localhost`` (no port)
    - ``127.0.0.1:4317`` → ``127.0.0.1`` (IPv4 with port)
    - ``[::1]:4317`` → ``::1`` (IPv6 with port; brackets stripped)
    - ``[::1]`` → ``::1`` (IPv6 without port)

    Returns the empty string for an empty input. The naive ``split(":", 1)``
    that previously sufficed for IPv4 returns ``"["`` for the bracketed
    IPv6 form — issue #33 fixes this so the membership check against
    ``_LOOPBACK_HOSTS`` matches for IPv6 callers too.
    """
    if not host_header:
        return ""
    if host_header.startswith("["):
        end = host_header.find("]")
        if end == -1:
            # Malformed — return empty so the check fails.
            return ""
        return host_header[1:end]
    return host_header.split(":", 1)[0]


def generate_token() -> str:
    """Return a fresh 32-byte (256-bit) hex token. Rotation-safe."""
    return secrets.token_hex(32)


def _token_path(vault_root: Path) -> Path:
    return vault_root / ".brain" / "run" / _TOKEN_FILENAME


def write_token_file(vault_root: Path, token: str) -> Path:
    """Write ``token`` to ``<vault>/.brain/run/api-secret.txt`` with mode 0600.

    POSIX: atomic-ish via ``os.open(..., O_CREAT | O_WRONLY | O_TRUNC, 0o600)``
    so the file is created with 0o600 before any bytes are written. A trailing
    ``os.chmod(path, 0o600)`` forces the mode even when the file already
    existed (O_CREAT without O_EXCL leaves pre-existing permissions intact).

    Windows: fall back to ``pathlib.Path.write_text`` + best-effort
    ``os.chmod(..., 0o600)``. Windows ``chmod`` only toggles the read-only
    bit — the real defense is NTFS ACLs via ``pywin32``, which Plan 05
    deliberately does NOT introduce as a new dep. See
    ``docs/testing/cross-platform.md`` for the threat-model discussion.
    """
    path = _token_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        # Windows: plain write + best-effort chmod.
        path.write_text(token + "\n", encoding="utf-8", newline="\n")
        # TODO(Windows ACL): pywin32 SetFileSecurityA for real lockdown.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)
    else:
        # POSIX: atomic create-with-mode. O_CREAT | O_TRUNC wipes any prior
        # contents; the mode argument applies only when the file is freshly
        # created, so we follow up with an explicit chmod for the overwrite
        # case.
        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        fd = os.open(str(path), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(token + "\n")
        os.chmod(path, 0o600)

    return path


def read_token_file(vault_root: Path) -> str | None:
    """Return the token from ``<vault>/.brain/run/api-secret.txt``, or None if missing."""
    path = _token_path(vault_root)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _is_loopback_origin(origin: str) -> bool:
    """Return True when ``origin`` is ``http(s)://localhost`` or ``http(s)://127.0.0.1``.

    Any port is accepted. Any other hostname — including public IPs that
    happen to resolve to loopback via a rebinding DNS attack — is rejected.
    """
    parsed = urlparse(origin)
    return parsed.hostname in _LOOPBACK_HOSTS


def _header_value(scope: Scope, name: str) -> str:
    """Return the raw value of header ``name`` from an ASGI scope, or ``""``.

    ASGI delivers headers as a list of ``(name_bytes, value_bytes)``
    tuples with lowercased names. We compare bytes to avoid a per-scope
    decode of every header.
    """
    needle = name.encode("latin-1").lower()
    for key, value in scope.get("headers", []):
        if key == needle:
            return value.decode("latin-1")
    return ""


class OriginHostMiddleware:
    """Reject non-loopback ``Host`` and cross-origin state-changing requests.

    Defends against two distinct attacks on the local-only API:

    1. **DNS rebinding.** An attacker lures the user to ``evil.example``;
       the attacker's DNS flips ``evil.example`` to ``127.0.0.1`` after the
       page loads. The browser keeps the original page's ``Origin`` but now
       sends requests (with ``Host: evil.example``) to the local API. We
       reject any non-loopback ``Host`` value to break this attack.

    2. **Cross-origin CSRF.** A malicious page on ``evil.example`` POSTs to
       ``http://localhost:4317/api/tools/...``. The browser includes the
       attacker's cookies/credentials but also an ``Origin`` header naming
       the attacker's site. We reject any non-loopback ``Origin`` on state-
       changing methods (and on WebSocket upgrades, which share the CSRF
       shape via the handshake GET).

    Implemented as a pure ASGI middleware (rather than
    :class:`starlette.middleware.base.BaseHTTPMiddleware`) so it runs on
    BOTH ``http`` and ``websocket`` scopes. ``BaseHTTPMiddleware`` short-
    circuits non-http scopes, which would silently skip WebSocket
    upgrades — a real CSRF hole. On an ``http`` refusal we send a 403
    JSON envelope; on a ``websocket`` refusal we send ``websocket.close``
    with code 1008 (Policy Violation) and reason ``refused``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")
        if scope_type not in ("http", "websocket"):
            # lifespan and other ASGI scopes pass straight through.
            await self.app(scope, receive, send)
            return

        # --- Host header check (always) ---------------------------------
        host = _header_value(scope, "host")
        hostname = _extract_hostname(host)
        if hostname not in _LOOPBACK_HOSTS:
            await _send_refusal(
                scope_type,
                send,
                message=f"host {host!r} is not a loopback address",
            )
            return

        # --- Origin header check -----------------------------------------
        # HTTP: check on state-changing methods. WebSocket: always check —
        # the handshake IS the state-changing request for CSRF purposes,
        # and the ASGI scope doesn't carry an Upgrade header on the
        # websocket scope (starlette has already parsed it).
        origin = _header_value(scope, "origin")
        needs_origin_check = scope_type == "websocket" or (
            scope_type == "http" and scope.get("method", "GET") not in _SAFE_METHODS
        )

        if needs_origin_check and origin and not _is_loopback_origin(origin):
            await _send_refusal(
                scope_type,
                send,
                message=f"origin {origin!r} is not a loopback address",
            )
            return

        await self.app(scope, receive, send)


class RequestIDMiddleware:
    """Stamp every HTTP request with a request_id and echo it back as ``X-Request-ID``.

    Issue #32. The 500 catch-all handler reads ``request.state.request_id``
    and surfaces it under ``detail.request_id`` so the frontend error
    boundary can show it to the user — and the matching server log line
    (``Unhandled exception ... (request_id=...)``) becomes joinable.

    Honors a caller-supplied ``X-Request-ID`` header if present (for
    distributed-trace propagation). Otherwise generates a fresh UUID4 hex.

    Pure ASGI middleware so it runs on both ``http`` and ``websocket``
    scopes (mirrors :class:`OriginHostMiddleware`). The id is attached to
    ``scope["state"]["request_id"]`` so FastAPI's ``request.state.request_id``
    sees it; the response wrapper injects the ``X-Request-ID`` header into
    the outgoing ``http.response.start`` message.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")
        if scope_type not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Honor an upstream-supplied ID; otherwise mint a fresh one. UUID4
        # hex (no dashes) keeps the header short and easy to copy.
        request_id = _header_value(scope, "x-request-id") or _new_request_id()
        scope.setdefault("state", {})["request_id"] = request_id

        if scope_type == "websocket":
            # WS doesn't have a single response we can stamp; the id is
            # available via scope state for any handler that wants it.
            await self.app(scope, receive, send)
            return

        # Wrap the send callable to inject X-Request-ID on the response
        # start. Match casing already used by other custom headers in this
        # codebase (lowercase bytes, per ASGI spec; HTTP/2 normalizes).
        # Type matches starlette's ``Send`` exactly:
        # ``Callable[[MutableMapping[str, Any]], Awaitable[None]]``.
        from collections.abc import MutableMapping
        from typing import Any

        async def send_with_request_id(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers_obj = message.get("headers")
                headers = list(headers_obj) if isinstance(headers_obj, list) else []
                # Drop any caller-supplied X-Request-ID so we always emit
                # the canonical (middleware-set) value exactly once.
                headers = [
                    (k, v)
                    for (k, v) in headers
                    if isinstance(k, (bytes, bytearray)) and k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def _new_request_id() -> str:
    """Return a fresh request-id (UUID4 hex, 32 chars, no dashes)."""
    import uuid

    return uuid.uuid4().hex


async def _send_refusal(scope_type: str, send: Send, *, message: str) -> None:
    """Emit a 403 JSON envelope for HTTP or a 1008 close frame for WebSocket.

    Plan 05 Task 25 aligned the HTTP envelope with the global error handler
    in :mod:`brain_api.errors` — every 4xx/5xx response now carries
    ``{"error", "message", "detail"}`` with ``detail = null`` when there's
    no structured payload. Frontend error boundaries parse a single shape
    regardless of whether the refusal came from a middleware short-circuit
    or a route-level ``ApiError``.

    WebSocket clients cannot receive a JSON body before accept, so we encode
    the same message in the ``reason`` field of the close frame (truncated
    to 123 bytes per RFC 6455 §5.5.1).
    """
    if scope_type == "http":
        body = json.dumps({"error": "refused", "message": message, "detail": None}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
    else:  # websocket
        # Close frame reason is UTF-8, max 123 bytes (125 - 2 for code).
        reason = message.encode("utf-8")[:123].decode("utf-8", errors="ignore")
        await send({"type": "websocket.close", "code": 1008, "reason": reason})


def require_token(
    request: Request,
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI evaluates Depends lazily per request
) -> None:
    """FastAPI dependency — require a matching ``X-Brain-Token`` header.

    Compares the request's ``X-Brain-Token`` header against ``ctx.token``
    in constant time via :func:`secrets.compare_digest`. Raises
    :class:`brain_api.errors.ApiError` 403 on missing or mismatched token;
    the global handler renders it as a flat ``{"error", "message", "detail"}``
    envelope.

    Attach to write endpoints with
    ``dependencies=[Depends(require_token)]``. Task 10 wires it onto
    ``POST /api/tools/{name}``; the liveness probe and the tool listing
    endpoint remain unauthenticated.
    """
    received = request.headers.get("x-brain-token", "")
    expected = ctx.token or ""

    if not received or not expected or not secrets.compare_digest(received, expected):
        raise ApiError(
            status=403,
            code="refused",
            message="missing or invalid X-Brain-Token header",
        )


def enforce_json_accept(request: Request) -> None:
    """FastAPI dependency — reject ``Accept`` headers that exclude ``application/json``.

    Attach to write endpoints with ``dependencies=[Depends(enforce_json_accept), ...]``
    BEFORE :func:`require_token` so callers get a tighter error code (406 vs 403)
    when the real bug is content negotiation rather than auth.

    Acceptance policy:

    - Missing ``Accept`` (curl default): **allowed** — treated as ``*/*``.
    - ``*/*`` or ``application/*`` wildcards: **allowed**.
    - ``application/json`` (optionally alongside other types): **allowed**.
    - Anything else (``text/html``, ``application/xml``, ...): **rejected** with 406.

    The check uses a simple ``in`` test rather than an RFC 7231 Accept parser:
    we only need to reject explicitly narrow clients, not do weighted negotiation.
    Missing Accept is treated as ``*/*`` per RFC 7231 §5.3.2 and per every HTTP
    client's default behavior.

    Raises :class:`brain_api.errors.ApiError` 406 on a narrow non-JSON Accept;
    the global handler renders it as a flat ``{"error", "message", "detail"}``
    envelope.
    """
    accept = request.headers.get("accept", "")
    if not accept:
        return
    accept_lc = accept.lower()
    if "application/json" in accept_lc or "*/*" in accept_lc or "application/*" in accept_lc:
        return
    raise ApiError(
        status=406,
        code="not_acceptable",
        message="this API speaks only application/json",
    )


async def check_ws_token(websocket: WebSocket, ctx: AppContext) -> bool:
    """Validate the ``?token=<hex>`` query param on a WebSocket handshake.

    Returns ``True`` when the token matches ``ctx.token`` in constant time.
    Otherwise closes the socket with code ``1008`` (Policy Violation, RFC 6455)
    + reason ``"invalid token"`` and returns ``False``. **The caller MUST
    ``return`` on a ``False`` result — the socket is already closed and any
    subsequent ``accept`` / ``send`` / ``receive`` will raise.**

    Token lives in the query string (not a header) because browsers cannot
    reliably attach custom headers to a ``WebSocket`` constructor; the
    ``?token=...`` convention matches VSCode / Jupyter's localhost WS auth.
    """
    received = websocket.query_params.get("token", "")
    expected = ctx.token or ""

    if not received or not expected or not secrets.compare_digest(received, expected):
        await websocket.close(code=1008, reason="invalid token")
        return False

    return True
