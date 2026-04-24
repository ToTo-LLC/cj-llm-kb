"""Tests for the brain_classify MCP tool.

Thin wrapper over brain_core.ingest.classifier.classify. We verify the MCP
layer wires it correctly, consumes from the tokens bucket, and sanitizes
out-of-scope domains.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from brain_core.llm.fake import FakeLLMProvider
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from brain_core.tools.base import ToolContext
from brain_mcp.tools.classify import INPUT_SCHEMA, NAME, handle


def _queue_classify_response(
    fake: FakeLLMProvider,
    *,
    domain: str = "research",
    confidence: float = 0.85,
    source_type: str = "text",
) -> None:
    """Queue a ClassifyOutput-shaped JSON response on the fake LLM."""
    fake.queue(
        json.dumps(
            {
                "source_type": source_type,
                "domain": domain,
                "confidence": confidence,
            }
        )
    )


def test_name() -> None:
    assert NAME == "brain_classify"


def test_classify_input_schema() -> None:
    assert INPUT_SCHEMA["required"] == ["content"]
    assert "hint" in INPUT_SCHEMA["properties"]


async def test_classify_research_content(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research", "work"))
    _queue_classify_response(ctx.llm, domain="research", confidence=0.85)
    out = await handle({"content": "Andrej Karpathy on transformers"}, ctx)
    data = json.loads(out[1].text)
    assert data["domain"] == "research"
    assert data["confidence"] == 0.85
    assert data["source_type"] == "text"
    assert "needs_user_pick" in data


async def test_classify_out_of_scope_domain_sanitized(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    _queue_classify_response(ctx.llm, domain="personal", confidence=0.9)
    out = await handle({"content": "my weekend plans"}, ctx)
    data = json.loads(out[1].text)
    assert data["domain"] == "unknown"  # sanitized because personal not in allowed_domains
    assert data["confidence"] == 0.0
    assert "reason" in data


async def test_classify_rate_limited(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    base = make_ctx(seeded_vault, allowed_domains=("research",))
    # tokens_per_minute=500 < cost 1000 => refused. FakeLLMProvider queue is
    # empty, so if the rate-limit check were bypassed, complete() would raise.
    limiter = RateLimiter(RateLimitConfig(tokens_per_minute=500))
    ctx = replace(base, rate_limiter=limiter)
    out = await handle({"content": "x"}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "rate_limited"
    assert data["bucket"] == "tokens"
