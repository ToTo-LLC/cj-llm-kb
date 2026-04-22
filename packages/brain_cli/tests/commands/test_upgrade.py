"""Tests for the ``brain upgrade`` command — Plan 08 Task 5.

All external effects are mocked:

* ``httpx`` release check (via ``release.check_latest_release``)
* ``release.download_release``
* ``subprocess.run`` for ``uv sync`` + ``pnpm`` calls
* ``shutil.which`` for the pnpm PATH probe
* ``pidfile`` + ``supervisor`` for the stop-before-swap step

Real disk I/O happens for stage/swap (actual tarball extraction + atomic
renames on ``tmp_path``) because that's what we want to cover.
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest
from brain_cli.app import app
from brain_cli.commands import upgrade as upgrade_mod
from brain_cli.runtime import release as release_mod
from brain_cli.runtime.release import ReleaseError, ReleaseInfo
from typer.testing import CliRunner

runner = CliRunner()


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------


def _build_tarball(path: Path, *, version: str = "0.2.0") -> Path:
    """Tiny valid tarball: VERSION file + state migrations dir + pyproject."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def _add(tf: tarfile.TarFile, name: str, data: bytes) -> None:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))

    with tarfile.open(str(path), mode="w:gz") as tf:
        _add(tf, "VERSION", f"{version}\n".encode())
        _add(tf, "pyproject.toml", b"[project]\nname = 'brain'\n")
        # A realistic migrations dir so the migrator step has something to do
        # (0001 bootstraps schema_version). Keep content minimal.
        _add(
            tf,
            "packages/brain_core/src/brain_core/state/migrations/0001_init.sql",
            (
                b"CREATE TABLE IF NOT EXISTS schema_version "
                b"(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);\n"
                b"CREATE TABLE IF NOT EXISTS upgrade_smoke "
                b"(id INTEGER PRIMARY KEY);\n"
            ),
        )
    return path


