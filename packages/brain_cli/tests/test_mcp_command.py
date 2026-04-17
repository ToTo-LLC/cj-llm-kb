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
