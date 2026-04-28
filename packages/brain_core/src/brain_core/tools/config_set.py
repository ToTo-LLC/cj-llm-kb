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

from brain_core.config.schema import Config, DomainOverride
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
# Allowlist of config keys that may be set via MCP. Plan 12 D2 inverted the
# Plan 07-era policy that excluded ``active_domain``: with persistent disk
# config (Plan 11) and the Settings UI scope picker (Plan 12 Task 8) as the
# new persistence path, ``active_domain`` is now settable here rather than
# requiring a dedicated ``brain_set_active_domain`` tool. The cross-field
# validator ``Config._check_active_domain_in_domains`` (Plan 10) defines the
# "must be a member of ``Config.domains``" invariant; ``handle`` mirrors that
# rule with an explicit pre-check before mutation so the error surfaces at
# write time rather than the next ``load_config``. ``vault_path`` and the
# ``llm.*`` keys remain out of scope for MCP (clients must not reroot the
# vault or swap the model from a tool call). ``budget.daily_usd`` matches the
# real schema field (``BudgetConfig.daily_usd``).
_SETTABLE_KEYS: frozenset[str] = frozenset(
    {
        "active_domain",
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
        # Plan 11 D10: privacy-rail slug list. The whole list is written
        # at once (a `list[str]`) — list-mutation as dotted-path is
        # awkward and error-prone. The Settings UI computes the new
        # list (add/remove a slug) and posts it here; the Config
        # validators enforce ``personal``-required + subset-of-domains.
        "privacy_railed",
        # Plan 12 D8 / Task 9: per-vault acknowledgment for the
        # cross-domain confirmation modal. ``true`` suppresses the
        # modal in future cross-domain-into-railed sessions; ``false``
        # re-enables it. Bound by the modal's "Don't show this again"
        # checkbox AND the Settings → Domains "Show cross-domain
        # warning" toggle (inverted UI sense). Schema field landed in
        # Plan 12 Task 1; this entry was added in Task 9 alongside
        # the typed helper ``setCrossDomainWarningAcknowledged`` to
        # close the cross-task gap (Task 1 added the field but did
        # not whitelist it for the open-set ``brain_config_set`` path).
        "cross_domain_warning_acknowledged",
    }
)

# Plan 11 D12 / Task 7: ``domain_overrides.<slug>.<field>`` is settable for
# every leaf field on ``DomainOverride``. The wildcard pattern is the same
# shape as Plan 11's narrative reference to ``handlers.<name>.<field>``,
# but expressed as a dynamic check rather than baked into _SETTABLE_KEYS
# (it's an open set — any user-defined slug is a valid second segment, so
# enumerating them statically would either rot or under-cover).
_DOMAIN_OVERRIDE_FIELDS: frozenset[str] = frozenset(DomainOverride.model_fields.keys())


