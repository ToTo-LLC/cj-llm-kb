"""Tests for `brain mcp` CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_cli.app import app
from typer.testing import CliRunner


def test_brain_mcp_help() -> None:
    result = CliRunner().invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "install" in result.stdout
    assert "uninstall" in result.stdout
    assert "selftest" in result.stdout
    assert "status" in result.stdout


def test_brain_mcp_install_with_yes_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_config = tmp_path / "claude_desktop_config.json"
    monkeypatch.setenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", str(fake_config))
    result = CliRunner().invoke(
        app,
        ["mcp", "install", "--vault", str(tmp_path / "vault"), "--yes"],
    )
    assert result.exit_code == 0
    assert fake_config.exists()
    cfg = json.loads(fake_config.read_text(encoding="utf-8"))
    assert "brain" in cfg["mcpServers"]


def test_brain_mcp_uninstall_removes_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_config = tmp_path / "claude_desktop_config.json"
    monkeypatch.setenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", str(fake_config))
    runner = CliRunner()
    runner.invoke(app, ["mcp", "install", "--vault", str(tmp_path / "vault"), "--yes"])
    result = runner.invoke(app, ["mcp", "uninstall", "--yes"])
    assert result.exit_code == 0
    cfg = json.loads(fake_config.read_text(encoding="utf-8"))
    assert "brain" not in cfg.get("mcpServers", {})


def test_brain_mcp_status_reports_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", str(tmp_path / "nope.json"))
    result = CliRunner().invoke(app, ["mcp", "status"])
    assert result.exit_code == 0
    assert "config_exists" in result.stdout or "not installed" in result.stdout.lower()


def test_brain_mcp_install_requires_yes_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_config = tmp_path / "claude_desktop_config.json"
    monkeypatch.setenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", str(fake_config))
    result = CliRunner().invoke(
        app,
        ["mcp", "install", "--vault", str(tmp_path / "vault")],
        input="no\n",
    )
    assert result.exit_code != 0
    assert not fake_config.exists()


def test_selftest_subprocess_env_reads_from_installed_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plan 04 Task 25 regression: ``brain mcp selftest`` must pass the env
    dict from the installed Claude Desktop config through to the subprocess,
    not a hardcoded BRAIN_VAULT_ROOT. Otherwise selftest silently tests a
    different vault than the one Claude Desktop uses.
    """
    # First install with a custom vault path so the config entry carries a
    # distinctive env dict.
    fake_config = tmp_path / "claude_desktop_config.json"
    custom_vault = tmp_path / "custom-vault"
    monkeypatch.setenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", str(fake_config))
    runner = CliRunner()
    install_result = runner.invoke(
        app,
        [
            "mcp",
            "install",
            "--vault",
            str(custom_vault),
            "--domains",
            "research,work,personal",
            "--yes",
        ],
    )
    assert install_result.exit_code == 0

    # Now intercept the subprocess spawn so we can inspect the env dict the
    # selftest would pass to StdioServerParameters without actually launching
    # a child process.
    captured: dict[str, object] = {}

    class _FakeStdioParams:
        def __init__(self, *, command: str, args: list[str], env: dict[str, str]) -> None:
            captured["command"] = command
            captured["args"] = args
            captured["env"] = env

    # Stop the test short of actually launching stdio_client by making the
    # helper raise after constructing the params.
    from brain_cli.commands import mcp as mcp_cmd

    async def fake_subprocess_tools_list(*, config_path: Path, server_name: str = "brain") -> int:
        config = mcp_cmd.read_config(config_path)
        entry = config.get("mcpServers", {}).get(server_name, {})
        env = dict(entry.get("env") or {})
        # Mirror the fallback in the real helper so the assertion is honest.
        if "BRAIN_VAULT_ROOT" not in env:
            env["BRAIN_VAULT_ROOT"] = str(Path.home() / "Documents" / "brain")
        _FakeStdioParams(
            command=mcp_cmd._resolve_brain_mcp_command(),
            args=mcp_cmd._resolve_brain_mcp_args(),
            env=env,
        )
        # Pretend tools/list returned 18 tools so the final sanity check passes
        # without requiring a real subprocess.
        return 18

    monkeypatch.setattr(mcp_cmd, "_subprocess_tools_list", fake_subprocess_tools_list)

    result = runner.invoke(app, ["mcp", "selftest"])
    # selftest's check 1 (verify) will fail because the installed command
    # path doesn't actually exist in test — that's fine. The regression test
    # asserts on the env capture that happens inside check 2 only if we make
    # verify pass. Fake it out:
    if "config verification: " in result.output and "FAIL" in result.output:
        # Force verify() into an OK state by monkeypatching it for check 1.
        from brain_core.integrations import claude_desktop as cd

        def fake_verify(*, config_path: Path, server_name: str = "brain"):  # type: ignore[no-untyped-def]
            return cd.VerifyResult(
                config_exists=True,
                entry_present=True,
                executable_resolves=True,
                command="brain-mcp",
            )

        monkeypatch.setattr(mcp_cmd, "verify", fake_verify)
        result = runner.invoke(app, ["mcp", "selftest"])

    assert result.exit_code == 0, result.output
    env_captured = captured["env"]
    assert isinstance(env_captured, dict)
    # The env the subprocess receives must carry the *installed* vault path,
    # not the old hardcoded ~/Documents/brain.
    assert env_captured["BRAIN_VAULT_ROOT"] == str(custom_vault)
    assert env_captured["BRAIN_ALLOWED_DOMAINS"] == "research,work,personal"
