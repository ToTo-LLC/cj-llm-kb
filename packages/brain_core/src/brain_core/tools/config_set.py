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

from brain_core.config.schema import (
    BudgetOverride,
    Config,
    DomainOverride,
    ProviderConfig,
    RateLimitOverride,
)
from brain_core.config.writer import persist_config_or_revert
from brain_core.tools._errors import raise_if_no_config
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
        # via ``should_auto_apply``. Persisted to ``<vault>/.brain/config.json``
        # via the ``persist_config_or_revert`` path in :func:`handle` below
        # (Plan 11 Task 4 wired the disk round-trip).
        "autonomous.ingest",
        "autonomous.entities",
        "autonomous.concepts",
        "autonomous.index_rewrites",
        "autonomous.draft",
        # Plan 07 Task 2: per-mode chat-model overrides. Each maps to the
        # matching ``ChatSessionConfig.{mode}_model`` field; None falls
        # back to the global ``llm.model`` default. These are session-scoped
        # (``_NON_PERSISTED_KEYS`` below) — applied per-session at chat
        # construction by the Settings UI, never written to disk; the
        # Plan 11 Task 4 split made this an explicit design choice.
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

# Plan 16 Task 29 / D26 step 4 of 4: ``budget.per_domain.<slug>`` is
# settable for any user-defined domain slug. Unlike ``domain_overrides``
# (where each LEAF field is set independently), the per-domain budget
# entry is written as a WHOLE :class:`BudgetOverride` payload — both
# caps land in one call and an absent cap is sent as ``None``. The 3-
# segment shape (``budget.per_domain.<slug>``) is intentional: it
# mirrors the ``budget.daily_usd`` dotted path users already know from
# ``brain_config_get``, and keeps the slug as the trailing variable
# segment so the wildcard check is identical in shape to
# ``domain_overrides.<slug>.<field>``.
_BUDGET_OVERRIDE_FIELDS: frozenset[str] = frozenset(BudgetOverride.model_fields.keys())

# Plan 16 Task 32 / D27 step 3 of 3:
# ``providers.<provider>.rate_limit_per_domain.<slug>`` is settable for any
# user-defined domain slug under any provider key. Mirrors the
# ``budget.per_domain.<slug>`` wildcard pattern (Task 29) — whole-payload
# write of a :class:`RateLimitOverride` dict (or ``None`` to clear), with
# the slug as the trailing variable segment. The 4-segment shape is
# necessary because the rate-limit map lives one level deeper than the
# budget map: ``Config.providers["anthropic"].rate_limit_per_domain[slug]``
# vs. ``Config.budget.per_domain[slug]``. Per-leaf paths weren't chosen
# because :class:`RateLimitOverride` only has one leaf today
# (``requests_per_minute``); whole-payload semantics future-proof the
# shape if the override grows additional fields and matches the budget
# pattern users now know.
_RATE_LIMIT_OVERRIDE_FIELDS: frozenset[str] = frozenset(
    RateLimitOverride.model_fields.keys()
)


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


def _is_settable_budget_per_domain_key(key: str) -> bool:
    """Return True if ``key`` matches ``budget.per_domain.<slug>``.

    Plan 16 Task 29 / D26 step 4 of 4. Three-segment wildcard pattern
    where the trailing slug is the open-set portion. Slug membership
    in ``Config.domains`` is enforced at apply time inside
    :func:`_apply_budget_per_domain` (mirroring the existing
    ``_apply_domain_override`` pattern) so the Settings UI surfaces a
    consistent error voice regardless of which seam catches it.

    Unlike ``domain_overrides.<slug>.<field>``, this wildcard takes a
    WHOLE-payload value — the caller posts a ``BudgetOverride`` dict
    (or ``None`` to clear the entry); there is no per-leaf-field path.
    Per-leaf would have required either a 4-segment path or a tighter
    coupling between the static allowlist and ``BudgetOverride``'s
    field set; both options are strictly more fragile than the whole-
    payload write because the Settings UI sets daily/monthly caps as a
    pair and a half-applied save would leave inconsistent state on
    disk if one leaf write failed.
    """
    parts = key.split(".")
    return (
        len(parts) == 3
        and parts[0] == "budget"
        and parts[1] == "per_domain"
        and bool(parts[2])
    )


