"""Tests for brain_core.tools.mcp_selftest."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from brain_core.integrations.claude_desktop import install as core_install
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.mcp_selftest import NAME, handle


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
    assert NAME == "brain_mcp_selftest"


async def test_selftest_fails_when_config_missing(tmp_path: Path) -> None:
    cfg = tmp_path / "absent.json"
    result = await handle({"config_path": str(cfg)}, _mk_ctx(tmp_path))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["ok"] is False
    assert result.data["status"] == "failed"


async def test_selftest_fails_when_command_unresolvable(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    core_install(config_path=cfg, command=str(tmp_path / "no-such-binary"))
    result = await handle({"config_path": str(cfg)}, _mk_ctx(tmp_path))
    assert result.data is not None
    assert result.data["entry_present"] is True
    assert result.data["executable_resolves"] is False
    assert result.data["ok"] is False


@pytest.mark.skipif(sys.platform == "win32", reason="chmod semantics differ on Windows")
async def test_selftest_passes_with_executable_command(tmp_path: Path) -> None:
    cfg = tmp_path / "claude_desktop_config.json"
    fake_binary = tmp_path / "brain-mcp"
    fake_binary.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    os.chmod(fake_binary, os.stat(fake_binary).st_mode | stat.S_IXUSR)
    core_install(config_path=cfg, command=str(fake_binary))
    result = await handle({"config_path": str(cfg)}, _mk_ctx(tmp_path))
    assert result.data is not None
    assert result.data["ok"] is True
    assert result.data["status"] == "passed"
