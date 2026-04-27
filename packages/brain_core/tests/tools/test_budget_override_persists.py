"""Plan 11 Task 4 — brain_budget_override persists override fields to disk.

Both ``budget.override_until`` and ``budget.override_delta_usd`` are in the
Plan 11 D4 ``_PERSISTED_FIELDS`` whitelist (they're sub-fields of the
``budget`` config), so they round-trip through ``save_config`` /
``load_config`` cleanly. This file pins that round-trip explicitly so a
future change to D4's whitelist that drops the override fields fails here
loudly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from brain_core.config.writer import ConfigPersistenceError
from brain_core.tools.base import ToolContext
from brain_core.tools.budget_override import handle


def _mk_ctx(vault: Path, cfg: Config | None) -> ToolContext:
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
        config=cfg,
    )


async def test_success_persists_override_fields(tmp_path: Path) -> None:
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"amount_usd": 5.0, "duration_hours": 12}, ctx)
    assert result.data is not None

    # In-memory: both fields set on cfg.budget.
    assert cfg.budget.override_delta_usd == pytest.approx(5.0)
    assert isinstance(cfg.budget.override_until, datetime)

    # Disk reflects the override.
    config_json = tmp_path / ".brain" / "config.json"
    assert config_json.is_file()


async def test_round_trip_through_load_config(tmp_path: Path) -> None:
    """Plan 11 Task 4 task spec: a budget_override set BEFORE save →
    reload via load_config shows the same override_until + override_delta_usd.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    await handle({"amount_usd": 7.50, "duration_hours": 24}, ctx)

    pre_until = cfg.budget.override_until
    assert pre_until is not None

    # Reload from disk into a fresh Config instance.
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert rehydrated.budget.override_delta_usd == pytest.approx(7.50)
    assert rehydrated.budget.override_until == pre_until


async def test_save_failure_reverts_in_memory_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config()
    pre_until = cfg.budget.override_until
    pre_delta = cfg.budget.override_delta_usd
    ctx = _mk_ctx(tmp_path, cfg)

    def boom(_config: Config, _vault_root: Path, **_kw: object) -> Path:
        raise ConfigPersistenceError("disk failed", cause="io_error")

    monkeypatch.setattr("brain_core.config.writer.save_config", boom)

    with pytest.raises(ConfigPersistenceError, match="disk failed"):
        await handle({"amount_usd": 5.0, "duration_hours": 12}, ctx)

    # Both override fields reverted to their pre-call values (defaults).
    assert cfg.budget.override_until == pre_until
    assert cfg.budget.override_delta_usd == pre_delta


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
        await handle({"amount_usd": 5.0, "duration_hours": 12}, ctx)
    assert exc_info.value.cause == "lock_timeout"
    assert exc_info.value.attempted_path == target


async def test_no_config_attached_skips_persistence(tmp_path: Path) -> None:
    """When ``ctx.config`` is None (low-level test contexts), the response
    payload still carries the intended window — the caller (frontend)
    mirrors locally — and no config.json is written.
    """
    ctx = _mk_ctx(tmp_path, None)

    result = await handle({"amount_usd": 5.0, "duration_hours": 12}, ctx)
    assert result.data is not None
    assert result.data["status"] == "override_set"
    assert not (tmp_path / ".brain" / "config.json").exists()
