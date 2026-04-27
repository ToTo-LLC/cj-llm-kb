"""Tests for ``brain_core.config.writer.save_config`` (Plan 11 Task 2).

Covers the contract described in ``writer.py``: atomic write, backup-on-write,
inter-process lock, mid-write crash safety, the LF/UTF-8/sort_keys output
shape, the persisted-field whitelist, the ISO-8601 datetime encoder, and the
POSIX-only ``fsync`` parent-dir branch.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

import filelock
import pytest
from brain_core.config.schema import _PERSISTED_FIELDS, BudgetConfig, Config
from brain_core.config.writer import (
    ConfigPersistenceError,
    _json_default,
    save_config,
)


def test_save_config_writes_persisted_fields(tmp_path: Path) -> None:
    target = save_config(Config(), tmp_path)

    assert target == tmp_path / ".brain" / "config.json"
    assert target.is_file()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    # D4: only the persisted-field whitelist hits disk.
    assert set(data.keys()) == set(_PERSISTED_FIELDS)


def test_save_config_excludes_vault_path(tmp_path: Path) -> None:
    # D4 sanity check: ``vault_path`` is the chicken-and-egg field —
    # we use it to find the config, so it must never be persisted.
    target = save_config(Config(vault_path=tmp_path), tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "vault_path" not in data


def test_save_config_round_trip_through_loader(tmp_path: Path) -> None:
    # Stronger than "keys match" — verify the on-disk blob round-trips
    # back into a ``Config`` cleanly. Catches encoder bugs and any drift
    # between writer output and pydantic input shape.
    original = Config(domains=["research", "work", "personal", "hobby"])
    target = save_config(original, tmp_path)

    rehydrated = Config(**json.loads(target.read_text(encoding="utf-8")))
    # ``vault_path`` falls back to its default (not persisted) on rehydrate;
    # all other fields should match the source object.
    for field in _PERSISTED_FIELDS:
        assert getattr(rehydrated, field) == getattr(original, field), field


def test_save_config_creates_brain_dir(tmp_path: Path) -> None:
    # Fresh vault: ``.brain/`` doesn't exist yet. ``save_config`` should
    # create it (parents=True, exist_ok=True).
    assert not (tmp_path / ".brain").exists()
    save_config(Config(), tmp_path)
    assert (tmp_path / ".brain").is_dir()


def test_save_config_writes_backup_on_second_save(tmp_path: Path) -> None:
    # First save: no backup yet (nothing to back up).
    save_config(Config(active_domain="research"), tmp_path)
    backup = tmp_path / ".brain" / "config.json.bak"
    assert not backup.exists()

    first_payload = (tmp_path / ".brain" / "config.json").read_text(encoding="utf-8")

    # Second save: the previous config.json should be copied to .bak
    # *before* the new payload is staged. The .bak must reflect the
    # FIRST save, not the second.
    save_config(Config(active_domain="work"), tmp_path)
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == first_payload
    assert backup.read_text(encoding="utf-8") != (tmp_path / ".brain" / "config.json").read_text(
        encoding="utf-8"
    )


def test_save_config_mid_write_crash_leaves_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate ``os.replace`` failing mid-write: the target should not
    # exist (replace never landed), and the tmp file should be cleaned
    # up by the writer's exception handler so a retry isn't confused.
    def boom(_src: object, _dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("brain_core.config.writer.os.replace", boom)

    with pytest.raises(OSError, match="disk full"):
        save_config(Config(), tmp_path)

    assert not (tmp_path / ".brain" / "config.json").exists()
    assert not (tmp_path / ".brain" / "config.json.tmp").exists()


def test_save_config_preserves_existing_target_on_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pre-existing config.json must survive a mid-write crash. ``os.replace``
    # is atomic — if it never runs, the target is untouched.
    save_config(Config(active_domain="research"), tmp_path)
    target = tmp_path / ".brain" / "config.json"
    pre_crash = target.read_text(encoding="utf-8")

    def boom(_src: object, _dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("brain_core.config.writer.os.replace", boom)

    with pytest.raises(OSError, match="disk full"):
        save_config(Config(active_domain="work"), tmp_path)

    assert target.read_text(encoding="utf-8") == pre_crash


def test_save_config_raises_on_lock_contention(tmp_path: Path) -> None:
    # Hold the lock from a separate thread, then assert the foreground
    # ``save_config`` surfaces a structured ``ConfigPersistenceError``
    # (not a bare ``filelock.Timeout``). Extended to also pin the
    # structured ``attempted_path`` + ``cause`` fields the Plan 11 Task 4
    # mutation tools rely on for uniform error UX — keeping these in one
    # test avoids duplicating the lock-contention threading scaffold.
    brain_dir = tmp_path / ".brain"
    brain_dir.mkdir(parents=True)
    lock_path = brain_dir / "config.json.lock"

    holder = filelock.FileLock(str(lock_path))
    holder_acquired = threading.Event()
    release_holder = threading.Event()

    def hold_lock() -> None:
        with holder.acquire():
            holder_acquired.set()
            release_holder.wait(timeout=10.0)

    t = threading.Thread(target=hold_lock)
    t.start()
    try:
        assert holder_acquired.wait(timeout=5.0)
        with pytest.raises(ConfigPersistenceError, match="another brain process") as excinfo:
            save_config(Config(), tmp_path, lock_timeout=0.5)
        # Structured fields: caller (Plan 11 Task 4) branches on these
        # rather than parsing the message string.
        assert excinfo.value.attempted_path == brain_dir / "config.json"
        assert excinfo.value.cause == "lock_timeout"
    finally:
        release_holder.set()
        t.join(timeout=5.0)


def test_config_persistence_error_backward_compat_no_kwargs() -> None:
    # Direct construction without the new kwargs must still work — both
    # for any external caller that hand-rolls the exception and for our
    # own future raise sites that don't have a meaningful path/cause.
    err = ConfigPersistenceError("just a message")
    assert str(err) == "just a message"
    assert err.attempted_path is None
    assert err.cause is None


def test_save_config_release_lock_after_success(tmp_path: Path) -> None:
    # Belt and suspenders: a successful save must release the lock so
    # the next save (or another process) can acquire it. If we leak the
    # lock, a second save in the same process would deadlock indefinitely
    # — ``timeout=0.5`` keeps the test fast even if it does.
    save_config(Config(), tmp_path)
    save_config(Config(active_domain="work"), tmp_path, lock_timeout=0.5)


def test_save_config_output_is_pretty_and_sorted(tmp_path: Path) -> None:
    # ``sort_keys=True`` + ``indent=2`` give us a deterministic, diff-friendly
    # blob. Same Config, two saves, two byte-identical files.
    cfg = Config(domains=["research", "work", "personal", "hobby"])

    a = tmp_path / "a"
    b = tmp_path / "b"
    save_config(cfg, a)
    save_config(cfg, b)

    blob_a = (a / ".brain" / "config.json").read_text(encoding="utf-8")
    blob_b = (b / ".brain" / "config.json").read_text(encoding="utf-8")
    assert blob_a == blob_b
    # ``sort_keys=True`` puts top-level keys in alphabetical order; the
    # first key after the opening brace is "active_domain".
    assert blob_a.startswith('{\n  "active_domain":')
    # ``domains`` order is preserved (lists are not sorted by sort_keys).
    parsed = json.loads(blob_a)
    assert parsed["domains"] == ["research", "work", "personal", "hobby"]


def test_save_config_uses_lf_line_endings(tmp_path: Path) -> None:
    # CLAUDE.md cross-platform rule: LF on disk, never CRLF, regardless
    # of OS default. Open in binary mode so the test sees the raw bytes
    # (text-mode reads would normalize CRLF on Windows and hide a bug).
    target = save_config(Config(), tmp_path)
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    assert b"\n" in raw


def test_save_config_no_fsync_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Spec: ``os.fsync`` parent-dir branch is skipped on Windows.
    # We can't run on a real Windows box from CI, so flip the writer's
    # ``_is_posix`` helper to return False and assert ``os.fsync`` is
    # never called. (Patching ``os.name`` directly would also flip
    # pathlib's flavour and break every Path op in the writer.)
    fsync_calls: list[int] = []

    real_fsync = os.fsync

    def tracking_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr("brain_core.config.writer._is_posix", lambda: False)
    monkeypatch.setattr("brain_core.config.writer.os.fsync", tracking_fsync)

    save_config(Config(), tmp_path)
    assert fsync_calls == []


def test_save_config_fsync_runs_on_posix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mirror image of the Windows skip: on POSIX the parent dir is
    # ``fsync``'d. Force the helper to ``True`` so the assertion holds
    # regardless of host OS.
    fsync_calls: list[int] = []

    real_fsync = os.fsync

    def tracking_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr("brain_core.config.writer._is_posix", lambda: True)
    monkeypatch.setattr("brain_core.config.writer.os.fsync", tracking_fsync)

    save_config(Config(), tmp_path)
    assert len(fsync_calls) == 1


def test_json_default_encodes_datetime_as_isoformat() -> None:
    # The "sharp trap" pin: a naive ``default=str`` would produce
    # ``"2026-05-01 12:00:00"`` (space separator). The encoder must
    # emit real ISO-8601 with the ``T`` separator.
    dt = datetime(2026, 5, 1, 12, 0, 0)
    assert _json_default(dt) == "2026-05-01T12:00:00"


def test_json_default_encodes_path_as_string(tmp_path: Path) -> None:
    p = tmp_path / "vault"
    assert _json_default(p) == str(p)


def test_json_default_raises_on_unknown_type() -> None:
    # Loud failure mode: an unexpected type must raise, not silently
    # ``str()`` itself into config.json.
    with pytest.raises(TypeError, match="not JSON serializable"):
        _json_default(object())


def test_save_config_serializes_budget_override_until_isoformat(tmp_path: Path) -> None:
    # End-to-end exercise of the datetime encoder via the real Config
    # path. ``override_until`` defaults to ``None``, so without this
    # test the encoder branch could ride along untriggered.
    cfg = Config(
        budget=BudgetConfig(
            override_until=datetime(2026, 5, 1, 12, 0, 0),
            override_delta_usd=2.5,
        )
    )
    target = save_config(cfg, tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["budget"]["override_until"] == "2026-05-01T12:00:00"
    assert data["budget"]["override_delta_usd"] == 2.5
