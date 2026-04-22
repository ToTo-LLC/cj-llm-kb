"""Tests for brain_core.tools.mcp_status."""

from __future__ import annotations

from pathlib import Path

from brain_core.integrations.claude_desktop import install as core_install
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.mcp_status import NAME, handle


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
    assert NAME == "brain_mcp_status"


async def test_reports_not_installed_when_missing(tmp_path: Path) -> None:
    cfg = tmp_path / "absent.json"
    result = await handle({"config_path": str(cfg)}, _mk_ctx(tmp_path))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "not_installed"
    assert result.data["config_exists"] is False
    assert result.data["entry_present"] is False


async def test_reports_entry_present_when_installed(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    core_install(config_path=cfg, command="/bin/brain-mcp")
    result = await handle({"config_path": str(cfg)}, _mk_ctx(tmp_path))
    assert result.data is not None
    assert result.data["config_exists"] is True
    assert result.data["entry_present"] is True
    assert result.data["command"] == "/bin/brain-mcp"


async def test_executable_resolution_is_honest(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    # Point at a real file so the resolution is honest; the install() helper
    # writes config unconditionally — the executable check happens on read.
    bogus = tmp_path / "this-does-not-exist"
    core_install(config_path=cfg, command=str(bogus))
    result = await handle({"config_path": str(cfg)}, _mk_ctx(tmp_path))
    assert result.data is not None
    assert result.data["executable_resolves"] is False
    assert result.data["status"] == "not_installed"  # entry present but cmd missing
