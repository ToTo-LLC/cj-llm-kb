"""Smoke test for brain_core.tools.ingest — handler contract.

The happy path drives the full IngestPipeline (three LLM calls). For the
smoke test we exercise the rate-limit-refused branch: the handler's first
line calls ``ctx.rate_limiter.check("patches", cost=1)``, which raises
:class:`RateLimitError` when the bucket is drained. Plan 05 Task 14 flipped
this from an inline-JSON return to an exception — the exception propagates;
brain_mcp's shim catches + converts, brain_api's global handler converts to
HTTP 429. brain_mcp's end-to-end ingest test still covers the happy path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from brain_core.chat.types import ChatMode
from brain_core.ingest.types import IngestResult, IngestStatus
from brain_core.rate_limit import RateLimitError
from brain_core.tools.base import ToolContext
from brain_core.tools.ingest import NAME, handle
from brain_core.vault.types import PatchSet


@dataclass
class _AlwaysRefusingLimiter:
    """Rate-limiter stand-in whose ``check`` always raises."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        raise RateLimitError(bucket=bucket, retry_after_seconds=60)


@dataclass
class _NoopLimiter:
    """Rate-limiter stand-in whose ``check`` is a no-op (lets handler proceed)."""

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
        rate_limiter=_AlwaysRefusingLimiter(),
        undo_log=None,
    )


class _FakePipeline:
    """Stand-in for IngestPipeline that returns a pre-baked IngestResult.

    Used by the key-set pin tests (Plan 18 T3.5) to drive each of the three
    backend return branches in :mod:`brain_core.tools.ingest` without standing
    up the real 9-stage pipeline.
    """

    def __init__(self, *_a: Any, **_kw: Any) -> None:
        # Result is set by the test via monkeypatch on the module-level
        # ``_FAKE_RESULT`` slot before invoking ``handle``.
        pass

    async def ingest(self, *_a: Any, **_kw: Any) -> IngestResult:
        return _FAKE_RESULT


# Module-level slot the fake pipeline reads from. Tests rebind this via
# ``monkeypatch.setattr`` before calling ``handle``.
_FAKE_RESULT: IngestResult = IngestResult(status=IngestStatus.OK, note_path=None)


class _RecordingPendingStore:
    """Pending-store stand-in that returns a fixed envelope for assertion."""

    def __init__(self, patch_id: str, target_path: Path) -> None:
        self._patch_id = patch_id
        self._target_path = target_path

    def put(
        self,
        patchset: PatchSet,
        source_thread: str,
        mode: ChatMode,
        tool: str,
        target_path: Path,
        reason: str,
    ) -> Any:
        # Return a duck-typed object exposing the attributes the handler reads.
        from types import SimpleNamespace

        return SimpleNamespace(
            patch_id=self._patch_id,
            target_path=self._target_path,
            created_at=datetime.now(UTC),
        )


def test_name() -> None:
    assert NAME == "brain_ingest"


async def test_rate_limit_refusal_propagates(tmp_path: Path) -> None:
    with pytest.raises(RateLimitError) as exc_info:
        await handle({"source": "some text"}, _mk_ctx(tmp_path))
    # ingest checks the patches bucket first — that's the one that fires.
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds == 60


