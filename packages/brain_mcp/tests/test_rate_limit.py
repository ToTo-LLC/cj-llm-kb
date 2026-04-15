"""Tests for brain_mcp.rate_limit.RateLimiter."""

from __future__ import annotations

import pytest
from brain_mcp.rate_limit import RateLimitConfig, RateLimiter


def test_fresh_limiter_allows_up_to_capacity() -> None:
    cfg = RateLimitConfig(patches_per_minute=5, tokens_per_minute=100)
    limiter = RateLimiter(cfg)
    # First 5 patches should all be allowed.
    for _ in range(5):
        assert limiter.check("patches", cost=1) is True
    # 6th should be refused.
    assert limiter.check("patches", cost=1) is False


def test_tokens_bucket_independent_of_patches() -> None:
    cfg = RateLimitConfig(patches_per_minute=1, tokens_per_minute=100)
    limiter = RateLimiter(cfg)
    assert limiter.check("patches", cost=1) is True
    # Patches bucket now exhausted, but tokens bucket is fresh.
    assert limiter.check("tokens", cost=50) is True
    assert limiter.check("tokens", cost=50) is True
    assert limiter.check("tokens", cost=1) is False


def test_unknown_bucket_raises() -> None:
    limiter = RateLimiter(RateLimitConfig())
    with pytest.raises(KeyError, match="unknown"):
        limiter.check("nonexistent", cost=1)


def test_bucket_refills_over_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock time.monotonic to advance 30s and confirm the bucket has refilled."""
    fake_time = [1000.0]

    def _now() -> float:
        return fake_time[0]

    monkeypatch.setattr("brain_mcp.rate_limit.time.monotonic", _now)
    cfg = RateLimitConfig(patches_per_minute=60)  # 1/s refill
    limiter = RateLimiter(cfg)
    # Drain the bucket.
    for _ in range(60):
        assert limiter.check("patches", cost=1) is True
    assert limiter.check("patches", cost=1) is False
    # Advance 30 seconds — should refill 30 tokens.
    fake_time[0] += 30.0
    for _ in range(30):
        assert limiter.check("patches", cost=1) is True
    assert limiter.check("patches", cost=1) is False


def test_cost_greater_than_capacity_refused() -> None:
    cfg = RateLimitConfig(tokens_per_minute=100)
    limiter = RateLimiter(cfg)
    assert limiter.check("tokens", cost=101) is False
    # Partial spend should still work.
    assert limiter.check("tokens", cost=50) is True


def test_defaults_match_spec() -> None:
    cfg = RateLimitConfig()
    assert cfg.patches_per_minute == 20
    assert cfg.tokens_per_minute == 100_000
