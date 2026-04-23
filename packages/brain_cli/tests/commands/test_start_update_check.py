"""Plan 09 Task 4 — ``brain start`` background update-check nudge (Q2a).

Unit-tests ``brain_cli.commands.start._update_check_nudge`` — the function
that the daemon thread runs after the "running at ..." banner. We do NOT
exercise the threading integration end-to-end; the stdlib's
``Thread(daemon=True)`` semantics are well-trusted and a thread-based
integration test would be flaky. Instead, we pin the four behaviors that
matter:

  (a) Newer version found → one-line nudge printed.
  (b) Same version (check returns ``None``) → no output.
  (c) Any exception (timeout, HTTP error, malformed JSON) → silent,
      no crash — the nudge must never escape an error to the supervising
      ``brain start`` process.
  (d) ``BRAIN_NO_UPDATE_CHECK=1`` → ``check_latest_release`` is never
      invoked (opt-out happens BEFORE the network call).

Tests assert against ``capsys`` rather than ``CliRunner`` output since we
call ``_update_check_nudge`` directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_cli.commands import start as start_mod
from brain_cli.runtime import release as release_mod
from brain_cli.runtime.release import ReleaseInfo


def _point_at_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: str) -> Path:
    """Create a tmp install dir with a VERSION file and point ``BRAIN_INSTALL_DIR`` at it."""
    install = tmp_path / "brain"
    install.mkdir()
    (install / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(install))
    return install


def test_nudge_prints_when_newer_version_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``ReleaseInfo`` from ``check_latest_release`` triggers the nudge line."""
    _point_at_install(monkeypatch, tmp_path, "0.1.0")
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)

    info = ReleaseInfo(
        version="0.2.0",
        tag_name="v0.2.0",
        tarball_url="https://example.com/brain-0.2.0.tar.gz",
        sha256=None,
        body="## What's new\n- faster everything",
    )

    def _fake_check(current_version: str, *, timeout_s: int = 10) -> ReleaseInfo | None:
        assert current_version == "0.1.0"
        assert timeout_s == 3
        return info

    monkeypatch.setattr(release_mod, "check_latest_release", _fake_check)

    start_mod._update_check_nudge()

    captured = capsys.readouterr()
    assert "A newer version is available" in captured.out
    assert "0.1.0" in captured.out
    assert "0.2.0" in captured.out
    assert "brain upgrade" in captured.out


def test_nudge_silent_when_already_latest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``check_latest_release`` returning ``None`` (already up-to-date) means no output."""
    _point_at_install(monkeypatch, tmp_path, "0.1.0")
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)

    def _fake_check(current_version: str, *, timeout_s: int = 10) -> ReleaseInfo | None:
        return None

    monkeypatch.setattr(release_mod, "check_latest_release", _fake_check)

    start_mod._update_check_nudge()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_nudge_silent_on_timeout_or_network_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Any exception during the check is swallowed — the nudge must never crash ``brain start``."""
    _point_at_install(monkeypatch, tmp_path, "0.1.0")
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)

    def _fake_check(current_version: str, *, timeout_s: int = 10) -> ReleaseInfo | None:
        raise TimeoutError("GitHub took too long")

    monkeypatch.setattr(release_mod, "check_latest_release", _fake_check)

    # Must not raise.
    start_mod._update_check_nudge()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_nudge_skips_network_call_when_env_opt_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``BRAIN_NO_UPDATE_CHECK=1`` → ``check_latest_release`` is never called.

    The opt-out is a privacy posture: no outbound network call at all.
    We verify by spying on ``check_latest_release`` and asserting the
    call count stays at zero even after the nudge runs.
    """
    _point_at_install(monkeypatch, tmp_path, "0.1.0")
    monkeypatch.setenv("BRAIN_NO_UPDATE_CHECK", "1")

    calls: list[tuple[str, int]] = []

    def _spy(current_version: str, *, timeout_s: int = 10) -> ReleaseInfo | None:
        calls.append((current_version, timeout_s))
        return None

    monkeypatch.setattr(release_mod, "check_latest_release", _spy)

    start_mod._update_check_nudge()

    assert calls == [], f"check_latest_release must not be called under opt-out; got {calls!r}"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
