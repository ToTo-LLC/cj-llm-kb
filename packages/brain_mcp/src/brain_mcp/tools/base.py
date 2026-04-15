"""ToolContext + shared helpers for brain_mcp tools.

Every concrete tool in brain_mcp.tools.* receives a ToolContext that carries
the primitives it might need. Heavy types (retrieval, llm, writer) are typed
as Any to avoid import cycles — concrete tools narrow at use site.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import mcp.types as types
from brain_core.vault.paths import scope_guard

# Tool-module registry entries are typed as this alias. A structural Protocol
# with a `handle` callable member was attempted first, but mypy treats Callable
# parameters as positional-only, which does not match the named (arguments, ctx)
# signature our concrete tool modules use. ModuleType gives us an explicit,
# honest type (these ARE modules) without fighting the type checker. Mypy won't
# narrow attribute access on ModuleType, so tool-module attribute typos still
# fall to runtime — but the pattern is documented and consistent across all
# tool modules in brain_mcp.tools.*.
ToolModule = ModuleType


@dataclass(frozen=True)
class ToolContext:
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


def scope_guard_path(rel_path: str, ctx: ToolContext) -> Path:
    """Convert a vault-relative string path to an absolute scope-guarded Path.

    Raises:
        ValueError: if ``rel_path`` is absolute
        ScopeError: if the resolved path falls outside ctx.allowed_domains
    """
    p = Path(rel_path)
    if p.is_absolute():
        raise ValueError(f"path must be vault-relative, not absolute: {rel_path!r}")
    return scope_guard(
        ctx.vault_root / p,
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
    )


def text_result(text: str, *, data: dict[str, Any] | None = None) -> list[types.TextContent]:
    """Wrap a tool's output into the MCP SDK's TextContent list shape.

    If ``data`` is provided, appends a second TextContent containing the JSON
    encoding. Clients (Claude Desktop) render both.
    """
    out: list[types.TextContent] = [types.TextContent(type="text", text=text)]
    if data is not None:
        out.append(types.TextContent(type="text", text=json.dumps(data, indent=2, default=str)))
    return out
