"""brain_core.tools — shared tool-handler registry.

Populated by Plan 05 Tasks 5-6 as handlers move from brain_mcp/tools/*.py to
brain_core/tools/*.py. Until then, the registry is empty and GET /api/tools
returns [].

The ``ToolModule`` alias mirrors the same choice in ``brain_mcp.tools.base``:
a structural Protocol with a ``handle`` callable member was attempted first,
but mypy treats Callable parameters as positional-only, which does not match
the named ``(arguments, ctx)`` signature our concrete tool modules use.
``ModuleType`` gives us an explicit, honest type (these ARE modules) without
fighting the type checker. Mypy won't narrow attribute access on ``ModuleType``,
so attribute typos still fall to runtime — but the pattern is documented and
consistent across every tool module.
"""

from __future__ import annotations

from types import ModuleType

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
