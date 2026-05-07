"""Plan 16 Task 31 / D27 step 2 of 3: per-domain leaky-bucket rate-limit pin tests.

Cases pinned (per Plan 16 Task 31 spec):

* (a) ``rpm=2`` — 2 calls in the same window pass.
* (b) 3rd call queues briefly (sleeps the right amount) and then succeeds.
* (c) Overflow beyond ``rpm * 2`` raises :class:`RateLimitExceeded`.
* (d) Advancing the clock by 1 minute replenishes the bucket.
* (e) Different domain has an independent bucket.

Plus an integration case routed through :class:`AnthropicProvider` with a
fake client + a real :class:`Config` carrying a per-domain rate-limit
override, to verify wiring end-to-end.

Time strategy: ``brain_core.llm.providers.anthropic._now`` is a module-level
``Callable[[], float]`` indirected over ``time.monotonic`` so tests patch
the clock without a freezegun dev-dep. ``_async_sleep`` is similarly
indirected so we don't burn real seconds when a waiter queues briefly.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from brain_core.config.schema import (
    Config,
    ProviderConfig,
    RateLimitOverride,
)
from brain_core.llm.providers import anthropic as anthropic_mod
from brain_core.llm.providers.anthropic import (
    AnthropicProvider,
    LeakyBucket,
    RateLimitExceeded,
    _get_or_create_bucket,
    _reset_buckets_for_tests,
)
from brain_core.llm.types import LLMMessage, LLMRequest


class _FakeClock:
    """Manually-advanced monotonic clock for deterministic rate-limit tests.

    Replaces ``brain_core.llm.providers.anthropic._now`` so :class:`LeakyBucket`'s
    refill arithmetic can be driven by ``clock.advance(seconds)`` calls instead
    of real wall time.
    """

    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    """Install a fake monotonic clock and clear bucket state before each test."""
    _reset_buckets_for_tests()
    clock = _FakeClock()
    monkeypatch.setattr(anthropic_mod, "_now", clock)
    return clock


@pytest.fixture
def fake_sleep(
    monkeypatch: pytest.MonkeyPatch, fake_clock: _FakeClock
) -> list[float]:
    """Replace asyncio sleep with a clock-advancing stub so waiters don't burn real time.

    Returns a list of recorded sleep durations so tests can assert "the 3rd
    call queued for ~30s" without timing instability.
    """
    durations: list[float] = []

    async def _record_and_advance(seconds: float) -> None:
        durations.append(seconds)
        fake_clock.advance(seconds)

    monkeypatch.setattr(anthropic_mod, "_async_sleep", _record_and_advance)
    return durations


# ---------------------------------------------------------------------------
# LeakyBucket — direct unit tests
# ---------------------------------------------------------------------------


def test_leaky_bucket_rejects_non_positive_rpm() -> None:
    with pytest.raises(ValueError, match="rpm must be positive"):
        LeakyBucket(0)
    with pytest.raises(ValueError, match="rpm must be positive"):
        LeakyBucket(-3)


@pytest.mark.asyncio
async def test_a_two_calls_within_rpm_window_pass(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Spec case (a): rpm=2, 2 calls in the same window → both pass without queueing."""
    bucket = LeakyBucket(rpm=2)

    await bucket.acquire()
    await bucket.acquire()

    # Neither call should have queued — capacity starts full.
    assert fake_sleep == []


