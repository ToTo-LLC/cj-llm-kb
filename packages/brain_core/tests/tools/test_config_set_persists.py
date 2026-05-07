"""Plan 11 Task 4 — brain_config_set persists Config-resolving keys to disk.

Persisted keys round-trip via load_config; non-persisted keys
(``ask_model``, ``brainstorm_model``, ``draft_model``, ``domain_order``)
return ``persisted=False`` and never touch ``config.json``.
"""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from brain_core.config.writer import ConfigPersistenceError
from brain_core.tools.base import ToolContext
from brain_core.tools.config_set import handle


def _mk_ctx(vault: Path, cfg: Config | None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research", "personal"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=cfg,
    )


async def test_top_level_key_persists(tmp_path: Path) -> None:
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "log_llm_payloads", "value": True}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.log_llm_payloads is True

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.log_llm_payloads is True


async def test_nested_key_persists(tmp_path: Path) -> None:
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "budget.daily_usd", "value": 7.5}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.budget.daily_usd == pytest.approx(7.5)

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.budget.daily_usd == pytest.approx(7.5)


async def test_handlers_nested_key_persists(tmp_path: Path) -> None:
    """Issue #23 keys live two levels deep on Config — exercise the
    deeper dotted path through ``_resolve_parent_and_field``.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "handlers.url.timeout_seconds", "value": 60.0}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.handlers.url.timeout_seconds == pytest.approx(60.0)

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.handlers.url.timeout_seconds == pytest.approx(60.0)


async def test_save_failure_reverts_in_memory_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config()
    pre = cfg.log_llm_payloads
    ctx = _mk_ctx(tmp_path, cfg)

    def boom(_config: Config, _vault_root: Path, **_kw: object) -> Path:
        raise ConfigPersistenceError("disk failed", cause="io_error")

    monkeypatch.setattr("brain_core.config.writer.save_config", boom)

    with pytest.raises(ConfigPersistenceError, match="disk failed"):
        await handle({"key": "log_llm_payloads", "value": True}, ctx)

    # In-memory mutation reverted.
    assert cfg.log_llm_payloads == pre
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_persistence_propagates_structured_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config()
    target = tmp_path / ".brain" / "config.json"

    def boom(_config: Config, _vault_root: Path, **_kw: object) -> Path:
        raise ConfigPersistenceError(
            "lock contention",
            attempted_path=target,
            cause="lock_timeout",
        )

    monkeypatch.setattr("brain_core.config.writer.save_config", boom)

    ctx = _mk_ctx(tmp_path, cfg)
    with pytest.raises(ConfigPersistenceError) as exc_info:
        await handle({"key": "log_llm_payloads", "value": True}, ctx)
    assert exc_info.value.cause == "lock_timeout"
    assert exc_info.value.attempted_path == target


async def test_non_persisted_keys_skip_save(tmp_path: Path) -> None:
    """``ask_model`` / ``brainstorm_model`` / ``draft_model`` live on
    ``ChatSessionConfig``, not Config — and ``domain_order`` is pending a
    Config field. All four return ``persisted=False`` and never touch
    config.json.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    for key in ("ask_model", "brainstorm_model", "draft_model"):
        result = await handle({"key": key, "value": "claude-haiku-4"}, ctx)
        assert result.data is not None
        assert result.data["persisted"] is False

    result = await handle({"key": "domain_order", "value": ["work", "research"]}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is False

    # No config.json written for any of them.
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_no_config_attached_raises_runtime_error(tmp_path: Path) -> None:
    """Plan 13 Task 1 / D1: ``ctx.config=None`` is a lifecycle violation,
    not a fallback case. The pre-Plan-13 lenient no-op (which returned
    ``persisted=False``) was a unit-test escape hatch from the era
    before both wrappers wired Config; post-Plan 12 D6, every
    production-shape path supplies Config, and the lenient branch was
    dead code. Mirrors ``brain_config_get``'s strict policy.
    """
    ctx = _mk_ctx(tmp_path, None)
    with pytest.raises(RuntimeError, match=r"ctx\.config to be a Config"):
        await handle({"key": "log_llm_payloads", "value": True}, ctx)
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_domain_override_dict_walk_creates_entry_and_persists(tmp_path: Path) -> None:
    """Plan 11 Task 7: ``domain_overrides.<slug>.<field>`` writes auto-
    create the per-slug DomainOverride if absent, then persist. The
    Config instance reference must remain identical across the call
    (in-place mutation; no model_copy in the dispatch path)."""
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg_id_before = id(cfg)
    ctx = _mk_ctx(tmp_path, cfg)

    # No prior override for "hobby" — auto-create on first set.
    assert "hobby" not in cfg.domain_overrides

    result = await handle(
        {"key": "domain_overrides.hobby.classify_model", "value": "claude-haiku-4-5-20251001"},
        ctx,
    )
    assert result.data is not None
    assert result.data["persisted"] is True
    # Config instance identity preserved (Plan 11 Task 6 reviewer note).
    assert id(cfg) == cfg_id_before
    assert "hobby" in cfg.domain_overrides
    assert cfg.domain_overrides["hobby"].classify_model == "claude-haiku-4-5-20251001"
    # Other fields still default (None) — auto-create yielded a fresh
    # DomainOverride() before the targeted setattr.
    assert cfg.domain_overrides["hobby"].default_model is None

    # Round-trip via load_config.
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.domain_overrides["hobby"].classify_model == "claude-haiku-4-5-20251001"


async def test_domain_override_reset_to_global_clears_field(tmp_path: Path) -> None:
    """Setting a field to None clears that override (returns to global).
    When the LAST set field clears, the slug entry is pruned entirely
    so config.json doesn't carry empty {} objects."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, cfg)

    # Seed two override fields.
    await handle(
        {"key": "domain_overrides.hobby.classify_model", "value": "haiku-X"},
        ctx,
    )
    await handle({"key": "domain_overrides.hobby.temperature", "value": 0.7}, ctx)
    assert cfg.domain_overrides["hobby"].classify_model == "haiku-X"
    assert cfg.domain_overrides["hobby"].temperature == pytest.approx(0.7)

    # Reset one field — slug entry stays.
    await handle(
        {"key": "domain_overrides.hobby.classify_model", "value": None},
        ctx,
    )
    assert "hobby" in cfg.domain_overrides
    assert cfg.domain_overrides["hobby"].classify_model is None
    assert cfg.domain_overrides["hobby"].temperature == pytest.approx(0.7)

    # Reset the last remaining field — slug entry is pruned.
    await handle({"key": "domain_overrides.hobby.temperature", "value": None}, ctx)
    assert "hobby" not in cfg.domain_overrides

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "hobby" not in rehydrated.domain_overrides


async def test_domain_override_rejects_orphan_slug(tmp_path: Path) -> None:
    """Plan 11 D8 / D12: ``domain_overrides.<slug>`` keys must reference
    a slug that exists in ``Config.domains``. The pre-check in
    _apply_domain_override raises ValueError so the user gets immediate
    feedback rather than waiting for the next ``load_config`` to fail.
    Persist must NOT happen on this path."""
    cfg = Config(domains=["research", "work", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    with pytest.raises(ValueError, match="not in domains"):
        await handle(
            {"key": "domain_overrides.ghost.classify_model", "value": "haiku-X"},
            ctx,
        )

    # Live Config not mutated.
    assert "ghost" not in cfg.domain_overrides
    # No config.json written.
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_budget_per_domain_whole_payload_persists(tmp_path: Path) -> None:
    """Plan 16 Task 29 / D26 step 4 of 4: ``budget.per_domain.<slug>``
    writes a whole :class:`BudgetOverride` payload at once and round-
    trips through ``load_config`` with both caps preserved.

    The Config instance reference must remain identical across the call
    (in-place dict mutation on ``Config.budget.per_domain``; no
    ``model_copy`` in the dispatch path) — same invariant as
    ``test_domain_override_dict_walk_creates_entry_and_persists``.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    cfg_id_before = id(cfg)
    ctx = _mk_ctx(tmp_path, cfg)

    assert "hobby" not in cfg.budget.per_domain

    result = await handle(
        {
            "key": "budget.per_domain.hobby",
            "value": {"daily_cap_usd": 1.5, "monthly_cap_usd": 30.0},
        },
        ctx,
    )
    assert result.data is not None
    assert result.data["persisted"] is True
    # Config instance identity preserved.
    assert id(cfg) == cfg_id_before
    assert "hobby" in cfg.budget.per_domain
    assert cfg.budget.per_domain["hobby"].daily_cap_usd == pytest.approx(1.5)
    assert cfg.budget.per_domain["hobby"].monthly_cap_usd == pytest.approx(30.0)

    # Round-trip via load_config.
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "hobby" in rehydrated.budget.per_domain
    assert rehydrated.budget.per_domain["hobby"].daily_cap_usd == pytest.approx(1.5)
    assert rehydrated.budget.per_domain["hobby"].monthly_cap_usd == pytest.approx(30.0)


async def test_budget_per_domain_partial_cap_persists(tmp_path: Path) -> None:
    """Setting only one cap (the other absent / None) is supported —
    the absent leaf stays None. Mirrors how the Settings UI sends a
    partial save when the user only fills one of the two inputs."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, cfg)

    await handle(
        {
            "key": "budget.per_domain.hobby",
            "value": {"daily_cap_usd": 2.0, "monthly_cap_usd": None},
        },
        ctx,
    )
    assert cfg.budget.per_domain["hobby"].daily_cap_usd == pytest.approx(2.0)
    assert cfg.budget.per_domain["hobby"].monthly_cap_usd is None

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.budget.per_domain["hobby"].daily_cap_usd == pytest.approx(2.0)
    assert rehydrated.budget.per_domain["hobby"].monthly_cap_usd is None


async def test_budget_per_domain_clear_with_none_round_trips(tmp_path: Path) -> None:
    """Posting ``None`` drops the slug entry, and the dropped state
    persists across a ``load_config`` round-trip (config.json carries
    no ``hobby`` entry)."""
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, cfg)

    # Seed an override.
    await handle(
        {
            "key": "budget.per_domain.hobby",
            "value": {"daily_cap_usd": 1.0},
        },
        ctx,
    )
    assert "hobby" in cfg.budget.per_domain

    # Clear it.
    await handle(
        {"key": "budget.per_domain.hobby", "value": None},
        ctx,
    )
    assert "hobby" not in cfg.budget.per_domain

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "hobby" not in rehydrated.budget.per_domain


async def test_budget_per_domain_orphan_slug_does_not_persist(tmp_path: Path) -> None:
    """``ghost`` is not in ``Config.domains`` — the apply helper raises
    before persistence, leaving config.json unwritten."""
    cfg = Config(domains=["research", "work", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    with pytest.raises(ValueError, match="not in domains"):
        await handle(
            {
                "key": "budget.per_domain.ghost",
                "value": {"daily_cap_usd": 1.0},
            },
            ctx,
        )

    assert "ghost" not in cfg.budget.per_domain
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_privacy_railed_whole_list_persists(tmp_path: Path) -> None:
    """Plan 11 D10/D11: ``privacy_railed`` is written as a whole list
    via ``brain_config_set``. ``personal`` must remain in the list (the
    Config validator enforces this on save)."""
    cfg = Config(domains=["research", "personal", "journal"])
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle(
        {"key": "privacy_railed", "value": ["personal", "journal"]},
        ctx,
    )
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.privacy_railed == ["personal", "journal"]

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.privacy_railed == ["personal", "journal"]


async def test_privacy_railed_removing_personal_raises_on_assignment(tmp_path: Path) -> None:
    """Plan 16 Task 36 / D29: ``validate_assignment=True`` makes
    removing ``personal`` from ``privacy_railed`` raise
    ``pydantic.ValidationError`` at assignment time.

    Previously a KNOWN-LIMITATION pin
    (``test_privacy_railed_removing_personal_load_rejects``) — the
    in-memory mutation went through silently and only ``load_config``
    on the persisted file caught it. Flipped here to a positive
    validation pin alongside ``test_validate_assignment_enforcement``
    per the locked decision: the field-level validator
    (:meth:`Config._check_privacy_railed`) now fires on every
    ``setattr``, so the bad list never reaches the live Config or the
    on-disk ``config.json``.
    """
    cfg = Config(domains=["research", "personal", "journal"])
    pre_value = list(cfg.privacy_railed)
    ctx = _mk_ctx(tmp_path, cfg)

    with pytest.raises(pydantic.ValidationError):
        await handle({"key": "privacy_railed", "value": ["journal"]}, ctx)

    # Live Config not mutated.
    assert cfg.privacy_railed == pre_value
    # No config.json written — save_config never ran.
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_active_domain_settable_round_trip(tmp_path: Path) -> None:
    """Plan 12 D2 / Task 6: ``active_domain`` is now settable via
    ``brain_config_set``. Round-trip via ``load_config`` proves the
    in-memory mutation AND on-disk persistence both land cleanly.

    Mirrors ``test_top_level_key_persists`` but exercises the policy
    inversion: pre-Plan-12 this call would have raised PermissionError
    ("not settable"); post-inversion it joins the standard persisted
    path with the explicit cross-field membership pre-check.
    """
    cfg = Config(domains=["research", "personal", "work"], active_domain="research")
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "active_domain", "value": "work"}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.active_domain == "work"

    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.active_domain == "work"


async def test_active_domain_must_be_in_domains(tmp_path: Path) -> None:
    """Plan 12 D2: setting ``active_domain`` to a slug outside
    ``Config.domains`` raises a structured validation error and does
    NOT mutate live Config or write config.json.

    The pre-check in ``_check_active_domain_membership`` mirrors the
    Plan 10 ``Config._check_active_domain_in_domains`` validator's
    error wording. Plan 16 Task 36 enabled ``validate_assignment=True``
    on ``Config`` (so per-field validators DO fire on assignment), but
    ``_check_active_domain_in_domains`` is a ``@model_validator(mode=
    "after")`` — and a Pydantic v2 cross-field validator failure does
    NOT roll back the triggering field mutation. Without this pre-check,
    an orphan slug would land on the live Config before the validator
    raises, leaving it in an inconsistent state. Same single-seam
    pattern as ``test_domain_override_rejects_orphan_slug`` above.
    """
    cfg = Config(domains=["research", "personal", "work"], active_domain="research")
    ctx = _mk_ctx(tmp_path, cfg)

    with pytest.raises(ValueError, match="not in domains"):
        await handle({"key": "active_domain", "value": "ghost-domain"}, ctx)

    # Live Config not mutated.
    assert cfg.active_domain == "research"
    # No config.json written — persist_config_or_revert never reached
    # save_config because the pre-check raised before the setattr.
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_validate_assignment_enforcement(tmp_path: Path) -> None:
    """Plan 16 Task 36 / D29 (locked 1.B + 3.A): ``validate_assignment=True``
    is now set unconditionally on :class:`Config` and every sub-config,
    so an out-of-range value raises ``pydantic.ValidationError`` on the
    assignment ``setattr`` itself instead of silently persisting until
    the next ``load_config`` rejects the on-disk file.

    This test was previously a KNOWN-LIMITATION pin
    (``test_invalid_value_currently_persists_without_validation`` in
    Plan 11 Task 4); flipped here to a positive validation pin per the
    locked decision. ``persist_config_or_revert`` catches the raise,
    restores the snapshot via the ``__dict__`` fast-path, and re-raises
    so the caller sees the canonical Pydantic error voice — neither the
    in-memory ``cfg`` nor on-disk ``config.json`` is mutated.
    """
    cfg = Config()
    pre_value = cfg.budget.daily_usd  # default 5.0
    ctx = _mk_ctx(tmp_path, cfg)

    # ``daily_usd`` schema requires ``ge=0``; -1.0 trips the field-level
    # validator on assignment (validate_assignment is now ON). The
    # ``ValidationError`` propagates out of ``handle`` via
    # ``persist_config_or_revert``'s re-raise.
    with pytest.raises(pydantic.ValidationError):
        await handle({"key": "budget.daily_usd", "value": -1.0}, ctx)

    # Live Config not mutated — field-level validator failures roll back
    # the assignment in Pydantic v2, and the snapshot revert is a
    # belt-and-suspenders safeguard.
    assert cfg.budget.daily_usd == pre_value
    # No config.json written — save_config never ran because
    # persist_config_or_revert caught the exception before the yield
    # could reach the save step.
    assert not (tmp_path / ".brain" / "config.json").exists()
