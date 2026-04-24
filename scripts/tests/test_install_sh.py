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
    # Shim must call uv via an absolute path (not bare ``uv run``) so it
    # survives invocation from a context without ~/.local/bin on PATH
    # (launchd / Spotlight / GUI / bash subshell). Capture the uv path
    # install.sh saw + assert the shim embeds it literally.
    uv_abs = shutil.which("uv")
    assert uv_abs, "uv must be on PATH for this test to run"
    assert f'exec "{uv_abs}" run --project' in body, (
        f"expected shim to embed absolute uv path; got:\n{body}"
    )
    assert "exec uv run" not in body, (
        f"shim must NOT call bare ``uv run`` — it breaks under stripped PATH\n{body}"
    )
    assert str(install_dir) in body
    # Shim must export BRAIN_INSTALL_DIR so ``brain start`` picks up the
    # versioned install path rather than the platform default (which
    # won't exist on disk). Regression guard for Plan 09 Task 11's
    # supervisor-cwd-not-found bug surfaced on 2026-04-24.
    assert "BRAIN_INSTALL_DIR" in body, (
        f"shim must export BRAIN_INSTALL_DIR; got:\n{body}"
    )
    assert f'BRAIN_INSTALL_DIR="${{BRAIN_INSTALL_DIR:-{install_dir}}}"' in body, (
        f"shim must export BRAIN_INSTALL_DIR={install_dir} (with env override); got:\n{body}"
    )

    # .app bundle exists (Mac only — this test is gated to darwin).
    app_launcher = fake_home / "Applications" / "brain.app" / "Contents" / "MacOS" / "brain"
    assert app_launcher.is_file()
    assert os.access(app_launcher, os.X_OK)
    # Same absolute-uv-path rule for the .app launcher. Finder / Spotlight
    # launches do NOT inherit the user's shell PATH.
    launcher_body = app_launcher.read_text()
    assert f'exec "{uv_abs}" run --project' in launcher_body, (
        f"expected .app launcher to embed absolute uv path; got:\n{launcher_body}"
    )
    assert "exec uv run" not in launcher_body, (
        f".app launcher must NOT call bare ``uv run``\n{launcher_body}"
    )
    # Same BRAIN_INSTALL_DIR guarantee as the shim — Spotlight / Launchpad
    # double-click inherits no env, so the launcher must set it explicitly.
    assert "BRAIN_INSTALL_DIR" in launcher_body, (
        f".app launcher must export BRAIN_INSTALL_DIR; got:\n{launcher_body}"
    )
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


