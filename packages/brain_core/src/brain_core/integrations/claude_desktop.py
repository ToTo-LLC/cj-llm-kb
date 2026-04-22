"""Claude Desktop integration — config detection, backup, merge, verify, uninstall.

Per Plan 04 D10a + D11a. Pure file handling; no MCP SDK dependency (that lives in
``brain_mcp``). Every config mutation goes through a timestamped backup + atomic
write, so a user's manual edits to ``claude_desktop_config.json`` are never lost.

Cross-platform: ``pathlib`` everywhere, LF newlines on disk, ``os.replace`` for
atomic rename, platform detection via ``platform.system()``. The env var
``BRAIN_CLAUDE_DESKTOP_CONFIG_PATH`` overrides default OS detection — tests use
this to avoid touching real user config.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class UnsupportedPlatformError(RuntimeError):
    """Raised when ``detect_config_path()`` runs on an unsupported OS."""


@dataclass(frozen=True)
class InstallResult:
    """Outcome of an ``install()`` call."""

    installed: bool
    config_path: Path
    backup_path: Path | None


@dataclass(frozen=True)
class UninstallResult:
    """Outcome of an ``uninstall()`` call."""

    removed: bool
    config_path: Path
    backup_path: Path | None


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of a ``verify()`` call — a snapshot, not a mutation."""

    config_exists: bool
    entry_present: bool
    executable_resolves: bool
    command: str | None


@dataclass(frozen=True)
class SelftestResult:
    """Outcome of a ``selftest()`` call.

    ``ok`` is True only when every check (config exists, entry present,
    executable resolves) passes. Individual check results are surfaced
    so the UI can render a checklist rather than a single pass/fail.
    The tool-tier wrapper in ``brain_core.tools.mcp_selftest`` does not
    spawn a subprocess — the CLI ``brain mcp selftest`` command retains
    the subprocess round-trip for the fuller end-to-end test.
    """

    ok: bool
    config_exists: bool
    entry_present: bool
    executable_resolves: bool
    command: str | None
    config_path: Path


def selftest(*, config_path: Path, server_name: str = "brain") -> SelftestResult:
    """Run the non-subprocess slice of `brain mcp selftest`.

    Pure file / path validation — spawning the MCP server as a child
    process requires ``mcp.client.stdio`` and the ``brain-mcp`` executable,
    which live above ``brain_core`` (brain_core must not import the MCP
    SDK). That check stays in ``brain_cli.commands.mcp.selftest_cmd``.
    """
    v = verify(config_path=config_path, server_name=server_name)
    ok = v.config_exists and v.entry_present and v.executable_resolves
    return SelftestResult(
        ok=ok,
        config_exists=v.config_exists,
        entry_present=v.entry_present,
        executable_resolves=v.executable_resolves,
        command=v.command,
        config_path=config_path,
    )


_ENV_OVERRIDE = "BRAIN_CLAUDE_DESKTOP_CONFIG_PATH"


def detect_config_path() -> Path:
    """Return the Claude Desktop config path for the current OS.

    Override via the ``BRAIN_CLAUDE_DESKTOP_CONFIG_PATH`` environment variable.
    Raises ``UnsupportedPlatformError`` on unknown platforms or when Windows is
    detected without ``%APPDATA%`` set.
    """
    override = os.environ.get(_ENV_OVERRIDE)
    if override:
        return Path(override)

    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise UnsupportedPlatformError("Windows platform detected but %APPDATA% is not set")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if system == "Linux":
        # Claude Desktop isn't officially on Linux, but the XDG path is stable.
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    raise UnsupportedPlatformError(f"unsupported platform: {system}")


def read_config(path: Path) -> dict[str, Any]:
    """Read the Claude Desktop config JSON; return ``{}`` if the file is absent."""
    if not path.exists():
        return {}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def write_config(path: Path, config: dict[str, Any]) -> Path | None:
    """Write ``config`` to ``path`` atomically, backing up any prior file first.

    Returns the backup file path (``<name>.backup.<YYYY-MM-DDTHH-MM-SS>.json``)
    if a prior file existed, else ``None``. Parent directories are created as
    needed. Output is UTF-8 with LF line endings and a trailing newline.
    """
    backup_path: Path | None = None
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
        backup_path = path.with_name(f"{path.name}.backup.{timestamp}.json")
        shutil.copy2(path, backup_path)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)
    return backup_path


def install(
    *,
    config_path: Path,
    server_name: str = "brain",
    command: str,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> InstallResult:
    """Install or update the ``mcpServers.<server_name>`` entry in the config.

    Idempotent: calling twice with the same arguments produces identical config
    content. A timestamped backup is created before every write (even when the
    prior config already matched).
    """
    config = read_config(config_path)
    mcp_servers = config.setdefault("mcpServers", {})

    entry: dict[str, Any] = {"command": command}
    if args:
        entry["args"] = args
    if env:
        entry["env"] = env
    mcp_servers[server_name] = entry

    backup = write_config(config_path, config)
    return InstallResult(installed=True, config_path=config_path, backup_path=backup)


def uninstall(*, config_path: Path, server_name: str = "brain") -> UninstallResult:
    """Remove ``mcpServers.<server_name>`` from the config.

    No-op when the entry is absent. If removing the entry leaves ``mcpServers``
    empty, the key itself is deleted to keep the config file tidy.
    """
    config = read_config(config_path)
    servers = config.get("mcpServers", {})
    if server_name not in servers:
        return UninstallResult(removed=False, config_path=config_path, backup_path=None)
    del servers[server_name]
    if not servers:
        del config["mcpServers"]
    backup = write_config(config_path, config)
    return UninstallResult(removed=True, config_path=config_path, backup_path=backup)


def verify(*, config_path: Path, server_name: str = "brain") -> VerifyResult:
    """Check whether the config has the expected entry and the command resolves.

    ``executable_resolves`` is ``True`` when the configured command path exists
    and passes ``os.access(..., os.X_OK)``. On Windows ``os.X_OK`` is largely
    cosmetic (most files report executable), but the check remains correct for
    the common case of a bad/typoed path.
    """
    if not config_path.exists():
        return VerifyResult(
            config_exists=False,
            entry_present=False,
            executable_resolves=False,
            command=None,
        )
    config = read_config(config_path)
    servers = config.get("mcpServers", {})
    entry = servers.get(server_name)
    if entry is None:
        return VerifyResult(
            config_exists=True,
            entry_present=False,
            executable_resolves=False,
            command=None,
        )
    command = entry.get("command")
    if not command:
        return VerifyResult(
            config_exists=True,
            entry_present=True,
            executable_resolves=False,
            command=None,
        )
    cmd_path = Path(command)
    resolves = cmd_path.exists() and os.access(cmd_path, os.X_OK)
    return VerifyResult(
        config_exists=True,
        entry_present=True,
        executable_resolves=resolves,
        command=command,
    )
