"""Smoke test for brain_core.tools.config_set — ToolResult shape + refusals.

Covers: secret-like refusal, non-settable-key refusal, and a successful
in-memory "updated" write on an allowlisted key. brain_mcp's existing
test_tool_config_get_set.py covers the transport wrapper behavior.

Plan 15 D8: ``_mk_ctx`` requires an explicit ``Config`` — no default, no
Optional union. Refusal-path tests (secret-like, non-allowlisted,
wrong-shape domain-override) still refuse BEFORE the cfg check in
``handle``, so they pass a default ``Config()`` for shape only;
persistence-path tests seed a real ``Config`` whose contents matter (e.g.,
``domains`` membership for domain-override leaves). The None-config raise
behavior is pinned in ``test_errors_raise_if_no_config.py`` (Plan 15 Task 8).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import (
    AutonomyCategoryFlags,
    BudgetOverride,
    Config,
    ProviderConfig,
    RateLimitOverride,
)
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_set import _SETTABLE_KEYS, NAME, handle


def _mk_ctx(vault: Path, *, config: Config) -> ToolContext:
    """Build a ToolContext for config_set tests.

    Plan 15 D8: ``config`` is a required ``Config`` (no default, no Optional
    union). Refusal-path tests (secret-like, non-allowlisted, wrong-shape
    domain-override) refuse BEFORE the cfg-None check in ``handle`` and
    therefore don't depend on the Config's contents — they pass a default
    ``Config()`` for shape only. The None-config raise behavior is pinned
    in ``test_errors_raise_if_no_config.py`` (Plan 15 Task 8); this fixture
    intentionally cannot construct a None-config context.
    """
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=config,
    )


def test_name() -> None:
    assert NAME == "brain_config_set"


def test_settable_keys_match_plan_07_task_4() -> None:
    """Allowlist is deliberately narrow.

    Plan 04 baseline: ``budget.daily_usd`` + ``log_llm_payloads``.
    Plan 07 Task 1: added 5 ``autonomous.<category>`` flags. Plan 16
    Task 39 DROPPED them from the static allowlist — Plan 16 Task 38
    reshaped ``Config.autonomous`` to ``dict[str, AutonomyCategoryFlags]``
    and the legacy flat keys no longer resolve. Plan 16 Task 40 will
    land the replacement ``autonomous.<slug>.<field>`` wildcard
    alongside the Settings UI panel.
    Plan 07 Task 2: adds the 3 per-mode ``{mode}_model`` overrides.
    Plan 07 Task 4: adds ``domain_order`` + 2 ``budget.override_*`` fields.
    Issue #23: adds 3 ``handlers.*`` per-handler tunables.
    Plan 11 Task 7: adds ``privacy_railed`` (whole-list write); the
    open-set ``domain_overrides.<slug>.<field>`` wildcard is matched
    dynamically by ``_is_settable_domain_override_key`` and is NOT in
    this static set.
    Plan 12 D2: adds ``active_domain`` (policy inversion — Settings UI
    is the new persistence path; Plan 10's cross-field validator
    enforces "must be in ``Config.domains``").
    Plan 12 D8 / Task 9: adds ``cross_domain_warning_acknowledged``
    (per-vault acknowledgment for the cross-domain confirmation modal;
    bound by both the modal's "Don't show this again" checkbox and the
    Settings → Domains "Show cross-domain warning" toggle).
    """
    assert (
        frozenset(
            {
                "active_domain",
                "budget.daily_usd",
                "log_llm_payloads",
                "ask_model",
                "brainstorm_model",
                "draft_model",
                "domain_order",
                "budget.override_until",
                "budget.override_delta_usd",
                "handlers.url.timeout_seconds",
                "handlers.tweet.timeout_seconds",
                "handlers.pdf.min_chars",
                "privacy_railed",
                "cross_domain_warning_acknowledged",
            }
        )
        == _SETTABLE_KEYS
    )


def test_settable_keys_all_resolve_to_a_real_schema_field() -> None:
    """Issue #10 regression test — drift watchdog for ``_SETTABLE_KEYS``.

    For every dotted key in the allowlist, walk the path against the live
    Config / ChatSessionConfig pydantic models and assert the leaf is a
    real ``model_fields`` entry. Catches the kind of drift that bit Plan
    04 (commit ``3b107cd``): an allowlist entry that points at a renamed
    or removed schema field is silently allowed past the security check
    and only fails at apply time when persistence finally lands.

    Exceptions are documented inline below — they're keys whose
    persistence path is intentionally deferred (``domain_order`` waits on
    Plan 07 Task 5) or which live on a non-Config schema (the
    ``{ask,brainstorm,draft}_model`` overrides live on ChatSessionConfig
    because they're per-session, not global).
    """
    from brain_core.chat.types import ChatSessionConfig
    from brain_core.config.schema import Config

    # Keys that legitimately don't resolve against Config — see test
    # docstring. Adding to this set requires a comment justifying why the
    # key is allowlisted but not on Config.
    known_not_on_config = {
        # Per-session chat-mode model overrides — live on
        # ``ChatSessionConfig.{ask,brainstorm,draft}_model``, not on the
        # global Config. brain_config_set surfaces them so the Settings
        # UI can write them, but they're applied per-session at chat
        # construction time, not persisted on Config.
        "ask_model": ("ChatSessionConfig", "ask_model"),
        "brainstorm_model": ("ChatSessionConfig", "brainstorm_model"),
        "draft_model": ("ChatSessionConfig", "draft_model"),
        # Plan 07 Task 4: ``domain_order`` is documented as a list[str] of
        # the user's preferred sidebar order; the persistence path is
        # explicitly deferred to Plan 07 Task 5 (see create_domain.py:108).
        # The allowlist entry exists so the Settings page can call
        # brain_config_set on it without raising; the in-memory write is
        # currently a no-op acknowledgement. Resolves to Config when Task
        # 5 lands; until then this exception keeps the drift watchdog
        # honest about WHY it's allowlisted.
        "domain_order": ("PENDING", "Config.domain_order (Plan 07 Task 5)"),
    }

    def _resolve(model: type, dotted: str) -> object:
        """Walk a dotted path against pydantic model_fields. Returns the
        leaf field info or raises KeyError with the failing segment."""
        parts = dotted.split(".")
        current_model: type = model
        for i, part in enumerate(parts):
            fields = getattr(current_model, "model_fields", None)
            if fields is None or part not in fields:
                raise KeyError(
                    f"key {dotted!r} does not resolve: "
                    f"segment {parts[i]!r} not in {current_model.__name__}.model_fields"
                )
            field_info = fields[part]
            if i == len(parts) - 1:
                return field_info
            # Descend into nested model.
            annotation = field_info.annotation
            if not isinstance(annotation, type):
                raise KeyError(
                    f"key {dotted!r}: cannot descend through non-class "
                    f"annotation {annotation!r} at segment {part!r}"
                )
            current_model = annotation
        return None  # pragma: no cover — loop always returns

    unresolved: list[str] = []
    for key in sorted(_SETTABLE_KEYS):
        if key in known_not_on_config:
            continue
        try:
            _resolve(Config, key)
        except KeyError as exc:
            unresolved.append(f"{key!r} → {exc}")

    assert not unresolved, (
        "Some keys in _SETTABLE_KEYS no longer resolve to real schema "
        "fields. Add the field to Config (or document the exception in "
        "known_not_on_config with a justification):\n  " + "\n  ".join(unresolved)
    )

    # Sanity-check the exceptions still resolve where they're documented
    # to live (so the exception itself doesn't rot).
    for key, (where, _explanation) in known_not_on_config.items():
        if where == "ChatSessionConfig":
            assert key in ChatSessionConfig.model_fields, (
                f"exception for {key!r} claims it lives on ChatSessionConfig "
                f"but the field is no longer there"
            )
        # PENDING entries don't resolve anywhere yet — that's the point.


async def test_allows_handler_config_keys(tmp_path: Path) -> None:
    """Issue #23: ``handlers.<handler>.<field>`` paths flow through the
    allowlist + secret-substring check without raising. Plan 13 Task 1 /
    D1: persisted keys require a real ``Config`` on the context; the
    handler keys round-trip through ``persist_config_or_revert``.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, config=cfg)
    for key, value in (
        ("handlers.url.timeout_seconds", 60.0),
        ("handlers.tweet.timeout_seconds", 5.0),
        ("handlers.pdf.min_chars", 50),
    ):
        result = await handle({"key": key, "value": value}, ctx)
        assert result.data is not None
        assert result.data["status"] == "updated"
        assert result.data["key"] == key
        assert result.data["value"] == value


