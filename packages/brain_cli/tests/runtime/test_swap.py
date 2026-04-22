"""Tests for ``brain_cli.runtime.swap`` — Plan 08 Task 5."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from brain_cli.runtime.swap import (
    SwapError,
    rollback_swap,
    stage_upgrade,
    swap_in,
)


def _make_tarball(target: Path, files: dict[str, bytes]) -> Path:
    """Build a minimal .tar.gz at ``target`` with the given member contents."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(target), mode="w:gz") as tf:
        for name, payload in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return target


def test_stage_upgrade_extracts_tarball(tmp_path: Path) -> None:
    """Tarball → ``<install>-staging/`` with the expected members."""
    install = tmp_path / "brain"
    tarball = _make_tarball(
        tmp_path / "dist" / "brain.tar.gz",
        {
            "VERSION": b"0.2.0\n",
            "packages/brain_core/pyproject.toml": b"[project]\nname = 'brain_core'\n",
        },
    )

    staging = stage_upgrade(install, tarball)

    assert staging.name == "brain-staging"
    assert staging.parent == install.parent
    assert (staging / "VERSION").read_bytes() == b"0.2.0\n"
    assert (staging / "packages" / "brain_core" / "pyproject.toml").exists()


def test_stage_upgrade_refuses_existing_staging(tmp_path: Path) -> None:
    """Pre-existing staging must abort — caller cleans up manually."""
    install = tmp_path / "brain"
    staging = install.parent / f"{install.name}-staging"
    staging.mkdir(parents=True)
    (staging / "LEFTOVER").write_text("oops", encoding="utf-8")

    tarball = _make_tarball(tmp_path / "brain.tar.gz", {"hi": b"x"})

    with pytest.raises(SwapError, match="already exists"):
        stage_upgrade(install, tarball)

    # Staging left untouched by our guard.
    assert (staging / "LEFTOVER").exists()


def test_swap_in_promotes_staging_and_backs_up_install(tmp_path: Path) -> None:
    """Current install renamed to backup; staging renamed to install."""
    install = tmp_path / "brain"
    install.mkdir()
    (install / "OLD_VERSION").write_text("0.1.0\n", encoding="utf-8")

    staging = install.parent / f"{install.name}-staging"
    staging.mkdir()
    (staging / "VERSION").write_text("0.2.0\n", encoding="utf-8")

    backup = swap_in(staging, install)

    assert install.exists()
    assert (install / "VERSION").read_text(encoding="utf-8") == "0.2.0\n"
    assert backup.exists()
    assert backup.name.startswith("brain-prev-")
    assert (backup / "OLD_VERSION").read_text(encoding="utf-8") == "0.1.0\n"
    # Staging has been consumed.
    assert not staging.exists()


def test_rollback_swap_restores_backup(tmp_path: Path) -> None:
    """``rollback_swap`` deletes the failed install and restores the backup."""
    install = tmp_path / "brain"
    install.mkdir()
    (install / "BROKEN").write_text("new but broken\n", encoding="utf-8")

    backup = install.parent / f"{install.name}-prev-20260421T120000Z"
    backup.mkdir()
    (backup / "OK").write_text("original\n", encoding="utf-8")

    rollback_swap(backup, install)

    assert install.exists()
    assert (install / "OK").read_text(encoding="utf-8") == "original\n"
    assert not (install / "BROKEN").exists()
    assert not backup.exists()
