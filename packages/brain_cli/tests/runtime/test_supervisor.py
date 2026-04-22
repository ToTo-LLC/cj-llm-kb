"""Unit tests for the supervisor module.

We never spawn a real uvicorn here; that belongs in the Plan 08 integration
demo. Instead we mock ``subprocess.Popen``, ``psutil.Process``, and
``httpx.get`` so the happy path, timeout, and kill branches are all
exercised fast + deterministically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from brain_cli.runtime import supervisor


class _FakePopen:
    """Minimal stand-in for ``subprocess.Popen`` — captures args + pid."""

    def __init__(self, args: list[str], **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.pid = 98765
        self._poll_result: int | None = None

    def poll(self) -> int | None:
        return self._poll_result

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_start_brain_api_spawns_with_correct_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``start_brain_api`` must pass BRAIN_VAULT_ROOT + BRAIN_WEB_OUT_DIR +
    the chosen port to the child env, and must not use ``shell=True``."""
    vault = tmp_path / "vault"
    install = tmp_path / "install"
    log_dir = vault / ".brain" / "logs"
    log_dir.mkdir(parents=True)

    captured: dict[str, Any] = {}

    def fake_popen(args: list[str], **kwargs: Any) -> _FakePopen:
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        captured["shell"] = kwargs.get("shell", False)
        captured["stdout"] = kwargs.get("stdout")
        captured["stderr"] = kwargs.get("stderr")
        return _FakePopen(args, **kwargs)

    monkeypatch.setattr(supervisor.subprocess, "Popen", fake_popen)

    proc = supervisor.start_brain_api(
        port=4317,
        install_dir=install,
        vault_root=vault,
        web_out_dir=install / "web" / "out",
        log_path=log_dir / "brain-api.log",
    )

    assert proc.pid == 98765
    assert captured["shell"] is False
    env = captured["env"]
    assert env["BRAIN_VAULT_ROOT"] == str(vault)
    assert env["BRAIN_WEB_OUT_DIR"] == str(install / "web" / "out")
    assert env["BRAIN_API_PORT"] == "4317"
    # Port appears on the argv (uvicorn --port <n>).
    assert "4317" in " ".join(str(a) for a in captured["args"])


def test_stop_brain_api_terminates_then_kills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Must call terminate() first and fall back to kill() if the process
    doesn't exit within the grace window."""
    calls: list[str] = []

    class _FakeProc:
        def terminate(self) -> None:
            calls.append("terminate")

        def wait(self, timeout: float | None = None) -> int:
            calls.append(f"wait({timeout})")
            # Simulate process NOT exiting in time — triggers kill path.
            import psutil

            raise psutil.TimeoutExpired(seconds=timeout or 0)

        def kill(self) -> None:
            calls.append("kill")

    monkeypatch.setattr(supervisor.psutil, "Process", lambda _pid: _FakeProc())
    supervisor.stop_brain_api(pid=12345)
    assert calls == ["terminate", "wait(5.0)", "kill"]


def test_stop_brain_api_clean_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """When terminate() works within the grace window, kill() must NOT be called."""
    calls: list[str] = []

    class _FakeProc:
        def terminate(self) -> None:
            calls.append("terminate")

        def wait(self, timeout: float | None = None) -> int:
            calls.append(f"wait({timeout})")
            return 0

        def kill(self) -> None:
            calls.append("kill")

    monkeypatch.setattr(supervisor.psutil, "Process", lambda _pid: _FakeProc())
    supervisor.stop_brain_api(pid=12345)
    assert calls == ["terminate", "wait(5.0)"]


def test_stop_brain_api_handles_already_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    """psutil raises NoSuchProcess if the PID is already gone — must swallow
    this since it's the happy case (nothing to kill)."""
    import psutil

    def raise_no_such(_pid: int) -> Any:
        raise psutil.NoSuchProcess(pid=_pid)

    monkeypatch.setattr(supervisor.psutil, "Process", raise_no_such)
    # Must not raise.
    supervisor.stop_brain_api(pid=12345)


def test_wait_for_healthz_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 on the first probe must return True immediately."""

    class _FakeResponse:
        status_code = 200

    def fake_get(_url: str, timeout: float = 1.0) -> _FakeResponse:
        return _FakeResponse()

    monkeypatch.setattr(supervisor.httpx, "get", fake_get)
    assert supervisor.wait_for_healthz(port=4317, timeout_s=1.0) is True


def test_wait_for_healthz_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the endpoint never responds 200 within the window, return False."""
    import httpx

    def fake_get(_url: str, timeout: float = 1.0) -> Any:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(supervisor.httpx, "get", fake_get)
    # Short timeout — the poll loop sleeps 200ms between tries. 0.5s is plenty
    # to prove the False branch without making the test slow.
    assert supervisor.wait_for_healthz(port=4317, timeout_s=0.5) is False
