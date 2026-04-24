"""End-to-end error surface tests — Task 16.

Every one of the eight exception types mapped by
:func:`brain_api.errors.register_error_handlers` is driven here through a real
``POST /api/tools/<name>`` request that triggers the underlying handler to
raise. No synthetic ``/_boom`` routes — those live in ``test_errors.py`` and
exist to spot-check the handlers in isolation. Task 16 pins the whole request
path end-to-end: middleware + Accept negotiation + token auth + Pydantic
validation + tool dispatch + exception handler + flat envelope rendering.

Also pins the OpenAPI shape: every error code declared on the dispatcher's
``responses`` kwarg must appear in ``/openapi.json`` so ``/docs`` renders the
error surface symmetrically.

Frozen-dataclass mutation: :class:`brain_core.tools.base.ToolContext` is a
``frozen=True`` dataclass, so swapping ``rate_limiter`` in place requires
``object.__setattr__``. This matches the pattern used by Plan 04's brain_mcp
rate-limit tests and keeps the test free of mocking the entire tool context.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# ApiClient fixture — mirrors the shape in test_tool_endpoints.py so the error
# tests exercise the same real transport path as the happy tests.
# ---------------------------------------------------------------------------


class ApiClient:
    """TestClient wrapper that auto-attaches Origin + X-Brain-Token on every POST."""

    def __init__(
        self,
        base: TestClient,
        token: str,
        origin: str = "http://localhost:4317",
    ) -> None:
        self._base = base
        self._headers = {"Origin": origin, "X-Brain-Token": token}

    def call(self, name: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self._base.post(
            f"/api/tools/{name}",
            json=body or {},
            headers=self._headers,
        )


@pytest.fixture
def api(app: FastAPI):
    """Lifespan-active ApiClient — mint the token inside ``TestClient`` context."""
    with TestClient(app, base_url="http://localhost") as base:
        token = app.state.ctx.token
        assert token is not None, "lifespan must mint a token"
        yield ApiClient(base, token=token)


# ---------------------------------------------------------------------------
# Per-exception integration tests. Each drives a REAL tool to trigger the
# mapped exception; asserts status code + flat-envelope fields.
# ---------------------------------------------------------------------------


def test_scope_error_403(api: ApiClient) -> None:
    """Reading a ``personal/`` path from a research-scoped app → 403 ``scope``.

    ``brain_read_note`` runs ``scope_guard_path`` before any I/O; the
    ``personal`` domain is not in ``allowed_domains=("research",)`` so the
    guard raises :class:`brain_core.vault.paths.ScopeError`. The handler maps
    that to 403 with ``error == "scope"`` at the top level.
    """
    r = api.call("brain_read_note", {"path": "personal/notes/secret.md"})
    assert r.status_code == 403
    assert r.json()["error"] == "scope"


def test_file_not_found_404(api: ApiClient) -> None:
    """Reading a missing in-scope note → 404 ``not_found``.

    Scope check passes for ``research/`` but the target file doesn't exist;
    ``brain_read_note`` raises ``FileNotFoundError`` which maps to 404.
    """
    r = api.call(
        "brain_read_note",
        {"path": "research/notes/does-not-exist.md"},
    )
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


def test_missing_key_404(api: ApiClient) -> None:
    """Unknown patch_id → 404 ``not_found`` via the KeyError mapping.

    ``brain_apply_patch`` raises ``KeyError(f"patch {patch_id!r} not found")``
    which the handler surfaces as 404. The raw ``args[0]`` message is used
    (not the quoted-repr default), so the response message is informative.
    """
    r = api.call("brain_apply_patch", {"patch_id": "not-a-real-patch"})
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


def test_invalid_input_400(api: ApiClient) -> None:
    """Missing required fields → 400 ``invalid_input`` with field-level errors.

    ``brain_propose_note`` requires ``path``, ``content``, ``reason``; we send
    only ``path``. Task 11's Pydantic validation runs before the handler and
    raises :class:`pydantic.ValidationError`, which the handler surfaces as
    400 with the canonical ``errors()`` list under ``detail.errors``.
    """
    r = api.call("brain_propose_note", {"path": "research/notes/x.md"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "invalid_input"
    assert "errors" in body["detail"]
    assert isinstance(body["detail"]["errors"], list)
    assert body["detail"]["errors"], "errors list must not be empty"


def test_permission_error_403(api: ApiClient) -> None:
    """Reading a secret-shaped config key → 403 ``refused``.

    ``brain_config_get`` checks the key against ``_SECRET_SUBSTRINGS`` BEFORE
    any dict traversal — ``llm.api_key`` contains ``api_key`` and triggers
    ``PermissionError("refusing to expose secret-like key ...")``. The handler
    maps to 403 with ``error == "refused"`` (not "scope" — ScopeError is
    registered first and is more specific; a bare PermissionError falls
    through to the refused branch).
    """
    r = api.call("brain_config_get", {"key": "llm.api_key"})
    assert r.status_code == 403
    assert r.json()["error"] == "refused"


def test_rate_limit_429(api: ApiClient, app: FastAPI) -> None:
    """Propose-note into a drained rate-limit bucket → 429 + Retry-After.

    The tool_ctx is a frozen dataclass, so we mutate ``rate_limiter`` via
    ``object.__setattr__`` (same pattern Plan 04's brain_mcp tests use). A
    fresh RateLimiter sized at 1 patch/min is drained to zero before the
    request; the handler's first ``rate_limiter.check("patches", cost=1)``
    call raises :class:`RateLimitError`, which maps to 429 with
    ``detail.bucket == "patches"`` and a ``Retry-After`` integer header.
    """
    from brain_core.rate_limit import RateLimitConfig, RateLimiter

    drained = RateLimiter(RateLimitConfig(patches_per_minute=1))
    drained.check("patches", cost=1)  # drain the bucket
    # ToolContext is frozen; swap the limiter via object.__setattr__.
    object.__setattr__(app.state.ctx.tool_ctx, "rate_limiter", drained)

    r = api.call(
        "brain_propose_note",
        {"path": "research/notes/x.md", "content": "x", "reason": "x"},
    )
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "rate_limited"
    assert body["detail"]["bucket"] == "patches"
    # ``Retry-After`` is an integer count of seconds — header semantics.
    assert r.headers["retry-after"].isdigit()


def test_validation_error_has_field_paths(api: ApiClient) -> None:
    """400 validation errors carry Pydantic's ``loc`` field paths.

    ``brain_search.INPUT_SCHEMA`` types ``top_k`` as integer; passing a string
    triggers Pydantic's ``int_parsing`` error. The canonical errors list
    includes ``"loc": ["top_k"]`` (tuple → list in the JSON response) so
    clients can render the exact field that failed. Check handles both tuple
    (in-process) and list (post-JSON) so the assertion is transport-agnostic.
    """
    r = api.call("brain_search", {"query": "x", "top_k": "not-an-int"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "invalid_input"
    errors = body["detail"]["errors"]
    assert any("top_k" in e.get("loc", []) for e in errors), (
        f"expected top_k in some error's loc; got {errors!r}"
    )


def test_unhandled_exception_500(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unmapped exception → 500 with generic body; no traceback / secret leak.

    Monkeypatch ``brain_core.tools.list_domains.handle`` to raise a
    ``RuntimeError`` carrying a secret-looking message. The response must be
    the static ``{"error": "internal", "message": "unexpected error"}``
    envelope — CLAUDE.md principle #10 forbids leaking exception type or args
    in the response body. The traceback goes to the ``brain_api.errors``
    logger, not the wire.

    Takes ``app`` directly (rather than the ``api`` fixture) so we can build
    our own TestClient with ``raise_server_exceptions=False``. TestClient's
    default re-raises any 500 past the registered handler, which would fail
    the test even though the handler produced the correct response; flipping
    it off lets the client return the actual 500 body.
    """
    from brain_core.tools import list_domains as ld_mod

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("secret-looking internal detail XYZ")

    monkeypatch.setattr(ld_mod, "handle", boom)

    with TestClient(
        app,
        base_url="http://localhost",
        raise_server_exceptions=False,
    ) as fresh:
        token = app.state.ctx.token
        assert token is not None
        response = fresh.post(
            "/api/tools/brain_list_domains",
            json={},
            headers={"Origin": "http://localhost:4317", "X-Brain-Token": token},
        )
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal"
    assert body["message"] == "unexpected error"
    # No traceback leakage — the secret message and exception type name are
    # never rendered into the response body.
    rendered = response.text
    assert "XYZ" not in rendered
    assert "RuntimeError" not in rendered

    # Issue #32: 500 body carries request_id under detail; X-Request-ID echoes
    # it back. The two values must be the same string so the user-visible id
    # matches the server log line.
    detail = body["detail"]
    assert isinstance(detail, dict)
    request_id = detail["request_id"]
    assert isinstance(request_id, str) and len(request_id) >= 16, (
        f"request_id should be a non-trivial string; got {request_id!r}"
    )
    assert response.headers.get("x-request-id") == request_id


def test_request_id_header_set_on_success_responses(api: ApiClient) -> None:
    """Issue #32: every successful response also carries X-Request-ID.

    The id is generated by RequestIDMiddleware regardless of route outcome —
    even successful 200s get one so callers can correlate any request with
    server logs (not just 500s).
    """
    response = api._base.get("/healthz")
    assert response.status_code == 200
    rid = response.headers.get("x-request-id")
    assert isinstance(rid, str) and len(rid) >= 16


def test_request_id_honors_caller_supplied_header(api: ApiClient) -> None:
    """Issue #32: an upstream-supplied X-Request-ID is preserved end-to-end.

    Lets callers propagate a trace id from a frontend or test harness so
    the server log + frontend error UI share the same string.
    """
    response = api._base.get("/healthz", headers={"X-Request-ID": "trace-abc-123"})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "trace-abc-123"


# ---------------------------------------------------------------------------
# OpenAPI shape tests — every error code the routes document must appear in
# the generated spec so ``/docs`` renders the full error surface.
# ---------------------------------------------------------------------------


def test_openapi_dispatcher_advertises_all_error_codes(client: TestClient) -> None:
    """``POST /api/tools/{name}`` advertises 400/403/404/406/429/500 in OpenAPI.

    The ``responses`` kwarg on the route becomes the ``responses`` object in
    the OpenAPI operation. Clients reading ``/openapi.json`` (or ``/docs``)
    must see every error shape brain_api can produce on this endpoint —
    anything missing means a type of failure the caller can't plan for.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    op = schema["paths"]["/api/tools/{name}"]["post"]
    declared = set(op["responses"].keys())
    assert {"400", "403", "404", "406", "429", "500"}.issubset(declared), (
        f"missing error codes on POST dispatcher: {declared!r}"
    )


def test_openapi_readonly_endpoints_advertise_500(client: TestClient) -> None:
    """Read-only endpoints (GET /api/tools, GET /healthz) advertise 500.

    Rate-limit / scope / validation can't fire on these endpoints — only the
    catch-all 500 is possible. Declaring it keeps ``/docs`` symmetric.
    """
    response = client.get("/openapi.json")
    schema = response.json()
    listing = schema["paths"]["/api/tools"]["get"]
    health = schema["paths"]["/healthz"]["get"]
    assert "500" in listing["responses"]
    assert "500" in health["responses"]
