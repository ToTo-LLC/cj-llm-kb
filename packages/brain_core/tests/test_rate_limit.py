"""Tests for brain_core.rate_limit — moved from brain_mcp Plan 04 Task 2.

Plan 05 Task 14: ``check()`` now raises :class:`RateLimitError` instead of
returning ``False``. These tests replace the prior bool-returning contract
and live in brain_core because the limiter itself is now core machinery.
"""

from __future__ import annotations

import pytest
from brain_core.rate_limit import RateLimitConfig, RateLimiter, RateLimitError


def test_check_within_budget_does_not_raise() -> None:
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=10))
    # Returns None on success (no value); absence of raise is the contract.
    limiter.check("patches", cost=1)
    limiter.check("patches", cost=1)


def test_check_over_budget_raises_with_bucket_name() -> None:
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=1))
    limiter.check("patches", cost=1)  # drain
    with pytest.raises(RateLimitError) as exc_info:
        limiter.check("patches", cost=1)
    assert exc_info.value.bucket == "patches"
    assert exc_info.value.retry_after_seconds >= 0


def test_rate_limit_error_exposes_retry_after() -> None:
    err = RateLimitError(bucket="patches", retry_after_seconds=42)
    assert err.bucket == "patches"
    assert err.retry_after_seconds == 42
    assert "patches" in str(err)


def test_separate_buckets_independent() -> None:
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=1, tokens_per_minute=1000))
    limiter.check("patches", cost=1)  # drain patches
    # tokens unaffected.
    limiter.check("tokens", cost=500)


def test_tokens_bucket_drains_by_cost() -> None:
    limiter = RateLimiter(RateLimitConfig(tokens_per_minute=1000))
    limiter.check("tokens", cost=700)
    limiter.check("tokens", cost=200)  # total 900 — still OK
    with pytest.raises(RateLimitError):
        limiter.check("tokens", cost=200)  # total 1100 — over


def test_refill_over_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens refill at ``config.<bucket>_per_minute / 60`` per second.

    patches_per_minute=60 → 1 patch/sec refill; capacity = 60. Drain the
    bucket fully, then monkeypatch ``time.monotonic`` to fast-forward 30
    seconds. The bucket should have exactly ~30 patches available; the 31st
    call at the same patched "now" should raise.
    """
    fake_now = [1000.0]
    monkeypatch.setattr(
        "brain_core.rate_limit.time.monotonic",
        lambda: fake_now[0],
    )
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=60))  # 1 patch/sec
    # Drain the bucket fully (60 patches at cap).
    for _ in range(60):
        limiter.check("patches", cost=1)
    # Advance 30s; the bucket should refill 30 patches.
    fake_now[0] += 30.0
    for _ in range(30):
        limiter.check("patches", cost=1)
    # 31st call without further time advance must raise — bucket is drained.
    with pytest.raises(RateLimitError):
        limiter.check("patches", cost=1)


def test_unknown_bucket_raises_value_error() -> None:
    limiter = RateLimiter(RateLimitConfig())
    with pytest.raises(ValueError):
        limiter.check("unknown_bucket", cost=1)


def test_config_defaults_sane() -> None:
    cfg = RateLimitConfig()
    assert cfg.patches_per_minute > 0
    assert cfg.tokens_per_minute > 0


def test_no_unused_config_attribute_post_refactor() -> None:
    """Issue #5: the unused ``self._config`` attribute was removed.

    Pinning its absence keeps anyone from re-introducing it as cargo-cult
    "we might need this someday" state. If the limiter ever needs to expose
    the original config it should add an explicit accessor with a real
    use case, not a private bag.
    """
    limiter = RateLimiter(RateLimitConfig())
    assert not hasattr(limiter, "_config"), (
        "RateLimiter._config was removed in issue #5 — re-adding it without "
        "a documented consumer is a regression."
    )


def test_internal_state_is_per_bucket_dataclass() -> None:
    """Issue #5: ``_Bucket`` dataclass replaces the parallel-dicts shape.

    A future refactor that reverts to ``dict[str, float]`` parallel state
    drops mypy narrowing for code that walks bucket state — pin the shape.
    """
    from brain_core.rate_limit import _Bucket

    limiter = RateLimiter(RateLimitConfig(patches_per_minute=42, tokens_per_minute=99))
    buckets = limiter._buckets  # type: ignore[attr-defined]
    assert set(buckets.keys()) == {"patches", "tokens"}
    assert isinstance(buckets["patches"], _Bucket)
    assert buckets["patches"].cap == 42.0
    assert buckets["patches"].remaining == 42.0
    assert buckets["tokens"].cap == 99.0


def test_clock_backwards_does_not_drain_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #5: a non-monotonic ``time.monotonic`` (hypothetical VM warp,
    runtime bug) must not silently subtract capacity from every bucket.

    The defensive ``elapsed = max(0.0, now - last)`` guard turns a
    backwards step into a zero-elapsed refill — buckets stay at whatever
    capacity they had before the warp.
    """
    fake_now = [1000.0]
    monkeypatch.setattr(
        "brain_core.rate_limit.time.monotonic",
        lambda: fake_now[0],
    )
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=60))
    # Drain to 50 (10 used).
    for _ in range(10):
        limiter.check("patches", cost=1)
    bucket_remaining_before = limiter._buckets["patches"].remaining  # type: ignore[attr-defined]
    # Warp clock backwards 100 seconds.
    fake_now[0] -= 100.0
    # A subsequent check triggers _refill — must NOT drain anything despite
    # the negative elapsed.
    limiter.check("patches", cost=1)
    bucket_remaining_after = limiter._buckets["patches"].remaining  # type: ignore[attr-defined]
    # Used 1 since the warp; remaining must be (before - 1), never less.
    assert bucket_remaining_after == bucket_remaining_before - 1, (
        f"clock-backwards must yield zero-elapsed refill, not negative; "
        f"before={bucket_remaining_before} after={bucket_remaining_after}"
    )
