"""brain_config_get — read a single config field, refusing secrets.

The caller session doesn't have access to the env Mapping + cli_overrides that
``brain_core.config.loader.load_config()`` requires, so we snapshot config the
same way ``brain://config/public`` does: build a defaults-backed ``Config()``
and overlay the session's ``vault_root``. That gives the client a consistent
view of the session's resolved settings, without needing a ``.brain/config.json``
on disk.

Secret-like keys (substring match on ``{api_key, secret, token, password}``,
case-insensitive) raise ``PermissionError`` before any dict traversal — so a
bad key can't leak a sibling value via a stacktrace.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.config.schema import Config
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
    """Return a session-scoped dump of Config defaults with vault_root injected.

    Mirrors the allowlist approach used by ``resources/config_public.py`` but
    returns the full Config model since ``brain_config_get`` is a typed lookup
    tool — callers name a field explicitly, so we don't need the resource's
    drop-everything-not-on-the-allowlist posture. Secret-key refusal happens
    at the caller before any dict traversal.
    """
    defaults = Config()
    data: dict[str, Any] = defaults.model_dump(mode="json")
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