# ---------------------------------------------------------------------------
# (f) Curl-bootstrap: install.sh without install_lib/ adjacent
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_bootstrap_without_install_lib(
    install_env: dict[str, str],
    install_dir: Path,
    fake_home: Path,
    tmp_path: Path,
) -> None:
    """Simulates the documented curl-bootstrap flow.

    When users run ``curl -fsSL .../install.sh | bash`` (or ``curl -o
    install.sh && bash install.sh``), the script lands in a temp dir by
    itself — there is NO install_lib/ directory next to it. Before the
    bootstrap fix, section 0 errored out immediately with ``install_lib/
    not found``. After the fix, section 0 should download the tarball,
    extract it, source install_lib/ from the extracted tree, set
    BRAIN_BOOTSTRAP_TARBALL, and continue into the main flow reusing
    the same tarball (no double download).

    We stage install.sh alone in a temp dir and point BRAIN_RELEASE_URL
    at a local file:// tarball so the test stays offline.
    """
    lonely_dir = tmp_path / "curl-staging"
    lonely_dir.mkdir()
    lonely_install = lonely_dir / "install.sh"
    shutil.copy2(INSTALL_SH, lonely_install)
    # Sanity: install_lib is NOT adjacent to this copy.
    assert not (lonely_dir / "install_lib").exists()

    result = subprocess.run(
        ["/bin/bash", str(lonely_install)],
        env=install_env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, (
        f"bootstrap install failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Log output must show the bootstrap path kicked in.
    combined = result.stdout + result.stderr
    assert "Bootstrapping install helpers" in combined, (
        f"expected bootstrap log in output; got:\n{combined}"
    )
    # And the main fetch_and_extract must show tarball reuse (proves we
    # didn't double-download).
    assert "reusing tarball downloaded during bootstrap" in combined, (
        f"expected tarball-reuse log; got:\n{combined}"
    )

    # Install still completed correctly.
    assert install_dir.is_dir()
    assert (install_dir / "pyproject.toml").is_file()
    assert (install_dir / "packages" / "brain_cli").is_dir()
    shim = fake_home / ".local" / "bin" / "brain"
    assert shim.is_file()


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


# ---------------------------------------------------------------------------
# (g) Shim survives stripped PATH (regression: Plan 09 Task 11 bug)
# ---------------------------------------------------------------------------


@skip_if_not_mac
def test_install_shim_runs_with_stripped_path(
    install_env: dict[str, str],
    install_dir: Path,
    fake_home: Path,
) -> None:
    """Regression: the generated shim must run in a minimal PATH env.

    Plan 09 Task 11 surfaced a ``brain start`` failure when the shim was
    invoked from a context without ``~/.local/bin`` on PATH (launchd /
    Spotlight / .app double-click / bash subshell without rc files). The
    root cause was a bare ``uv run ...`` in the shim — uv lives in
    ``~/.local/bin/uv`` and is NOT on the minimal PATH.

    Fix: write_shim.sh resolves ``uv`` to an absolute path at install
    time + embeds it in the shim. This test asserts that: (1) the
    generated shim file embeds an absolute uv path, and (2) invoking
    the shim under ``PATH=/usr/bin:/bin`` runs cleanly rather than
    erroring with "``uv`` not found on PATH".

    We stop short of running ``--version`` (which needs the full uv sync
    + brain package build) and instead run the shim enough to prove uv
    is reachable. The install_env fixture sets BRAIN_SKIP_UV_SYNC=1 so
    calling ``brain`` would fail with an import error even under the fix
    — what we assert here is the error is NOT the shim-level
    ``command not found``.
    """
    result = _run_install(install_env)
    assert result.returncode == 0, result.stderr

    shim = fake_home / ".local" / "bin" / "brain"
    assert shim.is_file()

    body = shim.read_text()
    uv_abs = shutil.which("uv")
    assert uv_abs, "uv must be on PATH for this test to run"
    assert f'"{uv_abs}"' in body, (
        f"expected absolute uv path {uv_abs!r} in shim body; got:\n{body}"
    )

    # Invoke the shim under a minimal PATH — no ~/.local/bin. The shim
    # itself is called by absolute path. If the fix works, bash will be
    # able to exec the shim's uv and uv will respond to --version
    # without any PATH lookup.
    stripped_env = {
        "HOME": str(fake_home),
        "PATH": "/usr/bin:/bin",
    }
    # Run: bash -lc '<shim> --version is too heavy; just run uv --version
    # via the shim's own path'. The shim does ``exec "$uv_abs" run
    # --project <dir> brain "$@"`` — so passing ``--version`` would
    # trigger a full brain load. Instead verify the shim header's
    # absolute-uv-path exec line at least can *find* uv. We do this by
    # running bash -n (syntax check) which parses the shim without
    # executing it, plus a standalone test that $uv_abs is executable
    # via /usr/bin:/bin only.
    syntax_check = subprocess.run(
        ["/bin/bash", "-n", str(shim)],
        env=stripped_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax_check.returncode == 0, (
        f"shim has bad bash syntax:\n{syntax_check.stderr}"
    )

    # Run the shim directly (via its absolute path) under stripped PATH.
    # With BRAIN_SKIP_UV_SYNC=1 in place the project isn't fully built,
    # so brain --version may fail at the Python level — but it MUST NOT
    # fail at the shim level with "uv: command not found". Parse the
    # combined output for that specific failure mode.
    invoke = subprocess.run(
        ["/bin/bash", "-c", f'"{shim}" --version'],
        env=stripped_env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    combined = invoke.stdout + invoke.stderr
    assert "uv: command not found" not in combined, (
        f"shim failed under stripped PATH — uv not reachable:\n{combined}"
    )
    assert "uv: not found" not in combined, (
        f"shim failed under stripped PATH — uv not reachable:\n{combined}"
    )
    # install.sh's ensure_uv always puts uv at ~/.local/bin/uv on Mac.
    # Confirm the shim used the same path.
    assert str(Path(uv_abs)) in body
