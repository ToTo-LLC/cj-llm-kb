"""Plan 11 Task 4 — brain_create_domain persists Config.domains to disk.

Asserts at the tool level (not the helper level): a successful create writes
``<vault>/.brain/config.json`` and a save failure reverts the in-memory append.
The helper-level mechanics live in tests/config/test_writer.py.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from brain_core.config.writer import ConfigPersistenceError
from brain_core.tools.base import ToolContext
from brain_core.tools.create_domain import handle


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


async def test_success_writes_config_json(tmp_path: Path) -> None:
    cfg = Config(domains=["research", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    await handle({"slug": "hobby", "name": "Hobby"}, ctx)

    # In-memory mutation present.
    assert "hobby" in cfg.domains
    # Disk reflects it.
    config_json = tmp_path / ".brain" / "config.json"
    assert config_json.is_file()
    rehydrated = load_config(config_file=config_json, env={}, cli_overrides={})
    assert "hobby" in rehydrated.domains


async def test_save_failure_reverts_in_memory_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config(domains=["research", "personal"])
    pre = list(cfg.domains)
    ctx = _mk_ctx(tmp_path, cfg)

    def boom(_config: Config, _vault_root: Path, **_kw: object) -> Path:
        raise ConfigPersistenceError("disk failed", cause="io_error")

    # Monkeypatch save_config at the helper's import site so the helper
    # bubbles the exception and reverts.
    monkeypatch.setattr("brain_core.config.writer.save_config", boom)

    with pytest.raises(ConfigPersistenceError, match="disk failed"):
        await handle({"slug": "hobby", "name": "Hobby"}, ctx)

    # In-memory append was reverted.
    assert cfg.domains == pre
    # Disk was not written.
    assert not (tmp_path / ".brain" / "config.json").exists()
    # Per the docstring: the on-disk folder created BEFORE the persistence
    # attempt is left in place — the caller can re-run after fixing the
    # disk issue (the folder-already-exists guard then trips and the
    # caller chooses to retry or rip the folder).
    assert (tmp_path / "hobby").exists()


async def test_persistence_propagates_structured_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ConfigPersistenceError.cause and .attempted_path must survive
    propagation through the tool handler so the UI layer can branch on
    them without parsing the message string.
    """
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
        await handle({"slug": "hobby", "name": "Hobby"}, ctx)
    assert exc_info.value.cause == "lock_timeout"
    assert exc_info.value.attempted_path == target


async def test_concurrent_creates_serialize_via_lock(tmp_path: Path) -> None:
    """Two threads concurrently creating different domains both succeed —
    the filelock in save_config serializes the writes. Both slugs end up
    in the on-disk config (no last-writer-wins data loss for the in-memory
    Config object, because the two threads share the same Config and we
    only assert on the on-disk shape, which is what subsequent ``load_config``
    calls will read).
    """
    cfg = Config(domains=["research", "personal"])
    ctx = _mk_ctx(tmp_path, cfg)

    errors: list[BaseException] = []

    def run(slug: str, name: str) -> None:
        import asyncio

        try:
            asyncio.run(handle({"slug": slug, "name": name}, ctx))
        except BaseException as exc:  # pragma: no cover — surfaces below
            errors.append(exc)

    t1 = threading.Thread(target=run, args=("alpha", "Alpha"))
    t2 = threading.Thread(target=run, args=("beta", "Beta"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], errors
    # Both folders exist on disk.
    assert (tmp_path / "alpha").is_dir()
    assert (tmp_path / "beta").is_dir()
    # Final on-disk config carries both slugs (lock serialization
    # ensured neither write clobbered the other's append).
    rehydrated = load_config(
        config_file=tmp_path / ".brain" / "config.json", env={}, cli_overrides={}
    )
    assert "alpha" in rehydrated.domains
    assert "beta" in rehydrated.domains
