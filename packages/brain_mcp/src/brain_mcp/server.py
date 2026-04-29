"""brain MCP server factory.

Tool modules in brain_mcp.tools.* each export NAME, DESCRIPTION, INPUT_SCHEMA,
and `async def handle(arguments, ctx)`. The factory registers all of them into
one list_tools / call_tool pair.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mcp.types as types
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.config.loader import load_config
from brain_core.cost.ledger import CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from brain_core.state.db import StateDB
from brain_core.tools import ToolModule
from brain_core.tools.base import ToolContext
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from pydantic import AnyUrl

from brain_mcp.resources import brain_md as _brain_md_res
from brain_mcp.resources import config_public as _config_public_res
from brain_mcp.resources import domain_index as _domain_index_res
from brain_mcp.tools import apply_patch as _apply_patch_tool
from brain_mcp.tools import backup_create as _backup_create_tool
from brain_mcp.tools import backup_list as _backup_list_tool
from brain_mcp.tools import backup_restore as _backup_restore_tool
from brain_mcp.tools import budget_override as _budget_override_tool
from brain_mcp.tools import bulk_import as _bulk_import_tool
from brain_mcp.tools import classify as _classify_tool
from brain_mcp.tools import config_get as _config_get_tool
from brain_mcp.tools import config_set as _config_set_tool
from brain_mcp.tools import cost_report as _cost_report_tool
from brain_mcp.tools import create_domain as _create_domain_tool
from brain_mcp.tools import delete_domain as _delete_domain_tool
from brain_mcp.tools import export_thread as _export_thread_tool
from brain_mcp.tools import fork_thread as _fork_thread_tool
from brain_mcp.tools import get_brain_md as _get_brain_md_tool
from brain_mcp.tools import get_index as _get_index_tool
from brain_mcp.tools import get_pending_patch as _get_pending_patch_tool
from brain_mcp.tools import ingest as _ingest_tool
from brain_mcp.tools import lint as _lint_tool
from brain_mcp.tools import list_domains as _list_domains_tool
from brain_mcp.tools import list_pending_patches as _list_pending_patches_tool
from brain_mcp.tools import list_threads as _list_threads_tool
from brain_mcp.tools import mcp_install as _mcp_install_tool
from brain_mcp.tools import mcp_selftest as _mcp_selftest_tool
from brain_mcp.tools import mcp_status as _mcp_status_tool
from brain_mcp.tools import mcp_uninstall as _mcp_uninstall_tool
from brain_mcp.tools import ping_llm as _ping_llm_tool
from brain_mcp.tools import propose_note as _propose_note_tool
from brain_mcp.tools import read_note as _read_note_tool
from brain_mcp.tools import recent as _recent_tool
from brain_mcp.tools import recent_ingests as _recent_ingests_tool
from brain_mcp.tools import reject_patch as _reject_patch_tool
from brain_mcp.tools import rename_domain as _rename_domain_tool
from brain_mcp.tools import search as _search_tool
from brain_mcp.tools import set_api_key as _set_api_key_tool
from brain_mcp.tools import undo_last as _undo_last_tool

# Task 10+ appends more modules here.
_TOOL_MODULES: list[ToolModule] = [
    _list_domains_tool,
    _get_index_tool,
    _read_note_tool,
    _search_tool,
    _recent_tool,
    _get_brain_md_tool,
    _ingest_tool,
    _classify_tool,
    _bulk_import_tool,
    _propose_note_tool,
    _list_pending_patches_tool,
    _get_pending_patch_tool,
    _apply_patch_tool,
    _reject_patch_tool,
    _undo_last_tool,
    _cost_report_tool,
    _lint_tool,
    _config_get_tool,
    _config_set_tool,
    # Plan 07 Task 4 — Inbox / Settings / Domain admin tools.
    _recent_ingests_tool,
    _create_domain_tool,
    _rename_domain_tool,
    _budget_override_tool,
    # Plan 07 Task 20 — Fork dialog support.
    _fork_thread_tool,
    # Plan 07 Task 25 sub-task A — sweep: MCP install / settings / backup / domain admin.
    _mcp_install_tool,
    _mcp_uninstall_tool,
    _mcp_status_tool,
    _mcp_selftest_tool,
    _set_api_key_tool,
    _ping_llm_tool,
    _backup_create_tool,
    _backup_list_tool,
    _backup_restore_tool,
    _delete_domain_tool,
    # Issue #18 — left-nav recent-chats panel data source.
    _list_threads_tool,
    # Issue #17 — chat-sub-header export-thread action.
    _export_thread_tool,
]


def create_server(
    *,
    vault_root: Path,
    allowed_domains: tuple[str, ...] = ("research",),
) -> Server:
    """Build a fresh `mcp.server.lowlevel.Server` with brain tools registered.

    Does NOT start transport — callers run the returned Server against their
    chosen transport (stdio in __main__, in-memory in tests).

    TODO(plan-05+): add an ``llm_factory`` kwarg so callers (Plan 05 demo
    scaffolding, integration tests, CLI selftest) can inject an Anthropic or
    fake LLM without monkey-patching FakeLLMProvider. Currently the demo
    scripts work around this by constructing the server with FakeLLMProvider
    and queueing responses; a factory kwarg would be the cleaner extension
    point.
    """
    server: Server = Server("brain")

    # Cached across tool calls within one session. An MCP session is short-lived
    # and bound to one (vault_root, allowed_domains) tuple closed over at
    # create_server() time, so the ToolContext (notably its BM25 index) is safe
    # to reuse instead of rebuilding on every tool call.
    #
    # Plan 12 Task 4: Config is now loaded once in ``_build_ctx`` and stashed
    # by reference on ``ctx.config``. Plan 11 mutation tools mutate this
    # instance in place (no model_copy in the dispatch path) so subsequent
    # reads via ``ctx.config`` see the updated values within the same session
    # — read-after-write contract preserved without cache invalidation. This
    # is symmetric to brain_api's ``build_app_context``, where the same Config
    # reference is shared across the app lifespan.
    _cached_ctx: ToolContext | None = None

    def _build_ctx() -> ToolContext:
        """Return the session's ToolContext, building it lazily on first use.

        Plan 12 Task 4 (mirrors Plan 11 Task 7's brain_api fix): load the live
        Config from ``<vault>/.brain/config.json`` and thread it through to
        ``ToolContext.config`` so Plan 11 mutation tools (config_set,
        create_domain, rename_domain, delete_domain, budget_override) can
        persist their changes via :func:`save_config`. Without this, every
        Plan 11 mutation dispatched via Claude Desktop → brain_mcp would land
        on the ``ctx.config is None`` no-op branch — the tool would report
        "saved" but the disk write would never happen.

        ``load_config`` uses Plan 11 D7's fallback chain
        (config.json → config.json.bak → ``Config()`` defaults), so first-run
        with no config.json on disk boots cleanly. ``vault_path`` is supplied
        via ``cli_overrides`` rather than the persisted blob — it's the
        chicken-and-egg field the loader's whitelist deliberately excludes.

        The lazy ``_cached_ctx`` singleton means the load happens once per
        server lifetime — that matches the brain_api eager-on-startup pattern
        in spirit (one load per process), just deferred to first tool call so
        a session that never invokes a tool pays nothing.
        """
        nonlocal _cached_ctx
        if _cached_ctx is not None:
            return _cached_ctx
        brain_dir = vault_root / ".brain"
        brain_dir.mkdir(parents=True, exist_ok=True)
        config = load_config(
            config_file=brain_dir / "config.json",
            env=os.environ,
            cli_overrides={"vault_path": vault_root},
        )
        db = StateDB.open(brain_dir / "state.sqlite")
        writer = VaultWriter(vault_root=vault_root)
        pending = PendingPatchStore(brain_dir / "pending")
        retrieval = BM25VaultIndex(vault_root=vault_root, db=db)
        retrieval.build(allowed_domains)
        _cached_ctx = ToolContext(
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
        return _cached_ctx

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=m.NAME,
                description=m.DESCRIPTION,
                inputSchema=m.INPUT_SCHEMA,
            )
            for m in _TOOL_MODULES
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        # O(n) linear scan over 18 tools per call. Plan 04 Task 25 flagged a
        # ``_TOOL_BY_NAME`` dict lookup as a perf / readability improvement;
        # Plan 05 Task 10 implemented the same pattern for brain_api in
        # ``brain_api.context.AppContext.tool_by_name`` (built once in
        # ``build_app_context``). The brain_mcp equivalent is a one-line
        # change here but was deferred to avoid touching an MCP server that
        # has been stable since Plan 04. Task 25 re-captures the deferral so
        # the next sweep can unify both dispatchers.
        ctx = _build_ctx()
        for m in _TOOL_MODULES:
            if name == m.NAME:
                result: list[types.TextContent] = await m.handle(arguments, ctx)
                return result
        raise ValueError(f"unknown tool: {name}")

    @server.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        resources: list[types.Resource] = [
            types.Resource(
                uri=AnyUrl(_brain_md_res.URI),
                name=_brain_md_res.NAME,
                description=_brain_md_res.DESCRIPTION,
                mimeType=_brain_md_res.MIME_TYPE,
            ),
            types.Resource(
                uri=AnyUrl(_config_public_res.URI),
                name=_config_public_res.NAME,
                description=_config_public_res.DESCRIPTION,
                mimeType=_config_public_res.MIME_TYPE,
            ),
        ]
        # One resource per allowed domain — enables Claude Desktop to surface
        # an index.md chooser that respects scope (personal is never listed
        # in a research-scoped session).
        for domain in allowed_domains:
            resources.append(
                types.Resource(
                    uri=AnyUrl(_domain_index_res.uri_for(domain)),
                    name=f"{domain}/index.md",
                    description=f"Index for the {domain} domain.",
                    mimeType=_domain_index_res.MIME_TYPE,
                )
            )
        return resources

    @server.read_resource()
    async def handle_read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        # MCP SDK gives us AnyUrl; compare via its str form so the hardcoded
        # URIs in resource modules stay plain strings (matches list_resources()).
        uri_str = str(uri)
        if uri_str == _brain_md_res.URI:
            body = _brain_md_res.read(vault_root)
            return [ReadResourceContents(content=body, mime_type=_brain_md_res.MIME_TYPE)]
        if uri_str == _config_public_res.URI:
            body = _config_public_res.read(vault_root)
            return [ReadResourceContents(content=body, mime_type=_config_public_res.MIME_TYPE)]
        if uri_str.startswith("brain://") and uri_str.endswith("/index.md"):
            body = _domain_index_res.read(
                uri_str,
                vault_root=vault_root,
                allowed_domains=allowed_domains,
            )
            return [ReadResourceContents(content=body, mime_type=_domain_index_res.MIME_TYPE)]
        raise ValueError(f"unknown resource: {uri_str}")

    return server
