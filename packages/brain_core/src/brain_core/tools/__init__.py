"""brain_core.tools — shared tool-handler registry and base types.

Populated by Plan 05 Tasks 5-6 as handlers move from brain_mcp/tools/*.py to
brain_core/tools/*.py. Each handler module self-registers at import time via
``_tools.register(sys.modules[__name__])`` (the per-module footer added in
Tasks 5-6). To surface the full registry to callers who import only
``brain_core.tools`` (e.g. ``brain_api.routes.tools``), the bottom of this
module eagerly imports every handler submodule so auto-registration runs
without each caller having to list them. Per the Task 5/6 hard rule, this
file does NOT call ``register(...)`` directly — the modules self-register.

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


# ---------------------------------------------------------------------------
# Eager imports — surface every handler module so auto-register fires on
# ``import brain_core.tools``. Must come AFTER ``register`` is defined (the
# submodules call back into it). Import-for-side-effect; aliased to underscore
# names so lint accepts the unused-name pattern.
# ---------------------------------------------------------------------------
from brain_core.tools import apply_patch as _apply_patch  # noqa: E402, F401
from brain_core.tools import budget_override as _budget_override  # noqa: E402, F401
from brain_core.tools import bulk_import as _bulk_import  # noqa: E402, F401
from brain_core.tools import classify as _classify  # noqa: E402, F401
from brain_core.tools import config_get as _config_get  # noqa: E402, F401
from brain_core.tools import config_set as _config_set  # noqa: E402, F401
from brain_core.tools import cost_report as _cost_report  # noqa: E402, F401
from brain_core.tools import create_domain as _create_domain  # noqa: E402, F401
from brain_core.tools import get_brain_md as _get_brain_md  # noqa: E402, F401
from brain_core.tools import get_index as _get_index  # noqa: E402, F401
from brain_core.tools import ingest as _ingest  # noqa: E402, F401
from brain_core.tools import lint as _lint  # noqa: E402, F401
from brain_core.tools import list_domains as _list_domains  # noqa: E402, F401
from brain_core.tools import list_pending_patches as _list_pending_patches  # noqa: E402, F401
from brain_core.tools import propose_note as _propose_note  # noqa: E402, F401
from brain_core.tools import read_note as _read_note  # noqa: E402, F401
from brain_core.tools import recent as _recent  # noqa: E402, F401
from brain_core.tools import recent_ingests as _recent_ingests  # noqa: E402, F401
from brain_core.tools import reject_patch as _reject_patch  # noqa: E402, F401
from brain_core.tools import rename_domain as _rename_domain  # noqa: E402, F401
from brain_core.tools import search as _search  # noqa: E402, F401
from brain_core.tools import undo_last as _undo_last  # noqa: E402, F401
