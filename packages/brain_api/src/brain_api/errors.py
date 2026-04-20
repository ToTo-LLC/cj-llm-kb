"""Global exception handlers for brain_api — D7a mapping.

Call :func:`register_error_handlers` once on an app instance (after middleware
install + router include) and every unhandled domain exception gets mapped to
the flat error envelope ``{"error", "message", "detail"}`` at a stable HTTP
status code:

- :class:`ApiError` → whatever the caller set (``status``, ``code``, ``message``, ``detail``)
- :class:`ScopeError` (from :mod:`brain_core.vault.paths`) → 403 ``scope``
- :class:`FileNotFoundError` → 404 ``not_found``
- :class:`KeyError` → 404 ``not_found`` (uses ``exc.args[0]`` to avoid the
  quoted-key default ``KeyError.__str__`` produces)
- :class:`ValueError` → 400 ``invalid_input``
- :class:`PermissionError` → 403 ``refused``
- :class:`RateLimitError` (from :mod:`brain_core.rate_limit`) → 429
  ``rate_limited`` with a ``Retry-After`` header
- :class:`pydantic.ValidationError` → 400 ``invalid_input`` with
  ``detail.errors`` (Pydantic's canonical ``exc.errors()`` list)
- Bare :class:`Exception` catch-all → 500 ``internal`` with a generic message;
  the full traceback goes to the ``brain_api.errors`` logger via
  ``logger.exception`` so we never leak exception type / message to the
  response body.

Per CLAUDE.md principle #10 (no traceback leakage) and principle #9 (plain
English messages + stable codes), 500 responses carry ONLY the static body
``{"error": "internal", "message": "unexpected error", "detail": null}``.

:class:`ScopeError` must be declared BEFORE :class:`PermissionError` in the
handler registry because ScopeError subclasses PermissionError; FastAPI's
handler dispatch walks the registered classes in insertion order and stops at
the first ``isinstance()`` match, so the most-specific class wins only when
it's registered first. (Contrast with Python's ``except`` chain, which walks
the clauses themselves in source order for the same reason.)
"""

from __future__ import annotations

import logging
from typing import Any

from brain_core.rate_limit import RateLimitError
from brain_core.vault.paths import ScopeError
from fastapi import FastAPI, Request
from pydantic import ValidationError
from starlette.responses import JSONResponse

logger = logging.getLogger("brain_api.errors")


class ApiError(Exception):
    """Application-level error with a flat HTTP envelope.

    Raise this from any route/dependency/tool-adapter when you want a specific
    4xx status + stable error code. The registered handler renders it as
    ``{"error": code, "message": message, "detail": detail}`` at ``status``.

    Prefer :class:`ApiError` over :class:`fastapi.HTTPException`: the latter
    wraps its body under a top-level ``detail`` key, producing the double-
    nested ``{"detail": {"error": ...}}`` shape this module was built to
    eliminate. Reserve :class:`HTTPException` for cases where you need
    FastAPI's framework-level handling (e.g. the 405 Method Not Allowed path
    FastAPI itself emits).
    """

    def __init__(
        self,
        *,
        status: int,
        code: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(f"{code}: {message}")


def _envelope(
    *,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
    status: int,
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Render the flat error envelope. Single choke point for shape consistency."""
    return JSONResponse(
        {"error": code, "message": message, "detail": detail},
        status_code=status,
        headers=extra_headers or {},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register every brain_api exception handler on ``app``.

    Call this once from :func:`brain_api.app.create_app` AFTER middleware +
    router installation. Registration order matters for subclass dispatch —
    see the module docstring for the ScopeError / PermissionError ordering
    rationale.
    """

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _envelope(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
            status=exc.status,
        )

    @app.exception_handler(ScopeError)
    async def _scope_error(request: Request, exc: ScopeError) -> JSONResponse:
        return _envelope(code="scope", message=str(exc), status=403)

    @app.exception_handler(FileNotFoundError)
    async def _not_found(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return _envelope(code="not_found", message=str(exc), status=404)

    @app.exception_handler(KeyError)
    async def _key_error(request: Request, exc: KeyError) -> JSONResponse:
        # ``KeyError.__str__`` wraps the key in repr quotes ("'patch_id'");
        # pull ``args[0]`` directly so the surfaced message is the raw key /
        # explanation the caller passed in.
        msg = exc.args[0] if exc.args else "key not found"
        return _envelope(code="not_found", message=str(msg), status=404)

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        return _envelope(code="invalid_input", message=str(exc), status=400)

    @app.exception_handler(PermissionError)
    async def _permission_error(request: Request, exc: PermissionError) -> JSONResponse:
        return _envelope(code="refused", message=str(exc), status=403)

    @app.exception_handler(RateLimitError)
    async def _rate_limit(request: Request, exc: RateLimitError) -> JSONResponse:
        return _envelope(
            code="rate_limited",
            message=str(exc),
            detail={
                "bucket": exc.bucket,
                "retry_after_seconds": exc.retry_after_seconds,
            },
            status=429,
            extra_headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(request: Request, exc: ValidationError) -> JSONResponse:
        # The ValidationError errors() list is intentionally nested under
        # ``detail.errors`` — it is structured payload, not a prose message.
        return _envelope(
            code="invalid_input",
            message="request body failed schema validation",
            detail={"errors": exc.errors()},
            status=400,
        )

    @app.exception_handler(Exception)
    async def _catch_all(request: Request, exc: Exception) -> JSONResponse:
        # Log the traceback server-side (where it belongs); return a generic
        # body so exception type / arguments never leak to callers.
        logger.exception("Unhandled exception in %s %s", request.method, request.url.path)
        return _envelope(code="internal", message="unexpected error", status=500)
