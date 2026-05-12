"""Entry point: `python -m brain_mcp` runs the stdio MCP server.

Launches the brain MCP server over stdio (the transport Claude Desktop uses).
Configuration flows in via environment variables that ``brain mcp install``
writes into the Claude Desktop config's ``env`` dict:

* ``BRAIN_VAULT_ROOT`` — absolute path to the vault (default
  ``~/Documents/brain``).
* ``BRAIN_ALLOWED_DOMAINS`` — comma-separated allow-list of domains the server
  may read/write (default ``"research,work"``; ``personal`` is deliberately
  excluded from the default).

The Task 1 stub that merely printed the version is replaced here.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import mcp.server.stdio
import structlog
from brain_core.config.hot_reload import ConfigWatcher
from brain_core.config.loader import invalidate_cache_for, resolve_config
from brain_core.config.schema import Config, WatchedFolder
from brain_core.watch import WatchedFolderWatcher

from brain_mcp.server import _reset_ctx_cache, create_server

_logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Plan 22 T8 — Watched-folder watcher module-level state.
# ---------------------------------------------------------------------------
#
# brain_api stashes the live ``WatchedFolderWatcher`` on ``app.state.
# folder_watcher`` (a FastAPI affordance). brain_mcp has no app.state
# equivalent — the stdio server has no per-app state container — so the
# watcher reference lives at module scope, mirroring how ``_cached_ctx``
# is lifted to module scope in :mod:`brain_mcp.server` (Plan 16 T39.5).
#
# The ``_last_known_watched_folders`` snapshot is the diff source for the
# hot-reload bridge: brain_api reads ``tool_ctx.config.watched_folders``
# off ``app.state.ctx`` because the lifespan guarantees the AppContext is
# built at startup. brain_mcp's :func:`brain_mcp.server._build_ctx` is
# lazy — the cached ToolContext may not exist when the first config
# change fires — so we cache the last-applied folder list independently.
#
# Both are reset by :func:`_reset_watcher_state` (tests use this to
# isolate module-level state between cases).
_folder_watcher: WatchedFolderWatcher | None = None
_last_known_watched_folders: list[WatchedFolder] = []
# The vault root and allowed-domains tuple captured at boot. Required by
# the hot-reload bridge to re-resolve the config and rebuild the watcher
# with the same scope the server was launched with.
_boot_vault_root: Path | None = None
_boot_allowed_domains: tuple[str, ...] = ()


def _reset_watcher_state() -> None:
    """Clear the module-level watcher slot + folder snapshot.

    Test-only helper so the watcher state doesn't leak between cases. In
    production the slot is populated exactly once (at :func:`_run`
    startup) and read by every :func:`_on_config_change` invocation.
    """
    global _folder_watcher, _last_known_watched_folders
    global _boot_vault_root, _boot_allowed_domains
    _folder_watcher = None
    _last_known_watched_folders = []
    _boot_vault_root = None
    _boot_allowed_domains = ()


def _watched_folders_changed(
    old: list[WatchedFolder], new: list[WatchedFolder]
) -> bool:
    """Return True when the watched_folders sets differ on any user-visible field.

    Mirrors :func:`brain_api.app._watched_folders_changed` byte-for-byte
    (Plan 22 T7). Kept duplicated here rather than imported across
    package boundaries — brain_mcp and brain_api are sibling packages
    and a cross-import is the anti-pattern. A future ``brain_core`` lift
    is a Plan 23 candidate (per T7's forward notes on the
    ``_build_pipeline`` triple-duplication concern, now FOUR sites with
    T8 landing).

    Plan 22 T7 v1 policy: any change to the watched-folder list (add,
    remove, enable/disable, path edit, domain edit, recursion toggle)
    triggers a full watcher restart. Comparing pydantic models by
    ``model_dump`` keeps the diff simple and pin-friendly without
    requiring callers to thread an "equality" overload through.
    """
    if len(old) != len(new):
        return True
    return [wf.model_dump() for wf in old] != [wf.model_dump() for wf in new]


def _build_watched_folder_watcher(
    config: Config,
    vault_root: Path,
    allowed_domains: tuple[str, ...],
) -> WatchedFolderWatcher:
    """Construct a :class:`WatchedFolderWatcher` from the live config.

    Plan 22 T8 — symmetric watcher per D7 (brain_mcp side). Mirrors
    :func:`brain_api.app._build_watched_folder_watcher`. The
    :class:`IngestPipeline` is built via the canonical recipe from
    :func:`brain_core.tools.watch_folder._build_pipeline` so the four
    call sites (bulk_import, watch_folder, resync_folder, AND this
    lifespan integration) stay in sync.

    The brain_mcp pipeline ALSO requires a fully-built
    :class:`~brain_core.tools.base.ToolContext` for the pipeline
    primitives. We obtain it from :mod:`brain_mcp.server` — the same
    factory the tool dispatcher reads — so the watcher's pipeline shares
    StateDB, CostLedger, RateLimiter, etc. with every concurrent tool
    call. The lazy build is the trade-off: if no tool has yet warmed
    ``_cached_ctx``, this call IS the first build. That's intentional —
    the watcher is one of the boot-time consumers of the ToolContext,
    sibling to the tool dispatcher.
    """
    # Late import: ``brain_core.tools.watch_folder`` pulls a chunky
    # dependency graph (dispatcher, handlers, budget guard). Python
    # only loads modules once per process so amortized cost is zero;
    # keeping the import inline makes the seam visible.
    from brain_core.tools.watch_folder import _build_pipeline

    # Build (or read cached) the ToolContext via the brain_mcp server
    # factory's lazy builder. We need a ``ToolContext`` to feed
    # ``_build_pipeline``; calling ``_build_ctx`` is the canonical
    # source. But that helper is defined inside ``create_server`` as a
    # closure — we can't call it from here. Instead reach into the
    # module-level singleton; if it's not yet warmed, build a
    # production-shape ToolContext here directly.
    #
    # Practical implementation: use the same primitives the server's
    # ``_build_ctx`` would build, reading from the live config that
    # arrived as our argument.
    ctx = _build_or_reuse_tool_ctx(config, vault_root, allowed_domains)
    pipeline = _build_pipeline(ctx)

    folders: list[WatchedFolder] = list(
        getattr(config, "watched_folders", []) or []
    )
    return WatchedFolderWatcher(
        observers=folders,
        pipeline=pipeline,
        allowed_domains=allowed_domains,
    )


def _build_or_reuse_tool_ctx(
    config: Config,
    vault_root: Path,
    allowed_domains: tuple[str, ...],
):  # type: ignore[no-untyped-def]
    """Return a ToolContext suitable for the watcher's IngestPipeline.

    Preference order:

    1. If :mod:`brain_mcp.server` already has a warm ``_cached_ctx``,
       reuse it. This keeps the watcher's pipeline pointing at the
       same StateDB / CostLedger / RateLimiter the tool dispatcher uses.
    2. Otherwise build a fresh ToolContext via the same primitives
       :func:`brain_mcp.server._build_ctx` would. This branch runs at
       cold-boot when no tool call has yet warmed the singleton —
       i.e. the watcher is the FIRST consumer of the ToolContext.

    The fresh build does NOT populate ``brain_mcp.server._cached_ctx``
    on its own — that path is owned by the server's tool dispatcher.
    If the next tool call rebuilds, both ToolContexts coexist briefly;
    the StateDB connection is acquired per-instance so there's no
    sharing hazard for v1.
    """
    from brain_core.chat.pending import PendingPatchStore
    from brain_core.chat.retrieval import BM25VaultIndex
    from brain_core.cost.ledger import CostLedger
    from brain_core.llm.fake import FakeLLMProvider
    from brain_core.rate_limit import RateLimitConfig, RateLimiter
    from brain_core.state.db import StateDB
    from brain_core.tools.base import ToolContext
    from brain_core.vault.undo import UndoLog
    from brain_core.vault.writer import VaultWriter

    from brain_mcp import server as _server_module

    if _server_module._cached_ctx is not None:
        return _server_module._cached_ctx

    brain_dir = vault_root / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    db = StateDB.open(brain_dir / "state.sqlite")
    writer = VaultWriter(vault_root=vault_root)
    pending = PendingPatchStore(brain_dir / "pending")
    retrieval = BM25VaultIndex(vault_root=vault_root, db=db)
    retrieval.build(allowed_domains)
    return ToolContext(
        vault_root=vault_root,
        allowed_domains=allowed_domains,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        writer=writer,
        llm=FakeLLMProvider(),
        cost_ledger=CostLedger(db_path=brain_dir / "costs.sqlite"),
        rate_limiter=RateLimiter(RateLimitConfig()),
        undo_log=UndoLog(vault_root=vault_root),
        config=config,
    )


def _restart_watched_folder_watcher(new_config: Config) -> None:
    """Stop the existing watcher and start a fresh one with ``new_config``.

    Plan 22 T8 hot-reload bridge — brain_mcp mirror of
    :func:`brain_api.app._restart_watched_folder_watcher`. Coarse v1
    policy: every ``watched_folders`` change does a full stop + start
    (rather than incremental schedule / unschedule). The coarse path
    is correct in all cases and avoids a class of "ghost schedule" bugs
    where an incremental update leaves a stale handler bound to a
    removed folder. Optimization is a Plan 23 candidate per T7's
    forward notes.

    Errors during stop OR start are logged + swallowed: brain_mcp's
    stdio transport is already connected to Claude Desktop at this
    point and we owe it a response. The user-visible degradation is
    "watched-folder sync stops working until next config save /
    restart" — acceptable for a v1 watcher.
    """
    global _folder_watcher, _last_known_watched_folders

    if _boot_vault_root is None:
        # ``_run`` did not complete startup wiring (or tests cleared
        # the slot). Defensive: log + bail rather than try to build a
        # watcher from incomplete state.
        _logger.warning(
            "watched_folder_watcher_restart_skipped",
            reason="boot_state_uninitialized",
        )
        return

    existing = _folder_watcher
    if existing is not None:
        try:
            existing.stop()
        except Exception as exc:  # pragma: no cover — defensive
            _logger.warning(
                "watched_folder_watcher_stop_failed",
                error=str(exc),
            )
    try:
        new_watcher = _build_watched_folder_watcher(
            new_config, _boot_vault_root, _boot_allowed_domains
        )
        new_watcher.start()
        _folder_watcher = new_watcher
        _last_known_watched_folders = list(
            getattr(new_config, "watched_folders", []) or []
        )
        _logger.info(
            "watched_folder_watcher_restarted",
            folder_count=len(new_config.watched_folders),
        )
    except Exception as exc:  # pragma: no cover — defensive
        _logger.warning(
            "watched_folder_watcher_restart_failed",
            error=str(exc),
        )
        _folder_watcher = None


def _on_config_change(config_path: Path) -> None:
    """Hot-reload callback: loader-cache invalidate + ctx clear + watcher diff.

    Plan 16 T35 / T39.5 baseline: invalidate the loader's cache then
    clear the MCP ToolContext singleton so the next tool call rebuilds
    with fresh config.

    Plan 22 T8 extension (this commit): diff
    :attr:`Config.watched_folders` against the last-known snapshot and
    restart the watcher if and only if the folder list changed. The
    snapshot lives in :data:`_last_known_watched_folders` because
    ``brain_mcp.server._cached_ctx`` may not yet be warmed when the
    first config change fires — it's a lazy build keyed off tool-call
    arrival, whereas the watcher is wired in at boot.

    Failures in re-resolve or diff are swallowed with a structlog
    warning — a transient bad write to ``config.json`` must NOT crash
    the running server. The watcher keeps its current schedule until
    the next successful change.
    """
    invalidate_cache_for(config_path)
    _reset_ctx_cache()

    if _boot_vault_root is None:
        # Watcher integration not yet wired (e.g. ConfigWatcher fired
        # before _run finished initial setup). The loader-cache +
        # ctx-reset above are still valuable; the watcher branch can
        # safely no-op.
        return

    try:
        new_config = resolve_config(
            config_file=config_path,
            env=os.environ,
            cli_overrides={"vault_path": _boot_vault_root},
        )
    except Exception as exc:
        _logger.warning(
            "config_hot_reload_failed",
            error=str(exc),
            config_path=str(config_path),
        )
        return

    new_folders: list[WatchedFolder] = list(
        getattr(new_config, "watched_folders", []) or []
    )
    if _watched_folders_changed(_last_known_watched_folders, new_folders):
        _restart_watched_folder_watcher(new_config)


async def _run() -> None:
    global _folder_watcher, _last_known_watched_folders
    global _boot_vault_root, _boot_allowed_domains

    vault_root = Path(os.environ.get("BRAIN_VAULT_ROOT", Path.home() / "Documents" / "brain"))
    allowed_domains = tuple(
        d.strip()
        for d in os.environ.get("BRAIN_ALLOWED_DOMAINS", "research,work").split(",")
        if d.strip()
    )
    server = create_server(vault_root=vault_root, allowed_domains=allowed_domains)

    # Capture boot params for the hot-reload bridge. The on_change
    # callback only receives the config_path; it reads these to
    # re-resolve config and rebuild the watcher.
    _boot_vault_root = vault_root
    _boot_allowed_domains = allowed_domains

    # Plan 16 Task 35 / D28 step 3 of 3: symmetric watchdog. brain_api
    # runs an identical ConfigWatcher; both processes share only the
    # on-disk vault, so each watches independently. Failure to start
    # the watcher must NOT block the MCP server — Claude Desktop is
    # already connected to our stdio at this point and we owe it a
    # response. T34's lazy peek inside ``resolve_config`` is the
    # safety net.
    #
    # Plan 16 Task 39.5: chain the loader-cache invalidation with
    # :func:`_reset_ctx_cache` so the per-server-lifetime ToolContext
    # singleton is also cleared. Without the second step, the watcher
    # would invalidate the loader cache but ``_build_ctx`` would still
    # return the cached ToolContext with stale ``.config`` — the watcher
    # only benefitted the FIRST tool call per process.
    config_path = vault_root / ".brain" / "config.json"

    config_watcher: ConfigWatcher | None = None
    try:
        config_watcher = ConfigWatcher(
            config_path=config_path,
            on_change=lambda: _on_config_change(config_path),
        )
        config_watcher.start()
    except Exception as exc:  # pragma: no cover — defensive
        _logger.warning(
            "hot_reload_unavailable",
            error=str(exc),
            config_path=str(config_path),
        )
        config_watcher = None

    # Plan 22 T8 — Watched-folder filesystem watcher. Built AFTER the
    # ConfigWatcher (so the hot-reload bridge in :func:`_on_config_change`
    # has something to restart) and BEFORE the stdio server enters its
    # message loop. Failure to start is logged + swallowed — the MCP
    # surface must boot even if the watcher cannot.
    try:
        initial_config = resolve_config(
            config_file=config_path,
            env=os.environ,
            cli_overrides={"vault_path": vault_root},
        )
        folder_watcher = _build_watched_folder_watcher(
            initial_config, vault_root, allowed_domains
        )
        folder_watcher.start()
        _folder_watcher = folder_watcher
        _last_known_watched_folders = list(
            getattr(initial_config, "watched_folders", []) or []
        )
        _logger.info(
            "watched_folder_watcher_started",
            folder_count=len(_last_known_watched_folders),
        )
    except Exception as exc:  # pragma: no cover — defensive
        _logger.warning(
            "watched_folder_watcher_unavailable",
            error=str(exc),
        )
        _folder_watcher = None

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        # Stop the folder watcher BEFORE the ConfigWatcher so a final
        # config-change callback can't try to restart a watcher we're
        # in the middle of tearing down. Both ``stop()`` calls are
        # idempotent and swallow their own errors.
        if _folder_watcher is not None:
            try:
                _folder_watcher.stop()
            except Exception as exc:  # pragma: no cover — defensive
                _logger.warning(
                    "watched_folder_watcher_stop_failed_at_shutdown",
                    error=str(exc),
                )
            _folder_watcher = None
        if config_watcher is not None:
            config_watcher.stop()
        # Clear boot state so a re-entered _run starts clean.
        _boot_vault_root = None
        _boot_allowed_domains = ()
        _last_known_watched_folders = []


def main() -> int:
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
