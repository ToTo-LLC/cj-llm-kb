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


async def test_no_config_attached_skips_save(tmp_path: Path) -> None:
    """Backwards-compat: ``ctx.config=None`` (low-level test contexts)
    still validates the key but skips persistence and reports
    ``persisted=False``. The existing test_config_set.py fixtures rely
    on this — losing it would cascade-break a dozen tests.
    """
    ctx = _mk_ctx(tmp_path, None)
    result = await handle({"key": "log_llm_payloads", "value": True}, ctx)
    assert result.data is not None
    assert result.data["persisted"] is False
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
