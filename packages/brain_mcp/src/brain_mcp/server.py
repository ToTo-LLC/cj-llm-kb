"""brain MCP server factory.

Tool modules in brain_mcp.tools.* each export NAME, DESCRIPTION, INPUT_SCHEMA,
and `async def handle(arguments, ctx)`. The factory registers all of them into
one list_tools / call_tool pair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mcp.types as types
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.cost.ledger import CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.state.db import StateDB
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter
from mcp.server.lowlevel import Server

from brain_mcp.rate_limit import RateLimitConfig, RateLimiter
from brain_mcp.tools import get_index as _get_index_tool
from brain_mcp.tools import list_domains as _list_domains_tool
from brain_mcp.tools import read_note as _read_note_tool
from brain_mcp.tools import recent as _recent_tool
from brain_mcp.tools import search as _search_tool
from brain_mcp.tools.base import ToolContext, ToolModule

# Task 9+ appends more modules here.
_TOOL_MODULES: list[ToolModule] = [
    _list_domains_tool,
    _get_index_tool,
    _read_note_tool,
    _search_tool,
    _recent_tool,
]


def create_server(
    *,
    vault_root: Path,
    allowed_domains: tuple[str, ...] = ("research",),
) -> Server:
    """Build a fresh `mcp.server.lowlevel.Server` with brain tools registered.

    Does NOT start transport — callers run the returned Server against their
    chosen transport (stdio in __main__, in-memory in tests).
    """
    server: Server = Server("brain")

    # Cached across tool calls within one session. An MCP session is short-lived
    # and bound to one (vault_root, allowed_domains) tuple closed over at
    # create_server() time, so the ToolContext (notably its BM25 index) is safe
    # to reuse instead of rebuilding on every tool call.
    # TODO(Task 21): invalidate cache after writes when real config wiring lands.
    _cached_ctx: ToolContext | None = None

    def _build_ctx() -> ToolContext:
        """Return the session's ToolContext, building it lazily on first use.

        Task 21 replaces this with a real builder that reads config from env;
        for now, wires everything from the vault_root + allowed_domains closed
        over at create_server() time.
        """
        nonlocal _cached_ctx
        if _cached_ctx is not None:
            return _cached_ctx
        brain_dir = vault_root / ".brain"
        brain_dir.mkdir(parents=True, exist_ok=True)
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
        ctx = _build_ctx()
        for m in _TOOL_MODULES:
            if name == m.NAME:
                result: list[types.TextContent] = await m.handle(arguments, ctx)
                return result
        raise ValueError(f"unknown tool: {name}")

    return server
