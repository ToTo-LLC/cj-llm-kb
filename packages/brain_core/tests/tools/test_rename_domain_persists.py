"""Plan 11 Task 4 — brain_rename_domain persists Config.domains rewrite to disk."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from brain_core.config.writer import ConfigPersistenceError
from brain_core.tools.base import ToolContext
from brain_core.tools.rename_domain import handle


def _seed_research(vault: Path) -> None:
    (vault / "research" / "notes").mkdir(parents=True)
    (vault / "research" / "index.md").write_text(
        "---\ntitle: Research\ndomain: research\ntype: index\n---\n\n# Research\n",
        encoding="utf-8",
    )
    (vault / "research" / "notes" / "alpha.md").write_text(
        "---\ntitle: Alpha\ndomain: research\n---\n\nbody\n",
        encoding="utf-8",
    )


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


async def test_success_writes_renamed_slug_to_disk(tmp_path: Path) -> None:
    _seed_research(tmp_path)
    cfg = Config(domains=["research", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    await handle({"from": "research", "to": "lab-notes"}, ctx)

    # In-memory rewrite present.
    assert "lab-notes" in cfg.domains
    assert "research" not in cfg.domains
    # Disk reflects the rewrite.
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "lab-notes" in rehydrated.domains
    assert "research" not in rehydrated.domains


async def test_save_failure_reverts_in_memory_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_research(tmp_path)
    cfg = Config(domains=["research", "personal"])
    pre = list(cfg.domains)
    ctx = _mk_ctx(tmp_path, cfg)

    def boom(_config: Config, _vault_root: Path, **_kw: object) -> Path:
        raise ConfigPersistenceError("disk failed", cause="io_error")

    monkeypatch.setattr("brain_core.config.writer.save_config", boom)

    with pytest.raises(ConfigPersistenceError, match="disk failed"):
        await handle({"from": "research", "to": "lab-notes"}, ctx)

    # In-memory rewrite was reverted.
    assert cfg.domains == pre
    # Note: the on-disk folder rename ALREADY committed before the
    # persistence step (Step 3 of the rename pipeline). Recovery is to
    # re-run the tool with the source/dest swapped, or to manually
    # repair config.json. The folder state IS divergent from cfg.domains
    # at this point — that's documented in rename_domain.py's docstring.
    assert (tmp_path / "lab-notes").exists()
    assert not (tmp_path / "research").exists()


async def test_persistence_propagates_structured_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_research(tmp_path)
    cfg = Config(domains=["research", "personal"])
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
        await handle({"from": "research", "to": "lab-notes"}, ctx)
    assert exc_info.value.cause == "lock_timeout"
    assert exc_info.value.attempted_path == target


async def test_rename_follows_active_domain(tmp_path: Path) -> None:
    """When the renamed slug is the active_domain, active_domain follows the rename.

    Without this behavior, a rename followed by save_config would persist
    a Config whose active_domain points at a slug not in domains, which
    fails the cross-field validator on next load_config (schema.py
    ``_check_active_domain_in_domains``). The follow-along is implemented
    at rename_domain.py inside the persist_config_or_revert block.
    """
    _seed_research(tmp_path)
    cfg = Config(domains=["research", "personal"], active_domain="research")
    ctx = _mk_ctx(tmp_path, cfg)

    await handle({"from": "research", "to": "lab-notes"}, ctx)

    # In-memory: active_domain follows the rename.
    assert "lab-notes" in cfg.domains
    assert "research" not in cfg.domains
    assert cfg.active_domain == "lab-notes"

    # On-disk: rehydrated config preserves both the rename AND the
    # active_domain update — without the follow-along the next
    # ``load_config`` would raise on the cross-field validator.
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "lab-notes" in rehydrated.domains
    assert rehydrated.active_domain == "lab-notes"
