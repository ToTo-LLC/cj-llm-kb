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

from brain_core.ingest.bulk import BulkItem, BulkPlan
from brain_core.ingest.types import IngestResult, IngestStatus
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


# ---------------------------------------------------------------------------
# Plan 18 T3.9 — backend-shape pin tests, one per branch.
#
# The TS wrapper at ``apps/brain_web/src/lib/api/tools.ts:278`` now declares a
# discriminated union over ``status`` with exactly these three branches and
# their key sets. If a handler edit changes the emitted keys here, these pins
# trip BEFORE the TS interface goes silently stale.
#
# The planned/applied branches require driving the BulkImporter without LLMs,
# so each test patches ``BulkImporter`` to a stand-in that returns a pre-baked
# plan / apply result. The refused branch fires before any pipeline work and
# needs no patching (mirrors ``test_refuses_large_folder_without_max_files``).
# ---------------------------------------------------------------------------


class _FakeBulkImporter:
    """Stand-in for ``BulkImporter`` that returns a pre-baked plan + results.

    Used by the T3.9 key-set pin tests to drive each backend return branch
    without standing up the real classifier / pipeline. The fake's ``plan``
    and ``apply`` async methods read module-level slots that tests rebind
    via :func:`_install_fake_importer`.
    """

    def __init__(self, *_a: Any, **_kw: Any) -> None:
        pass

    async def plan(self, *_a: Any, **_kw: Any) -> BulkPlan:
        return _FAKE_PLAN

    async def apply(self, *_a: Any, **_kw: Any) -> list[IngestResult]:
        return _FAKE_APPLY_RESULTS


# Module-level slots the fake importer reads from. Tests rebind these via
# ``monkeypatch.setattr`` before calling ``handle``.
_FAKE_PLAN: BulkPlan = BulkPlan()
_FAKE_APPLY_RESULTS: list[IngestResult] = []


def _install_fake_importer(
    monkeypatch: Any,
    *,
    plan: BulkPlan,
    apply_results: list[IngestResult] | None = None,
) -> None:
    """Wire ``BulkImporter`` symbol used by the handler to our fake."""
    global _FAKE_PLAN, _FAKE_APPLY_RESULTS
    _FAKE_PLAN = plan
    _FAKE_APPLY_RESULTS = apply_results if apply_results is not None else []
    monkeypatch.setattr("brain_core.tools.bulk_import.BulkImporter", _FakeBulkImporter)
    # Bypass the real _build_pipeline (which needs a Config + LLM). The fake
    # importer ignores its constructor args entirely, so any sentinel works.
    monkeypatch.setattr(
        "brain_core.tools.bulk_import._build_pipeline",
        lambda _ctx: object(),
    )


async def test_data_keys_pin_refused(tmp_path: Path) -> None:
    """Plan 18 T3.9 drift pin (refused branch): backend handler must emit
    exactly {"status", "reason", "file_count"} when the folder exceeds the
    20-file threshold without a ``max_files`` cap and ``dry_run=False``.
    """
    folder = tmp_path / "inbox"
    folder.mkdir()
    for i in range(25):
        (folder / f"{i}.txt").write_text("x", encoding="utf-8")

    result = await handle({"folder": str(folder), "dry_run": False}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"status", "reason", "file_count"}
    assert result.data["status"] == "refused"
    assert result.data["file_count"] == 25


async def test_data_keys_pin_planned(tmp_path: Path, monkeypatch: Any) -> None:
    """Plan 18 T3.9 drift pin (planned branch): backend handler must emit
    exactly {"status", "file_count", "skipped_count", "items"} on the
    ``dry_run=True`` path. Spot-check the items[0] shape too.
    """
    folder = tmp_path / "inbox"
    folder.mkdir()
    # One real file so the folder.exists() / is_dir() check passes; the fake
    # importer ignores the actual contents.
    (folder / "x.md").write_text("hi", encoding="utf-8")

    plan = BulkPlan(
        items=[
            BulkItem(
                spec=folder / "x.md",
                slug="x",
                classified_domain="research",
                confidence=0.91,
            ),
        ],
        skipped=[folder / "ignored.bin"],
    )
    _install_fake_importer(monkeypatch, plan=plan)

    result = await handle({"folder": str(folder), "dry_run": True}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"status", "file_count", "skipped_count", "items"}
    assert result.data["status"] == "planned"
    assert result.data["file_count"] == 1
    assert result.data["skipped_count"] == 1
    items = result.data["items"]
    assert isinstance(items, list) and len(items) == 1
    assert set(items[0].keys()) == {"path", "slug", "classified_domain", "confidence"}


async def test_data_keys_pin_applied(tmp_path: Path, monkeypatch: Any) -> None:
    """Plan 18 T3.9 drift pin (applied branch): backend handler must emit
    exactly {"status", "applied", "quarantined", "duplicate", "failed"} on
    the ``dry_run=False`` success path. Spot-check the failed[0] shape too.
    """
    folder = tmp_path / "inbox"
    folder.mkdir()
    # Two real files so file_count <= threshold (avoid the refused branch);
    # the fake importer ignores actual contents.
    (folder / "ok.md").write_text("hi", encoding="utf-8")
    (folder / "boom.md").write_text("hi", encoding="utf-8")

    plan = BulkPlan(
        items=[
            BulkItem(
                spec=folder / "ok.md",
                slug="ok",
                classified_domain="research",
                confidence=0.91,
            ),
            BulkItem(
                spec=folder / "boom.md",
                slug="boom",
                classified_domain="research",
                confidence=0.81,
            ),
        ],
    )
    apply_results = [
        IngestResult(status=IngestStatus.OK, note_path=folder / "ok.md"),
        IngestResult(status=IngestStatus.FAILED, note_path=None, errors=["kaboom"]),
    ]
    _install_fake_importer(monkeypatch, plan=plan, apply_results=apply_results)

    result = await handle({"folder": str(folder), "dry_run": False}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {
        "status",
        "applied",
        "quarantined",
        "duplicate",
        "failed",
    }
    assert result.data["status"] == "applied"
    assert result.data["applied"] == [(folder / "ok.md").as_posix()]
    failed = result.data["failed"]
    assert isinstance(failed, list) and len(failed) == 1
    assert set(failed[0].keys()) == {"path", "errors"}
    assert failed[0]["errors"] == ["kaboom"]
