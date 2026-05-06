"""Common error helpers for brain_core tools.

Centralizes the boilerplate raised when a tool is invoked with a
``ToolContext`` whose ``config`` field is ``None``. Plan 15 Task 8
extracts the previously-duplicated ``_NO_CONFIG_MESSAGE`` raise from
three call sites (``brain_config_get``, ``brain_list_domains``,
``brain_config_set``) into a single helper so the canonical wording —
audited under Plan 13 Task 1 review item M5 — has exactly one point of
maintenance.

The wording is preserved verbatim from ``brain_config_get`` (the
canonical site per Plan 12 Task 3 / D5). Only the leading
``{tool_name}`` token is interpolated so the LLM sees an actionable
identifier in the error.

SPAStaticFiles' non-http scope guard (brain_api Plan 14 Task 1) stays
separate per Plan 15 D7: different package, different scope-type
contract, different invariant being asserted.

The leading-underscore module name keeps this private to
``brain_core.tools.*`` — external callers should not import it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain_core.tools.base import ToolContext


def raise_if_no_config(ctx: ToolContext, tool_name: str) -> None:
    """Raise ``RuntimeError`` if ``ctx.config`` is ``None``.

    The wording matches the canonical message from ``brain_config_get``
    verbatim (Plan 13 Task 1 / M5 audit). ``tool_name`` is the public
    tool name (e.g. ``"brain_config_get"``, ``"brain_list_domains"``,
    ``"brain_config_set"``) and is interpolated as the leading token so
    the error identifies the offending tool to the LLM.

    A ``None`` config is a lifecycle violation, NOT a fallback case:
    the brain_api lifespan (Plan 11 Task 7) and the brain_mcp
    ``_build_ctx`` (Plan 12 Task 4) are responsible for threading the
    loaded Config through ``ToolContext``. Silently falling back to
    ``Config()`` defaults would make Settings reads lie about the
    resolved configuration (Plan 11 lesson 343).
    """
    if ctx.config is None:
        raise RuntimeError(
            f"{tool_name} requires ctx.config to be a Config instance, but "
            "got None. The brain_api lifespan (build_app_context) and brain_mcp "
            "_build_ctx are responsible for threading the loaded Config through "
            "ToolContext; a None config here means the wrapper hasn't wired it in. "
            "Falling back to Config() defaults would make Settings reads lie about "
            "the resolved configuration."
        )
