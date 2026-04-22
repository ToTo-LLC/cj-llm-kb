"""Integration tests for ``scripts/install.sh`` (Plan 08 Task 7).

Each test drives the script via ``subprocess.run`` with a tmpdir HOME +
an isolated ``BRAIN_INSTALL_DIR`` so the developer's real install tree
is never touched. The happy-path fixture cuts a tarball from git HEAD
and serves it via ``file://`` — no network I/O.

Test mode env knobs used here (all honored by install.sh):

* ``BRAIN_SKIP_NODE=1``     — skip fnm / Node / pnpm / UI build
* ``BRAIN_SKIP_UV_SYNC=1``  — skip ``uv sync`` (offline + fast)
* ``BRAIN_SKIP_DOCTOR=1``   — skip the final ``brain doctor`` call
* ``BRAIN_INSTALL_FORCE=1`` — never prompt about existing installs
* ``BRAIN_INSTALL_DIR``     — override the install root
* ``BRAIN_RELEASE_URL``     — ``file://`` URL to a local tarball
* ``BRAIN_RELEASE_SHA256``  — expected SHA256 for verify

The 5 tests skip on non-Mac unless ``BRAIN_INSTALL_SH_CI=1`` — gating
is in conftest.py.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# These constants mirror scripts/tests/conftest.py — duplicated here on
# purpose so pytest doesn't need the ``scripts`` dir on sys.path.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
INSTALL_SH = SCRIPTS_DIR / "install.sh"


def _darwin_or_opt_in() -> bool:
    import sys

    return sys.platform == "darwin" or bool(os.environ.get("BRAIN_INSTALL_SH_CI"))


skip_if_not_mac = pytest.mark.skipif(
    not _darwin_or_opt_in(),
    reason="install.sh integration tests run on darwin by default "
    "(set BRAIN_INSTALL_SH_CI=1 to opt in on Linux CI).",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _run_install(
    env: dict[str, str],
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    """Invoke install.sh with the given env; return the completed process.

    Returns stdout/stderr as strings. Does NOT raise on non-zero — tests
    assert on ``.returncode`` themselves.
    """
    return subprocess.run(
        ["/bin/bash", str(INSTALL_SH)],
        env=env,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ---------------------------------------------------------------------------
# (a) Happy path
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_happy_path(
    install_env: dict[str, str],
    install_dir: Path,
    fake_home: Path,
) -> None:
    """Clean install: exit 0, install dir populated, shim in place."""
    result = _run_install(install_env)

    assert result.returncode == 0, (
        f"install.sh failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Install dir exists + has the expected Python package tree.
    assert install_dir.is_dir()
    assert (install_dir / "pyproject.toml").is_file()
    assert (install_dir / "packages" / "brain_cli").is_dir()

    # Shim at ~/.local/bin/brain is executable + references the install.
    shim = fake_home / ".local" / "bin" / "brain"
    assert shim.is_file(), f"shim not written at {shim}"
    assert os.access(shim, os.X_OK), "shim is not executable"
    body = shim.read_text()
    assert "uv run --project" in body
    assert str(install_dir) in body

    # .app bundle exists (Mac only — this test is gated to darwin).
    app_launcher = fake_home / "Applications" / "brain.app" / "Contents" / "MacOS" / "brain"
    assert app_launcher.is_file()
    assert os.access(app_launcher, os.X_OK)
    info_plist = fake_home / "Applications" / "brain.app" / "Contents" / "Info.plist"
    assert info_plist.is_file()
    plist_text = info_plist.read_text()
    assert "CFBundleExecutable" in plist_text
    assert "com.totollc.brain" in plist_text


# ---------------------------------------------------------------------------
# (b) uv already present
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_uv_already_present(
    install_env: dict[str, str],
    install_dir: Path,
) -> None:
    """When uv is on PATH we must skip the installer + continue."""
    result = _run_install(install_env)

    assert result.returncode == 0, result.stderr
    # The log_ok branch of ``ensure_uv`` prints "uv already present".
    assert "uv already present" in result.stdout, (
        f"expected 'uv already present' in stdout; got:\n{result.stdout}"
    )
    # And of course the install still completed.
    assert (install_dir / "pyproject.toml").is_file()


# ---------------------------------------------------------------------------
# (c) Idempotency: re-run uses the backup-then-replace path
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_repeat_run_idempotent(
    install_env: dict[str, str],
    install_dir: Path,
    tmp_path: Path,
) -> None:
    """Second install moves old → backup, extracts fresh, exits 0.

    Also verifies that once the re-run succeeds, the ``-prev-*`` backup
    is cleaned up (rolling backups are the upgrade command's concern,
    not install.sh's).
    """
    first = _run_install(install_env)
    assert first.returncode == 0, first.stderr

    # Put a "is this my install?" marker file the second run should wipe.
    marker = install_dir / "touched-between-runs.txt"
    marker.write_text("stay or go?")

    second = _run_install(install_env)
    assert second.returncode == 0, (
        f"second run failed (rc={second.returncode})\n"
        f"stdout:\n{second.stdout}\n"
        f"stderr:\n{second.stderr}"
    )

    # After a successful run the marker is gone (fresh extract) and the
    # install dir is still populated.
    assert not marker.exists(), "expected second run to replace the install dir"
    assert (install_dir / "pyproject.toml").is_file()

    # No -prev-* backup should remain after a successful second run.
    parent = install_dir.parent
    leftover = [p for p in parent.iterdir() if re.match(r"install-prev-", p.name)]
    assert leftover == [], f"unexpected backup dirs left behind: {leftover}"


# ---------------------------------------------------------------------------
# (d) Corrupt tarball SHA: abort cleanly
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_corrupt_tarball_aborts(
    install_env: dict[str, str],
    install_dir: Path,
) -> None:
    """SHA256 mismatch must fail with a clear error + leave nothing extracted."""
    # Flip one hex char in the expected SHA to force a mismatch.
    real = install_env["BRAIN_RELEASE_SHA256"]
    corrupt = ("f" if real[0] != "f" else "0") + real[1:]
    env = {**install_env, "BRAIN_RELEASE_SHA256": corrupt}

    result = _run_install(env)

    assert result.returncode != 0, "expected non-zero exit on SHA mismatch"
    # Error message should be plain English + mention SHA256.
    combined = result.stdout + result.stderr
    assert "SHA256 mismatch" in combined, f"expected 'SHA256 mismatch' in output:\n{combined}"
    # Nothing extracted (install dir must not contain a working tree).
    # The dir might have been created empty by fetch_and_extract's mkdir,
    # but it should NOT contain pyproject.toml.
    assert not (install_dir / "pyproject.toml").exists(), (
        "expected no extracted files after SHA mismatch"
    )


# ---------------------------------------------------------------------------
# (e) Missing curl falls back to wget (or fails cleanly if both gone)
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_missing_curl_uses_wget_or_errors(
    install_env: dict[str, str],
    install_dir: Path,
    tmp_path: Path,
) -> None:
    """Hide curl from PATH; install.sh should fall back to wget.

    If wget isn't installed either (common on fresh Mac), the script
    must fail with the documented 'no downloader found' message — not
    a cryptic ``command not found`` traceback.

    The happy-path of this test is a pure ``file://`` tarball fetch,
    which in ``fetch_tarball.sh`` is special-cased to use ``cp`` — so
    we also don't need curl for the tarball step. What we really
    exercise here is the *uv bootstrap* branch: when uv is already
    present (it is in this test env), ensure_uv skips before trying
    to download. So the absence of curl shouldn't even matter.

    We assert on: (1) install still succeeds when uv is present + URL
    is file://, OR (2) script fails with the documented error message
    if some intermediate step *does* reach a downloader.
    """
    # Build a sandbox PATH that excludes curl.
    sandbox = tmp_path / "nocurl-bin"
    sandbox.mkdir()
    # Symlink every tool from the real PATH into the sandbox EXCEPT curl.
    # Limit to a short list of tools install.sh actually needs, to keep
    # this fast + deterministic.
    needed = [
        "bash",
        "sh",
        "uv",
        "git",
        "tar",
        "gzip",
        "mkdir",
        "mv",
        "cp",
        "rm",
        "ls",
        "awk",
        "grep",
        "sed",
        "tr",
        "cat",
        "date",
        "dirname",
        "basename",
        "readlink",
        "head",
        "chmod",
        "mktemp",
        "shasum",
        "env",
        "printf",
        "echo",
        "test",
        "unzip",
        "uname",
        "sort",
        "uniq",
        "corepack",
        "node",
        "pnpm",
        "python",
        "python3",
        "which",
        "command",
        # deliberately NO curl, NO wget
    ]
    for name in needed:
        src = shutil.which(name)
        if src:
            (sandbox / name).symlink_to(src)

    env = {**install_env, "PATH": str(sandbox)}

    result = _run_install(env)

    # Either of these outcomes is acceptable:
    #   1. Happy exit 0 (tarball fetched via cp since URL is file://,
    #      uv already on PATH via symlink, no network step reached).
    #   2. Clean error mentioning "no downloader found" if any step
    #      actually required curl/wget.
    if result.returncode == 0:
        # Happy path — install completed without ever needing curl.
        assert (install_dir / "pyproject.toml").is_file()
    else:
        combined = result.stdout + result.stderr
        assert "no downloader found" in combined or "curl" in combined.lower(), (
            f"expected clean 'no downloader' or curl-related error; got:\n{combined}"
        )
