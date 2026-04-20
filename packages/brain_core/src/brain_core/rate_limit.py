"""Token-bucket rate limiter for per-app / per-session limits.

Plan 05 Task 14: moved from brain_mcp.rate_limit (was Plan 04 Task 2). The
signature change is strictly additive — ``check()`` now raises
:class:`RateLimitError` instead of returning ``False``. brain_mcp shims catch
the exception and convert to the Plan 04 inline-JSON envelope so every
Plan 04 integration test still passes unchanged.

Per spec §7: per-session rate limit on patches/min and tokens/min. State is
in-memory on the limiter instance — lost on process restart, which is
acceptable for a single-user local tool (documented in CLAUDE.md
principle #5).
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitConfig:
    patches_per_minute: int = 20
    tokens_per_minute: int = 100_000


class RateLimitError(Exception):
    """Raised by :meth:`RateLimiter.check` when the bucket lacks capacity.

    Not a failure in the traditional sense — this is a control-flow signal
    the caller is expected to catch and convert into whatever their transport
    layer wants (MCP inline JSON, HTTP 429, etc.). Inherits directly from
    :class:`Exception` so a bare ``except Exception`` in a tool handler does
    NOT accidentally swallow it — rate limiting is a policy decision, and
    callers must deliberately opt in to handling it.

    Attributes:
        bucket: Which bucket ran out (``"patches"`` or ``"tokens"``).
        retry_after_seconds: Approximate seconds until enough capacity
            refills. Always non-negative; 0 means "barely over — retry
            immediately".
    """

    def __init__(self, bucket: str, retry_after_seconds: int) -> None:
        self.bucket = bucket
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limited on {bucket!r} bucket, retry after ~{retry_after_seconds}s")


class RateLimiter:
    """Two-bucket token-bucket limiter over ``patches`` and ``tokens``.

    :meth:`check` consumes ``cost`` from ``bucket`` and returns ``None`` on
    success; on insufficient capacity it raises :class:`RateLimitError` with
    a ``retry_after_seconds`` estimate. An unknown bucket name raises
    :class:`ValueError` (preserved from Plan 04's ``KeyError`` contract —
    see Task 14 docs for the rationale).
    """

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._caps: dict[str, float] = {
            "patches": float(config.patches_per_minute),
            "tokens": float(config.tokens_per_minute),
        }
        self._remaining: dict[str, float] = dict(self._caps)
        self._last_refill = time.monotonic()

    def check(self, bucket: str, *, cost: int | float = 1) -> None:
        """Consume ``cost`` from ``bucket``. Raises on insufficient capacity.

        Refills buckets at ``cap / 60`` per second since the last call.

        Raises:
            ValueError: if ``bucket`` is not a known bucket name.
            RateLimitError: if the bucket lacks capacity for ``cost``.
        """
        if bucket not in self._caps:
            raise ValueError(f"unknown rate-limit bucket: {bucket!r}")

        self._refill()

        remaining = self._remaining[bucket]
        if remaining < cost:
            cap = self._caps[bucket]
            # Seconds until enough refills to cover `cost`:
            #   (cost - remaining) / (cap / 60).
            # Guard against cap <= 0 (degenerate config) by falling back to
            # 1/sec so retry_after is still a finite non-negative integer.
            refill_rate = cap / 60.0 if cap > 0 else 1.0
            retry = max(0, int((cost - remaining) / refill_rate) + 1)
            raise RateLimitError(bucket=bucket, retry_after_seconds=retry)

        self._remaining[bucket] = remaining - cost

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = max(0.0, now - self._last_refill)
        self._last_refill = now
        for bucket, cap in self._caps.items():
            refill = (cap / 60.0) * elapsed
            self._remaining[bucket] = min(cap, self._remaining[bucket] + refill)


__all__ = ["RateLimitConfig", "RateLimitError", "RateLimiter"]
