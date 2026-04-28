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


async def test_privacy_railed_removing_personal_load_rejects(tmp_path: Path) -> None:
    """The Config validator forbids removing ``personal`` from
    privacy_railed. Because the Config object lacks
    ``validate_assignment=True``, the in-memory mutation goes through;
    the next ``load_config`` on the persisted file is what catches it.
    Pin this behavior so it's an intentional decision when validation
    tightens.
    """
    cfg = Config(domains=["research", "personal", "journal"])
    ctx = _mk_ctx(tmp_path, cfg)

    # In-memory and on-disk write both go through.
    result = await handle({"key": "privacy_railed", "value": ["journal"]}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.privacy_railed == ["journal"]

    # load_config rejects the bad on-disk file.
    with pytest.raises(pydantic.ValidationError):
        load_config(config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={})


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
    error wording — Config doesn't enable ``validate_assignment`` and
    ``persisted_dict`` bypasses ``model_validate``, so without this
    pre-check an orphan slug would persist silently and only fail on
    the next ``load_config``. Same single-seam pattern as
    ``test_domain_override_rejects_orphan_slug`` above.
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


async def test_invalid_value_currently_persists_without_validation(tmp_path: Path) -> None:
    """KNOWN-LIMITATION pin (Plan 11 Task 4): pydantic v2 only validates on
    assignment when ``validate_assignment=True``, which Config and its
    sub-configs do NOT enable. So an out-of-range value (e.g.
    ``budget.daily_usd = -1.0``) currently slips through ``setattr`` and
    is persisted as-is. The next ``load_config`` would reject the file.

    This test pins the current behavior so a future change that enables
    ``validate_assignment`` (or wires explicit pre-write validation in
    ``brain_config_set``) makes the test fail loudly and the author
    can decide whether to upgrade the assertion to expect a raise.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    # ``daily_usd`` schema requires ``ge=0``; -1.0 should trip but doesn't
    # (validate_assignment is off). The assignment silently lands.
    result = await handle({"key": "budget.daily_usd", "value": -1.0}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is True
    assert cfg.budget.daily_usd == -1.0
    # The bad value was persisted — load_config will reject this file.
    # Pin to ``pydantic.ValidationError`` specifically so a future
    # regression that raises a different exception type fails loudly
    # instead of being swallowed by a bare ``Exception`` match.
    with pytest.raises(pydantic.ValidationError):
        load_config(config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={})
