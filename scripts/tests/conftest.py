"""Shared fixtures for the install-script integration tests.

These live alongside the shell scripts they exercise, not under
``packages/``. pytest discovers them via the root ``pyproject.toml``'s
``testpaths`` entry.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _darwin_or_opt_in() -> bool:
    """These tests only run on Mac by default.

    CI systems (or curious humans) can opt in by exporting
    ``BRAIN_INSTALL_SH_CI=1`` — useful when we add Linux coverage.
    """
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("BRAIN_INSTALL_SH_CI"))


skip_if_not_mac = pytest.mark.skipif(
    not _darwin_or_opt_in(),
    reason="install.sh integration tests run on darwin by default "
    "(set BRAIN_INSTALL_SH_CI=1 to opt in on Linux CI).",
)


def _sha256_of(path: Path) -> str:
    """SHA256 hex digest of ``path``. Matches the shell helper's format."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="session")
def local_tarball(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """Cut a tarball from the current git HEAD and return (path, sha256).

    Session-scoped because all tests can share the same tarball.
    """
    out_dir = tmp_path_factory.mktemp("brain-tarball")
    tarball = out_dir / "brain-dev.tar.gz"
    subprocess.run(
        ["git", "archive", "--format=tar.gz", f"--output={tarball}", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
    )
    return tarball, _sha256_of(tarball)


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME so install.sh can't touch the developer's files."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Don't leak a real LOCALAPPDATA on Win-CI either (just in case).
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    return home


@pytest.fixture
def install_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override BRAIN_INSTALL_DIR so we never extract into ~/Applications."""
    d = tmp_path / "install"
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(d))
    return d


@pytest.fixture
def install_env(
    fake_home: Path,
    install_dir: Path,
    local_tarball: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """Assemble the env dict that install.sh needs for a happy-path run.

    Callers mutate the returned dict + pass it to subprocess.run().
    Skipping Node build + doctor keeps tests fast and offline-friendly.
    """
    tarball, sha256 = local_tarball
    return {
        **os.environ,
        "HOME": str(fake_home),
        "BRAIN_INSTALL_DIR": str(install_dir),
        "BRAIN_RELEASE_URL": f"file://{tarball}",
        "BRAIN_RELEASE_SHA256": sha256,
        # Keep the tests offline: no Node download, no uv sync, no doctor.
        "BRAIN_SKIP_NODE": "1",
        "BRAIN_SKIP_DOCTOR": "1",
        "BRAIN_SKIP_UV_SYNC": "1",  # honored via a small patch in test mode
        "BRAIN_INSTALL_FORCE": "1",
    }
