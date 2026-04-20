"""AppContext — per-app-instance primitives, injected via FastAPI Depends.

AppContext is the HTTP analog of brain_mcp.tools.base.ToolContext. It CONTAINS
a ToolContext (as `tool_ctx`) so the Task 10 tool dispatcher can hand the
embedded ToolContext straight to `handle(args, ctx)` without conversion.

Lifetime: one AppContext per FastAPI app instance, built once in the lifespan
and stashed on ``app.state.ctx``. FastAPI routes read it via ``Depends(get_ctx)``.

Imports note: ToolContext and RateLimiter currently live in ``brain_mcp.*``.
Group 2 (Task 4) moves ToolContext to ``brain_core.tools.base``; Task 14 moves
RateLimiter to ``brain_core.rate_limit``. This module flips its imports then.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.cost.ledger import CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.provider import LLMProvider
from brain_core.state.db import StateDB
from brain_core.tools import ToolModule
from brain_core.tools import list_tools as list_registered_tools
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter
from brain_mcp.rate_limit import RateLimitConfig, RateLimiter
from brain_mcp.tools.base import ToolContext
from fastapi import Request


@dataclass(frozen=True)
class AppContext:
    """Per-app-instance state — built once in the lifespan, injected via Depends.

    Attributes:
        vault_root: Absolute path to the brain vault for this app instance.
        allowed_domains: Tuple of domain names this app instance may access.
        tool_ctx: Embedded ToolContext — handed straight to brain_core.tools
            handlers by the Task 10 dispatcher. Carries the 10 primitives.
        tool_by_name: Name → module index built from ``brain_core.tools.list_tools()``
            at app startup. O(1) lookup in the POST /api/tools/{name} dispatcher.
            Also resolves Plan 04 Task 25's deferred _TOOL_BY_NAME perf concern.
        token: App secret for auth (populated by Task 7; None until then).
    """

    vault_root: Path
    allowed_domains: tuple[str, ...]
    tool_ctx: ToolContext
    tool_by_name: dict[str, ToolModule]
    token: str | None = None


def build_app_context(
    vault_root: Path,
    allowed_domains: tuple[str, ...],
    *,
    llm: LLMProvider | None = None,
    token: str | None = None,
) -> AppContext:
    """Build a fresh AppContext wired to all brain_core + brain_mcp primitives.

    Mirrors ``brain_mcp/tests/conftest.py::make_tool_context`` so the ctx shape
    is identical between MCP tests and HTTP tests. Uses FakeLLMProvider by
    default so tests never hit the network; callers pass ``llm=`` to override
    (e.g. a real AnthropicProvider in production).

    Args:
        vault_root: Absolute path to the brain vault.
        allowed_domains: Tuple of domain names this app may access.
        llm: Optional LLMProvider override. Defaults to FakeLLMProvider().
        token: Optional app-secret token (Task 7 populates in production).

    Returns:
        A fully-wired AppContext with an embedded ToolContext.
    """
    brain_dir = vault_root / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    state_db = StateDB.open(brain_dir / "state.sqlite")
    writer = VaultWriter(vault_root=vault_root)
    pending_store = PendingPatchStore(brain_dir / "pending")
    retrieval = BM25VaultIndex(vault_root=vault_root, db=state_db)
    retrieval.build(allowed_domains)
    undo_log = UndoLog(vault_root=vault_root)
    cost_ledger = CostLedger(db_path=brain_dir / "costs.sqlite")
    rate_limiter = RateLimiter(RateLimitConfig())
    tool_ctx = ToolContext(
        vault_root=vault_root,
        allowed_domains=allowed_domains,
        retrieval=retrieval,
        pending_store=pending_store,
        state_db=state_db,
        writer=writer,
        llm=llm or FakeLLMProvider(),
        cost_ledger=cost_ledger,
        rate_limiter=rate_limiter,
        undo_log=undo_log,
    )
    # Build the name → module index once, up front. Task 10 dispatcher reads it
    # via ``ctx.tool_by_name[name]``; this also eliminates the O(n) scan that
    # Plan 04 Task 25 flagged inside the MCP server's dispatcher.
    tool_by_name: dict[str, ToolModule] = {m.NAME: m for m in list_registered_tools()}
    return AppContext(
        vault_root=vault_root,
        allowed_domains=allowed_domains,
        tool_ctx=tool_ctx,
        tool_by_name=tool_by_name,
        token=token,
    )


def get_ctx(request: Request) -> AppContext:
    """FastAPI dependency — return the app's AppContext.

    The lifespan builds the AppContext at startup and stashes it on
    ``app.state.ctx``. This dependency reads it back for route handlers.

    Raises:
        RuntimeError: if ``app.state.ctx`` is missing. This indicates a boot
            failure (lifespan didn't run or crashed before stashing ctx) and
            should be surfaced loudly rather than masked as an AttributeError.
    """
    ctx: AppContext | None = getattr(request.app.state, "ctx", None)
    if ctx is None:
        raise RuntimeError("AppContext not initialized — lifespan failed?")
    return ctx
