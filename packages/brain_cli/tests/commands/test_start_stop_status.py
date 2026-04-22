"""Integration tests for the ``brain start / stop / status`` commands.

Uses Typer's CliRunner + heavy monkeypatching to avoid spawning real
processes. Each test sets ``BRAIN_VAULT_ROOT`` to a ``tmp_path`` so PID +
port files land in a scratch dir.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from brain_cli.app import app
from brain_cli.runtime import pidfile, supervisor
from typer.testing import CliRunner

runner = CliRunner()


class _FakePopen:
    """Stand-in for ``subprocess.Popen`` — records what the supervisor asked for."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.pid = 54321

    def poll(self) -> int | None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        return 0


def _set_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the supervisor at a throwaway vault + install dir. Returns vault."""
    vault = tmp_path / "vault"
    vault.mkdir()
    install = tmp_path / "install"
    install.mkdir()
    # Create a plausible web/out so the supervisor can resolve BRAIN_WEB_OUT_DIR.
    web_out = install / "web" / "out"
    web_out.mkdir(parents=True)
    (web_out / "index.html").write_text("<!-- stub -->", encoding="utf-8")

    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(vault))
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(install))
    return vault


def test_start_writes_pid_and_port_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``brain start`` must spawn the child + write pid + port files + open the browser."""
    vault = _set_vault(monkeypatch, tmp_path)
    opened: list[str] = []

    monkeypatch.setattr(supervisor.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(supervisor.httpx, "get", lambda *a, **kw: _Resp200())
    # Capture the browser URL without actually launching a browser in CI.
    from brain_cli.runtime import browser

    monkeypatch.setattr(browser, "open_browser", lambda url: opened.append(url))

    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0, result.output

    pid_file = vault / ".brain" / "run" / "brain.pid"
    port_file = vault / ".brain" / "run" / "brain.port"
    assert pid_file.exists(), f"pid file missing; output:\n{result.output}"
    assert port_file.exists()
    assert pidfile.read_pid(pid_file) == 54321
    port = int(port_file.read_text().strip())
    assert 4317 <= port <= 4330
    assert opened == [f"http://localhost:{port}/"]
    assert f"brain running at http://localhost:{port}/" in result.output


def test_start_idempotent_when_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second ``brain start`` while the daemon is alive must print
    "already running" + exit 0 without spawning a duplicate."""
    vault = _set_vault(monkeypatch, tmp_path)
    run_dir = vault / ".brain" / "run"
    run_dir.mkdir(parents=True)
    pidfile.write_pid(run_dir / "brain.pid", 77777)
    (run_dir / "brain.port").write_text("4321", encoding="utf-8")

    # Tell the supervisor this PID is alive + is brain_api.
    monkeypatch.setattr(pidfile, "is_alive", lambda _pid: True)
    monkeypatch.setattr(pidfile, "is_brain_api", lambda _pid: True)

    spawn_called = {"count": 0}

    def tracking_popen(*a: Any, **kw: Any) -> _FakePopen:
        spawn_called["count"] += 1
        return _FakePopen(*a, **kw)

    monkeypatch.setattr(supervisor.subprocess, "Popen", tracking_popen)

    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0, result.output
    assert "already running" in result.output
    assert spawn_called["count"] == 0


def test_status_reports_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``brain status`` on a live daemon must print pid + URL + "running"."""
    vault = _set_vault(monkeypatch, tmp_path)
    run_dir = vault / ".brain" / "run"
    run_dir.mkdir(parents=True)
    pidfile.write_pid(run_dir / "brain.pid", 44444)
    (run_dir / "brain.port").write_text("4319", encoding="utf-8")

    monkeypatch.setattr(pidfile, "is_alive", lambda _pid: True)
    monkeypatch.setattr(pidfile, "is_brain_api", lambda _pid: True)

    class _FakeProc:
        def create_time(self) -> float:
            import time

            return time.time() - 125  # 2m05s uptime

    monkeypatch.setattr(pidfile.psutil, "Process", lambda _pid: _FakeProc())

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "running" in result.output
    assert "44444" in result.output
    assert "http://localhost:4319/" in result.output


def test_status_reports_not_running_when_no_pidfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing pid file → "not running" exit 0 (it's a valid observable state,
    not an error)."""
    _set_vault(monkeypatch, tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "not running" in result.output


def test_status_json_returns_valid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``brain status --json`` must emit a single valid JSON document."""
    vault = _set_vault(monkeypatch, tmp_path)
    run_dir = vault / ".brain" / "run"
    run_dir.mkdir(parents=True)
    pidfile.write_pid(run_dir / "brain.pid", 33333)
    (run_dir / "brain.port").write_text("4320", encoding="utf-8")

    monkeypatch.setattr(pidfile, "is_alive", lambda _pid: True)
    monkeypatch.setattr(pidfile, "is_brain_api", lambda _pid: True)

    class _FakeProc:
        def create_time(self) -> float:
            import time

            return time.time() - 10

    monkeypatch.setattr(pidfile.psutil, "Process", lambda _pid: _FakeProc())

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert data["running"] is True
    assert data["pid"] == 33333
    assert data["port"] == 4320
    assert data["url"] == "http://localhost:4320/"


def test_stop_removes_files_and_calls_stop_brain_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``brain stop`` on a live daemon must call the psutil-backed terminator
    and remove pid + port files."""
    vault = _set_vault(monkeypatch, tmp_path)
    run_dir = vault / ".brain" / "run"
    run_dir.mkdir(parents=True)
    pid_file = run_dir / "brain.pid"
    port_file = run_dir / "brain.port"
    pidfile.write_pid(pid_file, 22222)
    port_file.write_text("4317", encoding="utf-8")

    monkeypatch.setattr(pidfile, "is_alive", lambda _pid: True)
    stop_calls: list[int] = []
    monkeypatch.setattr(supervisor, "stop_brain_api", lambda pid: stop_calls.append(pid))

    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0, result.output
    assert stop_calls == [22222]
    assert not pid_file.exists()
    assert not port_file.exists()


def test_stop_is_idempotent_when_not_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``brain stop`` with no pid file must exit 0 + print "not running"."""
    _set_vault(monkeypatch, tmp_path)
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0, result.output
    assert "not running" in result.output


class _Resp200:
    status_code = 200