async def test_refuses_secret_like_key(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="secret-like"):
        await handle(
            {"key": "llm.api_key", "value": "nope"},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_refuses_non_allowlisted_vault_path(tmp_path: Path) -> None:
    """``vault_path`` is permanently non-settable via MCP — clients must
    not reroot the vault from a tool call (see ``_SETTABLE_KEYS`` comment).
    Was previously ``active_domain``; Plan 12 D2 added ``active_domain``
    to the allowlist, so this test was retargeted to the next-best
    permanently-excluded Config field.
    """
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "vault_path", "value": "/tmp/elsewhere"},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_domain_override_keys_pass_allowlist_via_wildcard(tmp_path: Path) -> None:
    """Plan 11 Task 7: ``domain_overrides.<slug>.<field>`` is a wildcard
    pattern, not a static ``_SETTABLE_KEYS`` entry. Each leaf field on
    DomainOverride should flow through the allowlist gate without
    raising. The actual mutation behavior is covered in
    ``test_config_set_persists.py``; this test only proves the security
    gate accepts the open-set shape.

    Plan 13 Task 1 / D1: a real ``Config`` is now required for the
    persistence branch. ``hobby`` must be in ``Config.domains`` because
    ``_apply_domain_override`` enforces slug-membership.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    for field in ("classify_model", "default_model", "temperature", "max_output_tokens"):
        result = await handle(
            {"key": f"domain_overrides.hobby.{field}", "value": None},
            ctx,
        )
        assert result.data is not None
        assert result.data["status"] == "updated"


async def test_domain_override_rejects_unknown_field(tmp_path: Path) -> None:
    """An unknown leaf field doesn't match the wildcard and is rejected
    at the static-allowlist gate. Without the third-segment field check
    in ``_is_settable_domain_override_key`` an attacker could write
    ``domain_overrides.x.api_key`` and bypass the secret-substring
    check (the substring check would catch ``api_key`` first, but the
    field-allowlist is the real defense)."""
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "domain_overrides.hobby.unknown_field", "value": "x"},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_budget_per_domain_keys_pass_allowlist_via_wildcard(tmp_path: Path) -> None:
    """Plan 16 Task 29 / D26 step 4 of 4: ``budget.per_domain.<slug>``
    is a wildcard pattern, not a static ``_SETTABLE_KEYS`` entry. A
    whole-payload write (``BudgetOverride`` dict) should flow through
    the allowlist gate without raising and land on
    ``Config.budget.per_domain[slug]``.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {
            "key": "budget.per_domain.hobby",
            "value": {"daily_cap_usd": 1.0, "monthly_cap_usd": 10.0},
        },
        ctx,
    )
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert result.data["persisted"] is True
    assert "hobby" in cfg.budget.per_domain
    assert cfg.budget.per_domain["hobby"].daily_cap_usd == 1.0
    assert cfg.budget.per_domain["hobby"].monthly_cap_usd == 10.0