def test_build_pipeline_routes_through_resolve_llm_config_with_domain_override(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Plan 11 D8: ``_build_pipeline_from_ctx(domain=...)`` MUST call
    :func:`brain_core.llm.resolve_llm_config` with whatever ``domain`` the
    caller provides. When ``domain_override`` is set on the public handler,
    that slug flows through here so per-domain LLM overrides apply.

    Patch the resolver to a sentinel and verify the pipeline picks up
    the sentinel's models, AND that the resolver was invoked with the
    explicit domain (not ``None``).
    """
    from brain_core.config.schema import Config, LLMConfig
    from brain_core.tools.ingest import _build_pipeline_from_ctx

    captured: list[tuple[Any, Any]] = []

    def _sentinel(config: Any, domain: Any) -> LLMConfig:
        captured.append((config, domain))
        return LLMConfig(
            classify_model="classify-SENTINEL",
            default_model="default-SENTINEL",
        )

    monkeypatch.setattr("brain_core.tools.ingest.resolve_llm_config", _sentinel)

    cfg = Config(domains=["research", "work", "personal", "hobby"])
    from dataclasses import replace

    ctx = replace(_mk_ctx(tmp_path), config=cfg)

    pipeline = _build_pipeline_from_ctx(ctx, domain="hobby")

    assert len(captured) == 1
    assert captured[0][1] == "hobby"
    # Pipeline picked up sentinel's models.
    assert pipeline.classify_model == "classify-SENTINEL"
    assert pipeline.summarize_model == "default-SENTINEL"
    assert pipeline.integrate_model == "default-SENTINEL"


def test_build_pipeline_routes_with_none_domain_when_auto_detect(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """The auto-detect path (no ``domain_override``) MUST call the
    resolver with ``domain=None`` — chicken-and-egg around classify.
    """
    from brain_core.config.schema import Config, LLMConfig
    from brain_core.tools.ingest import _build_pipeline_from_ctx

    captured: list[tuple[Any, Any]] = []

    def _sentinel(config: Any, domain: Any) -> LLMConfig:
        captured.append((config, domain))
        return LLMConfig()

    monkeypatch.setattr("brain_core.tools.ingest.resolve_llm_config", _sentinel)

    cfg = Config()
    from dataclasses import replace

    ctx = replace(_mk_ctx(tmp_path), config=cfg)

    _build_pipeline_from_ctx(ctx, domain=None)
    assert captured[0][1] is None


# ---------------------------------------------------------------------------
# Plan 18 T3.5 — backend-branch key-set pins.
#
# The TS typed-wrapper ``ingest()`` in ``apps/brain_web/src/lib/api/tools.ts``
# is narrowed to a discriminated union over ``status`` with three variants:
#   - applied      → keys = {status, note_path}
#   - pending      → keys = {status, patch_id, target_path}
#   - error/skip   → keys = {status, errors, note_path}
# These three pins lock the backend handler's ``data`` shape to those exact
# key-sets. If the handler ever adds, renames, or drops a field, one of these
# tests fails BEFORE the TS interface goes silently stale.
#
# Each pin patches ``IngestPipeline`` to a stand-in (_FakePipeline) and rebinds
# the module-level ``_FAKE_RESULT`` slot to drive the desired branch.
# ---------------------------------------------------------------------------


def _install_fake_pipeline(monkeypatch: Any, result: IngestResult) -> None:
    """Wire ``IngestPipeline`` symbol used by the handler to our fake."""
    global _FAKE_RESULT
    _FAKE_RESULT = result
    monkeypatch.setattr("brain_core.tools.ingest.IngestPipeline", _FakePipeline)


async def test_data_keys_pin_applied(tmp_path: Path, monkeypatch: Any) -> None:
    """Plan 18 T3.5 drift pin (applied branch): backend handler must emit
    exactly {"status", "note_path"} when autonomous=True and pipeline → OK.
    """
    note_path = tmp_path / "research" / "notes" / "applied.md"
    _install_fake_pipeline(
        monkeypatch,
        IngestResult(status=IngestStatus.OK, note_path=note_path),
    )
    ctx = replace(_mk_ctx(tmp_path), rate_limiter=_NoopLimiter())

    result = await handle({"source": "some text", "autonomous": True}, ctx)

    assert result.data is not None
    assert set(result.data.keys()) == {"status", "note_path"}
    assert result.data["status"] == "applied"
    assert result.data["note_path"] == str(note_path)


async def test_data_keys_pin_pending(tmp_path: Path, monkeypatch: Any) -> None:
    """Plan 18 T3.5 drift pin (pending branch): backend handler must emit
    exactly {"status", "patch_id", "target_path"} when autonomous=False
    (default) and pipeline → OK.
    """
    note_path = tmp_path / "research" / "notes" / "pending.md"
    patchset = PatchSet()  # empty new_files → handler falls back to note_path
    _install_fake_pipeline(
        monkeypatch,
        IngestResult(status=IngestStatus.OK, note_path=note_path, patchset=patchset),
    )
    expected_target = Path("research/notes/pending.md")
    store = _RecordingPendingStore(patch_id="20260511-aaaaaaaa", target_path=expected_target)
    ctx = replace(_mk_ctx(tmp_path), rate_limiter=_NoopLimiter(), pending_store=store)

    result = await handle({"source": "some text"}, ctx)

    assert result.data is not None
    assert set(result.data.keys()) == {"status", "patch_id", "target_path"}
    assert result.data["status"] == "pending"
    assert result.data["patch_id"] == "20260511-aaaaaaaa"
    # target_path is serialized POSIX-form by the handler (envelope.target_path.as_posix())
    assert result.data["target_path"] == expected_target.as_posix()


@pytest.mark.parametrize(
    "status",
    [IngestStatus.QUARANTINED, IngestStatus.FAILED, IngestStatus.SKIPPED_DUPLICATE],
)
async def test_data_keys_pin_error(
    tmp_path: Path, monkeypatch: Any, status: IngestStatus
) -> None:
    """Plan 18 T3.5 drift pin (error/skip branch): backend handler must emit
    exactly {"status", "errors", "note_path"} for every non-OK pipeline status.
    """
    _install_fake_pipeline(
        monkeypatch,
        IngestResult(status=status, note_path=None, errors=["boom"]),
    )
    ctx = replace(_mk_ctx(tmp_path), rate_limiter=_NoopLimiter())

    result = await handle({"source": "some text"}, ctx)

    assert result.data is not None
    assert set(result.data.keys()) == {"status", "errors", "note_path"}
    assert result.data["status"] == status.value
    assert result.data["status"] in {"quarantined", "failed", "skipped_duplicate"}
    assert result.data["errors"] == ["boom"]
    assert result.data["note_path"] is None
