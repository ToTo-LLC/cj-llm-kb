"""Token-bucket rate limiter for brain_mcp.

Per spec §7: per-session rate limit on patches/min and tokens/min. This is an
in-memory bucket on the server instance — state is lost on restart, which is
acceptable for a per-session bound.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitConfig:
    patches_per_minute: int = 20
    tokens_per_minute: int = 100_000


class RateLimiter:
    """Two-bucket token-bucket limiter. `check(bucket, cost)` returns True if
    the cost was consumed, False if refused."""

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        now = time.monotonic()
        # Each bucket: [capacity, refill_rate_per_second, current_tokens, last_refill_time]
        self._buckets: dict[str, list[float]] = {
            "patches": [
                float(config.patches_per_minute),
                config.patches_per_minute / 60.0,
                float(config.patches_per_minute),
                now,
            ],
            "tokens": [
                float(config.tokens_per_minute),
                config.tokens_per_minute / 60.0,
                float(config.tokens_per_minute),
                now,
            ],
        }

    def check(self, bucket: str, *, cost: int) -> bool:
        if bucket not in self._buckets:
            raise KeyError(f"unknown rate-limit bucket: {bucket!r}")
        b = self._buckets[bucket]
        capacity, refill_rate, current, last = b
        now = time.monotonic()
        elapsed = now - last
        refilled = min(capacity, current + elapsed * refill_rate)
        if refilled >= cost:
            b[2] = refilled - cost
            b[3] = now
            return True
        b[2] = refilled
        b[3] = now
        return False
