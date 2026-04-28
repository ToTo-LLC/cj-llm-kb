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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from brain_core.rate_limit import RateLimitError
from brain_core.tools.base import ToolContext
from brain_core.tools.ingest import NAME, handle


@dataclass
class _AlwaysRefusingLimiter:
    """Rate-limiter stand-in whose ``check`` always raises."""

    def check(self, bucket: str, *, cost: int = 1) -> None:
        raise RateLimitError(bucket=bucket, retry_after_seconds=60)


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
