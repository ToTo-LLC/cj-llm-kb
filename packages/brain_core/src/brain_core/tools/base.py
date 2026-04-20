"""Shared tool primitives for brain_core.tools.<name> modules.

Task 4 lands ``ToolContext``, ``ToolResult``, ``scope_guard_path``. These are
transport-agnostic — MCP-specific helpers (``text_result``, MCP SDK imports)
live in ``brain_mcp.tools.base``. Tasks 5 and 6 move handler bodies into
``brain_core.tools.<name>``; those handlers return ``ToolResult`` and the
brain_mcp shims wrap the result into MCP ``TextContent`` at the transport edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain_core.vault.paths import scope_guard


@dataclass(frozen=True)
class ToolContext:
    """Per-request primitives every tool handler may need.

    Heavy types (retrieval, llm, writer) are typed as ``Any`` to avoid import
    cycles — concrete tools narrow at use site. Mirrors the Plan 04 brain_mcp
    shape 1:1 so every handler moves without signature changes. This class is
    re-exported by ``brain_mcp.tools.base`` — identity is preserved so existing
    ``brain_mcp`` tests that construct ``ToolContext(...)`` from the brain_mcp
    import path build the same class.
    """

    vault_root: Path
    allowed_domains: tuple[str, ...]
    retrieval: Any  # BM25VaultIndex
    pending_store: Any  # PendingPatchStore
    state_db: Any  # StateDB
    writer: Any  # VaultWriter
    llm: Any  # LLMProvider
    cost_ledger: Any  # CostLedger
    rate_limiter: Any  # RateLimiter
    undo_log: Any  # UndoLog


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Transport-agnostic return value for every tool handler.

    ``text`` is a human-readable summary shown to LLMs or rendered in the UI.
    ``data`` is the structured payload (``None`` when the tool has nothing more
    to say than the text). MCP wraps this into ``TextContent`` via
    ``brain_mcp.tools.base.text_result``; the REST API serializes it as
    ``{"text": ..., "data": ...}`` directly.
    """

    text: str
    data: dict[str, Any] | None = None


def scope_guard_path(rel_path: str, ctx: ToolContext) -> Path:
    """Convert a vault-relative string path to an absolute scope-guarded Path.

    Raises:
        ValueError: if ``rel_path`` is absolute.
        ScopeError: if the resolved path falls outside ctx.allowed_domains.
    """
    p = Path(rel_path)
    if p.is_absolute():
        raise ValueError(f"path must be vault-relative, not absolute: {rel_path!r}")
    return scope_guard(
        ctx.vault_root / p,
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
    )
