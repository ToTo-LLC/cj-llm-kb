"""Plan 16 Task 34 / D28 step 2 of 3: ``Config.config_version`` + single-process invalidation pin tests.

Cases pinned (per Plan 16 Task 34 spec):

* (1) ``Config.config_version`` defaults to ``0`` and round-trips through
  ``Config(**{...})``.
* (2) ``save_config`` increments ``config_version`` in place on every
  successful write (0 → 1 → 2).
* (3) ``save_config`` writes the post-increment ``config_version`` to disk
  JSON (so a peeker reading the file head sees the new value).
* (4) ``resolve_config`` returns the SAME object on consecutive calls when
  the on-disk version is unchanged (object-identity cache hit).
* (5) After ``save_config`` mutates the on-disk version, the next
  ``resolve_config`` returns a new object reflecting the new disk state.
* (6) ``resolve_config(force_reload=True)`` always re-reads, even on a
  warm cache + unchanged disk.
* (7) ``_peek_config_version`` returns ``None`` for missing-file +
  parse-error inputs (and raises on a corrupted non-int field — fail
  loud per CLAUDE.md "fail loud on unexpected state").
* (8) ``persist_config_or_revert`` revert restores the pre-yield
  ``config_version`` when a mid-yield exception fires (regression for
  the in-place-mutation snapshot contract).
* (9) Cache key separates by ``config_file`` path: two different vault
  roots get independent cache entries (no cross-vault state leakage).

Cache fixture: ``_reset_cache_for_tests()`` (mirrors
``_reset_buckets_for_tests`` in ``brain_core.llm.providers.anthropic``)
clears the loader's module-level cache so each test starts cold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.config.loader import (
    _peek_config_version,
    _reset_cache_for_tests,
    resolve_config,
)
from brain_core.config.schema import Config
from brain_core.config.writer import persist_config_or_revert, save_config


@pytest.fixture(autouse=True)
def _reset_loader_cache() -> None:
    """Clear the loader's in-memory cache before every test."""
    _reset_cache_for_tests()


# (1) Schema default + round-trip.
def test_config_version_defaults_to_zero() -> None:
    cfg = Config()
    assert cfg.config_version == 0


def test_config_version_round_trips_through_init() -> None:
    cfg = Config(config_version=5)
    assert cfg.config_version == 5


def test_config_version_persists_to_disk(tmp_path: Path) -> None:
    # T34 (A): the persistence whitelist must include ``config_version``
    # — the field's whole purpose is to round-trip through disk so the
    # loader can detect a stale cache. If the whitelist drops it, the
    # cache invalidation path silently breaks.
    cfg = Config()
    target = save_config(cfg, tmp_path)
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert "config_version" in on_disk


# (2) save_config increments in place.
def test_save_config_increments_config_version(tmp_path: Path) -> None:
    cfg = Config()
    assert cfg.config_version == 0

    save_config(cfg, tmp_path)
    assert cfg.config_version == 1

    save_config(cfg, tmp_path)
    assert cfg.config_version == 2


# (3) save_config writes the post-increment version to disk.
def test_save_config_writes_incremented_version_to_disk(tmp_path: Path) -> None:
    cfg = Config()
    target = save_config(cfg, tmp_path)
    assert json.loads(target.read_text(encoding="utf-8"))["config_version"] == 1

    save_config(cfg, tmp_path)
    assert json.loads(target.read_text(encoding="utf-8"))["config_version"] == 2


# (4) Identity cache hit when version unchanged.
def test_resolve_config_returns_same_object_when_version_unchanged(tmp_path: Path) -> None:
    config_file = tmp_path / ".brain" / "config.json"
    save_config(Config(), tmp_path)

    a = resolve_config(config_file=config_file, env={}, cli_overrides={})
    b = resolve_config(config_file=config_file, env={}, cli_overrides={})
    assert a is b


