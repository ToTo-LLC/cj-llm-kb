"""Smoke test for brain_core.tools.bulk_import — ToolResult shape.

Exercises the large-folder refusal path: the handler's pre-classify check
counts files and refuses a ``dry_run=False`` call on >20 files without a
``max_files`` cap. This branch fires before any LLM work, so the smoke test
does not need to wire up a real pipeline. brain_mcp's existing
test_tool_bulk_import.py still exercises the plan/apply LLM paths via the
shim — coverage is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.bulk_import import NAME, handle


@dataclass
class _AllowAllLimiter:
    """Rate-limiter stand-in: every ``check`` succeeds (no raise, no return)."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        return None


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
        rate_limiter=_AllowAllLimiter(),
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_bulk_import"


async def test_refuses_large_folder_without_max_files(tmp_path: Path) -> None:
    folder = tmp_path / "inbox"
    folder.mkdir()
    for i in range(25):
        (folder / f"{i}.txt").write_text("x", encoding="utf-8")

    result = await handle({"folder": str(folder), "dry_run": False}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "refused"
    assert result.data["file_count"] == 25


def test_build_pipeline_routes_through_resolve_llm_config_with_none(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Plan 11 D8: ``_build_pipeline`` MUST route model lookup through
    :func:`brain_core.llm.resolve_llm_config`. Bulk import is intrinsically
    auto-detect (per-file classification inside BulkImporter), and the
    pipeline is constructed once for the whole batch — so the resolver
    MUST be called with ``domain=None`` and the global llm config used.

    Patch the resolver to a sentinel and verify both the call args AND
    that the constructed pipeline picked up the sentinel's models.
    """
    from brain_core.config.schema import Config, LLMConfig
    from brain_core.tools.bulk_import import _build_pipeline

    captured: list[tuple[Any, Any]] = []

    def _sentinel(config: Any, domain: Any) -> LLMConfig:
        captured.append((config, domain))
        return LLMConfig(
            classify_model="bulk-classify-SENTINEL",
            default_model="bulk-default-SENTINEL",
        )

    monkeypatch.setattr("brain_core.tools.bulk_import.resolve_llm_config", _sentinel)

    cfg = Config()
    from dataclasses import replace

    ctx = replace(_mk_ctx(tmp_path), config=cfg)

    pipeline = _build_pipeline(ctx)

    assert len(captured) == 1
    # domain=None is the correct semantics for bulk import (chicken-and-egg).
    assert captured[0][1] is None
    assert pipeline.classify_model == "bulk-classify-SENTINEL"
    assert pipeline.summarize_model == "bulk-default-SENTINEL"
    assert pipeline.integrate_model == "bulk-default-SENTINEL"