async def test_budget_per_domain_clear_with_none_drops_entry(tmp_path: Path) -> None:
    """``None`` is the documented "no override" sentinel — posting it
    drops the slug entry from ``Config.budget.per_domain`` entirely."""
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.budget.per_domain["hobby"] = BudgetOverride(daily_cap_usd=2.0)
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {"key": "budget.per_domain.hobby", "value": None},
        ctx,
    )
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert "hobby" not in cfg.budget.per_domain


async def test_budget_per_domain_prunes_all_none_payload(tmp_path: Path) -> None:
    """A payload where both caps are ``None`` is semantically a no-op
    (same as "no entry") — the apply helper prunes it rather than
    writing an empty ``BudgetOverride()`` to disk. Mirrors the
    ``_apply_domain_override`` prune-empty behaviour."""
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.budget.per_domain["hobby"] = BudgetOverride(daily_cap_usd=2.0)
    ctx = _mk_ctx(tmp_path, config=cfg)
    await handle(
        {
            "key": "budget.per_domain.hobby",
            "value": {"daily_cap_usd": None, "monthly_cap_usd": None},
        },
        ctx,
    )
    assert "hobby" not in cfg.budget.per_domain


async def test_budget_per_domain_rejects_orphan_slug(tmp_path: Path) -> None:
    """Slug must be in ``Config.domains``. Mirrors the
    ``_apply_domain_override`` orphan-slug guard so the Settings UI
    surfaces a consistent error voice for both override paths."""
    cfg = Config(domains=["research", "personal"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(ValueError, match="not in domains"):
        await handle(
            {
                "key": "budget.per_domain.ghost",
                "value": {"daily_cap_usd": 1.0},
            },
            ctx,
        )


async def test_budget_per_domain_rejects_zero_or_negative_cap(tmp_path: Path) -> None:
    """The schema-level ``BudgetOverride._validate_positive`` rejects
    zero / negative caps. Construction inside ``_apply_budget_per_domain``
    raises ``ValidationError`` which propagates as-is — the Settings UI
    surfaces the canonical Pydantic voice."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(Exception, match="positive"):
        await handle(
            {
                "key": "budget.per_domain.hobby",
                "value": {"daily_cap_usd": 0.0},
            },
            ctx,
        )


async def test_budget_per_domain_rejects_wrong_segment_count(tmp_path: Path) -> None:
    """Two-segment ``budget.per_domain`` (would shadow the dict itself)
    and four-segment ``budget.per_domain.hobby.daily_cap_usd`` (would
    suggest a per-leaf path that the wildcard does NOT support) both
    fail the wildcard shape check and hit the static-allowlist gate."""
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "budget.per_domain", "value": {}},
            _mk_ctx(tmp_path, config=Config()),
        )
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "budget.per_domain.hobby.daily_cap_usd", "value": 1.0},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_budget_per_domain_rejects_non_dict_value(tmp_path: Path) -> None:
    """A stray string / number / list value (the wire could carry
    anything) raises a clear ``ValueError`` rather than a confusing
    Pydantic validation error."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(ValueError, match="must be a dict"):
        await handle(
            {"key": "budget.per_domain.hobby", "value": "not a dict"},
            ctx,
        )


async def test_rate_limit_per_domain_keys_pass_allowlist_via_wildcard(
    tmp_path: Path,
) -> None:
    """Plan 16 Task 32 / D27 step 3 of 3:
    ``providers.<provider>.rate_limit_per_domain.<slug>`` is a 4-segment
    wildcard pattern, not a static ``_SETTABLE_KEYS`` entry. A
    whole-payload write (``RateLimitOverride`` dict) should flow through
    the allowlist gate without raising and land on
    ``Config.providers[<provider>].rate_limit_per_domain[slug]`` — with
    the parent ``ProviderConfig`` auto-created on first set."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {
            "key": "providers.anthropic.rate_limit_per_domain.hobby",
            "value": {"requests_per_minute": 30},
        },
        ctx,
    )
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert result.data["persisted"] is True
    assert "anthropic" in cfg.providers
    assert "hobby" in cfg.providers["anthropic"].rate_limit_per_domain
    assert (
        cfg.providers["anthropic"].rate_limit_per_domain["hobby"].requests_per_minute
        == 30
    )


async def test_rate_limit_per_domain_clear_with_none_drops_entry(
    tmp_path: Path,
) -> None:
    """``None`` is the documented "no override" sentinel — posting it
    drops the slug entry from
    ``Config.providers[<provider>].rate_limit_per_domain`` entirely.
    Mirrors :func:`test_budget_per_domain_clear_with_none_drops_entry`."""
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.providers["anthropic"] = ProviderConfig(
        rate_limit_per_domain={
            "hobby": RateLimitOverride(requests_per_minute=20),
            "research": RateLimitOverride(requests_per_minute=60),
        }
    )
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {
            "key": "providers.anthropic.rate_limit_per_domain.hobby",
            "value": None,
        },
        ctx,
    )
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert "hobby" not in cfg.providers["anthropic"].rate_limit_per_domain
    # The provider entry is still around because ``research`` still
    # has a rate-limit override — the parent prune is gated on
    # "default state".
    assert "anthropic" in cfg.providers


async def test_rate_limit_per_domain_prunes_empty_provider_after_clear(
    tmp_path: Path,
) -> None:
    """Clearing the LAST per-domain rate-limit entry under a provider
    drops the now-default ``ProviderConfig`` from ``Config.providers``
    entirely so a "set then clear" round-trip leaves the persisted
    shape minimal."""
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.providers["anthropic"] = ProviderConfig(
        rate_limit_per_domain={"hobby": RateLimitOverride(requests_per_minute=20)}
    )
    ctx = _mk_ctx(tmp_path, config=cfg)
    await handle(
        {
            "key": "providers.anthropic.rate_limit_per_domain.hobby",
            "value": None,
        },
        ctx,
    )
    # Last slug entry gone -> the parent provider entry is also pruned
    # because the post-mutation ``ProviderConfig`` equals
    # ``ProviderConfig()`` (default state).
    assert "anthropic" not in cfg.providers


async def test_rate_limit_per_domain_prunes_all_none_payload(tmp_path: Path) -> None:
    """A payload where the only leaf is ``None`` (i.e.,
    ``{"requests_per_minute": None}``) is semantically a no-op (same as
    "no entry") — the apply helper prunes it rather than writing an
    empty ``RateLimitOverride()`` to disk. Mirrors the
    ``_apply_budget_per_domain`` prune-empty behaviour."""
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.providers["anthropic"] = ProviderConfig(
        rate_limit_per_domain={"hobby": RateLimitOverride(requests_per_minute=20)}
    )
    ctx = _mk_ctx(tmp_path, config=cfg)
    await handle(
        {
            "key": "providers.anthropic.rate_limit_per_domain.hobby",
            "value": {"requests_per_minute": None},
        },
        ctx,
    )
    # Slug pruned -> parent provider also pruned (default-state check).
    assert "anthropic" not in cfg.providers


async def test_rate_limit_per_domain_rejects_orphan_slug(tmp_path: Path) -> None:
    """Slug must be in ``Config.domains``. Mirrors the
    ``_apply_budget_per_domain`` orphan-slug guard so the Settings UI
    surfaces a consistent error voice for both per-domain override
    paths."""
    cfg = Config(domains=["research", "personal"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(ValueError, match="not in domains"):
        await handle(
            {
                "key": "providers.anthropic.rate_limit_per_domain.ghost",
                "value": {"requests_per_minute": 60},
            },
            ctx,
        )


async def test_rate_limit_per_domain_rejects_zero_or_negative_rpm(
    tmp_path: Path,
) -> None:
    """The schema-level ``RateLimitOverride._validate_positive`` rejects
    zero / negative ``requests_per_minute``. Construction inside
    ``_apply_rate_limit_per_domain`` raises ``ValidationError`` which
    propagates as-is — the Settings UI surfaces the canonical Pydantic
    voice."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(Exception, match="positive"):
        await handle(
            {
                "key": "providers.anthropic.rate_limit_per_domain.hobby",
                "value": {"requests_per_minute": 0},
            },
            ctx,
        )


async def test_rate_limit_per_domain_rejects_wrong_segment_count(
    tmp_path: Path,
) -> None:
    """Three-segment ``providers.anthropic.rate_limit_per_domain`` (would
    shadow the dict itself) and five-segment
    ``providers.anthropic.rate_limit_per_domain.hobby.requests_per_minute``
    (would suggest a per-leaf path the wildcard does NOT support) both
    fail the wildcard shape check and hit the static-allowlist gate."""
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {
                "key": "providers.anthropic.rate_limit_per_domain",
                "value": {},
            },
            _mk_ctx(tmp_path, config=Config()),
        )
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {
                "key": (
                    "providers.anthropic.rate_limit_per_domain.hobby."
                    "requests_per_minute"
                ),
                "value": 60,
            },
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_rate_limit_per_domain_rejects_non_dict_value(tmp_path: Path) -> None:
    """A stray string / number / list value (the wire could carry
    anything) raises a clear ``ValueError`` rather than a confusing
    Pydantic validation error."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(ValueError, match="must be a dict"):
        await handle(
            {
                "key": "providers.anthropic.rate_limit_per_domain.hobby",
                "value": "not a dict",
            },
            ctx,
        )


async def test_rate_limit_per_domain_auto_creates_new_provider_entry(
    tmp_path: Path,
) -> None:
    """Setting an override under a never-before-seen provider key
    auto-creates the parent ``ProviderConfig``. Mirrors the per-slug
    auto-create in :func:`_apply_domain_override`."""
    cfg = Config(domains=["research", "personal", "hobby"])
    assert cfg.providers == {}
    ctx = _mk_ctx(tmp_path, config=cfg)
    await handle(
        {
            "key": "providers.anthropic.rate_limit_per_domain.hobby",
            "value": {"requests_per_minute": 45},
        },
        ctx,
    )
    assert set(cfg.providers.keys()) == {"anthropic"}
    assert (
        cfg.providers["anthropic"].rate_limit_per_domain["hobby"].requests_per_minute
        == 45
    )


async def test_domain_override_rejects_wrong_segment_count(tmp_path: Path) -> None:
    """Two-segment ``domain_overrides.hobby`` and four-segment
    ``domain_overrides.hobby.foo.bar`` both fail the wildcard shape
    check and end up at the static-allowlist gate.
    """
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "domain_overrides.hobby", "value": {}},
            _mk_ctx(tmp_path, config=Config()),
        )
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "domain_overrides.hobby.foo.bar", "value": "x"},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_allows_budget_daily_usd(tmp_path: Path) -> None:
    """Plan 13 Task 1 / D1: persisted keys (``budget.daily_usd`` is a
    real Config field) require a real ``Config`` on the context; the
    response carries ``persisted=True`` once the round-trip lands on
    disk via ``persist_config_or_revert``.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {"key": "budget.daily_usd", "value": 5.0},
        ctx,
    )

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert result.data["persisted"] is True
    assert result.data["value"] == 5.0


