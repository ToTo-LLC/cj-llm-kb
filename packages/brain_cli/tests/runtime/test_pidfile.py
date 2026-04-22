"""Unit tests for the cross-platform PID file helper.

The supervisor treats a PID file as a three-state signal:
    * missing      → no daemon is running
    * present + live + cmdline matches brain_api → running
    * present + dead OR wrong cmdline          → stale, delete + continue

These tests pin each branch with psutil mocks so we never need to spawn a
real ``brain_api`` process. The one non-mocked signal we use is ``os.getpid()``
for the alive-PID happy path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from brain_cli.runtime import pidfile


def test_write_and_read_pid_round_trip(tmp_path: Path) -> None:
    """``read_pid`` must return exactly what ``write_pid`` wrote."""
    path = tmp_path / "brain.pid"
    pidfile.write_pid(path, 12345)
    assert pidfile.read_pid(path) == 12345


def test_read_pid_missing_returns_none(tmp_path: Path) -> None:
    """A non-existent PID file is the normal "no daemon running" state."""
    path = tmp_path / "brain.pid"
    assert pidfile.read_pid(path) is None


def test_is_alive_true_for_current_process_false_for_bogus() -> None:
    """``is_alive`` uses psutil; verify it agrees on the test runner PID
    and disagrees for a PID we're confident is unused."""
    assert pidfile.is_alive(os.getpid()) is True
    # PID 0 / 1 are reserved (kernel / init) — never match brain_api cmdline.
    # Use a large random-ish PID that we're confident is free.
    assert pidfile.is_alive(999_999_999) is False


def test_is_brain_api_detects_cmdline(monkeypatch: pytest.MonkeyPatch) -> None:
    """``is_brain_api`` must return True when cmdline contains the factory path."""

    class _FakeProc:
        def cmdline(self) -> list[str]:
            return ["python", "-m", "uvicorn", "brain_cli.runtime.backend_factory:build_app"]

        def name(self) -> str:
            return "python3.12"

    def fake_process(_pid: int) -> _FakeProc:
        return _FakeProc()

    monkeypatch.setattr(pidfile.psutil, "Process", fake_process)
    assert pidfile.is_brain_api(12345) is True


def test_is_brain_api_false_for_unrelated_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live PID belonging to some other process must be treated as stale."""

    class _OtherProc:
        def cmdline(self) -> list[str]:
            return ["/Applications/Safari.app/Contents/MacOS/Safari"]

        def name(self) -> str:
            return "Safari"

    monkeypatch.setattr(pidfile.psutil, "Process", lambda _pid: _OtherProc())
    assert pidfile.is_brain_api(12345) is False


def test_is_brain_api_handles_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """psutil raises AccessDenied on some restricted processes — treat as unknown
    (return False so the PID file is considered stale + recreated)."""
    import psutil

    def raise_denied(_pid: int) -> Any:
        raise psutil.AccessDenied(pid=_pid)

    monkeypatch.setattr(pidfile.psutil, "Process", raise_denied)
    assert pidfile.is_brain_api(12345) is False


def test_delete_pid_cleans_up(tmp_path: Path) -> None:
    """``delete_pid`` removes the file and is idempotent if missing."""
    path = tmp_path / "brain.pid"
    pidfile.write_pid(path, 42)
    assert path.exists()

    pidfile.delete_pid(path)
    assert not path.exists()

    # Second call is a no-op — deletes must be idempotent since the
    # supervisor's cleanup path calls this unconditionally.
    pidfile.delete_pid(path)
    assert not path.exists()
