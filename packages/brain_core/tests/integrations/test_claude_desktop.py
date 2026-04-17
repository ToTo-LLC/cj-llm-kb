"""Tests for brain_core.integrations.claude_desktop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.integrations.claude_desktop import (
    detect_config_path,
    install,
    read_config,
    uninstall,
    verify,
    write_config,
)


class TestDetectConfigPath:
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", str(tmp_path / "custom.json"))
        assert detect_config_path() == tmp_path / "custom.json"

    def test_default_macos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", raising=False)
        monkeypatch.setattr(
            "brain_core.integrations.claude_desktop.platform.system", lambda: "Darwin"
        )
        path = detect_config_path()
        assert path.name == "claude_desktop_config.json"
        assert "Library/Application Support/Claude" in str(path)

    def test_default_windows(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("BRAIN_CLAUDE_DESKTOP_CONFIG_PATH", raising=False)
        monkeypatch.setattr(
            "brain_core.integrations.claude_desktop.platform.system", lambda: "Windows"
        )
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
        path = detect_config_path()
        assert "Claude" in str(path)
        assert path.name == "claude_desktop_config.json"


class TestReadWriteConfig:
    def test_read_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_config(tmp_path / "nope.json") == {}

    def test_write_and_read_round_trip(self, tmp_path: Path) -> None:
        cfg = {"mcpServers": {"brain": {"command": "/bin/brain"}}}
        write_config(tmp_path / "config.json", cfg)
        assert read_config(tmp_path / "config.json") == cfg

    def test_write_creates_backup(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text('{"existing": true}', encoding="utf-8")
        backup_path = write_config(path, {"updated": True})
        assert backup_path is not None
        assert backup_path.exists()
        assert "backup" in backup_path.name
        assert read_config(backup_path) == {"existing": True}


class TestInstall:
    def test_install_fresh_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        result = install(
            config_path=config_path,
            command="/usr/local/bin/brain-mcp",
            args=["--vault", "/home/user/brain"],
        )
        assert result.installed is True
        cfg = read_config(config_path)
        assert "brain" in cfg["mcpServers"]
        assert cfg["mcpServers"]["brain"]["command"] == "/usr/local/bin/brain-mcp"
        assert cfg["mcpServers"]["brain"]["args"] == ["--vault", "/home/user/brain"]

    def test_install_preserves_existing_servers(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"mcpServers": {"other": {"command": "/other"}}}),
            encoding="utf-8",
        )
        install(config_path=config_path, command="/brain-mcp")
        cfg = read_config(config_path)
        assert "other" in cfg["mcpServers"]
        assert "brain" in cfg["mcpServers"]

    def test_install_is_idempotent(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        install(config_path=config_path, command="/brain-mcp")
        install(config_path=config_path, command="/brain-mcp")
        cfg = read_config(config_path)
        assert cfg["mcpServers"]["brain"]["command"] == "/brain-mcp"
        # Two install calls produce at least one backup (second install backs up the first).
        backups = list(config_path.parent.glob("config.json.backup.*"))
        assert len(backups) >= 1


class TestUninstall:
    def test_uninstall_removes_entry(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        install(config_path=config_path, command="/brain-mcp")
        result = uninstall(config_path=config_path)
        assert result.removed is True
        cfg = read_config(config_path)
        assert "brain" not in cfg.get("mcpServers", {})

    def test_uninstall_noop_when_missing(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        result = uninstall(config_path=config_path)
        assert result.removed is False


class TestVerify:
    def test_verify_missing_config(self, tmp_path: Path) -> None:
        result = verify(config_path=tmp_path / "nope.json")
        assert result.config_exists is False
        assert result.entry_present is False

    def test_verify_installed_with_valid_executable(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        # Use a real executable that exists on every POSIX system.
        install(config_path=config_path, command="/bin/sh")
        result = verify(config_path=config_path)
        assert result.config_exists is True
        assert result.entry_present is True
        assert result.executable_resolves is True

    def test_verify_installed_with_missing_executable(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        install(config_path=config_path, command="/definitely/not/a/real/path/brain-mcp")
        result = verify(config_path=config_path)
        assert result.config_exists is True
        assert result.entry_present is True
        assert result.executable_resolves is False