def _point_at_scratch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(install_dir, vault_root)`` inside ``tmp_path`` + env set."""
    install = tmp_path / "brain"
    install.mkdir()
    (install / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (install / "old_file").write_text("pre-upgrade\n", encoding="utf-8")

    vault = tmp_path / "vault"
    (vault / ".brain" / "run").mkdir(parents=True)
    (vault / ".brain" / "cache").mkdir(parents=True)

    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(install))
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(vault))
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)
    return install, vault


def _mock_uv_and_pnpm_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub subprocess.run so uv sync + pnpm install/build all "succeed"."""

    class _Ok:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(*_args: object, **_kwargs: object) -> _Ok:
        return _Ok()

    monkeypatch.setattr(upgrade_mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(upgrade_mod.shutil, "which", lambda _name: "/usr/local/bin/pnpm")


def _mock_no_running_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the ``_stop_running_daemon`` step a no-op."""
    monkeypatch.setattr(upgrade_mod.pidfile, "read_pid", lambda _p: None)
    monkeypatch.setattr(upgrade_mod.pidfile, "is_alive", lambda _p: False)


def _mock_release(
    monkeypatch: pytest.MonkeyPatch,
    info: ReleaseInfo | None,
    *,
    raises: Exception | None = None,
) -> None:
    """Stub ``release.check_latest_release`` return value or exception."""

    def _fake(**_kwargs: object) -> ReleaseInfo | None:
        if raises is not None:
            raise raises
        return info

    monkeypatch.setattr(release_mod, "check_latest_release", _fake)


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_upgrade_up_to_date_prints_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the API says "same version", we print + exit 0 without touching disk."""
    install, _vault = _point_at_scratch(monkeypatch, tmp_path)
    _mock_release(monkeypatch, info=None)

    result = runner.invoke(app, ["upgrade", "--yes"])

    assert result.exit_code == 0, result.output
    assert "up to date" in result.output
    # Install untouched.
    assert (install / "old_file").exists()


def test_upgrade_happy_path_with_tarball_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--tarball`` skips the API call + goes through the full stage/swap path."""
    install, vault = _point_at_scratch(monkeypatch, tmp_path)
    tarball = _build_tarball(tmp_path / "dist" / "brain-0.2.0.tar.gz")

    # Ensure the API check would fail loudly if accidentally invoked.
    def _should_not_be_called(**_kwargs: object) -> None:
        raise AssertionError("--tarball must skip check_latest_release")

    monkeypatch.setattr(release_mod, "check_latest_release", _should_not_be_called)
    _mock_uv_and_pnpm_ok(monkeypatch)
    _mock_no_running_daemon(monkeypatch)

    result = runner.invoke(app, ["upgrade", "--yes", "--tarball", str(tarball)])

    assert result.exit_code == 0, result.output
    # New install has the VERSION bundled in the tarball.
    assert (install / "VERSION").read_text(encoding="utf-8").strip() in {
        "0.2.0",
        "v0.2.0",
    }
    # Backup preserved.
    backups = list(install.parent.glob(f"{install.name}-prev-*"))
    assert len(backups) == 1
    assert (backups[0] / "old_file").exists()
    # State DB got the bootstrap migration.
    state_db = vault / ".brain" / "state.sqlite"
    assert state_db.exists()


def test_upgrade_network_failure_surfaces_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A GitHub transport error → exit 1 + no disk mutation."""
    install, _vault = _point_at_scratch(monkeypatch, tmp_path)
    _mock_release(monkeypatch, info=None, raises=ReleaseError("Could not reach GitHub: down"))

    result = runner.invoke(app, ["upgrade", "--yes"])

    assert result.exit_code == 1
    assert "Could not reach GitHub" in result.output
    assert (install / "old_file").exists()
    # No staging dir left behind.
    assert not (install.parent / f"{install.name}-staging").exists()


def test_upgrade_rolls_back_when_uv_sync_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``uv sync`` failure cleans up staging + leaves install untouched."""
    install, _vault = _point_at_scratch(monkeypatch, tmp_path)
    tarball = _build_tarball(tmp_path / "dist" / "brain-0.2.0.tar.gz")

    class _Fail:
        returncode = 1
        stdout = ""
        stderr = "uv: no internet"

    def _fake_run(args: Any, **_kwargs: object) -> _Fail:
        # Only fail the uv sync invocation — but in this test we'd never get
        # past that anyway. Be explicit for readability.
        return _Fail()

    monkeypatch.setattr(upgrade_mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(upgrade_mod.shutil, "which", lambda _name: "/usr/local/bin/pnpm")
    _mock_no_running_daemon(monkeypatch)

    result = runner.invoke(app, ["upgrade", "--yes", "--tarball", str(tarball)])

    assert result.exit_code == 1
    assert "uv sync" in result.output
    # Staging cleaned up; install intact.
    assert not (install.parent / f"{install.name}-staging").exists()
    assert (install / "old_file").exists()


def test_upgrade_rolls_back_when_migration_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Broken migration in the tarball → cleanup + exit 1; install untouched."""
    install, vault = _point_at_scratch(monkeypatch, tmp_path)

    # Build a tarball whose 0001 migration is intentionally broken.
    tarball_path = tmp_path / "dist" / "brain-0.2.0.tar.gz"
    tarball_path.parent.mkdir(parents=True)
    with tarfile.open(str(tarball_path), mode="w:gz") as tf:
        version = b"0.2.0\n"
        info = tarfile.TarInfo(name="VERSION")
        info.size = len(version)
        tf.addfile(info, io.BytesIO(version))
        # Missing schema_version table creation; INSERT will blow up.
        bad_sql = b"INSERT INTO nope VALUES (1);\n"
        info = tarfile.TarInfo(
            name="packages/brain_core/src/brain_core/state/migrations/0001_bad.sql"
        )
        info.size = len(bad_sql)
        tf.addfile(info, io.BytesIO(bad_sql))

    _mock_uv_and_pnpm_ok(monkeypatch)
    _mock_no_running_daemon(monkeypatch)

    result = runner.invoke(app, ["upgrade", "--yes", "--tarball", str(tarball_path)])

    assert result.exit_code == 1
    assert "0001_bad.sql" in result.output or "Migration" in result.output
    # Staging cleaned up; install still on 0.1.0.
    assert not (install.parent / f"{install.name}-staging").exists()
    assert (install / "old_file").exists()
    # Vault untouched except for maybe a zero-row state DB.
    assert vault.exists()


def test_upgrade_uses_release_info_when_no_tarball_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When GitHub says "new version", we download + install end-to-end."""
    _install, vault = _point_at_scratch(monkeypatch, tmp_path)
    tarball = _build_tarball(tmp_path / "dist" / "brain-0.2.0.tar.gz")

    info = ReleaseInfo(
        version="0.2.0",
        tag_name="v0.2.0",
        tarball_url="https://example.com/brain-0.2.0.tar.gz",
        sha256=None,
        body="## What's new\n- faster everything",
    )
    _mock_release(monkeypatch, info=info)

    # Stub the downloader to return our local tarball (simulating "downloaded").
    def _fake_download(
        _url: str,
        dest: Path,
        *,
        expected_sha256: str | None = None,
        timeout_s: int = 120,
        progress: Any = None,
    ) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(tarball.read_bytes())
        return dest

    monkeypatch.setattr(release_mod, "download_release", _fake_download)
    _mock_uv_and_pnpm_ok(monkeypatch)
    _mock_no_running_daemon(monkeypatch)

    result = runner.invoke(app, ["upgrade", "--yes"])

    assert result.exit_code == 0, result.output
    assert "Upgraded brain to 0.2.0" in result.output
    # Tarball landed in vault cache.
    cached = list((vault / ".brain" / "cache").glob("brain-0.2.0.tar.gz"))
    assert cached, "download_release should have landed a tarball in the vault cache"


# Silence a false-positive on the imported subprocess module in the no-op
# helper path (we reach into upgrade_mod.subprocess, not import subprocess
# here, but keep the import so the fallback stub in tests that compose
# their own subprocess.run replacement lines up).
_ = subprocess