@pytest.mark.asyncio
async def test_b_third_call_queues_briefly_then_succeeds(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Spec case (b): rpm=2, 3rd call queues for ~30s then completes."""
    bucket = LeakyBucket(rpm=2)

    await bucket.acquire()
    await bucket.acquire()
    # Bucket is now empty. 3rd call must sleep until the next token replenishes.
    # Replenish rate = 2/60 = 1/30 tokens/sec → need ~30s for 1 token.
    await bucket.acquire()

    assert len(fake_sleep) == 1
    # 30s ± floating-point fuzz.
    assert 29.9 < fake_sleep[0] < 30.1


@pytest.mark.asyncio
async def test_c_overflow_beyond_rpm_times_two_raises(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Spec case (c): excessive overflow raises :class:`RateLimitExceeded`.

    With rpm=2, max_queue=4. Drain initial capacity (2 calls), then issue 4
    concurrent calls that queue (waiters=4 → still within max_queue), then a
    5th call must raise: it sees waiters >= max_queue.
    """
    import asyncio

    bucket = LeakyBucket(rpm=2)

    # Drain initial capacity — these don't queue.
    await bucket.acquire()
    await bucket.acquire()

    # Stage 4 concurrent waiters that fill the queue. We don't await them
    # here — we want them to be parked in the queue when the 5th call
    # checks overflow. ``asyncio.gather`` would await; ``create_task`` +
    # a yield lets them register as waiters.
    tasks = [asyncio.create_task(bucket.acquire()) for _ in range(4)]
    # Yield control so the tasks can run up to the await-sleep point.
    # Each task runs until it hits ``await _async_sleep(...)`` — our fake
    # sleep records and returns immediately, but the task still yields
    # control, so we need to drive enough event-loop iterations to land
    # them all in the sleep state. With a fake-instant sleep they actually
    # complete; that's fine — they completed BUT they each incremented
    # waiters during the sleep window, which is what we're verifying
    # below (we observe the recorded sleep count).
    for t in tasks:
        await t

    # All 4 queued (each recorded one sleep), then completed.
    assert len(fake_sleep) == 4

    # Now stage 5 concurrent waiters with the queue at max from a fresh drain.
    # Drain again (refill should have brought it positive, then we take 2).
    fake_clock.advance(60.0)  # full refill
    fake_sleep.clear()

    await bucket.acquire()
    await bucket.acquire()

    # Now hold 5 waiters open. We need them to all be in the queue at once;
    # the fake sleep returns instantly, so to truly test the >=max_queue
    # branch we instead patch sleep to NEVER return (await an event we
    # don't set), then verify the 5th call raises before sleeping.
    blocking_event = asyncio.Event()
    sleep_calls = 0

    async def _block_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        # Park forever — until the test cancels.
        await blocking_event.wait()

    import brain_core.llm.providers.anthropic as anth_mod

    anth_mod._async_sleep = _block_sleep  # type: ignore[assignment]

    waiters = [asyncio.create_task(bucket.acquire()) for _ in range(4)]
    # Drive the event loop so all 4 register as waiters.
    for _ in range(10):
        await asyncio.sleep(0)

    # All 4 should now be parked in our blocking sleep.
    assert sleep_calls == 4

    # The 5th call: queue depth is 4 (== rpm * 2), so it MUST raise.
    with pytest.raises(RateLimitExceeded) as exc_info:
        await bucket.acquire()
    assert "rpm=2" in str(exc_info.value)
    assert "max_queue=4" in str(exc_info.value)

    # Cleanup: cancel the parked waiters so the test exits cleanly.
    import contextlib

    for w in waiters:
        w.cancel()
    for w in waiters:
        with contextlib.suppress(asyncio.CancelledError):
            await w


@pytest.mark.asyncio
async def test_d_advancing_clock_replenishes_bucket(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Spec case (d): after 1 minute the bucket is full again."""
    bucket = LeakyBucket(rpm=2)

    # Drain.
    await bucket.acquire()
    await bucket.acquire()

    # Advance 60s — refill should bring tokens back to capacity (2).
    fake_clock.advance(60.0)

    # Two more calls should pass without queueing.
    await bucket.acquire()
    await bucket.acquire()

    # No sleeps recorded for the post-replenish calls.
    assert fake_sleep == []


@pytest.mark.asyncio
async def test_e_different_domains_have_independent_buckets(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Spec case (e): each domain key gets its own :class:`LeakyBucket`."""
    bucket_research = _get_or_create_bucket("research", rpm=2)
    bucket_work = _get_or_create_bucket("work", rpm=2)

    # Drain research.
    await bucket_research.acquire()
    await bucket_research.acquire()

    # Work bucket is completely untouched — both calls pass.
    await bucket_work.acquire()
    await bucket_work.acquire()

    assert fake_sleep == []
    assert bucket_research is not bucket_work
    # Same key returns the same instance.
    assert _get_or_create_bucket("research", rpm=2) is bucket_research
    # Different rpm → different bucket (config change creates a fresh one).
    assert _get_or_create_bucket("research", rpm=5) is not bucket_research


# ---------------------------------------------------------------------------
# AnthropicProvider integration — gate fires before client.messages.create
# ---------------------------------------------------------------------------


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = SimpleNamespace(create=self._create)
        self.calls: list[dict[str, Any]] = []

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
            model=kwargs["model"],
        )


def _build_config_with_rate_limit(domain: str, rpm: int) -> Config:
    """Return a minimal :class:`Config` with one provider override."""
    return Config(
        domains=[domain, "personal"],
        active_domain=domain,
        privacy_railed=["personal"],
        providers={
            "anthropic": ProviderConfig(
                rate_limit_per_domain={domain: RateLimitOverride(requests_per_minute=rpm)}
            ),
        },
    )


@pytest.mark.asyncio
async def test_provider_gates_when_domain_has_rate_limit(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """End-to-end: provider with config + request.domain triggers the gate."""
    client = _FakeAnthropicClient()
    config = _build_config_with_rate_limit("research", rpm=2)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)

    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
        domain="research",
    )

    # First two calls drain the bucket.
    await provider.complete(req)
    await provider.complete(req)
    assert fake_sleep == []
    assert len(client.calls) == 2

    # Third call queues for ~30s.
    await provider.complete(req)
    assert len(fake_sleep) == 1
    assert 29.9 < fake_sleep[0] < 30.1
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_provider_bypasses_when_no_domain_on_request(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Legacy-shape callers (no ``domain``) bypass the gate entirely."""
    client = _FakeAnthropicClient()
    config = _build_config_with_rate_limit("research", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)

    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
    )

    # 5 calls in a row — none should queue, even though rpm=1.
    for _ in range(5):
        await provider.complete(req)

    assert fake_sleep == []
    assert len(client.calls) == 5


@pytest.mark.asyncio
async def test_provider_bypasses_when_domain_has_no_override(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Domains without an explicit rate-limit override pass through ungated."""
    client = _FakeAnthropicClient()
    # Config has an override for "research" but request.domain="work".
    config = _build_config_with_rate_limit("research", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)

    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
        domain="work",
    )

    for _ in range(5):
        await provider.complete(req)

    assert fake_sleep == []
    assert len(client.calls) == 5


@pytest.mark.asyncio
async def test_provider_bypasses_when_no_config(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    """Provider built without a Config reference doesn't gate (preserves Plan 02 shape)."""
    client = _FakeAnthropicClient()
    provider = AnthropicProvider(api_key="sk-test", client=client)  # no config

    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
        domain="research",
    )

    for _ in range(5):
        await provider.complete(req)

    assert fake_sleep == []
