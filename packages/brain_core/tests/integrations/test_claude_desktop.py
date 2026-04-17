"""Tests for brain_core.integrations.claude_desktop."""

from __future__ import annotations

import json
import sys
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
        # Use sys.executable (the running Python interpreter) — guaranteed to
        # exist on every platform the test suite runs on (Mac, Windows, Linux).
        # Hardcoding /bin/sh would fail the Windows CI matrix.
        install(config_path=config_path, command=sys.executable)
        result = verify(config_path=config_path)
        assert result.config_exists is True
        assert result.entry_present is True
        assert result.executable_resolves is True

    def test_verify_installed_with_missing_executable(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        # Build a path guaranteed not to exist on ANY platform by pointing
        # below tmp_path. Hardcoding a POSIX-flavored path would still "work"
        # on Windows (the file wouldn't exist there either) but this is more
        # obviously correct regardless of OS.
        missing = tmp_path / "definitely" / "not" / "a" / "real" / "brain-mcp"
        install(config_path=config_path, command=str(missing))
        result = verify(config_path=config_path)
        assert result.config_exists is True
        assert result.entry_present is True
        assert result.executable_resolves is False


class TestCrossPlatformProperties:
    """Plan 04 Task 23 — pin the cross-platform invariants the audit asserts.

    These tests fail loudly if a future change reintroduces a POSIX-only test
    executable, adds a Windows-unsafe character to the backup filename, or
    writes CRLF line endings to ``claude_desktop_config.json``.
    """

    def test_backup_filename_has_no_windows_reserved_chars(self, tmp_path: Path) -> None:
        # Windows forbids : < > " | ? * \ / in filenames. Backup timestamps must
        # use `-` separators, not `:`, so the filename is portable.
        path = tmp_path / "config.json"
        path.write_text('{"existing": true}', encoding="utf-8")
        backup = write_config(path, {"updated": True})
        assert backup is not None
        forbidden = set(':<>"|?*')
        assert not (forbidden & set(backup.name)), (
            f"backup filename {backup.name!r} contains Windows-forbidden chars"
        )

    def test_write_config_uses_lf_line_endings_on_disk(self, tmp_path: Path) -> None:
        # Read raw bytes — `write_text(newline="\n")` must prevent the platform
        # default CRLF translation on Windows. If someone removes the newline
        # kwarg, this assertion catches it.
        path = tmp_path / "config.json"
        write_config(path, {"mcpServers": {"brain": {"command": "x"}}})
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"CRLF found in config: {raw!r}"
        assert raw.endswith(b"\n")

    def test_verify_valid_executable_test_does_not_hardcode_posix_path(self) -> None:
        # Regression pin — if someone re-introduces `/bin/sh` or similar in the
        # valid-executable test, the Windows matrix would break silently until
        # CI ran. We assemble the forbidden patterns at runtime from their
        # non-adjacent parts so this very assertion doesn't self-match.
        test_file = Path(__file__)
        source = test_file.read_text(encoding="utf-8")
        posix_binaries = ("sh", "bash", "dash")
        # Build the strings at runtime so the literals never appear verbatim
        # in the test source itself.
        quote_styles = ('"', "'")
        forbidden = []
        for binary in posix_binaries:
            for q in quote_styles:
                forbidden.append(f"command={q}/bin/{binary}{q}")
                forbidden.append(f"command={q}/usr/bin/{binary}{q}")
        for pattern in forbidden:
            assert pattern not in source, (
                f"POSIX-only executable {pattern!r} reappeared — "
                "use sys.executable instead for cross-platform safety"
            )

    def test_detect_config_path_no_hardcoded_slashes_in_source(self) -> None:
        # The implementation must build paths via pathlib's `/` operator, not
        # string concatenation with hardcoded separators. Grep the source of
        # `claude_desktop.py` for forbidden literal path strings.
        import brain_core.integrations.claude_desktop as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        forbidden_literals = [
            '"Library/Application Support/Claude/claude_desktop_config.json"',
            '"\\Claude\\claude_desktop_config.json"',
            '".config/Claude/claude_desktop_config.json"',
        ]
        for literal in forbidden_literals:
            assert literal not in src, (
                f"hardcoded path literal {literal!r} found — use pathlib instead"
            )
