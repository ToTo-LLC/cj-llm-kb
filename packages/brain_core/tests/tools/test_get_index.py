"""Smoke test for brain_core.tools.get_index — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.get_index import NAME, handle


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
    assert NAME == "brain_get_index"


async def test_reads_existing_index(tmp_path: Path) -> None:
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "index.md").write_text(
        "---\ntitle: research\n---\n# research\nbody here\n", encoding="utf-8"
    )

    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["domain"] == "research"
    assert result.data["frontmatter"] == {"title": "research"}
    assert "body here" in result.data["body"]


async def test_missing_index_returns_stub(tmp_path: Path) -> None:
    (tmp_path / "research").mkdir()

    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["domain"] == "research"
    assert result.data["frontmatter"] == {}
    assert result.data["body"] == ""


async def test_data_keys_pin_happy(tmp_path: Path) -> None:
    """Plan 18 T3.2 drift pin (happy path): backend handler must emit
    exactly these keys in ``ToolResult.data``. The TS ``getIndex()``
    interface at ``apps/brain_web/src/lib/api/tools.ts`` mirrors this
    set. Individual-key reads in the other tests would not catch a
    silent key-set drift (e.g., adding ``raw_yaml`` or renaming
    ``body`` -> ``content``).
    """
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "index.md").write_text(
        "---\ntitle: research\n---\nbody here\n", encoding="utf-8"
    )

    result = await handle({}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"domain", "frontmatter", "body"}


async def test_data_keys_pin_miss(tmp_path: Path) -> None:
    """Plan 18 T3.2 drift pin (miss branch): the missing-file branch
    must emit the same key set as the happy path so TS callers can
    unconditionally read all three keys.
    """
    (tmp_path / "research").mkdir()

    result = await handle({}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"domain", "frontmatter", "body"}
