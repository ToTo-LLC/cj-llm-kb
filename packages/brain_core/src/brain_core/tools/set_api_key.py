"""brain_set_api_key — write an LLM provider API key to ``<vault>/.brain/secrets.env``.

Deliberate carve-out from the ``brain_config_set`` secret blocklist. The
Settings page "Save API key" button has to land somewhere, and that
somewhere is the secrets store — never the main ``config.json``.

The secret value is written via :class:`brain_core.config.secrets.SecretsStore`
which handles atomic write + POSIX 0600 chmod. The handler NEVER echoes
the plaintext back; the returned ``masked`` string shows the last four
characters only (the standard Stripe / Anthropic console pattern).

Supported providers: ``anthropic`` (the day-one provider). Adding a new
provider is a one-line enum extension here plus an ``_ENV_KEYS`` mapping
entry.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.config.secrets import SecretsStore
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_set_api_key"
DESCRIPTION = (
    "Save an LLM provider API key to <vault>/.brain/secrets.env. "
    "File permissions are restricted to 0600 on POSIX. The plaintext key "
    "is never echoed back — the response returns a masked suffix only."
)

_ENV_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
}

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "provider": {
            "type": "string",
            "enum": sorted(_ENV_KEYS.keys()),
        },
        "api_key": {"type": "string", "minLength": 1},
    },
    "required": ["provider", "api_key"],
}


def _mask(api_key: str) -> str:
    """Return a display-safe mask: leading ``sk-ant-...`` prefix + last 4 chars.

    Guard against absurdly short keys — always reveal at most 4 characters.
    """
    if len(api_key) <= 4:
        return "•" * max(len(api_key), 1)
    prefix_end = min(7, len(api_key) - 4)
    prefix = api_key[:prefix_end]
    suffix = api_key[-4:]
    return f"{prefix}•••{suffix}"


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    provider = str(arguments["provider"])
    api_key = str(arguments["api_key"])

    if provider not in _ENV_KEYS:
        raise ValueError(
            f"unsupported provider {provider!r} — supported: {sorted(_ENV_KEYS)}"
        )
    if not api_key.strip():
        raise ValueError("api_key must be a non-empty string")

    env_key = _ENV_KEYS[provider]
    secrets_path = ctx.vault_root / ".brain" / "secrets.env"
    store = SecretsStore(secrets_path)
    store.set(env_key, api_key)

    return ToolResult(
        text=f"saved {env_key} for provider {provider!r}",
        data={
            "status": "saved",
            "provider": provider,
            "env_key": env_key,
            "masked": _mask(api_key),
            "path": str(secrets_path),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
