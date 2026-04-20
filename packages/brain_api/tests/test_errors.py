"""Tests for global exception handlers in :mod:`brain_api.errors` — Task 15.

Each test mounts a synthetic ``GET /_boom`` route that raises the target
exception, then asserts the handler produces the D7a-mapped status + flat
envelope. The synthetic route goes on the shared ``app`` fixture from
``conftest.py``, which has the handlers already registered via
:func:`brain_api.app.create_app`.

The ``TestClient`` default ``raise_server_exceptions=True`` is correct here:
the whole point of Task 15 is that domain exceptions are caught by the
registered handlers *before* they can bubble to Starlette's server-error
middleware, so the TestClient's per-request shield never trips.
"""

from __future__ import annotations

from collections.abc import Callable

from brain_api.errors import ApiError
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _attach_failing_route(app: FastAPI, exc_factory: Callable[[], BaseException]) -> None:
    """Mount a synthetic ``GET /_boom`` that raises ``exc_factory()`` on request.

    Defined inline per-test so each test gets a fresh registration on the
    shared ``app`` fixture. TestClient re-entry picks up the new route.
    """

    @app.get("/_boom")
    async def boom() -> dict[str, str]:
        raise exc_factory()


def test_scope_error_maps_to_403(app: FastAPI) -> None:
    from brain_core.vault.paths import ScopeError

    _attach_failing_route(app, lambda: ScopeError("domain 'personal' is out of scope"))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "scope"
    assert "personal" in body["message"]


def test_file_not_found_maps_to_404(app: FastAPI) -> None:
    _attach_failing_route(app, lambda: FileNotFoundError("note 'x' not found"))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_key_error_maps_to_404(app: FastAPI) -> None:
    """KeyError surfaces the raw arg, not the quoted-repr ``"'arg'"``."""
    _attach_failing_route(app, lambda: KeyError("patch_id 'abc' not in store"))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    # The message is the raw arg ("patch_id 'abc' not in store"), not
    # KeyError's default str() form ("\"patch_id 'abc' not in store\"").
    assert body["message"] == "patch_id 'abc' not in store"


def test_value_error_maps_to_400(app: FastAPI) -> None:
    _attach_failing_route(app, lambda: ValueError("path must be vault-relative"))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_input"


def test_permission_error_maps_to_403(app: FastAPI) -> None:
    """PermissionError → 403 ``refused``.

    ScopeError subclasses PermissionError but is registered first, so the
    more-specific handler wins for ScopeError; a bare PermissionError falls
    through to this handler.
    """
    _attach_failing_route(app, lambda: PermissionError("refusing to expose secret key"))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 403
    assert response.json()["error"] == "refused"


def test_rate_limit_error_maps_to_429_with_header(app: FastAPI) -> None:
    """RateLimitError → 429 + ``Retry-After`` header per HTTP convention."""
    from brain_core.rate_limit import RateLimitError

    _attach_failing_route(app, lambda: RateLimitError(bucket="patches", retry_after_seconds=42))
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
    body = response.json()
    assert body["error"] == "rate_limited"
    assert body["detail"]["bucket"] == "patches"
    assert body["detail"]["retry_after_seconds"] == 42


def test_uncaught_exception_maps_to_500_no_traceback(app: FastAPI) -> None:
    """Bare Exception → 500 with a generic body — no exception type/args leak.

    CLAUDE.md principle #10: 500 responses never expose traceback info to
    callers. The logger gets the full traceback server-side.
    """
    _attach_failing_route(app, lambda: RuntimeError("internal wiring blew up"))
    with TestClient(app, base_url="http://localhost", raise_server_exceptions=False) as c:
        response = c.get("/_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal"
    assert body["message"] == "unexpected error"
    # Verify no traceback leakage: the exception type name and the arg text
    # must not appear anywhere in the serialized body.
    rendered = response.text
    assert "RuntimeError" not in rendered
    assert "internal wiring" not in rendered


def test_api_error_renders_flat(app: FastAPI) -> None:
    """ApiError renders directly — no double-wrap under ``detail``."""
    _attach_failing_route(
        app,
        lambda: ApiError(status=418, code="teapot", message="I'm a teapot"),
    )
    with TestClient(app, base_url="http://localhost") as c:
        response = c.get("/_boom")
    assert response.status_code == 418
    body = response.json()
    # Flat envelope — exactly three keys, no nested ``detail`` wrap.
    assert body == {"error": "teapot", "message": "I'm a teapot", "detail": None}
