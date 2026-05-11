"""FastAPI app factory.

Task 1 lands the skeleton — create_app returns a FastAPI instance with
/healthz wired and an empty lifespan stub. Tasks 2+ populate AppContext;
Tasks 10+ register the tool dispatcher.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import structlog
from brain_core.config.hot_reload import ConfigWatcher
from brain_core.config.loader import invalidate_cache_for, resolve_config
from brain_core.llm.provider import LLMProvider
from fastapi import FastAPI

from brain_api.auth import OriginHostMiddleware, RequestIDMiddleware
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

_lifespan_logger = structlog.get_logger(__name__)


def _on_config_change(config_path: Path, app_state: Any, vault_root: Path) -> None:
    """Hot-reload callback: invalidate cache then push new Config onto AppContext.

    Called by the :class:`~brain_core.config.hot_reload.ConfigWatcher` whenever
    ``<vault>/.brain/config.json`` changes on disk.  Two things happen in order:

    1. :func:`~brain_core.config.loader.invalidate_cache_for` evicts the
       in-memory snapshot so the ``resolve_config`` call below gets a fresh read.
    2. :func:`~brain_core.config.loader.resolve_config` re-loads from disk and
       the resulting :class:`~brain_core.config.schema.Config` is written onto
       ``app_state.ctx.tool_ctx.config`` via ``object.__setattr__``.  Both
       ``AppContext`` and ``ToolContext`` are ``frozen=True`` dataclasses; the
       setattr bypass is the canonical pattern for in-place mutation without
       replacing the container object (preserving identity guarantees for callers
       that hold a reference to ``ctx`` or ``ctx.tool_ctx``).

    Failures in resolve/update are swallowed with a ``structlog.warning`` — a
    transient bad write to ``config.json`` must NOT crash the running server.
    The stale config remains in place until the next successful reload.

    Plan 16 T39.5 used the same ``object.__setattr__`` pattern for brain_mcp's
    ``_reset_ctx_cache``; this extends it to brain_api's stateful AppContext.

    Args:
        config_path: Path to ``<vault>/.brain/config.json``.
        app_state: The ``app.state`` object (holds ``.ctx``).
        vault_root: Vault root; forwarded to ``resolve_config`` as the
            ``cli_overrides["vault_path"]`` chicken-and-egg field.
    """
    invalidate_cache_for(config_path)
    try:
        new_config = resolve_config(
            config_file=config_path,
            env=os.environ,
            cli_overrides={"vault_path": vault_root},
        )
        tool_ctx = app_state.ctx.tool_ctx
        object.__setattr__(tool_ctx, "config", new_config)
        _lifespan_logger.info("config_hot_reloaded", config_path=str(config_path))
    except Exception as exc:
        _lifespan_logger.warning(
            "config_hot_reload_failed",
            error=str(exc),
            config_path=str(config_path),
        )


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

    # Plan 11 Task 7 polish: load the live Config from
    # ``<vault>/.brain/config.json`` and thread it through to ToolContext so
    # mutation tools (config_set, create_domain, rename_domain,
    # delete_domain, budget_override) can persist their changes via
    # ``save_config``. Without this, every Plan 11 mutation dispatched via
    # brain_web → brain_api would land on the ``ctx.config is None`` no-op
    # branch — the toast would say "saved" but the disk write never happens.
    #
    # ``resolve_config`` (Plan 16 T34) wraps ``load_config``'s Plan 11 D7
    # fallback chain (config.json → config.json.bak → ``Config()``
    # defaults) with a single-process cache layer. First boot is a cache
    # miss that calls ``load_config`` and populates the cache; subsequent
    # in-process callers (e.g. tool dispatchers wired via T34.5+) get
    # cache hits, and T35's ``ConfigWatcher`` (started below) invalidates
    # the cache on disk-change so post-edit reads pick up new state.
    # ``vault_path`` is supplied via ``cli_overrides`` rather than the
    # persisted blob — it's the chicken-and-egg field the loader's
    # whitelist deliberately excludes.
    config = resolve_config(
        config_file=app.state.vault_root / ".brain" / "config.json",
        env=os.environ,
        cli_overrides={"vault_path": app.state.vault_root},
    )

    # Plan 16 Task 39.5: construct a real :class:`AnthropicProvider` when
    # an API key is set in the environment. Without this, every brain_api
    # instance would default to ``FakeLLMProvider`` (the safe-for-tests
    # fallback baked into ``build_app_context``) and brain_web users would
    # get scripted fake responses in production.
    #
    # ``brain_cli`` reads ``ANTHROPIC_API_KEY`` from the env directly
    # (see ``brain_cli/session_factory.py::_build_anthropic_provider``);
    # we follow the same pattern here. ``brain start`` and the install
    # scripts surface the variable to the launched process; users running
    # ``uvicorn`` directly export it manually. Tests run without the var
    # set so they keep getting the FakeLLMProvider via ``llm=None``.
    #
    # The provider receives the resolved Config so its T31 per-domain
    # rate-limit gate (``Config.providers["anthropic"].rate_limit_per_domain``)
    # fires end-to-end — same wiring shape as
    # ``session_factory._build_anthropic_provider(config)``.
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    llm: LLMProvider | None
    if api_key:
        from brain_core.llm.providers.anthropic import AnthropicProvider

        llm = AnthropicProvider(api_key=api_key, config=config)
        _lifespan_logger.info("anthropic_provider_initialized")
    else:
        llm = None  # build_app_context defaults to FakeLLMProvider
        _lifespan_logger.info("anthropic_provider_skipped", reason="no_api_key")

    ctx = build_app_context(
        vault_root=app.state.vault_root,
        allowed_domains=app.state.allowed_domains,
        token=token,
        config=config,
        llm=llm,
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

    # Plan 16 Task 35 / D28 step 3 of 3: cross-process config hot-reload.
    # Watch ``<vault>/.brain/config.json`` and invalidate the loader's
    # in-memory cache on filesystem event so the NEXT ``resolve_config``
    # call (e.g. from a tool dispatcher holding a stale ``ctx.config``)
    # re-loads from disk. Symmetric architecture: brain_mcp runs the same
    # watcher independently — there is no IPC between the two processes.
    #
    # Wrap in try/except: a watcher failure must NOT block app startup.
    # T34's lazy peek inside ``resolve_config`` remains the safety net,
    # so the app keeps functioning even if the watcher silently dies.
    config_path = app.state.vault_root / ".brain" / "config.json"
    config_watcher: ConfigWatcher | None = None
    try:
        config_watcher = ConfigWatcher(
            config_path=config_path,
            on_change=lambda: _on_config_change(
                config_path, app.state, app.state.vault_root
            ),
        )
        config_watcher.start()
    except Exception as exc:  # pragma: no cover — defensive
        _lifespan_logger.warning(
            "hot_reload_unavailable",
            error=str(exc),
            config_path=str(config_path),
        )
        config_watcher = None

    try:
        yield
    finally:
        # Stop the watcher BEFORE other teardown so its observer thread
        # joins cleanly. ``stop()`` is idempotent and never raises out.
        if config_watcher is not None:
            config_watcher.stop()


def create_app(
    vault_root: Path,
    allowed_domains: tuple[str, ...] = ("research",),
    *,
    token_override: str | None = None,
    mount_static_ui: bool = True,
) -> FastAPI:
    """Build a fresh FastAPI app bound to the given vault.

    Task 1 lands the skeleton; Tasks 2+ wire AppContext, auth, and routes.

    Args:
        vault_root: Absolute path to the brain vault (e.g. ~/Documents/brain).
        allowed_domains: Tuple of domain names this app instance may access.
        token_override: Task 7 uses this to inject a fixed token for tests.
            None (the default) means generate a fresh token at startup.
        mount_static_ui: When True (production default), mount the Next.js
            static export at ``/`` so the app serves both the SPA and the
            API. When False, skip the SPA mount entirely — used by the
            brain_api test suite so synthetic test routes (e.g. ``/_boom``,
            ``/_protected``, ``/_ctx_echo``) registered AFTER ``create_app``
            returns aren't shadowed by the catch-all static mount. Plan 13
            Task 4 diagnosed this shadowing as the root cause of the 13
            previously-failing brain_api unit tests; Task 5 added this flag.
            Production callers (brain_cli.runtime.backend_factory and
            apps/brain_web/scripts/e2e_backend) keep the default ``True``.
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

    # Issue #32: stamp every request with a request_id and echo as
    # ``X-Request-ID``. Installed AFTER OriginHostMiddleware so refused
    # requests don't carry an id (they never reach a handler), but BEFORE
    # any router so downstream code (route handlers, the 500 catch-all,
    # logging) sees ``request.state.request_id``.
    app.add_middleware(RequestIDMiddleware)

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
    #
    # Plan 13 Task 5: when ``mount_static_ui=False`` (test fixture), skip the
    # mount entirely. Synthetic test routes registered AFTER ``create_app``
    # returns get shadowed by the catch-all SPA mount when ``apps/brain_web/
    # out/`` exists from a prior ``pnpm build`` — the test suite explicitly
    # wants a bare API surface.
    if mount_static_ui:
        try:
            out_dir = resolve_out_dir()
            app.mount("/", SPAStaticFiles(directory=str(out_dir), html=True), name="ui")
        except RuntimeError:
            # API-only mode (CI, contract tests, headless). Intentional no-op.
            pass

    return app
