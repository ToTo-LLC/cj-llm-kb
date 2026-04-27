"""Plan 11 Task 4 — brain_delete_domain persists Config.domains removal to disk."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from brain_core.config.writer import ConfigPersistenceError
from brain_core.tools.base import ToolContext
from brain_core.tools.delete_domain import handle
from brain_core.vault.undo import UndoLog


def _seed_domain(vault: Path, slug: str) -> None:
    domain_dir = vault / slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "index.md").write_text(f"---\ntitle: {slug}\n---\n# {slug}\n", encoding="utf-8")
    (domain_dir / "note.md").write_text(
        f"---\ntitle: note\ndomain: {slug}\n---\nbody\n", encoding="utf-8"
    )


def _mk_ctx(vault: Path, cfg: Config | None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research", "music", "personal"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=UndoLog(vault_root=vault),
        config=cfg,
    )


async def test_success_removes_slug_from_disk(tmp_path: Path) -> None:
    _seed_domain(tmp_path, "music")
    _seed_domain(tmp_path, "research")  # last-non-personal guard needs >=2
    cfg = Config(domains=["research", "music", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    await handle({"slug": "music", "typed_confirm": True}, ctx)

    # In-memory removal present.
    assert "music" not in cfg.domains
    # Disk reflects the removal.
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "music" not in rehydrated.domains
    assert "research" in rehydrated.domains


async def test_save_failure_reverts_in_memory_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_domain(tmp_path, "music")
    _seed_domain(tmp_path, "research")
    cfg = Config(domains=["research", "music", "personal"])
    pre = list(cfg.domains)
    ctx = _mk_ctx(tmp_path, cfg)

    def boom(_config: Config, _vault_root: Path, **_kw: object) -> Path:
        raise ConfigPersistenceError("disk failed", cause="io_error")

    monkeypatch.setattr("brain_core.config.writer.save_config", boom)

    with pytest.raises(ConfigPersistenceError, match="disk failed"):
        await handle({"slug": "music", "typed_confirm": True}, ctx)

    # In-memory removal was reverted.
    assert cfg.domains == pre
    # The folder is in trash (the move ran BEFORE the persist step) —
    # ``brain_undo_last`` reverses the move, so no data lost. This
    # mirrors delete_domain.py's recovery docstring.
    assert not (tmp_path / "music").exists()
    trash = tmp_path / ".brain" / "trash"
    assert trash.exists()


async def test_skip_persistence_when_slug_not_in_config_domains(
    tmp_path: Path,
) -> None:
    """D7-style divergence: an on-disk-only domain (not in cfg.domains)
    deletes successfully without writing config.json — there's no
    Config mutation to persist.

    Setup needs cfg.domains to carry >=2 non-personal slugs so the
    Plan 10 last-non-personal guard doesn't pre-empt; the deleted slug
    is on disk only.
    """
    _seed_domain(tmp_path, "music")  # on-disk-only, not in cfg
    _seed_domain(tmp_path, "research")
    _seed_domain(tmp_path, "work")
    # cfg has work + research + personal (2 non-personal); ``music`` is
    # the on-disk-only divergent slug we delete. The guard sees 2 in
    # cfg.domains and lets us through.
    cfg = Config(domains=["research", "work", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    await handle({"slug": "music", "typed_confirm": True}, ctx)

    # cfg.domains untouched (the slug wasn't there to remove).
    assert cfg.domains == ["research", "work", "personal"]
    # No config.json written — skipping persistence on a no-op config
    # change is the documented behavior.
    assert not (tmp_path / ".brain" / "config.json").exists()


async def test_persistence_propagates_structured_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_domain(tmp_path, "music")
    _seed_domain(tmp_path, "research")
    cfg = Config(domains=["research", "music", "personal"])
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
        await handle({"slug": "music", "typed_confirm": True}, ctx)
    assert exc_info.value.cause == "lock_timeout"
    assert exc_info.value.attempted_path == target