# ----------------------------------------------------------------
# Plan 16 Task 40 / D30 step 4 of 4 — autonomous.<slug>.<field> wildcard
# ----------------------------------------------------------------


async def test_autonomous_per_domain_keys_pass_allowlist_via_wildcard(
    tmp_path: Path,
) -> None:
    """Plan 16 Task 40 / D30 step 4 of 4: ``autonomous.<slug>.<field>`` is
    a wildcard pattern, not a static ``_SETTABLE_KEYS`` entry. Setting a
    leaf flag on a never-before-seen slug auto-creates the per-slug
    :class:`AutonomyCategoryFlags` and lands the requested value (other
    fields default to ``False`` per the schema — CLAUDE.md principle #3).
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {"key": "autonomous.research.new_files", "value": True},
        ctx,
    )
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert result.data["persisted"] is True
    assert "research" in cfg.autonomous
    flags = cfg.autonomous["research"]
    assert flags.new_files is True
    # Other fields stay at their schema defaults (False).
    assert flags.edits is False
    assert flags.index_entries is False
    assert flags.concepts is False
    assert flags.draft is False


async def test_autonomous_per_domain_mutates_existing_entry(tmp_path: Path) -> None:
    """A second set on the same slug mutates the existing
    :class:`AutonomyCategoryFlags` rather than constructing a new one
    that overwrites prior flags. Plan 16 Task 36's
    ``validate_assignment=True`` runs the field-level bool validator on
    the setattr.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.autonomous["research"] = AutonomyCategoryFlags(new_files=True)
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {"key": "autonomous.research.edits", "value": True},
        ctx,
    )
    assert result.data is not None
    assert result.data["status"] == "updated"
    flags = cfg.autonomous["research"]
    # Both prior and new flags are True — the second set didn't blow
    # away ``new_files`` by reconstructing a fresh AutonomyCategoryFlags.
    assert flags.new_files is True
    assert flags.edits is True
    # Untouched fields stay at default.
    assert flags.index_entries is False