def _is_settable_rate_limit_per_domain_key(key: str) -> bool:
    """Return True if ``key`` matches ``providers.<provider>.rate_limit_per_domain.<slug>``.

    Plan 16 Task 32 / D27 step 3 of 3. Four-segment wildcard pattern.
    Both the provider name AND the trailing slug are open-set portions
    (the provider-name set is intentionally NOT validated against any
    Literal — adding a new LLM provider should not require a schema
    migration of every user's persisted config; the schema comment on
    ``Config.providers`` pins this). Slug membership in
    ``Config.domains`` is enforced at apply time inside
    :func:`_apply_rate_limit_per_domain`, mirroring the
    ``_apply_budget_per_domain`` orphan-slug guard so the Settings UI
    surfaces a consistent error voice regardless of which seam catches
    it.

    Whole-payload write of a :class:`RateLimitOverride` dict (or
    ``None`` to clear). RateLimitOverride only has a single leaf
    (``requests_per_minute``) today, but the whole-payload shape
    future-proofs the wire contract — if the override grows more
    fields, the wire shape and apply-helper don't need to change.
    """
    parts = key.split(".")
    return (
        len(parts) == 4
        and parts[0] == "providers"
        and parts[2] == "rate_limit_per_domain"
        and bool(parts[1])
        and bool(parts[3])
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
    # ``_check_domain_overrides_keys_in_domains`` validator runs at
    # construction time and (post-Plan-16-Task-36) on every ``setattr``
    # via ``validate_assignment=True``, but NEITHER seam fires for
    # IN-PLACE DICT MUTATION (``config.domain_overrides[slug] = ...``):
    # the dict is the same object Pydantic already validated, so
    # appending to it doesn't trigger field-level validation. The
    # writer's ``model_dump`` path also doesn't re-run model validators.
    # Without this guard, an orphan slug would persist silently and only
    # fail on the *next* ``load_config`` (typically the next process
    # boot) — terrible feedback latency. Mirror the validator's error
    # message so the Settings UI surfaces the same wording regardless
    # of which seam catches it.
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


def _apply_budget_per_domain(config: Config, key: str, value: Any) -> None:
    """Apply a ``budget.per_domain.<slug>`` mutation in place.

    Plan 16 Task 29 / D26 step 4 of 4. Mirrors
    :func:`_apply_domain_override` for the
    ``Config.budget.per_domain: dict[str, BudgetOverride]`` shape. The
    standard :func:`_resolve_parent_and_field` walker can't descend
    through ``Config.budget.per_domain`` because the value is a
    ``dict[str, BudgetOverride]``, not a pydantic model.

    Semantics:

    1. Parse ``budget.per_domain.<slug>``. The caller has already
       validated the shape via :func:`_is_settable_budget_per_domain_key`.
    2. Slug-membership pre-check: ``slug`` must be in
       ``config.domains``. Without this guard, an orphan slug would
       persist silently — the Plan 16 Task 26 schema landed without a
       cross-field validator on ``per_domain`` (the cross-field
       reference would have to reach across into the parent ``Config``,
       which Pydantic v2 doesn't expose at the sub-model layer
       cleanly), so the disk-write path is the only seam that catches
       orphan slugs today and only at the next ``load_config`` if at
       all.
    3. Coerce ``value``:
         - ``None`` → delete the slug entry entirely (the documented
           way to clear a per-domain budget — equivalent to "fall back
           to global").
         - ``dict`` → construct a ``BudgetOverride(**value)``;
           Pydantic's positive-cap validator
           (:meth:`BudgetOverride._validate_positive`) catches zero /
           negative caps before the mutation lands.
         - anything else → ``ValueError`` (non-callers like a stray
           string from the wire shouldn't fail with a confusing
           Pydantic error).
    4. Prune empty overrides — if both caps are ``None`` the entry is
       semantically a no-op and shouldn't pollute ``config.json``.
       Mirrors the ``_apply_domain_override`` prune step exactly.

    The function mutates ``config`` IN PLACE — no ``model_copy``, no new
    Config instance.
    """
    parts = key.split(".")
    assert len(parts) == 3 and parts[0] == "budget" and parts[1] == "per_domain", (
        f"_apply_budget_per_domain called with non-budget-per-domain key {key!r}"
    )
    slug = parts[2]

    if slug not in config.domains:
        raise ValueError(
            f"budget.per_domain keys {[slug]!r} are not in domains "
            f"{config.domains!r}; remove the override or add the domain first."
        )

    per_domain = config.budget.per_domain

    if value is None:
        # Clear the per-domain budget entirely — equivalent to "no
        # override; fall back to global ``BudgetConfig`` caps".
        per_domain.pop(slug, None)
        return

    if not isinstance(value, dict):
        raise ValueError(
            f"budget.per_domain value must be a dict (BudgetOverride payload) or None, "
            f"got {type(value).__name__}"
        )

    # ``BudgetOverride(**value)`` raises ``ValidationError`` on a zero /
    # negative cap (the schema-level positive-cap validator) and on any
    # extra fields (``extra="forbid"``). We let those bubble up as-is so
    # the Settings UI surfaces the canonical Pydantic error voice.
    override = BudgetOverride(**value)

    # Prune empty entries — both caps None is a no-op and shouldn't
    # land in ``config.json``. Mirrors the ``_apply_domain_override``
    # prune so a "set then clear all caps" round-trip leaves the
    # persisted shape minimal.
    if all(getattr(override, f) is None for f in _BUDGET_OVERRIDE_FIELDS):
        per_domain.pop(slug, None)
        return

    per_domain[slug] = override


def _apply_rate_limit_per_domain(config: Config, key: str, value: Any) -> None:
    """Apply a ``providers.<provider>.rate_limit_per_domain.<slug>`` mutation in place.

    Plan 16 Task 32 / D27 step 3 of 3. Mirrors
    :func:`_apply_budget_per_domain` for the
    ``Config.providers[<provider>].rate_limit_per_domain: dict[str,
    RateLimitOverride]`` shape, with one extra wrinkle: the parent
    ``ProviderConfig`` may not exist yet (a fresh Config has
    ``providers={}`` because the per-provider config is a backward-compat
    addition). Auto-create on first set so the user doesn't have to
    pre-seed an empty provider entry via a separate write.

    Semantics:

    1. Parse ``providers.<provider>.rate_limit_per_domain.<slug>``. The
       caller has already validated the shape via
       :func:`_is_settable_rate_limit_per_domain_key`.
    2. Slug-membership pre-check: ``slug`` must be in
       ``config.domains``. Mirrors the
       :func:`_apply_budget_per_domain` orphan-slug guard. The
       ``ProviderConfig.rate_limit_per_domain`` schema landed without a
       cross-field validator (Task 30 schema comment pins this — the
       cross-field reference would have to reach across into the parent
       ``Config``, which Pydantic v2 doesn't expose at the sub-model
       layer cleanly), so the disk-write path is the only seam that
       catches orphan slugs today.
    3. Auto-create the parent ``ProviderConfig`` if missing — the
       provider-name set is open per the schema comment, so any string
       is a valid key. The auto-created ``ProviderConfig`` has
       ``rate_limit_per_domain={}`` by default; the next step writes
       into it.
    4. Coerce ``value``:
         - ``None`` → delete the slug entry entirely (the documented
           way to clear a per-domain rate limit — equivalent to "no
           override; the provider bypasses rate-limit gating for this
           domain").
         - ``dict`` → construct a ``RateLimitOverride(**value)``;
           Pydantic's positive-RPM validator
           (:meth:`RateLimitOverride._validate_positive`) catches zero
           / negative caps before the mutation lands.
         - anything else → ``ValueError`` (a stray string from the wire
           shouldn't fail with a confusing Pydantic error).
    5. Prune empty overrides — if every leaf is ``None`` the entry is
       semantically a no-op and shouldn't pollute ``config.json``.
       Mirrors the ``_apply_budget_per_domain`` prune step.
    6. After pruning the slug, if the parent ``ProviderConfig`` is now
       at default state (empty ``rate_limit_per_domain``) AND was
       auto-created by this call (i.e., it didn't exist before), drop
       the empty parent entry too. We approximate "was auto-created"
       by checking whether the post-mutation ``ProviderConfig`` is
       value-equal to a default ``ProviderConfig()`` — defensive
       cleanup so a "set then clear" round-trip leaves the persisted
       shape minimal.

    The function mutates ``config`` IN PLACE — no ``model_copy``, no new
    Config instance.
    """
    parts = key.split(".")
    assert (
        len(parts) == 4
        and parts[0] == "providers"
        and parts[2] == "rate_limit_per_domain"
    ), (
        f"_apply_rate_limit_per_domain called with non-rate-limit-per-domain key {key!r}"
    )
    provider_name = parts[1]
    slug = parts[3]

    if slug not in config.domains:
        raise ValueError(
            f"providers.{provider_name}.rate_limit_per_domain keys {[slug]!r} "
            f"are not in domains {config.domains!r}; remove the override or "
            f"add the domain first."
        )

    providers = config.providers
    provider = providers.get(provider_name)
    if provider is None:
        # Auto-create the parent ``ProviderConfig`` on first set —
        # mirrors the per-slug ``DomainOverride`` auto-create in
        # :func:`_apply_domain_override`. The default ``ProviderConfig``
        # has ``rate_limit_per_domain={}``; the next step writes into
        # it.
        provider = ProviderConfig()
        providers[provider_name] = provider

    rate_limit_map = provider.rate_limit_per_domain

    if value is None:
        # Clear the per-domain rate limit entirely — equivalent to "no
        # override; the provider bypasses rate-limit gating for this
        # domain".
        rate_limit_map.pop(slug, None)
    elif isinstance(value, dict):
        # ``RateLimitOverride(**value)`` raises ``ValidationError`` on a
        # zero / negative RPM (the schema-level positive validator) and
        # on any extra fields (``extra="forbid"``). We let those bubble
        # up as-is so the Settings UI surfaces the canonical Pydantic
        # error voice.
        override = RateLimitOverride(**value)
        if all(getattr(override, f) is None for f in _RATE_LIMIT_OVERRIDE_FIELDS):
            # Prune empty entries — every leaf None is a no-op and
            # shouldn't land in ``config.json``. Mirrors the
            # ``_apply_budget_per_domain`` prune.
            rate_limit_map.pop(slug, None)
        else:
            rate_limit_map[slug] = override
    else:
        raise ValueError(
            f"providers.{provider_name}.rate_limit_per_domain value must be a "
            f"dict (RateLimitOverride payload) or None, got {type(value).__name__}"
        )

    # Drop a now-default parent ``ProviderConfig`` so a "set then clear"
    # round-trip leaves the persisted shape minimal. We compare against
    # a fresh ``ProviderConfig()`` rather than tracking "was auto-created"
    # state — pydantic equality is structural so this is precise.
    if provider == ProviderConfig():
        providers.pop(provider_name, None)


def _check_active_domain_membership(config: Config, value: Any) -> None:
    """Mirror ``Config._check_active_domain_in_domains`` at write time.

    Plan 12 D2 inverted the Plan 07-era exclusion of ``active_domain``
    from ``_SETTABLE_KEYS``. The Plan 10 cross-field validator on
    Config enforces "must be in ``self.domains``"; Plan 16 Task 36
    enabled ``validate_assignment=True`` so the cross-field validator
    DOES now fire on a single-field ``setattr`` — but with a Pydantic
    v2 quirk: a ``model_validator(mode="after")`` raise leaves the
    field mutated to the bad value (only field-level validators roll
    back). The pre-check below runs BEFORE the assignment so the bad
    slug never lands on the live ``Config``, and the error wording
    matches the model validator so the Settings UI surfaces the same
    message regardless of which seam catches it.

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
    # Plan 16 Task 29 / D26 step 4 of 4: ``budget.per_domain.<slug>`` is
    # an open-set wildcard like ``domain_overrides.<slug>.<field>`` —
    # check it BEFORE the static allowlist for the same reason. The
    # 3-segment shape is explicit enough that the secret-substring
    # check can still run on it without false-positives (no leaf field
    # contains "api_key" / "secret" / "token" / "password" — caps are
    # plain numerics — so the substring check stays as a redundant
    # safety net).
    is_budget_per_domain = _is_settable_budget_per_domain_key(key)
    # Plan 16 Task 32 / D27 step 3 of 3:
    # ``providers.<provider>.rate_limit_per_domain.<slug>`` is the
    # third open-set wildcard pattern (mirroring ``budget.per_domain``).
    # The 4-segment shape is explicit enough that the secret-substring
    # check below would still false-negative cleanly: no leaf field
    # contains ``api_key`` / ``secret`` / ``token`` / ``password``
    # (``requests_per_minute`` is a plain integer), so the substring
    # check stays as a redundant safety net for unknown keys but is
    # bypassed (along with the static allowlist) for this wildcard.
    is_rate_limit_per_domain = _is_settable_rate_limit_per_domain_key(key)
    if not (is_domain_override or is_budget_per_domain or is_rate_limit_per_domain):
        if any(s in key.lower() for s in _SECRET_SUBSTRINGS):
            raise PermissionError(f"refusing to set secret-like key {key!r}")
        if key not in _SETTABLE_KEYS:
            raise PermissionError(
                f"key {key!r} is not settable via MCP — settable keys: "
                f"{sorted(_SETTABLE_KEYS)} (plus domain_overrides.<slug>.<field>, "
                f"budget.per_domain.<slug>, and "
                f"providers.<provider>.rate_limit_per_domain.<slug>)"
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
    # Plan 13 Task 1 / D1: a ``None`` config is a lifecycle violation, not a
    # fallback case. The brain_api lifespan (Plan 11 Task 7) and the brain_mcp
    # ``_build_ctx`` (Plan 12 Task 4) are responsible for threading a real
    # Config through; raise ``RuntimeError`` if they haven't, mirroring
    # ``brain_config_get`` (Plan 12 Task 3 / D5). The pre-Plan-13 lenient
    # no-op was a unit-test escape hatch from the era before both wrappers
    # wired Config; production-shape integration tests (Plan 11 lesson 343)
    # post-Plan-12 D6 always supply Config, so the lenient branch was dead
    # code in production.
    raise_if_no_config(ctx, "brain_config_set")
    cfg = ctx.config

    # NOTE on validation: Plan 16 Task 36 / D29 enabled
    # ``validate_assignment=True`` UNCONDITIONALLY on :class:`Config`
    # and every sub-config. An out-of-range or wrong-type value raises
    # ``pydantic.ValidationError`` on the ``setattr`` line below;
    # ``persist_config_or_revert`` catches the exception, restores the
    # snapshot, and re-raises so the caller sees the canonical Pydantic
    # error voice. The positive validation pin
    # (``test_validate_assignment_enforcement`` in
    # ``tests/tools/test_config_set_persists.py``) covers the contract.
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
        elif is_budget_per_domain:
            _apply_budget_per_domain(cfg, key, value)
        elif is_rate_limit_per_domain:
            _apply_rate_limit_per_domain(cfg, key, value)
        else:
            # Plan 12 D2: ``active_domain`` membership is validated here
            # to short-circuit the bad assignment. Plan 16 Task 36 turned
            # ``validate_assignment=True`` on, so ``setattr`` itself now
            # runs the cross-field model_validator — but a Pydantic v2
            # quirk leaves the field MUTATED to the bad value when a
            # ``model_validator(mode="after")`` raises (only field-level
            # validators roll back). The pre-check below runs before the
            # assignment so an orphan slug never lands on the live Config
            # in the first place; the snapshot/revert path still covers
            # the fall-through if anything else raises mid-mutation.
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
