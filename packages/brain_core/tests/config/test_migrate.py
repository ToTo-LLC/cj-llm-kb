"""Plan 16 Task 41 — pin tests for :func:`migrate_config_file` (D31).

Coverage:

  (a) Old-shape (flat ``autonomous``) file migrates to nested; backup
      lands at ``.pre-migrate.bak``; ``MigrationResult.migrated`` True;
      ``changes`` records the autonomy-shape rewrite; backup contents
      equal the pre-migration original.
  (b) Re-run on an already-migrated file is a no-op (no new backup file
      appears, ``migrated`` False, ``backup_path`` None).
  (c) Backup naming is stable: pre-existing ``.bak`` / ``.bak.1`` /
      ``.bak.2`` are NOT overwritten — the next backup is ``.bak.3``.
  (d) Missing file raises :class:`FileNotFoundError`.
  (e) Malformed JSON raises :class:`json.JSONDecodeError`.
  (f) Non-dict top-level (e.g. JSON array) raises :class:`ValueError`.
  (g) :class:`MigrationResult.changes` carries the human-readable label.
  (h) Mid-write failure (mock ``os.replace`` to raise) leaves the
      original file intact + scrubs the temp file + scrubs the
      stillborn backup so a transient failure doesn't pollute the vault.
  (i) Idempotency / round-trip: migrate → re-read → migrate again is a
      no-op on the second call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.config.migrate import (
    _MAX_BACKUP_SUFFIX,
    MigrationResult,
    _next_backup_path,
    migrate_config_file,
)


def _legacy_payload() -> dict[str, object]:
    """Pre-T38 flat autonomous shape — the canonical "needs migration" input."""
    return {
        "domains": ["research", "personal"],
        "autonomous": {
            "ingest": True,
            "entities": False,
            "concepts": True,
            "index_rewrites": False,
            "draft": False,
        },
    }


def _new_shape_payload() -> dict[str, object]:
    """Post-T38 nested shape — the canonical "already migrated" input."""
    return {
        "domains": ["research"],
        "autonomous": {
            "research": {
                "new_files": True,
                "edits": False,
                "index_entries": True,
                "concepts": False,
                "draft": False,
            }
        },
    }


# ---------------------------------------------------------------------------
# (a) Old shape migrates; backup created; result populated.
# ---------------------------------------------------------------------------


def test_migrate_old_shape_rewrites_and_backs_up(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    original = _legacy_payload()
    cfg_path.write_text(json.dumps(original), encoding="utf-8")

    result = migrate_config_file(cfg_path)

    assert isinstance(result, MigrationResult)
    assert result.migrated is True
    assert result.path == cfg_path
    assert result.backup_path == cfg_path.with_name("config.json.pre-migrate.bak")
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.changes == ["autonomous: flat → nested"]

    # Backup is an exact byte copy of the pre-migration file.
    assert json.loads(result.backup_path.read_text(encoding="utf-8")) == original

    # The rewritten file has the new nested shape — driven by T38's
    # mapping table: ingest=True ⇒ new_files+index_entries; concepts=True
    # ⇒ concepts; entities/index_rewrites/draft contribute nothing here.
    rewritten = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert rewritten["autonomous"] == {
        "research": {
            "new_files": True,
            "edits": False,
            "index_entries": True,
            "concepts": True,
            "draft": False,
        },
        "personal": {
            "new_files": True,
            "edits": False,
            "index_entries": True,
            "concepts": True,
            "draft": False,
        },
    }


# ---------------------------------------------------------------------------
# (b) Already-migrated file is a no-op.
# ---------------------------------------------------------------------------


def test_migrate_already_new_shape_is_no_op(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    payload = _new_shape_payload()
    cfg_path.write_text(json.dumps(payload), encoding="utf-8")
    pre_bytes = cfg_path.read_bytes()

    result = migrate_config_file(cfg_path)

    assert result.migrated is False
    assert result.backup_path is None
    assert result.changes == []
    # The file is byte-identical — a no-op MUST NOT touch the file.
    assert cfg_path.read_bytes() == pre_bytes
    # No backup created.
    assert not cfg_path.with_name("config.json.pre-migrate.bak").exists()


# ---------------------------------------------------------------------------
# (c) Backup naming stability — never overwrite an existing .bak.
# ---------------------------------------------------------------------------


def test_migrate_backup_naming_avoids_overwrite(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_legacy_payload()), encoding="utf-8")

    # Pre-create three prior backups with distinguishable contents so
    # we can prove the migrator NEVER touched them.
    bak0 = cfg_path.with_name("config.json.pre-migrate.bak")
    bak1 = cfg_path.with_name("config.json.pre-migrate.bak.1")
    bak2 = cfg_path.with_name("config.json.pre-migrate.bak.2")
    bak0.write_text("OLD-BAK-0", encoding="utf-8")
    bak1.write_text("OLD-BAK-1", encoding="utf-8")
    bak2.write_text("OLD-BAK-2", encoding="utf-8")

    result = migrate_config_file(cfg_path)

    expected_bak3 = cfg_path.with_name("config.json.pre-migrate.bak.3")
    assert result.backup_path == expected_bak3
    assert expected_bak3.exists()

    # Originals untouched.
    assert bak0.read_text(encoding="utf-8") == "OLD-BAK-0"
    assert bak1.read_text(encoding="utf-8") == "OLD-BAK-1"
    assert bak2.read_text(encoding="utf-8") == "OLD-BAK-2"


def test_next_backup_path_raises_after_max_slots(tmp_path: Path) -> None:
    """Defensive: refusing to create more than ``_MAX_BACKUP_SUFFIX``
    backups surfaces a runaway loop instead of spinning forever.
    """
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    # Saturate every slot.
    cfg_path.with_name("config.json.pre-migrate.bak").write_text("x", encoding="utf-8")
    for n in range(1, _MAX_BACKUP_SUFFIX + 1):
        cfg_path.with_name(f"config.json.pre-migrate.bak.{n}").write_text(
            "x", encoding="utf-8"
        )

    with pytest.raises(RuntimeError) as exc:
        _next_backup_path(cfg_path)
    assert "refusing to create more than" in str(exc.value)


# ---------------------------------------------------------------------------
# (d), (e), (f) Error surface.
# ---------------------------------------------------------------------------


def test_migrate_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        migrate_config_file(tmp_path / "does-not-exist.json")


def test_migrate_malformed_json_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        migrate_config_file(cfg_path)


def test_migrate_non_dict_top_level_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        migrate_config_file(cfg_path)
    assert "expected object" in str(exc.value)


# ---------------------------------------------------------------------------
# (g) MigrationResult.changes captures the human-readable label.
# ---------------------------------------------------------------------------


def test_migrate_records_change_label(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_legacy_payload()), encoding="utf-8")
    result = migrate_config_file(cfg_path)
    assert "autonomous: flat → nested" in result.changes


# ---------------------------------------------------------------------------
# (h) Mid-write failure: original untouched, temp + backup both scrubbed.
# ---------------------------------------------------------------------------


def test_migrate_replace_failure_preserves_original_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = tmp_path / "config.json"
    original_payload = _legacy_payload()
    cfg_path.write_text(json.dumps(original_payload), encoding="utf-8")
    pre_bytes = cfg_path.read_bytes()

    # Force os.replace to blow up so we exercise the cleanup path.
    def boom(src: object, dst: object) -> None:
        raise OSError("simulated mid-write failure")

    monkeypatch.setattr("brain_core.config.migrate.os.replace", boom)

    with pytest.raises(OSError, match="simulated mid-write failure"):
        migrate_config_file(cfg_path)

    # 1. Original file is byte-identical — atomic rewrite never landed.
    assert cfg_path.read_bytes() == pre_bytes
    # 2. No leftover temp file OR stillborn backup in the parent
    # directory. The cleanup path scrubs both so a transient failure
    # doesn't pollute the user's vault with .tmp / .pre-migrate.bak
    # files that don't correspond to a real migration.
    leftovers = sorted(p.name for p in tmp_path.iterdir())
    assert leftovers == ["config.json"], (
        f"expected only the original config.json, found extras: {leftovers!r}"
    )


# ---------------------------------------------------------------------------
# (i) Idempotency: migrate twice — second call is a no-op.
# ---------------------------------------------------------------------------


def test_migrate_is_idempotent_across_runs(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_legacy_payload()), encoding="utf-8")

    first = migrate_config_file(cfg_path)
    assert first.migrated is True

    # Second invocation: file is now in the new shape; nothing to do.
    second = migrate_config_file(cfg_path)
    assert second.migrated is False
    assert second.backup_path is None
    assert second.changes == []
    # Only one backup file in the directory (the first run's).
    backups = sorted(p.name for p in tmp_path.iterdir() if "pre-migrate" in p.name)
    assert backups == ["config.json.pre-migrate.bak"]