async def test_autonomous_per_domain_rejects_orphan_slug(tmp_path: Path) -> None:
    """Slug must be in ``Config.domains``. Mirrors the
    ``_apply_domain_override`` / ``_apply_budget_per_domain`` orphan-slug
    guards so the Settings UI surfaces a consistent error voice across
    every per-domain wildcard. The Plan 16 Task 38 cross-field validator
    (``_check_autonomous_keys_in_domains``) on Config catches the same
    case at persist time, but the apply-helper guard fires first so the
    user gets the canonical "not in domains" wording rather than a
    Pydantic ``ValidationError`` from the writer.
    """
    cfg = Config(domains=["research", "personal"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(ValueError, match="not in domains"):
        await handle(
            {"key": "autonomous.ghost-domain.new_files", "value": True},
            ctx,
        )


async def test_autonomous_per_domain_rejects_unknown_field(tmp_path: Path) -> None:
    """An unknown leaf field doesn't match the wildcard's third-segment
    allowlist (``_AUTONOMY_FIELDS``) and falls through to the static
    ``_SETTABLE_KEYS`` gate, which raises ``PermissionError``. Mirrors
    :func:`test_domain_override_rejects_unknown_field` — the field
    allowlist is the real defense for this open-set wildcard.
    """
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "autonomous.research.bogus_field", "value": True},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_autonomous_per_domain_set_false_persists(tmp_path: Path) -> None:
    """Posting ``False`` for a flag explicitly clears it. The mutation
    path uses ``setattr`` on the existing entry so the assignment is
    applied even when the flag was already False (a no-op assignment is
    safe — ``validate_assignment=True`` re-runs the bool validator
    cheaply).
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.autonomous["research"] = AutonomyCategoryFlags(new_files=True, edits=True)
    ctx = _mk_ctx(tmp_path, config=cfg)
    await handle(
        {"key": "autonomous.research.new_files", "value": False},
        ctx,
    )
    # ``new_files`` was True, now False; ``edits`` (untouched) stays True
    # so the entry is NOT pruned (see prune-empty test below).
    flags = cfg.autonomous["research"]
    assert flags.new_files is False
    assert flags.edits is True


async def test_autonomous_per_domain_prunes_all_false_entry(tmp_path: Path) -> None:
    """When the post-mutation entry has every field at ``False`` (the
    schema default), the slug is dropped from ``Config.autonomous`` so
    a "set then reset every flag" round-trip leaves the persisted shape
    minimal. Mirrors the prune step in
    :func:`_apply_domain_override` and :func:`_apply_budget_per_domain`.
    The gate (:func:`brain_core.autonomy.should_auto_apply`) treats a
    missing slug entry the same as an explicit all-False entry, so the
    prune is semantically a no-op.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg.autonomous["research"] = AutonomyCategoryFlags(new_files=True)
    ctx = _mk_ctx(tmp_path, config=cfg)
    await handle(
        {"key": "autonomous.research.new_files", "value": False},
        ctx,
    )
    # Post-mutation every field is False -> entry pruned.
    assert "research" not in cfg.autonomous


async def test_autonomous_per_domain_rejects_non_bool_value(tmp_path: Path) -> None:
    """A stray string / number / None value (the wire could carry
    anything) raises a clear ``ValueError`` rather than letting an
    awkward Pydantic error surface to the Settings UI.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    with pytest.raises(ValueError, match="must be bool"):
        await handle(
            {"key": "autonomous.research.new_files", "value": "yes"},
            ctx,
        )


async def test_autonomous_per_domain_rejects_wrong_segment_count(
    tmp_path: Path,
) -> None:
    """Two-segment ``autonomous.research`` (would shadow the dict) and
    four-segment ``autonomous.research.new_files.extra`` (would suggest a
    nested path that doesn't exist) both fail the wildcard shape check
    and hit the static-allowlist gate.
    """
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "autonomous.research", "value": {}},
            _mk_ctx(tmp_path, config=Config()),
        )
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "autonomous.research.new_files.extra", "value": True},
            _mk_ctx(tmp_path, config=Config()),
        )


async def test_autonomous_per_domain_field_allowlist_matches_schema() -> None:
    """The wildcard's leaf-field allowlist must equal
    :class:`AutonomyCategoryFlags.model_fields` exactly — drift watchdog.
    Adding a new flag to the schema without updating the wildcard would
    silently make the new flag NON-settable from the Settings UI; adding
    a flag to the wildcard without a matching schema field would let an
    invalid setattr land at apply time and fail with a confusing error.
    """
    from brain_core.config.schema import AutonomyCategoryFlags
    from brain_core.tools.config_set import _AUTONOMY_FIELDS

    assert frozenset(AutonomyCategoryFlags.model_fields.keys()) == _AUTONOMY_FIELDS


def test_non_persisted_keys_match_known_not_on_config_watchdog() -> None:
    """The production ``_NON_PERSISTED_KEYS`` set must match the test's
    ``known_not_on_config`` drift watchdog set, otherwise the two will
    diverge silently as Plan 11+ adds new keys.

    Without this assertion, a future addition to the production allowlist
    that should also be a non-persisted key (or vice versa) would slip
    past review — the schema-vs-allowlist watchdog would still pass
    because the test-side set acts as an allowlist of known exceptions,
    and production code would still run, but the two sets would drift
    until the next code-quality pass caught them.
    """
    from brain_core.tools.config_set import _NON_PERSISTED_KEYS

    # Re-derive the test-side keys by running the same known_not_on_config
    # logic but stripping the per-key explanation tuples. The test-side
    # set is defined inline inside ``test_settable_keys_all_resolve_to_a_real_schema_field``
    # — keeping the watchdog source-of-truth here means the two stay
    # mechanically tied even if either side moves.
    known_not_on_config = {
        "ask_model",
        "brainstorm_model",
        "draft_model",
        "domain_order",
    }
    assert known_not_on_config == _NON_PERSISTED_KEYS, (
        "_NON_PERSISTED_KEYS (production) and known_not_on_config (test) drifted: "
        f"in production not test: {_NON_PERSISTED_KEYS - known_not_on_config}; "
        f"in test not production: {known_not_on_config - _NON_PERSISTED_KEYS}"
    )
