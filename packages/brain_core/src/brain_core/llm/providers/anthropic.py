"""AnthropicProvider — production LLMProvider implementation.

This is the ONLY module in the project that imports the `anthropic` SDK.
All other modules depend on `brain_core.llm.LLMProvider` (the Protocol).

Plan 16 Task 31 / D27 step 2 of 3 adds a per-domain leaky-bucket rate-limit
gate. When the provider is constructed with a :class:`Config` reference and
the request carries a ``domain``, the provider reads
``config.providers["anthropic"].rate_limit_per_domain[domain]`` and gates the
upstream call through a leaky-bucket. The gate is OFF by default — every
existing caller (FakeLLMProvider tests, callers that pass no config) keeps
its Plan 02 behavior unchanged.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from brain_core.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TokenUsage,
    ToolUse,
    ToolUseStart,
)

if TYPE_CHECKING:
    from brain_core.config.schema import Config


# Module-level injectable clock — keyed off ``time.monotonic`` so tests can
# patch a fake clock without touching wall-clock state. Indirected as a
# ``Callable[[], float]`` rather than the bare function so monkeypatching
# ``brain_core.llm.providers.anthropic._now`` is a single-attribute swap.
_now: Callable[[], float] = time.monotonic


# Module-level injectable async sleep, mirroring ``_now``. Tests that want
# to assert "the call queued briefly" without burning real seconds patch
# this to a no-op or a record-and-return stub.
async def _async_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


class RateLimitExceeded(RuntimeError):  # noqa: N818  # name locked by Plan 16 Task 31 spec / D27 step 2 of 3
    """Raised when a per-domain rate-limit overflow exceeds queue capacity.

    Inherits ``RuntimeError`` so call sites that already catch ``RuntimeError``
    (or its :class:`brain_core.budget.per_domain_guard.BudgetCapExceeded`
    sibling) keep working when this new class layers in. Message shape:
    ``"domain={...}, rpm={...}, queue_depth={...}, max_queue={...}"``.
    """


class LeakyBucket:
    """Leaky-bucket rate limiter with bounded async-queue overflow.

    Tokens replenish continuously at ``rpm / 60`` per second, capped at
    ``rpm`` (one minute's worth of capacity). :meth:`acquire` consumes one
    token; if no tokens are available, the caller awaits until one is
    available — UNLESS the number of already-queued waiters exceeds
    ``rpm * 2``, in which case :meth:`acquire` raises
    :class:`RateLimitExceeded` immediately.

    The ``rpm * 2`` cap matches the Plan 16 Task 31 / D27 spec wording —
    "queue brief overflow; raise on excessive overflow". A user that bursts
    well above their per-minute cap shouldn't accumulate an unbounded async
    backlog; the raise surfaces the cap breach to the caller so the UI can
    show "you've hit your rate limit" instead of pretending nothing's wrong.

    Time source is the module-level :data:`_now` (defaults to
    ``time.monotonic``). Tests patch :data:`_now` to a deterministic clock
    instead of pulling in ``freezegun`` as a dev dependency.
    """

    def __init__(self, rpm: int) -> None:
        if rpm <= 0:
            raise ValueError("rpm must be positive")
        self._rpm = rpm
        self._capacity = float(rpm)
        self._tokens = float(rpm)  # start full so the first burst is free
        self._last_refill = _now()
        self._max_queue = rpm * 2  # Plan 16 D27: overflow tolerance ceiling
        self._waiters = 0
        self._lock = asyncio.Lock()

    @property
    def rpm(self) -> int:
        return self._rpm

    def _refill(self) -> None:
        """Add tokens proportional to elapsed wall-clock time, capped at capacity."""
        now = _now()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * (self._rpm / 60.0))
            self._last_refill = now

    async def acquire(self) -> None:
        """Consume one token. Sleep until available; raise on excessive backlog."""
        # Fast path + queue-depth check happens under the lock so the
        # ``_waiters`` counter and ``_tokens`` reservoir stay consistent
        # under concurrent acquire callers. The actual sleep happens
        # outside the lock so we don't serialize all waiters.
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            if self._waiters >= self._max_queue:
                raise RateLimitExceeded(
                    f"rpm={self._rpm}, queue_depth={self._waiters}, "
                    f"max_queue={self._max_queue}"
                )
            # Time-to-next-token: how many seconds until self._tokens >= 1.
                # Replenish rate is rpm/60 tokens/sec; need (1 - tokens) more.
            needed = 1.0 - self._tokens
            wait_seconds = needed / (self._rpm / 60.0)
            self._waiters += 1

        try:
            await _async_sleep(wait_seconds)
        finally:
            async with self._lock:
                self._waiters -= 1
                self._refill()
                # Decrement regardless of whether we got "exactly 1" — the
                # refill above is monotonic, and we've already counted this
                # call against the queue. If somehow tokens are still < 1
                # (clock skew, multiple concurrent acquires racing through),
                # subtract anyway and let the bucket go briefly negative;
                # the next refill restores monotonicity.
                self._tokens -= 1.0


# Module-private bucket registry, keyed on (domain, rpm) so a config change
# (e.g. user raises rpm via Settings) creates a fresh bucket rather than
# stretching the old one's reservoir. Tests reach in to clear this between
# cases — see :func:`_reset_buckets_for_tests`.
_per_domain_buckets: dict[tuple[str, int], LeakyBucket] = {}


def _get_or_create_bucket(domain: str, rpm: int) -> LeakyBucket:
    """Return the bucket for (domain, rpm), creating one if missing."""
    key = (domain, rpm)
    bucket = _per_domain_buckets.get(key)
    if bucket is None:
        bucket = LeakyBucket(rpm)
        _per_domain_buckets[key] = bucket
    return bucket


def _reset_buckets_for_tests() -> None:
    """Clear module-level bucket state. Test-only — never called from production."""
    _per_domain_buckets.clear()


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        client: Any | None = None,
        config: Config | None = None,
    ) -> None:
        if client is None:
            from anthropic import AsyncAnthropic  # imported lazily; tests inject via client=

            client = AsyncAnthropic(api_key=api_key)
        # Stored as Any so we can accept either a real AsyncAnthropic or a duck-typed
        # test stub without fighting the SDK's strict TypedDicts at the call sites.
        self._client: Any = client
        # Plan 16 Task 31: optional Config reference for per-domain rate-limit
        # lookup. Held as Any internally to avoid an import cycle through
        # brain_core.config in production paths that don't construct one.
        self._config: Any = config

    def _serialize_message(self, m: LLMMessage) -> dict[str, Any]:
        """Translate an LLMMessage to the SDK's expected shape."""
        if isinstance(m.content, str):
            return {"role": m.role, "content": m.content}
        blocks: list[dict[str, Any]] = []
        for block in m.content:
            if block.kind == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.kind == "tool_use":
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
            elif block.kind == "tool_result":
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.tool_use_id,
                        "content": block.content,
                        "is_error": block.is_error,
                    }
                )
        return {"role": m.role, "content": blocks}

    async def _gate_rate_limit(self, request: LLMRequest) -> None:
        """Plan 16 Task 31: gate the upstream call through a per-domain leaky-bucket.

        No-op when:

        * ``request.domain`` is ``None`` (legacy caller; preserves Plan 02 shape).
        * ``self._config`` is ``None`` (provider built without a Config reference).
        * No ``providers["anthropic"]`` entry exists.
        * No override exists for ``request.domain``.
        * The override exists but ``requests_per_minute`` is ``None``.

        Otherwise consumes one token from the bucket — sleeping briefly if
        the bucket is empty, or raising :class:`RateLimitExceeded` when
        the queue depth has overflowed past ``rpm * 2``.
        """
        domain = request.domain
        if domain is None or self._config is None:
            return
        provider_cfg = self._config.providers.get("anthropic")
        if provider_cfg is None:
            return
        override = provider_cfg.rate_limit_per_domain.get(domain)
        if override is None or override.requests_per_minute is None:
            return
        bucket = _get_or_create_bucket(domain, override.requests_per_minute)
        await bucket.acquire()

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await self._gate_rate_limit(request)
        raw: Any = await self._client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[self._serialize_message(m) for m in request.messages],
            stop_sequences=request.stop_sequences or None,
            tools=[t.model_dump() for t in request.tools] if request.tools else None,
        )
        text_blocks: list[str] = []
        tool_uses: list[ToolUse] = []
        for block in raw.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_blocks.append(block.text)
            elif btype == "tool_use":
                tool_uses.append(
                    ToolUse(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        input=dict(getattr(block, "input", {})),
                    )
                )
        return LLMResponse(
            model=raw.model,
            content="".join(text_blocks),
            usage=TokenUsage(
                input_tokens=getattr(raw.usage, "input_tokens", 0),
                output_tokens=getattr(raw.usage, "output_tokens", 0),
            ),
            stop_reason=getattr(raw, "stop_reason", None),
            tool_uses=tool_uses,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        # Minimal async-iter bridge. Full streaming is tested live in Plan 02 contract tests.
        # For tool_use, we emit tool_use_start on content_block_start, tool_use_input_delta
        # on input_json_delta events, and rely on the session loop (Task 17) to accumulate
        # input deltas between tool_use_start markers.
        await self._gate_rate_limit(request)
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": request.system or "",
            "messages": [self._serialize_message(m) for m in request.messages],
        }
        if request.tools:
            kwargs["tools"] = [t.model_dump() for t in request.tools]
        async with self._client.messages.stream(**kwargs) as s:
            async for event in s:
                ev_type = getattr(event, "type", "")
                if ev_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    btype = getattr(block, "type", "") if block else ""
                    if btype == "tool_use":
                        yield LLMStreamChunk(
                            tool_use_start=ToolUseStart(
                                id=getattr(block, "id", ""),
                                name=getattr(block, "name", ""),
                            )
                        )
                elif ev_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", "") if delta else ""
                    if dtype == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            yield LLMStreamChunk(delta=text)
                    elif dtype == "input_json_delta":
                        partial = getattr(delta, "partial_json", "")
                        if partial:
                            yield LLMStreamChunk(tool_use_input_delta=partial)
                else:
                    # Fallback: some stream events expose a `.delta.text` directly.
                    delta = getattr(event, "delta", None)
                    text = getattr(delta, "text", "") if delta else ""
                    if text:
                        yield LLMStreamChunk(delta=text)
            final = await s.get_final_message()
            yield LLMStreamChunk(
                usage=TokenUsage(
                    input_tokens=getattr(final.usage, "input_tokens", 0),
                    output_tokens=getattr(final.usage, "output_tokens", 0),
                ),
                done=True,
            )
