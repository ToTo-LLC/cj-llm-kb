"""Smoke test for brain_core.tools.get_brain_md — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.get_brain_md import NAME, handle


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
    assert NAME == "brain_get_brain_md"


async def test_reads_existing_brain_md(tmp_path: Path) -> None:
    (tmp_path / "BRAIN.md").write_text("# BRAIN\n\npersona\n", encoding="utf-8")

    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["exists"] is True
    assert "persona" in result.data["body"]


async def test_missing_brain_md_returns_stub(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["exists"] is False
    assert result.data["body"] == ""


async def test_data_keys_pin_happy(tmp_path: Path) -> None:
    """Plan 18 T3.3 drift pin (happy path): backend handler must emit
    exactly these keys in ``ToolResult.data``. The TS ``getBrainMd()``
    interface at ``apps/brain_web/src/lib/api/tools.ts`` mirrors this
    set. Individual-key reads in the other tests would not catch a
    silent key-set drift (e.g., adding ``path`` or renaming ``body``
    -> ``content``).
    """
    (tmp_path / "BRAIN.md").write_text("# BRAIN\n\npersona\n", encoding="utf-8")

    result = await handle({}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"exists", "body"}


async def test_data_keys_pin_miss(tmp_path: Path) -> None:
    """Plan 18 T3.3 drift pin (miss branch): the missing-file branch
    must emit the same key set as the happy path so TS callers can
    unconditionally read both keys.
    """
    result = await handle({}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"exists", "body"}
