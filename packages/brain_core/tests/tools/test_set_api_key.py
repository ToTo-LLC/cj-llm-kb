"""Tests for brain_core.tools.set_api_key."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.set_api_key import NAME, handle


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
    assert NAME == "brain_set_api_key"


async def test_writes_key_to_secrets_env(tmp_path: Path) -> None:
    result = await handle(
        {"provider": "anthropic", "api_key": "sk-ant-xxxxYYYYzzzz1234"},
        _mk_ctx(tmp_path),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "saved"
    assert result.data["env_key"] == "ANTHROPIC_API_KEY"

    secrets_file = tmp_path / ".brain" / "secrets.env"
    assert secrets_file.exists()
    body = secrets_file.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-ant-xxxxYYYYzzzz1234" in body
    # Plaintext key NEVER echoed in the masked field.
    assert "sk-ant-xxxxYYYYzzzz1234" not in result.data["masked"]


async def test_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        await handle(
            {"provider": "openai", "api_key": "sk-xxx"},
            _mk_ctx(tmp_path),
        )
    # Nothing was persisted.
    assert not (tmp_path / ".brain" / "secrets.env").exists()


async def test_masked_suffix_reveals_only_last_four(tmp_path: Path) -> None:
    result = await handle(
        {"provider": "anthropic", "api_key": "sk-ant-api03-AAAABBBB"},
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    masked = result.data["masked"]
    assert masked.endswith("BBBB")
    # Middle of the key is masked.
    assert "AAAABBBB" not in masked or masked.count("•") >= 3


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only chmod test")
async def test_secrets_file_is_0600_on_posix(tmp_path: Path) -> None:
    await handle(
        {"provider": "anthropic", "api_key": "sk-ant-xyz1"},
        _mk_ctx(tmp_path),
    )
    secrets_file = tmp_path / ".brain" / "secrets.env"
    mode = stat.S_IMODE(os.stat(secrets_file).st_mode)
    assert mode == 0o600


async def test_rejects_empty_api_key(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        await handle(
            {"provider": "anthropic", "api_key": "   "},
            _mk_ctx(tmp_path),
        )
