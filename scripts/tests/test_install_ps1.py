"""Integration tests for ``scripts/install.ps1`` (Plan 08 Task 8).

Each test drives the script via ``subprocess.run`` with a tmpdir
HOME + LOCALAPPDATA + BRAIN_INSTALL_DIR so the developer's real install
tree is never touched. The happy-path fixture cuts a tarball via the
cross-platform ``scripts/cut_local_tarball.py`` helper (no bash
required on Windows).

Test mode env knobs used here (all honored by install.ps1):

* ``BRAIN_SKIP_NODE=1``     — skip fnm / Node / pnpm / UI build
* ``BRAIN_SKIP_UV_SYNC=1``  — skip ``uv sync``
* ``BRAIN_SKIP_DOCTOR=1``   — skip the final ``brain doctor`` call
* ``BRAIN_SKIP_DESKTOP=1``  — skip the optional desktop shortcut
* ``BRAIN_INSTALL_FORCE=1`` — never prompt about existing installs
* ``BRAIN_INSTALL_DIR``     — override the install root
* ``BRAIN_RELEASE_URL``     — ``file:///`` URL to a local tarball
* ``BRAIN_RELEASE_SHA256``  — expected SHA256 for verify
* ``BRAIN_INSTALL_PS1_CI=1``— bypass the Windows version gate (tests)

The 5 tests skip on non-Windows unless ``BRAIN_INSTALL_PS1_CI=1`` is
set AND PowerShell (``pwsh`` or ``powershell``) is on PATH.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
INSTALL_PS1 = SCRIPTS_DIR / "install.ps1"


def _powershell_exe() -> str | None:
    """Return a usable PowerShell exe path (or ``None``).

    Prefers ``powershell.exe`` (Windows PowerShell 5.1) on Windows to
    match the documented target. Falls back to ``pwsh`` (PowerShell 7)
    where available — primarily for Mac/Linux CI opt-in.
    """
    if sys.platform == "win32":
        for name in ("powershell.exe", "pwsh.exe", "pwsh"):
            found = shutil.which(name)
            if found:
                return found
        return None
    # Non-Windows opt-in path: pwsh only.
    return shutil.which("pwsh")


def _windows_or_opt_in() -> bool:
    if sys.platform == "win32":
        return True
    if not os.environ.get("BRAIN_INSTALL_PS1_CI"):
        return False
    # Opt-in requires PowerShell on PATH — otherwise there's nothing to test.
    return _powershell_exe() is not None


skip_if_not_windows = pytest.mark.skipif(
    not _windows_or_opt_in(),
    reason="install.ps1 integration tests run on Windows by default "
    "(set BRAIN_INSTALL_PS1_CI=1 AND install PowerShell to opt in on "
    "Mac/Linux CI).",
)


# ---------------------------------------------------------------------------
# Fixtures (scoped to this module — conftest.py handles the sh side)
# ---------------------------------------------------------------------------


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="session")
def local_tarball_ps(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str]:
    """Cross-platform tarball via cut_local_tarball.py.

    Uses the Python helper so these tests don't depend on a bash shell
    being installed on Windows.
    """
    out_dir = tmp_path_factory.mktemp("brain-tarball-ps")
    tarball = out_dir / "brain-dev.tar.gz"
    subprocess.run(
        ["git", "archive", "--format=tar.gz", f"--output={tarball}", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
    )
    return tarball, _sha256_of(tarball)


@pytest.fixture
def ps_fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME + LOCALAPPDATA + APPDATA so install.ps1 can't touch
    the developer's real profile.

    On Windows ``install.ps1`` honors BRAIN_INSTALL_DIR for the install
    root, but the shim + Start Menu shortcut paths derive from
    LOCALAPPDATA and APPDATA. Overriding those via monkeypatch is
    enough to fully sandbox the run.
    """
    home = tmp_path / "home"
    local_appdata = home / "AppData" / "Local"
    roaming_appdata = home / "AppData" / "Roaming"
    local_appdata.mkdir(parents=True)
    roaming_appdata.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setenv("APPDATA", str(roaming_appdata))
    return home


