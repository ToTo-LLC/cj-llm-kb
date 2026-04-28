"""brain_config_get — read a single config field, refusing secrets.

Reads the live :class:`brain_core.config.schema.Config` off ``ctx.config`` so
the response reflects the session's actual resolved settings (after
``brain_config_set`` mutations, after ``load_config`` overrides, etc.) — NOT
a defaults-backed snapshot. Plan 12 Task 3 / D5: an earlier implementation
constructed ``Config()`` here, which made the Settings UI render schema
defaults regardless of what was actually loaded; that anti-pattern is now
gated by a parametrized contract test (``test_read_tools_thread_ctx_config``).

If ``ctx.config`` is ``None`` we raise ``RuntimeError``: the brain_api
lifespan (Plan 11 Task 7) and the brain_mcp ``_build_ctx`` (Plan 12 Task 4)
are responsible for threading a real Config in. A ``None`` config indicates
a lifecycle violation — silently falling back to ``Config()`` defaults
would make Settings reads lie to the user (Plan 11 lesson 343).

Secret-like keys (substring match on ``{api_key, secret, token, password}``,
case-insensitive) raise ``PermissionError`` before any dict traversal — so a
bad key can't leak a sibling value via a stacktrace.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_config_get"
DESCRIPTION = (
    "Read a config field by key (e.g. 'active_domain', 'budget.daily_usd'). "
    "Refuses keys that look like secrets."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
}

_SECRET_SUBSTRINGS: frozenset[str] = frozenset({"api_key", "secret", "token", "password"})


def _looks_like_secret(key: str) -> bool:
    lowered = key.lower()
    return any(s in lowered for s in _SECRET_SUBSTRINGS)


def _snapshot_config(ctx: ToolContext) -> dict[str, Any]:
    """Return a session-scoped dump of the LIVE Config with vault_root injected.

    Reads ``ctx.config`` directly so the response reflects the current
    in-memory Config — including any prior ``brain_config_set`` mutations
    within this session and any values loaded from
    ``<vault>/.brain/config.json``. ``vault_path`` is overlaid from
    ``ctx.vault_root`` because the loader's allowlist deliberately
    excludes it from the persisted blob (chicken-and-egg field).
    """
    cfg = ctx.config
    if cfg is None:
        raise RuntimeError(
            "brain_config_get requires ctx.config to be a Config instance, but "
            "got None. The brain_api lifespan (build_app_context) and brain_mcp "
            "_build_ctx are responsible for threading the loaded Config through "
            "ToolContext; a None config here means the wrapper hasn't wired it in. "
            "Falling back to Config() defaults would make Settings reads lie about "
            "the resolved configuration."
        )
    data: dict[str, Any] = cfg.model_dump(mode="json")
    # Reflect the session's actual vault root rather than the default.
    data["vault_path"] = str(ctx.vault_root)
    return data


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    key = str(arguments["key"])
    if _looks_like_secret(key):
        raise PermissionError(f"refusing to expose secret-like key {key!r}")

    data = _snapshot_config(ctx)

    # Support dotted-key lookup: "budget.daily_usd".
    value: Any = data
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"config key {key!r} not found")
        value = value[part]

    return ToolResult(
        text=f"{key} = {value!r}",
        data={"key": key, "value": value},
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
