"""brain_config_set — set a whitelisted config field.

**Persistence behavior (Plan 11 Task 4):**

Settable keys split into two groups:

* **Persisted keys.** Keys that resolve against a real
  :class:`brain_core.config.schema.Config` field path (e.g.
  ``budget.daily_usd``, ``log_llm_payloads``, ``autonomous.ingest``,
  ``handlers.url.timeout_seconds``, ``budget.override_until``,
  ``budget.override_delta_usd``). These are mutated on ``ctx.config`` in
  place and persisted to ``<vault>/.brain/config.json`` via
  :func:`persist_config_or_revert`. The response carries ``persisted=True``.
* **Non-persisted keys.** Keys whose target lives elsewhere or is
  intentionally session-scoped: the per-mode chat-model overrides
  (``ask_model``, ``brainstorm_model``, ``draft_model`` — these live on
  ``ChatSessionConfig``, applied per-session at chat construction) and
  ``domain_order`` (still pending a backing Config field). The tool
  validates the key, returns ``persisted=False``, and the caller
  (Settings UI) is responsible for applying the value at session start.

Safety layers (applied before any state change):
  1. Secret-substring blocklist mirrors ``brain_config_get``.
  2. Settable-key allowlist (``_SETTABLE_KEYS``) — anything outside this set
     raises ``PermissionError("...not settable...")``. Notably ``vault_path``
     is NOT settable from a session (clients must not reroot the vault).

If the on-disk write fails, the in-memory mutation is reverted via the
helper and ``ConfigPersistenceError`` propagates — the live ``Config``
never diverges from disk.
"""

from __future__ import annotations

import sys
from typing import Any

from pydantic import BaseModel

from brain_core.config.schema import Config
from brain_core.config.writer import persist_config_or_revert
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_config_set"
DESCRIPTION = (
    "Set a whitelisted config field. Persisted keys (Config fields) round-trip "
    "to <vault>/.brain/config.json via save_config(); non-persisted keys "
    "(chat-mode model overrides, domain_order) are session-scoped."
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


# Plan 11 Task 4: keys whose target is intentionally NOT a Config field.
# ``ask_model``/``brainstorm_model``/``draft_model`` live on
# ``ChatSessionConfig`` (per-session, applied at chat construction) and
# ``domain_order`` is still pending a backing Config field. These flow
# through allowlist + secret checks but skip the persistence path; the
# response carries ``persisted=False`` and the caller (Settings UI)
# applies the value session-side. Mirrors the test_config_set drift
# watchdog's ``_KNOWN_NOT_ON_CONFIG`` set.
_NON_PERSISTED_KEYS: frozenset[str] = frozenset(
    {
        "ask_model",
        "brainstorm_model",
        "draft_model",
        "domain_order",
    }
)


def _resolve_parent_and_field(config: Config, dotted: str) -> tuple[BaseModel, str]:
    """Walk a dotted Config path and return ``(parent_model, leaf_field)``.

    For ``"budget.daily_usd"`` returns ``(config.budget, "daily_usd")``;
    for ``"log_llm_payloads"`` returns ``(config, "log_llm_payloads")``.
    Raises ``KeyError`` if any segment doesn't exist on the live model
    (the allowlist + drift watchdog should prevent this — the explicit
    raise is the safety net).
    """
    parts = dotted.split(".")
    current: BaseModel = config
    for part in parts[:-1]:
        if part not in type(current).model_fields:
            raise KeyError(f"{part!r} is not a field of {type(current).__name__}")
        nxt = getattr(current, part)
        if not isinstance(nxt, BaseModel):
            raise KeyError(
                f"cannot descend through {part!r} ({type(nxt).__name__}) — "
                f"intermediate segments must be pydantic models"
            )
        current = nxt
    leaf = parts[-1]
    if leaf not in type(current).model_fields:
        raise KeyError(f"{leaf!r} is not a field of {type(current).__name__}")
    return current, leaf


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    key = str(arguments["key"])
    if any(s in key.lower() for s in _SECRET_SUBSTRINGS):
        raise PermissionError(f"refusing to set secret-like key {key!r}")
    if key not in _SETTABLE_KEYS:
        raise PermissionError(
            f"key {key!r} is not settable via MCP — settable keys: {sorted(_SETTABLE_KEYS)}"
        )

    value = arguments["value"]

    # Non-persisted keys: validate, return without touching ctx.config.
    # Persistence is the caller's responsibility (chat construction time
    # for the *_model overrides, Settings UI session state for domain_order).
    if key in _NON_PERSISTED_KEYS:
        return ToolResult(
            text=f"set {key} = {value!r} (session-scoped — caller persists)",
            data={
                "status": "updated",
                "key": key,
                "value": value,
                "persisted": False,
                "note": (
                    "This key is session-scoped (chat-mode model overrides) or "
                    "pending a Config field (domain_order) — caller applies "
                    "at session start."
                ),
            },
        )

    # Persisted keys: mutate ctx.config in place, persist via the helper.
    # If ctx.config is None (low-level test contexts) we behave like the
    # non-persisted branch above so the tool stays usable as a validator
    # without a Config wired through.
    cfg = ctx.config
    if cfg is None:
        return ToolResult(
            text=f"set {key} = {value!r} (no Config attached — persistence skipped)",
            data={
                "status": "updated",
                "key": key,
                "value": value,
                "persisted": False,
                "note": "ctx.config is None; key validated but not applied.",
            },
        )

    # NOTE on validation: pydantic v2 only validates on assignment when
    # ``validate_assignment=True``, which Config / its sub-configs do
    # NOT enable. So an out-of-range or wrong-type value slips through
    # ``setattr`` and is persisted as-is; the next ``load_config`` is
    # what ultimately rejects the file. Pinning that behavior in
    # tests/tools/test_config_set_persists.py so a future tightening
    # (validate_assignment, or pre-write validation here) is intentional.
    parent, leaf = _resolve_parent_and_field(cfg, key)
    with persist_config_or_revert(cfg, ctx.vault_root):
        setattr(parent, leaf, value)

    return ToolResult(
        text=f"set {key} = {value!r} (persisted)",
        data={
            "status": "updated",
            "key": key,
            "value": value,
            "persisted": True,
            "note": "Persisted to <vault>/.brain/config.json via save_config().",
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