@pytest.fixture
def ps_install_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override BRAIN_INSTALL_DIR so we never extract into %LOCALAPPDATA%\\brain."""
    d = tmp_path / "install"
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(d))
    return d


@pytest.fixture
def ps_install_env(
    ps_fake_home: Path,
    ps_install_dir: Path,
    local_tarball_ps: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    tarball, sha256 = local_tarball_ps
    # Build the file:/// URL with forward slashes regardless of host OS
    # — that matches the form install.ps1 parses.
    abs_str = str(tarball.resolve()).replace("\\", "/")
    # Windows-style path like ``C:/foo``: produce ``file:///C:/foo``.
    # Unix-style path like ``/tmp/foo``: produce ``file:///tmp/foo``.
    url = (
        "file:///" + abs_str
        if not abs_str.startswith("/")
        else "file://" + abs_str
    )

    return {
        **os.environ,
        "HOME": str(ps_fake_home),
        "USERPROFILE": str(ps_fake_home),
        "LOCALAPPDATA": str(ps_fake_home / "AppData" / "Local"),
        "APPDATA": str(ps_fake_home / "AppData" / "Roaming"),
        "BRAIN_INSTALL_DIR": str(ps_install_dir),
        "BRAIN_RELEASE_URL": url,
        "BRAIN_RELEASE_SHA256": sha256,
        "BRAIN_SKIP_NODE": "1",
        "BRAIN_SKIP_DOCTOR": "1",
        "BRAIN_SKIP_UV_SYNC": "1",
        "BRAIN_SKIP_DESKTOP": "1",
        "BRAIN_INSTALL_FORCE": "1",
        # Bypass the Windows build check when running on Mac/Linux CI.
        "BRAIN_INSTALL_PS1_CI": "1",
    }


def _run_install_ps(
    env: dict[str, str],
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("no PowerShell available on PATH")
    return subprocess.run(
        [
            exe,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL_PS1),
        ],
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


@skip_if_not_windows
def test_install_ps_happy_path(
    ps_install_env: dict[str, str],
    ps_install_dir: Path,
    ps_fake_home: Path,
) -> None:
    """Clean install: exit 0, install dir populated, shim in place."""
    result = _run_install_ps(ps_install_env)

    assert result.returncode == 0, (
        f"install.ps1 failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert ps_install_dir.is_dir()
    assert (ps_install_dir / "pyproject.toml").is_file()
    assert (ps_install_dir / "packages" / "brain_cli").is_dir()

    shim = ps_fake_home / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "brain.cmd"
    assert shim.is_file(), f"shim not written at {shim}"
    body = shim.read_text()
    assert "uv run --project" in body
    assert str(ps_install_dir) in body

    start_menu_lnk = (
        ps_fake_home
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "brain.lnk"
    )
    assert start_menu_lnk.is_file(), f"Start Menu .lnk missing at {start_menu_lnk}"


# ---------------------------------------------------------------------------
# (b) uv already present
# ---------------------------------------------------------------------------


@skip_if_not_windows
def test_install_ps_uv_already_present(
    ps_install_env: dict[str, str],
    ps_install_dir: Path,
) -> None:
    """When uv is on PATH we must skip the installer + continue."""
    result = _run_install_ps(ps_install_env)

    assert result.returncode == 0, result.stderr
    assert "uv already present" in result.stdout, (
        f"expected 'uv already present' in stdout; got:\n{result.stdout}"
    )
    assert (ps_install_dir / "pyproject.toml").is_file()


# ---------------------------------------------------------------------------
# (c) Idempotency: re-run uses the backup-then-replace path
# ---------------------------------------------------------------------------


@skip_if_not_windows
def test_install_ps_repeat_run_idempotent(
    ps_install_env: dict[str, str],
    ps_install_dir: Path,
) -> None:
    """Second install moves old → backup, extracts fresh, exits 0.

    Also verifies that the ``-prev-*`` backup is cleaned up after the
    successful re-run (install.ps1 owns its own backup hygiene; the
    upgrade command rolls differently).
    """
    first = _run_install_ps(ps_install_env)
    assert first.returncode == 0, first.stderr

    marker = ps_install_dir / "touched-between-runs.txt"
    marker.write_text("stay or go?")

    second = _run_install_ps(ps_install_env)
    assert second.returncode == 0, (
        f"second run failed (rc={second.returncode})\n"
        f"stdout:\n{second.stdout}\n"
        f"stderr:\n{second.stderr}"
    )

    assert not marker.exists(), "expected second run to replace the install dir"
    assert (ps_install_dir / "pyproject.toml").is_file()

    parent = ps_install_dir.parent
    leftover = [p for p in parent.iterdir() if "-prev-" in p.name and p != ps_install_dir]
    assert leftover == [], f"unexpected backup dirs left behind: {leftover}"


# ---------------------------------------------------------------------------
# (d) Corrupt tarball SHA: abort cleanly
# ---------------------------------------------------------------------------


@skip_if_not_windows
def test_install_ps_corrupt_tarball_aborts(
    ps_install_env: dict[str, str],
    ps_install_dir: Path,
) -> None:
    """SHA256 mismatch must fail with a clear error + leave nothing extracted."""
    real = ps_install_env["BRAIN_RELEASE_SHA256"]
    corrupt = ("f" if real[0] != "f" else "0") + real[1:]
    env = {**ps_install_env, "BRAIN_RELEASE_SHA256": corrupt}

    result = _run_install_ps(env)

    assert result.returncode != 0, "expected non-zero exit on SHA mismatch"
    combined = result.stdout + result.stderr
    assert "SHA256 mismatch" in combined, (
        f"expected 'SHA256 mismatch' in output:\n{combined}"
    )
    assert not (ps_install_dir / "pyproject.toml").exists(), (
        "expected no extracted files after SHA mismatch"
    )


# ---------------------------------------------------------------------------
# (e) tar.exe missing: clean error + non-zero exit
# ---------------------------------------------------------------------------


@skip_if_not_windows
def test_install_ps_missing_tar_errors(
    ps_install_env: dict[str, str],
    ps_install_dir: Path,
    tmp_path: Path,
) -> None:
    """Hide tar.exe from PATH; install.ps1 should fail with a clear error.

    The Assert-TarExe helper in fetch_tarball.ps1 prints a message
    naming the Windows 10 build 17063+ requirement.
    """
    sandbox = tmp_path / "notar-bin"
    sandbox.mkdir()

    # Symlink (or copy where symlinks aren't permitted) every tool we
    # might need — EXCEPT tar(.exe). We use .which() to discover absolute
    # paths on the host.
    needed = [
        "powershell.exe",
        "powershell",
        "pwsh.exe",
        "pwsh",
        "uv",
        "uv.exe",
        "git",
        "git.exe",
        "cmd.exe",
        "conhost.exe",
        "python",
        "python.exe",
        "python3",
    ]
    for name in needed:
        src = shutil.which(name)
        if not src:
            continue
        dst = sandbox / Path(name).name
        if dst.exists():
            continue
        try:
            dst.symlink_to(src)
        except (OSError, NotImplementedError):
            with contextlib.suppress(OSError):
                shutil.copy2(src, dst)

    env = {**ps_install_env, "PATH": str(sandbox)}

    result = _run_install_ps(env)

    assert result.returncode != 0, "expected non-zero exit when tar.exe missing"
    combined = result.stdout + result.stderr
    assert "tar.exe" in combined or "tar" in combined.lower(), (
        f"expected tar-related error; got:\n{combined}"
    )
