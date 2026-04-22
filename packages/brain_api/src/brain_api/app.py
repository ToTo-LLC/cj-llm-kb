"""FastAPI app factory.

Task 1 lands the skeleton — create_app returns a FastAPI instance with
/healthz wired and an empty lifespan stub. Tasks 2+ populate AppContext;
Tasks 10+ register the tool dispatcher.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI

from brain_api.auth import OriginHostMiddleware
from brain_api.context import build_app_context
from brain_api.endpoints import setup_status as setup_status_endpoint
from brain_api.endpoints import token as token_endpoint
from brain_api.endpoints import upload as upload_endpoint
from brain_api.errors import register_error_handlers
from brain_api.routes import chat as chat_routes
from brain_api.routes import health
from brain_api.routes import tools as tools_routes
from brain_api.schema import build_model_from_schema
from brain_api.static_ui import SPAStaticFiles, resolve_out_dir

try:
    _VERSION = version("brain_api")
except PackageNotFoundError:  # pragma: no cover — fallback for source tree w/o metadata
    _VERSION = "0.0.0"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build AppContext at startup; hold it open for the app's lifetime.

    Task 7 adds the token-rotation step: generate (or honor the
    ``token_override`` injected by tests), write to
    ``<vault>/.brain/run/api-secret.txt`` with mode 0600, and stash on
    ``ctx.token`` so Task 9's ``require_token`` dependency can read it back.

    Reads the constructor args stashed on app.state by ``create_app``, builds
    the full ctx (StateDB, VaultWriter, retrieval, cost ledger, rate limiter,
    embedded ToolContext, etc.), and stashes the result on ``app.state.ctx``.
    FastAPI routes read it back via ``Depends(get_ctx)``.
    """
    from brain_api.auth import generate_token, write_token_file

    token = app.state.token_override or generate_token()
    write_token_file(app.state.vault_root, token)

    ctx = build_app_context(
        vault_root=app.state.vault_root,
        allowed_domains=app.state.allowed_domains,
        token=token,
    )
    app.state.ctx = ctx

    # Task 11: build one Pydantic model per tool INPUT_SCHEMA so the dispatcher
    # can validate request bodies at the edge. Any unsupported schema feature
    # raises ``UnsupportedSchemaError`` HERE (at boot), not on the first
    # request — fail-loud is correct for a tool-author bug.
    app.state.tool_models = {
        name: build_model_from_schema(name, module.INPUT_SCHEMA)
        for name, module in ctx.tool_by_name.items()
    }

    try:
        yield
    finally:
        # Close any resources needing explicit teardown (future-proof hook —
        # current primitives all clean up via GC).
        pass


def create_app(
    vault_root: Path,
    allowed_domains: tuple[str, ...] = ("research",),
    *,
    token_override: str | None = None,
) -> FastAPI:
    """Build a fresh FastAPI app bound to the given vault.

    Task 1 lands the skeleton; Tasks 2+ wire AppContext, auth, and routes.

    Args:
        vault_root: Absolute path to the brain vault (e.g. ~/Documents/brain).
        allowed_domains: Tuple of domain names this app instance may access.
        token_override: Task 7 uses this to inject a fixed token for tests.
            None (the default) means generate a fresh token at startup.
    """
    app = FastAPI(
        title="brain API",
        version=_VERSION,
        description="Local REST + WebSocket backend for the brain personal knowledge base.",
        lifespan=_lifespan,
    )
    # Stash for later tasks to read during lifespan.
    app.state.vault_root = vault_root
    app.state.allowed_domains = allowed_domains
    app.state.token_override = token_override

    # Install OriginHostMiddleware FIRST so it wraps every subsequent
    # middleware and router. Starlette applies middleware in reverse of
    # ``add_middleware`` order, meaning the first-added runs outermost —
    # exactly what we want for a guard that short-circuits bad requests
    # before any downstream processing (logging, exception handlers,
    # auth deps, route dispatch) ever sees them.
    app.add_middleware(OriginHostMiddleware)

    app.include_router(health.router)
    app.include_router(tools_routes.router)
    app.include_router(chat_routes.router)
    # Plan 08 Task 1: self-service endpoints the SPA calls before it has a
    # token + during its own startup handshake. Included BEFORE the static
    # mount so ``/api/*`` never falls through to the SPA index.html.
    app.include_router(setup_status_endpoint.router)
    app.include_router(token_endpoint.router)
    app.include_router(upload_endpoint.router)

    # Task 15: project-wide exception handlers (D7a mapping). Installed AFTER
    # router include so the handlers wrap every endpoint's exceptions — middleware
    # (which sits outside routing) remains responsible for its own 403 envelope.
    register_error_handlers(app)

    # Plan 08 Task 1: serve the Next.js static export under ``/`` LAST so
    # every API + WS route takes precedence. :class:`SPAStaticFiles` falls
    # back to ``index.html`` for non-reserved 404s (SPA client routes).
    #
    # The resolver raises if no candidate directory contains an index.html.
    # Production (the install script sets ``BRAIN_INSTALL_DIR``) + static-UI
    # tests (set ``BRAIN_WEB_OUT_DIR``) always resolve; headless API tests
    # that never touch the UI should stay bootable, so we catch the error
    # and leave the mount off. A deploy with missing UI content surfaces as
    # ``GET /`` 404 at first browser load — visibly broken, not silently.
    try:
        out_dir = resolve_out_dir()
        app.mount("/", SPAStaticFiles(directory=str(out_dir), html=True), name="ui")
    except RuntimeError:
        # API-only mode (CI, contract tests, headless). Intentional no-op.
        pass

    return app
