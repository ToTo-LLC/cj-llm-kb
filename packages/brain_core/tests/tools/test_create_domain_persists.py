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


def test_concurrent_creates_serialize_via_lock(tmp_path: Path) -> None:
    """Two concurrent ``brain_create_domain`` calls serialize via the filelock.

    Production never shares one ``Config`` object across threads doing
    parallel mutations — each request handler gets its own. What the
    filelock IS responsible for: ensuring two concurrent ``save_config``
    calls don't corrupt the on-disk file or stomp on one another's
    backup. This test pins THAT property by giving each thread its own
    ``Config`` + ``ToolContext`` (matching production), then asserting:

    1. Both threads complete without exception (filelock waits, never fails).
    2. The on-disk file is a valid ``Config`` rehydratable by ``load_config``
       (catches half-written corruption).
    3. Exactly one of the two new slugs ("alpha" or "beta") wins the race —
       NOT both. Each thread snapshots its OWN cfg (which lacks the other
       thread's append), so the second writer's ``save_config`` overwrites
       the first writer's persisted state. This pins the deliberate scope
       boundary: cross-process / cross-handler config invalidation (so the
       second writer reads the first writer's state and merges) is a Plan
       12+ concern, not Task 4. The filelock guarantees on-disk integrity,
       not in-memory consistency.

    The previous version of this test shared one ``cfg`` between both
    threads and asserted both new slugs landed on disk — that was a
    test-design bug (both threads observed each other's in-memory append
    via shared mutable state, masking the actual race) producing ~10%
    flake rate when the revert path tripped under load.
    """
    vault_root = tmp_path / "vault"
    (vault_root / ".brain").mkdir(parents=True)

    cfg_a = Config(domains=["research", "personal"])
    cfg_b = Config(domains=["research", "personal"])
    ctx_a = _mk_ctx(vault_root, cfg_a)
    ctx_b = _mk_ctx(vault_root, cfg_b)

    errors: list[BaseException] = []

    def run(ctx: ToolContext, slug: str, name: str) -> None:
        import asyncio

        try:
            asyncio.run(handle({"slug": slug, "name": name}, ctx))
        except BaseException as exc:  # pragma: no cover — surfaces below
            errors.append(exc)

    t_a = threading.Thread(target=run, args=(ctx_a, "alpha", "Alpha"))
    t_b = threading.Thread(target=run, args=(ctx_b, "beta", "Beta"))
    t_a.start()
    t_b.start()
    t_a.join(timeout=10)
    t_b.join(timeout=10)

    # Property 1: filelock waits, neither thread fails.
    assert errors == [], f"Concurrent saves raised: {errors}"
    assert not t_a.is_alive() and not t_b.is_alive(), (
        "Threads did not complete within 10s — filelock may be deadlocked"
    )
    # Both domain folders are created up front (before save_config runs),
    # so both exist regardless of which thread wins the on-disk race.
    assert (vault_root / "alpha").is_dir()
    assert (vault_root / "beta").is_dir()

    # Property 2: on-disk file is a valid Config (no half-written corruption).
    rehydrated = load_config(
        config_file=vault_root / ".brain" / "config.json",
        env={},
        cli_overrides={"vault_path": vault_root},
    )

    # Property 3: exactly one new slug wins (the second writer doesn't
    # see the first writer's mutation because each has its own cfg).
    assert "research" in rehydrated.domains
    assert "personal" in rehydrated.domains
    new_slugs = set(rehydrated.domains) - {"research", "personal"}
    assert new_slugs in ({"alpha"}, {"beta"}), (
        f"Expected exactly one new slug (alpha or beta) — got {new_slugs}. "
        "If both, something else is merging in-memory state across the two "
        "Config instances; if neither, save_config silently dropped the "
        "winning thread's append."
    )