def _is_settable_domain_override_key(key: str) -> bool:
    """Return True if ``key`` matches ``domain_overrides.<slug>.<field>``.

    The slug shape is validated by the Config schema's
    ``_check_domain_overrides_keys_in_domains`` model validator on save —
    we don't pre-validate it here so a user-entered "ghost" slug fails
    with the canonical Config-validator error message rather than a
    duplicate, drift-prone copy.
    """
    parts = key.split(".")
    return (
        len(parts) == 3
        and parts[0] == "domain_overrides"
        and parts[2] in _DOMAIN_OVERRIDE_FIELDS
        and bool(parts[1])
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

    NOTE: this helper handles only pydantic-model walks. Dict-keyed
    paths (``domain_overrides.<slug>.<field>``) are routed through
    :func:`_apply_domain_override` in :func:`handle` because the leaf
    write semantics are different: the parent is a ``dict`` not a
    pydantic model, the slug key may not exist yet (auto-create with
    ``DomainOverride()``), and slug membership in ``Config.domains``
    must round-trip through the Config validator on persist (not via
    a parallel pre-check here).
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


def _apply_domain_override(config: Config, key: str, value: Any) -> None:
    """Apply a ``domain_overrides.<slug>.<field>`` mutation in place.

    Plan 11 Task 7 dict-walk extension. The standard
    :func:`_resolve_parent_and_field` walker can't descend through
    ``Config.domain_overrides`` because the value is a ``dict[str,
    DomainOverride]``, not a pydantic model. This helper handles the
    three-segment shape directly:

    1. Parse ``domain_overrides.<slug>.<field>``. The caller has
       already validated the shape via ``_is_settable_domain_override_key``.
    2. Look up ``config.domain_overrides[slug]``. If absent, construct
       a fresh ``DomainOverride()`` (all-None defaults — equivalent to
       "no override for any field") and insert it. This is the
       auto-create path: a setter call for a brand-new override slug
       lands cleanly without requiring a separate "create override"
       step. The Config-level
       ``_check_domain_overrides_keys_in_domains`` validator runs on
       :func:`save_config` and rejects orphan slugs (not in
       ``Config.domains``), so the validation seam stays single.
    3. Setattr ``<field> = value`` on the override model. ``value=None``
       clears the override for that specific field (the field type is
       ``X | None`` for every leaf, so None is a valid assignment).
    4. If after the assignment every field on the override is None,
       drop the slug entirely from ``domain_overrides`` to keep the
       persisted shape minimal — an all-None entry is semantically
       identical to "no entry" but pollutes ``config.json``.

    The function mutates ``config`` IN PLACE — no ``model_copy``, no new
    Config instance. The caller's reference stays live so the rest of
    the request flow sees the mutation.
    """
    parts = key.split(".")
    # The caller is _is_settable_domain_override_key-gated, so this
    # assertion is a defense-in-depth assert rather than user-facing
    # error UX.
    assert len(parts) == 3 and parts[0] == "domain_overrides", (
        f"_apply_domain_override called with non-domain-override key {key!r}"
    )
    slug = parts[1]
    field = parts[2]
    if field not in _DOMAIN_OVERRIDE_FIELDS:
        raise KeyError(f"{field!r} is not a field of DomainOverride")

    # Slug-membership pre-check. The Config-level
    # ``_check_domain_overrides_keys_in_domains`` validator only runs at
    # construction time (Pydantic v2 model_validator semantics), not on
    # in-place dict mutation, and the writer's ``model_dump`` path
    # doesn't re-trigger it either. Without this guard, an orphan slug
    # would persist silently and only fail on the *next* ``load_config``
    # (typically the next process boot) — terrible feedback latency.
    # Mirror the validator's error message so the Settings UI surfaces
    # the same wording regardless of which seam catches it.
    if slug not in config.domains:
        raise ValueError(
            f"domain_overrides keys {[slug]!r} are not in domains "
            f"{config.domains!r}; remove the override or add the domain first."
        )

    overrides = config.domain_overrides
    existing = overrides.get(slug)
    if existing is None:
        # Auto-create on first override-set for this slug — the slug
        # has already been validated as a member of ``config.domains``
        # above, so the auto-create is safe.
        existing = DomainOverride()
        overrides[slug] = existing
    setattr(existing, field, value)

    # Prune empty overrides — if every field is None now, the entry is
    # semantically a no-op and shouldn't show up in config.json. Without
    # this prune, "set then reset to global on every field" would leave
    # an empty {} object in the persisted dict.
    if all(getattr(existing, f) is None for f in _DOMAIN_OVERRIDE_FIELDS):
        del overrides[slug]


def _check_active_domain_membership(config: Config, value: Any) -> None:
    """Mirror ``Config._check_active_domain_in_domains`` at write time.

    Plan 12 D2 inverted the Plan 07-era exclusion of ``active_domain``
    from ``_SETTABLE_KEYS``. The Plan 10 cross-field validator on
    Config enforces "must be in ``self.domains``", but it only fires at
    construction time (``load_config``) — Config does NOT enable
    ``validate_assignment``, and ``save_config`` serializes via
    ``persisted_dict`` without re-validating. Without this pre-check, a
    bad slug would persist silently and only fail on the next process
    boot. Mirror the validator's error wording so the Settings UI
    surfaces the same message regardless of which seam catches it.

    The ``value`` argument intentionally accepts ``Any`` and rejects
    anything non-string before the membership check — passing a list or
    None would otherwise produce a misleading "not in domains" error.
    """
    if not isinstance(value, str):
        raise ValueError(f"active_domain must be a string slug, got {type(value).__name__}")
    if value not in config.domains:
        raise ValueError(f"active_domain {value!r} is not in domains {config.domains!r}")


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    key = str(arguments["key"])
    # Plan 11 Task 7: ``domain_overrides.<slug>.<field>`` is an open-set
    # wildcard pattern, not a static allowlist entry. Route through
    # ``_is_settable_domain_override_key`` first so user-defined slugs
    # don't fail the static membership check below. The wildcard
    # check is also why the secret-substring check moved BELOW this
    # branch: ``DomainOverride.max_output_tokens`` legitimately contains
    # "token" as a substring, and the field-allowlist
    # (``_DOMAIN_OVERRIDE_FIELDS``) is the real security gate for
    # override-path keys — only known-safe leaf fields pass the
    # wildcard check, so the secret-substring blocklist would
    # double-cover and false-positive.
    is_domain_override = _is_settable_domain_override_key(key)
    if not is_domain_override:
        if any(s in key.lower() for s in _SECRET_SUBSTRINGS):
            raise PermissionError(f"refusing to set secret-like key {key!r}")
        if key not in _SETTABLE_KEYS:
            raise PermissionError(
                f"key {key!r} is not settable via MCP — settable keys: "
                f"{sorted(_SETTABLE_KEYS)} (plus domain_overrides.<slug>.<field>)"
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
    #
    # Plan 11 Task 7: ``domain_overrides.<slug>.<field>`` writes route
    # through ``_apply_domain_override`` (dict-walk on
    # ``Config.domain_overrides``); everything else uses the standard
    # pydantic-model walker. Both mutate ``cfg`` in place inside the
    # ``persist_config_or_revert`` context so the helper's snapshot/
    # revert path covers both shapes.
    with persist_config_or_revert(cfg, ctx.vault_root):
        if is_domain_override:
            _apply_domain_override(cfg, key, value)
        else:
            # Plan 12 D2: ``active_domain`` membership is validated here
            # because Config's cross-field validator only fires at
            # construction time (validate_assignment=False, persisted_dict
            # bypasses model_validate). Without this seam an orphan slug
            # would persist silently and only fail on the next process
            # boot — terrible feedback latency for the Settings UI.
            if key == "active_domain":
                _check_active_domain_membership(cfg, value)
            parent, leaf = _resolve_parent_and_field(cfg, key)
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
