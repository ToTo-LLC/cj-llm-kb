"""brain_api auth primitives — token generation, filesystem IO, middleware.

Task 7 lands the token-file primitives. Task 8 adds Origin/Host middleware;
Task 9 adds the FastAPI dependency that enforces X-Brain-Token on write routes.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from brain_api.context import AppContext, get_ctx

_TOKEN_FILENAME = "api-secret.txt"

# Methods that don't mutate state — Origin check bypassed (except on WS upgrade,
# which uses GET at the HTTP layer but IS state-changing at the protocol level).
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Accepted hostnames for Host header (any port) and Origin parsing.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1"})


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


class OriginHostMiddleware(BaseHTTPMiddleware):
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

    Runs at the ASGI layer, so both HTTP and WebSocket connections go
    through it. Safe methods (GET/HEAD/OPTIONS) bypass the Origin check
    unless the request is a WebSocket upgrade handshake.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # --- Host header check (always) ---------------------------------
        host = request.headers.get("host", "")
        hostname = host.split(":", 1)[0] if host else ""
        if hostname not in _LOOPBACK_HOSTS:
            return JSONResponse(
                {
                    "error": "refused",
                    "message": f"host {host!r} is not a loopback address",
                },
                status_code=403,
            )

        # --- Origin header check (state-changing methods + WS upgrades) --
        # WebSocket handshakes are GET at the HTTP layer but carry
        # ``Upgrade: websocket``; treat them as state-changing for CSRF
        # purposes.
        is_ws_upgrade = "websocket" in request.headers.get("upgrade", "").lower()
        is_state_changing = request.method not in _SAFE_METHODS

        if is_state_changing or is_ws_upgrade:
            origin = request.headers.get("origin")
            if origin is not None and not _is_loopback_origin(origin):
                return JSONResponse(
                    {
                        "error": "refused",
                        "message": f"origin {origin!r} is not a loopback address",
                    },
                    status_code=403,
                )

        return await call_next(request)


def require_token(
    request: Request,
    ctx: AppContext = Depends(get_ctx),  # noqa: B008 — FastAPI evaluates Depends lazily per request
) -> None:
    """FastAPI dependency — require a matching ``X-Brain-Token`` header.

    Compares the request's ``X-Brain-Token`` header against ``ctx.token``
    in constant time via :func:`secrets.compare_digest`. Raises
    :class:`HTTPException` 403 on missing or mismatched token.

    Attach to write endpoints with
    ``dependencies=[Depends(require_token)]``. Task 10 wires it onto
    ``POST /api/tools/{name}``; the liveness probe and the tool listing
    endpoint remain unauthenticated.

    Note: the 403 body is currently ``{"detail": {"error": ..., "message": ...}}``
    because FastAPI wraps :class:`HTTPException` ``detail`` under a top-level
    ``detail`` key. Plan 05 Task 15 flattens this via a project-wide exception
    handler / ``ApiError`` so the envelope matches ``{"error", "message"}``
    everywhere.
    """
    received = request.headers.get("x-brain-token", "")
    expected = ctx.token or ""

    if not received or not expected or not secrets.compare_digest(received, expected):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "refused",
                "message": "missing or invalid X-Brain-Token header",
            },
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
