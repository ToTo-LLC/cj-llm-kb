"""Tests for the brain_ingest MCP tool.

All tests use FakeLLMProvider and a real text file on tmp_path so no network
traffic and no real URL fetching. The pipeline itself is Plan 02 code —
brain_core's `tests/ingest/test_pipeline.py` exercises it end-to-end. Here we
verify the MCP layer wires it correctly and respects the `autonomous` flag.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from brain_core.tools.base import ToolContext
from brain_mcp.tools.ingest import INPUT_SCHEMA, NAME, handle


def _queue_ingest_pipeline_responses(
    fake: FakeLLMProvider,
    *,
    include_classify: bool = True,
    title: str = "sample-source",
) -> None:
    """Queue the LLM responses an ingest run consumes.

    The pipeline calls classify (skipped when `domain_override` is set),
    summarize, and integrate — in that order. Each response is a JSON string.
    """
    if include_classify:
        fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title=title,
            summary="Karpathy described the LLM wiki pattern.",
            key_points=["LLM compiles raw material into a wiki"],
            entities=[],
            concepts=["LLM wiki"],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            index_entries=[
                IndexEntryPatch(
                    section="Sources",
                    line=f"- [[{title}]] — LLM wiki",
                    domain="research",
                )
            ],
            log_entry=None,
            reason="ingest test",
        ).model_dump_json()
    )


def _research_vault(tmp_path: Path) -> Path:
    """Build a minimal research-only vault layout the pipeline + writer accept."""
    vault = tmp_path / "vault"
    (vault / ".brain").mkdir(parents=True)
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (vault / "research" / sub).mkdir(parents=True)
    (vault / "research" / "index.md").write_text(
        "# research — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    (vault / "research" / "log.md").write_text("# research — log\n", encoding="utf-8")
    for sub in ("inbox", "failed", "archive"):
        (vault / "raw" / sub).mkdir(parents=True)
    (vault / "BRAIN.md").write_text("# BRAIN\n\nDefault schema doc.\n", encoding="utf-8")
    return vault


def _write_source_file(tmp_path: Path, *, stem: str = "sample-source") -> Path:
    """Write a small UTF-8 .txt source file TextHandler will claim."""
    src = tmp_path / f"{stem}.txt"
    src.write_text(
        "Karpathy wrote about LLM wikis.\n\nThe pattern turns source material into a wiki.\n",
        encoding="utf-8",
    )
    return src


def test_name() -> None:
    assert NAME == "brain_ingest"


def test_ingest_input_schema() -> None:
    assert INPUT_SCHEMA["required"] == ["source"]
    assert "autonomous" in INPUT_SCHEMA["properties"]
    assert INPUT_SCHEMA["properties"]["autonomous"]["default"] is False


async def test_ingest_default_stages_patch(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Default call (no autonomous) stages the patch, leaves the vault untouched."""
    vault = _research_vault(tmp_path)
    ctx = make_ctx(vault, allowed_domains=("research",))
    _queue_ingest_pipeline_responses(ctx.llm)

    src = _write_source_file(tmp_path)
    out = await handle({"source": str(src)}, ctx)
    data = json.loads(out[1].text)

    assert data["status"] == "pending"
    assert "patch_id" in data
    # No vault write yet — the pipeline stage 9 was skipped.
    assert not (vault / "research" / "sources" / "sample-source.md").exists()
    # Staging store has the envelope under the brain_ingest tool name.
    pending = ctx.pending_store.list()
    assert any(env.tool == "brain_ingest" for env in pending)
    # Issue #30: brain_ingest-staged patches carry ChatMode.MCP so the patch-
    # queue UI can distinguish them from chat-origin patches.
    from brain_core.chat.types import ChatMode
    ingest_envs = [env for env in pending if env.tool == "brain_ingest"]
    assert all(env.mode is ChatMode.MCP for env in ingest_envs), (
        f"expected ChatMode.MCP, got {[env.mode for env in ingest_envs]}"
    )


async def test_ingest_autonomous_applies_immediately(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """autonomous=true routes through Stage 9 apply; vault file exists."""
    vault = _research_vault(tmp_path)
    ctx = make_ctx(vault, allowed_domains=("research",))
    _queue_ingest_pipeline_responses(ctx.llm)

    src = _write_source_file(tmp_path)
    out = await handle({"source": str(src), "autonomous": True}, ctx)
    data = json.loads(out[1].text)

    assert data["status"] == "applied"
    assert (vault / "research" / "sources" / "sample-source.md").exists()
    assert data["note_path"].endswith("research/sources/sample-source.md")


async def test_ingest_rate_limited_patches(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """A drained patches bucket short-circuits before any pipeline work."""
    vault = _research_vault(tmp_path)
    base_ctx = make_ctx(vault, allowed_domains=("research",))
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=1, tokens_per_minute=100_000))
    limiter.check("patches", cost=1)  # drain the patches bucket
    tight_ctx = ToolContext(
        vault_root=base_ctx.vault_root,
        allowed_domains=base_ctx.allowed_domains,
        retrieval=base_ctx.retrieval,
        pending_store=base_ctx.pending_store,
        state_db=base_ctx.state_db,
        writer=base_ctx.writer,
        llm=base_ctx.llm,  # deliberately empty queue — must not be consumed
        cost_ledger=base_ctx.cost_ledger,
        rate_limiter=limiter,
        undo_log=base_ctx.undo_log,
    )

    out = await handle({"source": "https://example.com/x"}, tight_ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "rate_limited"
    assert data["bucket"] == "patches"


async def test_ingest_domain_override_skips_classify(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """domain_override skips the classify LLM call; confirms via FakeLLMProvider."""
    vault = _research_vault(tmp_path)
    ctx = make_ctx(vault, allowed_domains=("research",))
    # include_classify=False — if the pipeline tried to classify, FakeLLMProvider
    # would raise on an empty queue and the test would fail loudly.
    _queue_ingest_pipeline_responses(ctx.llm, include_classify=False)

    src = _write_source_file(tmp_path)
    out = await handle(
        {"source": str(src), "domain_override": "research"},
        ctx,
    )
    data = json.loads(out[1].text)
    assert data["status"] == "pending"


async def test_ingest_domain_override_out_of_scope_raises(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """domain_override not in ctx.allowed_domains raises ScopeError."""
    from brain_core.vault.paths import ScopeError

    vault = _research_vault(tmp_path)
    ctx = make_ctx(vault, allowed_domains=("research",))
    src = _write_source_file(tmp_path)
    with pytest.raises(ScopeError):
        await handle({"source": str(src), "domain_override": "personal"}, ctx)
