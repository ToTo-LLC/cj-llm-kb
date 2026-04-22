"""Tests for brain_core.tools.mcp_install."""

from __future__ import annotations

import json
from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.mcp_install import NAME, handle


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_mcp_install"


async def test_installs_entry_and_returns_config_path(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    result = await handle(
        {
            "command": "/usr/local/bin/brain-mcp",
            "args": [],
            "env": {"BRAIN_VAULT_ROOT": str(tmp_path / "vault")},
            "config_path": str(cfg),
        },
        _mk_ctx(tmp_path),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "installed"
    assert Path(result.data["config_path"]) == cfg
    assert cfg.exists()
    body = json.loads(cfg.read_text(encoding="utf-8"))
    assert body["mcpServers"]["brain"]["command"] == "/usr/local/bin/brain-mcp"
    assert body["mcpServers"]["brain"]["env"]["BRAIN_VAULT_ROOT"] == str(
        tmp_path / "vault"
    )


async def test_reinstall_creates_backup(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    # First install writes without a backup.
    await handle(
        {"command": "/bin/brain-mcp", "config_path": str(cfg)},
        _mk_ctx(tmp_path),
    )
    # Second install always backs up the prior file.
    result = await handle(
        {"command": "/bin/brain-mcp-2", "config_path": str(cfg)},
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    assert result.data["backup_path"] is not None
    assert Path(result.data["backup_path"]).exists()


async def test_custom_server_name_supported(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    result = await handle(
        {
            "command": "/bin/brain-mcp",
            "config_path": str(cfg),
            "server_name": "brain-staging",
        },
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    assert result.data["server_name"] == "brain-staging"
    body = json.loads(cfg.read_text(encoding="utf-8"))
    assert "brain-staging" in body["mcpServers"]
    assert "brain" not in body["mcpServers"]
