"""brain_config_set — set a whitelisted config field (in-memory only in Plan 04).

**Design note:** Writing the config file correctly requires typed round-tripping
through ``Config.model_validate(...)`` + JSON serialization, which is more work
than the rest of Task 19 combined. Plan 04 ships the tool surface so clients
(Claude Desktop, browser) can discover it; actual persistence lands in
Plan 07's Settings page. This tool returns ``status="updated"`` with
``persisted=False`` and a note pointing callers at the CLI for now.

Safety layers (both applied before any state change):
  1. Secret-substring blocklist mirrors ``brain_config_get``.
  2. Settable-key allowlist (``_SETTABLE_KEYS``) — anything outside this set
     raises ``PermissionError("...not settable...")``. Notably ``vault_path``
     is NOT settable from a session (clients must not reroot the vault).
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_config_set"
DESCRIPTION = (
    "Set a whitelisted config field (budget.daily_usd, log_llm_payloads). "
    "Plan 04: in-memory only — persistence lands in Plan 07."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {},  # any — validated at apply time (Plan 07)
    },
    "required": ["key", "value"],
}

_SECRET_SUBSTRINGS: frozenset[str] = frozenset({"api_key", "secret", "token", "password"})
# Allowlist of config keys that may be set via MCP. ``active_domain`` is
# deliberately excluded: scope is set per-session by the caller's allowed
# domains, not by a persisted mid-session toggle. ``vault_path`` and the
# ``llm.*`` keys are also out of scope for MCP (clients must not reroot the
# vault or swap the model from a tool call). ``budget.daily_usd`` matches the
# real schema field (``BudgetConfig.daily_usd``).
_SETTABLE_KEYS: frozenset[str] = frozenset(
    {
        "budget.daily_usd",
        "log_llm_payloads",
        # Plan 07 Task 1: per-category autonomy flags. Each maps 1:1 to a
        # field on ``AutonomousConfig`` and a value in ``PatchCategory``.
        # Setting any of these to True opts that category into auto-apply
        # via ``should_auto_apply``. Persistence lands in Plan 07 Task 5.
        "autonomous.ingest",
        "autonomous.entities",
        "autonomous.concepts",
        "autonomous.index_rewrites",
        "autonomous.draft",
        # Plan 07 Task 2: per-mode chat-model overrides. Each maps to the
        # matching ``ChatSessionConfig.{mode}_model`` field; None falls
        # back to the global ``llm.model`` default. Persistence lands in
        # Plan 07 Task 5 alongside the autonomy flags above.
        "ask_model",
        "brainstorm_model",
        "draft_model",
        # Plan 07 Task 4: domain ordering for the sidebar + ephemeral
        # budget override fields. ``domain_order`` is a list[str] mirroring
        # the user's preferred sidebar order; the override fields are
        # written by ``brain_budget_override`` directly but also exposed
        # here so the Settings page can wipe them via brain_config_set.
        "domain_order",
        "budget.override_until",
        "budget.override_delta_usd",
        # Issue #23: per-handler tunables (URL/Tweet timeouts, PDF
        # min_chars). Each maps to a field on ``HandlersConfig.<handler>``.
        # Plan 07's persistence path (Task 5) will write these to disk; the
        # Settings page surfaces them in the next frontend pass.
        "handlers.url.timeout_seconds",
        "handlers.tweet.timeout_seconds",
        "handlers.pdf.min_chars",
    }
)


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = ctx  # no ctx state mutated yet; Plan 07 will persist through ctx.
    key = str(arguments["key"])
    if any(s in key.lower() for s in _SECRET_SUBSTRINGS):
        raise PermissionError(f"refusing to set secret-like key {key!r}")
    if key not in _SETTABLE_KEYS:
        raise PermissionError(
            f"key {key!r} is not settable via MCP — settable keys: {sorted(_SETTABLE_KEYS)}"
        )

    value = arguments["value"]
    return ToolResult(
        text=f"set {key} = {value!r} (IN-MEMORY ONLY — persistence deferred to Plan 07)",
        data={
            "status": "updated",
            "key": key,
            "value": value,
            "persisted": False,
            "note": (
                "Plan 04 acknowledges the write but doesn't persist. "
                "Use the brain CLI or wait for Plan 07's Settings page."
            ),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