# (5) Cache invalidates after save_config bumps disk version.
def test_resolve_config_returns_new_object_after_save(tmp_path: Path) -> None:
    config_file = tmp_path / ".brain" / "config.json"
    cfg_initial = Config()
    save_config(cfg_initial, tmp_path)

    a = resolve_config(config_file=config_file, env={}, cli_overrides={})
    pre_version = a.config_version

    # Save a fresh config object to bump the disk version. Using the
    # same object ``a`` would mutate the cached object's version
    # in-place and hide the cache-invalidation behavior we're pinning.
    cfg_next = Config(**a.persisted_dict())
    save_config(cfg_next, tmp_path)

    b = resolve_config(config_file=config_file, env={}, cli_overrides={})
    assert a is not b
    assert b.config_version == pre_version + 1


# (6) force_reload always re-reads.
def test_resolve_config_force_reload_always_returns_new_object(tmp_path: Path) -> None:
    config_file = tmp_path / ".brain" / "config.json"
    save_config(Config(), tmp_path)

    a = resolve_config(config_file=config_file, env={}, cli_overrides={})
    b = resolve_config(
        config_file=config_file,
        env={},
        cli_overrides={},
        force_reload=True,
    )
    assert a is not b
    # Same disk content → same persisted state, but distinct objects.
    assert a.config_version == b.config_version


# (7) _peek_config_version edge cases.
def test_peek_config_version_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert _peek_config_version(tmp_path / "does-not-exist.json") is None


def test_peek_config_version_returns_none_for_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json at all", encoding="utf-8")
    assert _peek_config_version(bad) is None


def test_peek_config_version_returns_none_when_field_absent(tmp_path: Path) -> None:
    no_version = tmp_path / "no-version.json"
    no_version.write_text(json.dumps({"web_port": 4317}), encoding="utf-8")
    assert _peek_config_version(no_version) is None


def test_peek_config_version_raises_on_corrupted_non_int_field(tmp_path: Path) -> None:
    # Fail-loud: a string where an int is expected is corrupted disk
    # state and should NOT silently coerce to ``None`` (which would
    # hide the corruption behind a "version unknown — keep cached
    # object" branch in ``resolve_config``).
    bad = tmp_path / "bad-version.json"
    bad.write_text(json.dumps({"config_version": "not-an-int"}), encoding="utf-8")
    with pytest.raises(TypeError):
        _peek_config_version(bad)


def test_peek_config_version_returns_int_on_happy_path(tmp_path: Path) -> None:
    cfg_file = tmp_path / ".brain" / "config.json"
    save_config(Config(), tmp_path)
    assert _peek_config_version(cfg_file) == 1


# (8) persist_config_or_revert restores pre-yield version on failure.
def test_persist_config_or_revert_restores_config_version_on_failure(tmp_path: Path) -> None:
    cfg = Config()
    save_config(cfg, tmp_path)
    assert cfg.config_version == 1

    pre_yield_version = cfg.config_version

    class _BoomError(Exception):
        pass

    with pytest.raises(_BoomError), persist_config_or_revert(cfg, tmp_path):
        # Mutate something the snapshot will restore — and then raise
        # before save_config runs, so the revert path triggers.
        cfg.web_port = 4318
        raise _BoomError

    assert cfg.config_version == pre_yield_version
    assert cfg.web_port == 4317  # web_port also reverted (sanity check)


# (9) Cache key separates by config_file path — independent cache entries.
def test_resolve_config_cache_keyed_by_config_file_path(tmp_path: Path) -> None:
    vault_a = tmp_path / "vault-a"
    vault_b = tmp_path / "vault-b"
    save_config(Config(), vault_a)
    save_config(Config(), vault_b)

    cfg_a = resolve_config(
        config_file=vault_a / ".brain" / "config.json",
        env={},
        cli_overrides={},
    )
    cfg_b = resolve_config(
        config_file=vault_b / ".brain" / "config.json",
        env={},
        cli_overrides={},
    )
    assert cfg_a is not cfg_b

    # Independence: a re-fetch of vault_a does NOT return vault_b's cached
    # object — and vice versa.
    cfg_a_again = resolve_config(
        config_file=vault_a / ".brain" / "config.json",
        env={},
        cli_overrides={},
    )
    cfg_b_again = resolve_config(
        config_file=vault_b / ".brain" / "config.json",
        env={},
        cli_overrides={},
    )
    assert cfg_a_again is cfg_a
    assert cfg_b_again is cfg_b
