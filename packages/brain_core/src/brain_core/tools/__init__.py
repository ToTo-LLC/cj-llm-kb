"""brain_core.tools — shared tool-handler registry and base types.

Populated by Plan 05 Tasks 5-6 as handlers move from brain_mcp/tools/*.py to
brain_core/tools/*.py. Until then, the registry is empty and GET /api/tools
returns [].

The ``ToolModule`` alias is the same ``ModuleType`` choice used across every
tool module: a structural Protocol with a ``handle`` callable member was
attempted first, but mypy treats Callable parameters as positional-only, which
does not match the named ``(arguments, ctx)`` signature our concrete tool
modules use. ``ModuleType`` gives us an explicit, honest type (these ARE
modules) without fighting the type checker. Mypy won't narrow attribute access
on ``ModuleType``, so attribute typos still fall to runtime — but the pattern
is documented and consistent across every tool module.

``ToolContext``, ``ToolResult``, and ``scope_guard_path`` are re-exported from
``brain_core.tools.base`` for convenience so callers can do either
``from brain_core.tools import ToolContext`` or
``from brain_core.tools.base import ToolContext`` — both work.
"""

from __future__ import annotations

from types import ModuleType

from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path

ToolModule = ModuleType

_TOOL_MODULES: list[ToolModule] = []


def register(module: ToolModule) -> None:
    """Append a tool module to the registry. Idempotent on duplicate imports."""
    if module not in _TOOL_MODULES:
        _TOOL_MODULES.append(module)


def list_tools() -> list[ToolModule]:
    """Return a copy of the registered tool modules in registration order.

    Returning a copy prevents callers from mutating the registry in place.
    """
    return list(_TOOL_MODULES)


__all__ = [
    "ToolContext",
    "ToolModule",
    "ToolResult",
    "list_tools",
    "register",
    "scope_guard_path",
]
