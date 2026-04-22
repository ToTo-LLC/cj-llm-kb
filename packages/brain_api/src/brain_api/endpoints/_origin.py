"""Endpoint-level Origin check helper — Plan 08 Task 1.

The shared :class:`brain_api.auth.OriginHostMiddleware` only enforces Origin on
state-changing methods (POST/PUT/DELETE) + WebSocket handshakes; GET is exempt
at the middleware layer because safe methods don't cause CSRF damage. The
Plan 08 endpoints (``/api/setup-status``, ``/api/token``, ``/api/upload``)
carry information a malicious cross-origin page should not be able to read
(setup state, app secret) even over a safe method — so we layer an explicit
endpoint-level Origin check on top of the middleware.

Policy:
- Missing Origin header: **allowed** (server-to-server / curl).
- Loopback Origin (``http(s)://localhost`` or ``http(s)://127.0.0.1``, any port):
  **allowed**.
- Any other Origin: rejected with :class:`brain_api.errors.ApiError` 403
  ``refused``, which the global handler renders as the flat envelope.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

from brain_api.errors import ApiError

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1"})


def require_loopback_origin(request: Request) -> None:
    """FastAPI dependency — 403 any non-loopback Origin, including on GET.

    Missing Origin is allowed (common for curl / server-to-server calls; the
    threat model this guards against is a browser tab on another site making a
    fetch() to our loopback API, and browsers always attach Origin in that
    case).
    """
    origin = request.headers.get("origin", "")
    if not origin:
        return
    parsed = urlparse(origin)
    if parsed.hostname in _LOOPBACK_HOSTS:
        return
    raise ApiError(
        status=403,
        code="refused",
        message=f"origin {origin!r} is not a loopback address",
    )
