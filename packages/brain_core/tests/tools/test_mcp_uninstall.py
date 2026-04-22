"""Tests for brain_core.tools.mcp_uninstall."""

from __future__ import annotations

import json
from pathlib import Path

from brain_core.integrations.claude_desktop import install as core_install
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.mcp_uninstall import NAME, handle


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
    assert NAME == "brain_mcp_uninstall"


async def test_removes_existing_entry(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    core_install(config_path=cfg, command="/bin/brain-mcp")
    result = await handle(
        {"config_path": str(cfg)},
        _mk_ctx(tmp_path),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "uninstalled"
    body = json.loads(cfg.read_text(encoding="utf-8"))
    assert "brain" not in body.get("mcpServers", {})


async def test_missing_entry_returns_not_installed(tmp_path: Path) -> None:
    cfg = tmp_path / "nope.json"
    result = await handle(
        {"config_path": str(cfg)},
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    assert result.data["status"] == "not_installed"


async def test_uninstall_creates_backup_when_entry_present(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    core_install(config_path=cfg, command="/bin/brain-mcp")
    result = await handle(
        {"config_path": str(cfg)},
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    assert result.data["backup_path"] is not None
    assert Path(result.data["backup_path"]).exists()
