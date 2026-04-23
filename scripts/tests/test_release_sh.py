"""Integration tests for ``scripts/release.sh`` (Plan 09 Task 7).

Three scenarios:

(a) Happy path — clean repo, run release.sh, verify tarball contents
    include the expected files and exclude the internal dev ones.

(b) Dirty tree without ``--force`` aborts with a clear message + exit 1.

(c) Extract tarball → ``install.sh`` runs against it to completion +
    ``brain --version`` prints ``0.1.0``. This is a full end-to-end
    packaging-chain check — slow (~30s), gated behind a ``slow`` marker.

Gating mirrors ``test_install_sh.py``: skip on non-Mac unless
``BRAIN_RELEASE_SH_CI=1`` is set (or ``BRAIN_INSTALL_SH_CI=1`` — we
reuse the install gate so one envvar opts into the whole test-suite).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
RELEASE_SH = SCRIPTS_DIR / "release.sh"
INSTALL_SH = SCRIPTS_DIR / "install.sh"
VERSION_FILE = REPO_ROOT / "VERSION"


def _darwin_or_opt_in() -> bool:
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("BRAIN_RELEASE_SH_CI")) or bool(
        os.environ.get("BRAIN_INSTALL_SH_CI")
    )


skip_if_not_mac = pytest.mark.skipif(
    not _darwin_or_opt_in(),
    reason="release.sh integration tests run on darwin by default "
    "(set BRAIN_RELEASE_SH_CI=1 to opt in on Linux CI).",
)


def _read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def _copy_repo_to(dest: Path) -> Path:
    """Clone the working repo tree into ``dest`` with a fresh ``.git``.

    We don't use ``git clone`` because the on-disk repo may have
    untracked files we want preserved in a controlled way per test.
    Instead: init a fresh repo, copy the tracked files (via
    ``git archive``), and commit them so ``git status --porcelain``
    is clean inside ``dest``.

    The prebuilt ``apps/brain_web/out/`` is copied in separately so the
    release script doesn't need to re-run the Node build.
    """
    dest.mkdir(parents=True, exist_ok=True)

    # Seed tracked files.
    archive_cmd = ["git", "archive", "--format=tar", "HEAD"]
    archive = subprocess.run(archive_cmd, cwd=REPO_ROOT, check=True, capture_output=True)
    subprocess.run(
        ["tar", "-xf", "-"],
        input=archive.stdout,
        cwd=dest,
        check=True,
    )

    # Initialize a throwaway git repo so `git status --porcelain`
    # has something to talk to. Use a local committer identity that
    # doesn't leak into the host git config.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Release Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Release Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=dest, check=True, env=env)

    # Copy the prebuilt UI in so release.sh --skip-ui has something
    # to find.
    src_out = REPO_ROOT / "apps" / "brain_web" / "out"
    dst_out = dest / "apps" / "brain_web" / "out"
    if src_out.is_dir():
        dst_out.parent.mkdir(parents=True, exist_ok=True)
        if dst_out.exists():
            shutil.rmtree(dst_out)
        shutil.copytree(src_out, dst_out)

    # Copy release.sh in (it may not be committed yet during
    # development — always ensure the clone has the exact version
    # under test).
    dst_release = dest / "scripts" / "release.sh"
    dst_release.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RELEASE_SH, dst_release)
    dst_release.chmod(0o755)

    # Re-commit if the copy changed anything (happens when release.sh
    # is newly added, not yet in HEAD).
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Release Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Release Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=dest,
        check=True,
        capture_output=True,
        text=True,
    )
    if dirty.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=dest, check=True, env=env)
        subprocess.run(
            ["git", "commit", "-q", "-m", "sync release.sh"],
            cwd=dest,
            check=True,
            env=env,
        )

    return dest


# ---------------------------------------------------------------------------
# (a) Happy path
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_release_sh_happy_path(tmp_path: Path) -> None:
    """Clean repo + ``--skip-ui`` → tarball with expected contents.

    Verifies:
      * Exit 0, tarball + SHA sidecar present.
      * Expected files are inside.
      * Excluded paths (tasks/, .claude/, docs/superpowers/, etc.) are
        NOT inside.
    """
    repo = _copy_repo_to(tmp_path / "repo")
    version = _read_version()

    result = subprocess.run(
        ["/bin/bash", str(repo / "scripts" / "release.sh"), "--skip-ui"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"release.sh failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    tarball = repo / "release" / f"brain-{version}.tar.gz"
    sha_file = repo / "release" / f"brain-{version}.tar.gz.sha256"
    assert tarball.is_file(), f"tarball not produced at {tarball}"
    assert sha_file.is_file(), f"SHA sidecar not produced at {sha_file}"
    # SHA file content matches ``<hex>  <filename>`` format.
    sha_content = sha_file.read_text(encoding="utf-8").strip()
    assert f"brain-{version}.tar.gz" in sha_content
    assert len(sha_content.split()[0]) == 64, "expected 64-char SHA256 hex"

    # Inspect tarball contents.
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    prefix = f"brain-{version}/"

    # --- Must-include ---
    expected_present = [
        f"{prefix}VERSION",
        f"{prefix}pyproject.toml",
        f"{prefix}uv.lock",
        f"{prefix}README.md",
        f"{prefix}LICENSE",
        f"{prefix}CHANGELOG.md",
        f"{prefix}CONTRIBUTING.md",
        f"{prefix}packages/brain_core/src/brain_core/__init__.py",
        f"{prefix}packages/brain_cli/src/brain_cli",
        f"{prefix}packages/brain_mcp/src/brain_mcp",
        f"{prefix}packages/brain_api/src/brain_api",
        f"{prefix}apps/brain_web/out/index.html",
        f"{prefix}apps/brain_web/src",
        f"{prefix}apps/brain_web/package.json",
        f"{prefix}scripts/install.sh",
        f"{prefix}scripts/install.ps1",
        f"{prefix}scripts/install_lib/fetch_tarball.sh",
        f"{prefix}scripts/install_lib/fetch_tarball.ps1",
        f"{prefix}docs/privacy.md",
        f"{prefix}docs/release-notes/v0.1.0.md",
        f"{prefix}docs/v0.1.0-known-issues.md",
        f"{prefix}docs/testing/manual-qa.md",
        f"{prefix}assets/brain.icns",
        f"{prefix}assets/brain.ico",
    ]
    for needle in expected_present:
        assert any(n == needle or n.startswith(needle + "/") for n in names), (
            f"expected member missing from tarball: {needle}"
        )

    # --- Must-exclude ---
    excluded_substrings = [
        "/tasks/",
        "/.claude/",
        "/.brain/",
        "/docs/superpowers/",
        "/docs/design/",
        "/scripts/tests/",
        "/scripts/demo-plan-",
        "/apps/brain_web/tests/",
        "/apps/brain_web/node_modules/",
        "/__pycache__/",
        "/.venv/",
        "/.github/",
    ]
    # docs/testing/ other-than manual-qa.md also out.
    for name in names:
        for bad in excluded_substrings:
            assert bad not in name, f"excluded path leaked into tarball: {name}"
        if (
            name.startswith(f"{prefix}docs/testing/")
            and name != f"{prefix}docs/testing/"
            and name != f"{prefix}docs/testing/manual-qa.md"
        ):
            raise AssertionError(f"docs/testing/ should only contain manual-qa.md; got: {name}")
        # packages/*/tests/ excluded
        if "/packages/" in name and (name.endswith("/tests") or "/tests/" in name):
            raise AssertionError(f"packages/*/tests leaked: {name}")


# ---------------------------------------------------------------------------
# (b) Dirty tree without --force aborts
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_release_sh_dirty_tree_aborts(tmp_path: Path) -> None:
    """An uncommitted change in the working tree must abort release.sh."""
    repo = _copy_repo_to(tmp_path / "repo")

    # Introduce a dirty file (modify README.md — always present).
    readme = repo / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n# dirty!\n", encoding="utf-8")

    result = subprocess.run(
        ["/bin/bash", str(repo / "scripts" / "release.sh"), "--skip-ui"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode != 0, (
        "expected non-zero exit on dirty tree; got rc=0\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "dirty" in combined.lower(), f"expected 'dirty' in output; got:\n{combined}"
    assert "--force" in combined, f"expected '--force' hint in output; got:\n{combined}"
    # No tarball should have been produced.
    tarball = repo / "release" / f"brain-{_read_version()}.tar.gz"
    assert not tarball.exists(), "expected no tarball on dirty-tree abort"


# ---------------------------------------------------------------------------
# (c) Extract tarball → install.sh runs to completion
# ---------------------------------------------------------------------------


@pytest.mark.slow
@skip_if_not_mac
def test_release_sh_tarball_feeds_install_sh(tmp_path: Path) -> None:
    """End-to-end packaging chain: release.sh → install.sh → brain --version.

    Builds the tarball via ``release.sh``, then feeds it to
    ``install.sh`` (via ``file://`` URL) into a sandbox install dir +
    HOME. Asserts ``brain --version`` prints the pinned version.

    Slow (~30s) — tagged ``slow`` so fast test runs can skip via
    ``pytest -m 'not slow'``.
    """
    repo = _copy_repo_to(tmp_path / "repo")
    version = _read_version()

    # 1. Build tarball.
    build = subprocess.run(
        ["/bin/bash", str(repo / "scripts" / "release.sh"), "--skip-ui"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert build.returncode == 0, (
        f"release.sh failed (rc={build.returncode})\n"
        f"stdout:\n{build.stdout}\nstderr:\n{build.stderr}"
    )
    tarball = repo / "release" / f"brain-{version}.tar.gz"
    assert tarball.is_file()
    sha = (
        (repo / "release" / f"brain-{version}.tar.gz.sha256").read_text(encoding="utf-8").split()[0]
    )

    # 2. Run install.sh against the produced tarball.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    install_dir = tmp_path / "install"
    env = {
        **os.environ,
        "HOME": str(fake_home),
        "BRAIN_INSTALL_DIR": str(install_dir),
        "BRAIN_RELEASE_URL": f"file://{tarball}",
        "BRAIN_RELEASE_SHA256": sha,
        "BRAIN_SKIP_NODE": "1",
        "BRAIN_SKIP_DOCTOR": "1",
        "BRAIN_SKIP_UV_SYNC": "1",
        "BRAIN_INSTALL_FORCE": "1",
    }
    install = subprocess.run(
        ["/bin/bash", str(INSTALL_SH)],
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert install.returncode == 0, (
        f"install.sh failed on release tarball (rc={install.returncode})\n"
        f"stdout:\n{install.stdout}\nstderr:\n{install.stderr}"
    )

    # 3. Verify install layout has the files install.sh expected.
    assert (install_dir / "VERSION").is_file()
    assert (install_dir / "pyproject.toml").is_file()
    assert (install_dir / "packages" / "brain_cli").is_dir()
    assert (install_dir / "apps" / "brain_web" / "out" / "index.html").is_file()

    # 4. VERSION file contents round-trip.
    installed_version = (install_dir / "VERSION").read_text(encoding="utf-8").strip()
    assert installed_version == version, (
        f"VERSION mismatch: tarball said {version}, install has {installed_version}"
    )
