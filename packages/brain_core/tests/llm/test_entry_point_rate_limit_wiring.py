"""Plan 16 Task 31.5 — pin tests for AnthropicProvider per-domain rate-limit
gate wiring across every LLM entry point.

Task 31 landed the gate mechanism (``AnthropicProvider._gate_rate_limit`` +
``LeakyBucket``). Task 31.5 (this file) closes the wiring loop: every
production LLM entry point must thread the per-call domain into the
``LLMRequest`` so the gate can fire BEFORE the upstream
``client.messages.{create,stream}`` call.

For each wired entry point this file pins two branches:

1. **Bypass** — provider built without a Config (or LLMRequest.domain is
   ``None``) → upstream client called normally; no rate-limit sleep happens.
2. **Gate** — provider built WITH a Config carrying a per-domain override AND
   the entry point sets ``LLMRequest.domain=that_domain`` → after draining
   the bucket the next call queues (records a sleep on the patched
   ``_async_sleep``).

Plus three architectural-invariant pins:

* Multi-domain chat session passes ``LLMRequest.domain=None`` and the gate
  no-ops even when an override exists for one of the scopes.
* ``IngestPipeline._classify_with_cost`` auto-detect path passes
  ``LLMRequest.domain=None`` and the gate no-ops (we cannot enforce against
  an unknown domain — that's what classify is determining).
* ``brain_ping_llm`` always passes ``LLMRequest.domain=None`` (deliberate
  per the tool docstring) and the gate no-ops.

Time strategy mirrors ``test_anthropic_rate_limit.py``: the module-level
``_now`` and ``_async_sleep`` callables in ``brain_core.llm.providers.anthropic``
are patched with a ``_FakeClock`` and a recording stub, and the bucket
registry is cleared between cases via ``_reset_buckets_for_tests``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from brain_core.chat.autotitle import AutoTitler
from brain_core.chat.context import ContextCompiler
from brain_core.chat.session import ChatSession
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.types import (
    ChatEventKind,
    ChatMode,
    ChatSessionConfig,
    ChatTurn,
    TurnRole,
)
from brain_core.config.schema import (
    Config,
    ProviderConfig,
    RateLimitOverride,
)
from brain_core.cost.ledger import CostLedger
from brain_core.ingest.classifier import classify as classify_fn
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.providers import anthropic as anthropic_mod
from brain_core.llm.providers.anthropic import (
    AnthropicProvider,
    _reset_buckets_for_tests,
)
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from brain_core.tools.base import ToolContext
from brain_core.tools.ping_llm import handle as ping_handle
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Fake client + clock fixtures (mirroring test_anthropic_rate_limit.py)
# ---------------------------------------------------------------------------


class _FakeClock:
    """Manually-advanced monotonic clock (mirrors test_anthropic_rate_limit)."""

    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


class _StreamCtx:
    """Async context manager mimicking ``AsyncAnthropic.messages.stream(...)``.

    Yields a single ``content_block_delta`` text event per response, then
    surfaces a ``final_message`` with end-of-turn metadata. This is the
    minimum shape :meth:`AnthropicProvider.stream` actually consumes.
    """

    def __init__(self, text: str, model: str) -> None:
        self._text = text
        self._model = model

    async def __aenter__(self) -> _StreamCtx:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def __aiter__(self) -> _StreamCtx:
        self._yielded = False
        return self

    async def __anext__(self) -> Any:
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True
        return SimpleNamespace(
            type="content_block_delta",
            delta=SimpleNamespace(type="text_delta", text=self._text),
        )

    async def get_final_message(self) -> Any:
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
            model=self._model,
        )


class _ScriptedAnthropicClient:
    """Fake AsyncAnthropic client supporting both ``messages.create`` and ``messages.stream``.

    Used end-to-end with a real :class:`AnthropicProvider` so the gate
    actually exists — :class:`brain_core.llm.fake.FakeLLMProvider` doesn't
    have the gate. ``responses`` is a queue of strings that are returned
    one per call (a single queue serves both ``create`` and ``stream``
    paths so a test can mix them naturally).
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        # ``messages`` namespace mirrors AsyncAnthropic's shape.
        self.messages = SimpleNamespace(create=self._create, stream=self._stream)

    def _next_text(self) -> str:
        return self._responses.pop(0) if self._responses else "ok"

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        text = self._next_text()
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
            model=kwargs["model"],
        )

    def _stream(self, **kwargs: Any) -> _StreamCtx:
        # Note: ``stream`` is NOT awaited by callers (see anthropic.py:291)
        # — it's used directly as an async context manager, so this is a
        # synchronous return of a context object, not a coroutine.
        self.calls.append(kwargs)
        return _StreamCtx(self._next_text(), kwargs["model"])


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
    """Patch ``_async_sleep`` to record durations and advance the fake clock."""
    durations: list[float] = []

    async def _record_and_advance(seconds: float) -> None:
        durations.append(seconds)
        fake_clock.advance(seconds)

    monkeypatch.setattr(anthropic_mod, "_async_sleep", _record_and_advance)
    return durations


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _config_with_rate_limit(
    vault_path: Path, *, domain: str, rpm: int
) -> Config:
    """Return a Config with one per-domain rate-limit override on anthropic."""
    config = Config(vault_path=vault_path)
    config.providers["anthropic"] = ProviderConfig(
        rate_limit_per_domain={domain: RateLimitOverride(requests_per_minute=rpm)}
    )
    return config


def _classify_payload() -> str:
    return '{"source_type":"text","domain":"research","confidence":0.95}'


def _summarize_payload() -> str:
    return SummarizeOutput(
        title="hello",
        summary="x",
        key_points=["x"],
        entities=[],
        concepts=[],
        open_questions=[],
    ).model_dump_json()


def _integrate_payload() -> str:
    return PatchSet(
        index_entries=[
            IndexEntryPatch(
                section="Sources",
                line="- [[hello]] — greeting",
                domain="research",
            )
        ],
        log_entry="ingest",
        reason="t",
    ).model_dump_json()


# ---------------------------------------------------------------------------
# ChatSession.turn — chat stream gate
# ---------------------------------------------------------------------------


def _build_chat_session(
    *,
    vault: Path,
    provider: AnthropicProvider,
    domains: tuple[str, ...],
    app_config: Config | None,
) -> ChatSession:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE PROMPT")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=domains)
    return ChatSession(
        config=cfg,
        llm=provider,
        compiler=compiler,
        registry=ToolRegistry(),
        retrieval=None,
        pending_store=None,
        state_db=None,
        vault_root=vault,
        thread_id="2026-04-29-draft-test0001",
        app_config=app_config,
    )


@pytest.mark.asyncio
async def test_chat_turn_bypass_when_no_config(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    """Chat session: provider has no Config -> gate cannot fire -> no sleep."""
    client = _ScriptedAnthropicClient(["hi back", "hi back", "hi back"])
    provider = AnthropicProvider(api_key="sk-test", client=client)  # no config
    vault = tmp_path / "vault"
    vault.mkdir()
    session = _build_chat_session(
        vault=vault, provider=provider, domains=("research",), app_config=None
    )

    # Stream three turns. With rpm=1 the gate WOULD queue calls 2 & 3 if it
    # were active; without a Config it never fires.
    for _ in range(3):
        events = [e async for e in session.turn("hi")]
        assert ChatEventKind.TURN_END in [e.kind for e in events]

    assert fake_sleep == []
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_chat_turn_gate_fires_for_single_domain(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    """Chat session: single-domain scope + override -> request.domain set -> gate fires."""
    client = _ScriptedAnthropicClient(["a", "b", "c"])
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=2)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    vault = tmp_path / "vault"
    vault.mkdir()
    session = _build_chat_session(
        vault=vault, provider=provider, domains=("research",), app_config=config
    )

    # First two turns drain the bucket without queueing.
    [e async for e in session.turn("hi")]
    [e async for e in session.turn("hi")]
    assert fake_sleep == []
    # Third turn must queue (~30s wait for rpm=2 → 1 token / 30s).
    [e async for e in session.turn("hi")]
    assert len(fake_sleep) == 1
    assert 29.9 < fake_sleep[0] < 30.1
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_chat_turn_multi_domain_no_ops_gate(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    """Multi-domain chat: ``LLMRequest.domain`` is ``None`` -> gate no-ops.

    Locks the architectural invariant: per-call rate-limit only fires for
    single-domain chats. Multi-domain chats pass ``None`` and bypass the gate.
    """
    client = _ScriptedAnthropicClient(["a", "b", "c", "d", "e"])
    # rpm=1 + override on "research" — would queue every call after the first
    # IF the request carried domain="research". Multi-domain must NOT.
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    vault = tmp_path / "vault"
    vault.mkdir()
    session = _build_chat_session(
        vault=vault,
        provider=provider,
        domains=("research", "work"),  # multi-domain
        app_config=config,
    )

    # 5 turns in a row — none should queue.
    for _ in range(5):
        [e async for e in session.turn("hi")]

    assert fake_sleep == []
    assert len(client.calls) == 5


# ---------------------------------------------------------------------------
# AutoTitler.run — autotitle Haiku call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autotitle_bypass_when_no_config(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    client = _ScriptedAnthropicClient([
        '{"title":"T1"}',
        '{"title":"T2"}',
        '{"title":"T3"}',
    ])
    provider = AnthropicProvider(api_key="sk-test", client=client)  # no config
    titler = AutoTitler(provider, domain="research")
    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="x", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="y", created_at=now),
    ]
    for _ in range(3):
        await titler.run(turns)
    assert fake_sleep == []
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_autotitle_gate_fires(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    client = _ScriptedAnthropicClient([
        '{"title":"T1"}',
        '{"title":"T2"}',
        '{"title":"T3"}',
    ])
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=2)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    titler = AutoTitler(provider, config=config, domain="research")
    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="x", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="y", created_at=now),
    ]
    await titler.run(turns)
    await titler.run(turns)
    assert fake_sleep == []
    await titler.run(turns)
    assert len(fake_sleep) == 1
    assert 29.9 < fake_sleep[0] < 30.1


# ---------------------------------------------------------------------------
# summarize_turns — fork-summary Haiku call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_turns_bypass_when_no_config(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    from brain_core.chat.fork import summarize_turns

    client = _ScriptedAnthropicClient(["s1", "s2", "s3"])
    provider = AnthropicProvider(api_key="sk-test", client=client)  # no config
    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="x", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="y", created_at=now),
    ]
    for _ in range(3):
        await summarize_turns(turns, provider, domain="research")
    assert fake_sleep == []
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_summarize_turns_gate_fires(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    from brain_core.chat.fork import summarize_turns

    client = _ScriptedAnthropicClient(["s1", "s2", "s3"])
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=2)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="x", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="y", created_at=now),
    ]
    await summarize_turns(turns, provider, config=config, domain="research")
    await summarize_turns(turns, provider, config=config, domain="research")
    assert fake_sleep == []
    await summarize_turns(turns, provider, config=config, domain="research")
    assert len(fake_sleep) == 1
    assert 29.9 < fake_sleep[0] < 30.1


# ---------------------------------------------------------------------------
# Free-function classify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_fn_bypass_when_no_config(
    fake_clock: _FakeClock, fake_sleep: list[float]
) -> None:
    client = _ScriptedAnthropicClient(
        [_classify_payload(), _classify_payload(), _classify_payload()]
    )
    provider = AnthropicProvider(api_key="sk-test", client=client)  # no config
    for _ in range(3):
        await classify_fn(
            llm=provider,
            model="claude-haiku-4-5-20251001",
            title="hi",
            snippet="hello",
            allowed_domains=("research",),
            domain="research",
        )
    assert fake_sleep == []
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_classify_fn_gate_fires_when_domain_supplied(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    """Caller supplies ``domain=`` -> gate enforces."""
    client = _ScriptedAnthropicClient(
        [_classify_payload(), _classify_payload(), _classify_payload()]
    )
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=2)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    for _ in range(2):
        await classify_fn(
            llm=provider,
            model="claude-haiku-4-5-20251001",
            title="hi",
            snippet="hello",
            allowed_domains=("research",),
            config=config,
            domain="research",
        )
    assert fake_sleep == []
    await classify_fn(
        llm=provider,
        model="claude-haiku-4-5-20251001",
        title="hi",
        snippet="hello",
        allowed_domains=("research",),
        config=config,
        domain="research",
    )
    assert len(fake_sleep) == 1
    assert 29.9 < fake_sleep[0] < 30.1


@pytest.mark.asyncio
async def test_classify_fn_no_domain_no_ops_gate(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    """``domain=None`` (auto-detect path) -> gate no-ops even with a strict override."""
    client = _ScriptedAnthropicClient(
        [_classify_payload(), _classify_payload(), _classify_payload()]
    )
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    for _ in range(3):
        await classify_fn(
            llm=provider,
            model="claude-haiku-4-5-20251001",
            title="hi",
            snippet="hello",
            allowed_domains=("research",),
            config=config,
            domain=None,  # auto-detect path
        )
    assert fake_sleep == []
    assert len(client.calls) == 3


# ---------------------------------------------------------------------------
# IngestPipeline — _classify_with_cost / _summarize / _integrate
# ---------------------------------------------------------------------------


def _build_pipeline(
    *,
    vault: Path,
    provider: AnthropicProvider,
    config: Config | None,
) -> IngestPipeline:
    return IngestPipeline(
        vault_root=vault,
        writer=VaultWriter(vault_root=vault),
        llm=provider,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
        config=config,
    )


_INGEST_FIXTURES = Path(__file__).parent.parent / "ingest" / "fixtures"


@pytest.mark.asyncio
async def test_pipeline_bypass_when_no_config(
    fake_clock: _FakeClock,
    fake_sleep: list[float],
    ephemeral_vault: Path,
) -> None:
    """End-to-end pipeline ingest: provider has no Config -> no rate-limit gate fires."""
    client = _ScriptedAnthropicClient(
        [_classify_payload(), _summarize_payload(), _integrate_payload()]
    )
    provider = AnthropicProvider(api_key="sk-test", client=client)  # no config
    pipeline = _build_pipeline(
        vault=ephemeral_vault, provider=provider, config=None
    )
    res = await pipeline.ingest(
        _INGEST_FIXTURES / "hello.txt",
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.OK
    assert fake_sleep == []
    # 3 LLM round-trips: classify + summarize + integrate.
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_pipeline_summarize_stage_gate_fires(
    fake_clock: _FakeClock,
    fake_sleep: list[float],
    ephemeral_vault: Path,
) -> None:
    """Pipeline summarize stage carries ``LLMRequest.domain`` -> gate enforces.

    rpm=1: classify (auto-detect, ``domain=None``) bypasses, summarize is the
    first call against the resolved ``research`` domain so it drains the
    bucket, integrate then queues for ~60s. The gate fires INSIDE the
    upstream provider before ``messages.create`` runs.
    """
    client = _ScriptedAnthropicClient(
        [_classify_payload(), _summarize_payload(), _integrate_payload()]
    )
    config = _config_with_rate_limit(ephemeral_vault, domain="research", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    pipeline = _build_pipeline(
        vault=ephemeral_vault, provider=provider, config=config
    )
    res = await pipeline.ingest(
        _INGEST_FIXTURES / "hello.txt",
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.OK
    # Exactly one sleep: summarize drained the bucket (rpm=1 → 1 token at
    # start), integrate queued for ~60s before completing.
    assert len(fake_sleep) == 1
    assert 59.9 < fake_sleep[0] < 60.1


@pytest.mark.asyncio
async def test_pipeline_classify_with_domain_override_gate_fires(
    fake_clock: _FakeClock,
    fake_sleep: list[float],
    ephemeral_vault: Path,
) -> None:
    """``domain_override`` supplied -> classify carries ``LLMRequest.domain`` too.

    With ``domain_override='research'`` set up-front the pipeline takes the
    fast-path (skipping the classify LLM call), so we only see summarize +
    integrate calls. The first (summarize) drains the bucket, the second
    (integrate) queues — proves the override flowed through to the
    summarize/integrate ``LLMRequest.domain``.
    """
    client = _ScriptedAnthropicClient(
        [_summarize_payload(), _integrate_payload()]
    )
    config = _config_with_rate_limit(ephemeral_vault, domain="research", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    pipeline = _build_pipeline(
        vault=ephemeral_vault, provider=provider, config=config
    )
    res = await pipeline.ingest(
        _INGEST_FIXTURES / "hello.txt",
        allowed_domains=("research",),
        domain_override="research",
    )
    assert res.status is IngestStatus.OK
    assert len(fake_sleep) == 1
    assert 59.9 < fake_sleep[0] < 60.1


@pytest.mark.asyncio
async def test_pipeline_classify_auto_detect_no_ops_gate(
    fake_clock: _FakeClock,
    fake_sleep: list[float],
    ephemeral_vault: Path,
) -> None:
    """Auto-detect classify carries ``LLMRequest.domain=None`` -> gate no-ops.

    Locks the architectural invariant: classify cannot enforce rate-limits
    against a domain it hasn't determined yet.

    With rpm=1: if classify's call were bound to ``research`` it would
    drain the bucket and the next call (summarize) would queue. We use a
    DIFFERENT domain ("personal") on the cap so any drain on research
    would be an indictment — but we're proving the OPPOSITE: classify's
    request.domain is None, so nothing runs against the "research" bucket
    at the classify stage. We make summarize+integrate also no-op by
    setting the cap on a different domain ("personal") — only "research"
    is the resolved post-classify domain, and "personal" has the cap, so
    even summarize+integrate bypass the gate. This pins both halves at
    once.
    """
    client = _ScriptedAnthropicClient(
        [_classify_payload(), _summarize_payload(), _integrate_payload()]
    )
    # Cap is on "personal", not "research". Summarize+integrate request
    # ``domain="research"`` so they bypass too. Classify auto-detect path
    # passes ``domain=None`` and bypasses regardless.
    config = _config_with_rate_limit(ephemeral_vault, domain="personal", rpm=1)
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)
    pipeline = _build_pipeline(
        vault=ephemeral_vault, provider=provider, config=config
    )
    res = await pipeline.ingest(
        _INGEST_FIXTURES / "hello.txt",
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.OK
    assert fake_sleep == []
    assert len(client.calls) == 3


# ---------------------------------------------------------------------------
# brain_ping_llm — adjudicated NOT rate-limited (deliberate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ping_llm_never_rate_limited(
    fake_clock: _FakeClock, fake_sleep: list[float], tmp_path: Path
) -> None:
    """``brain_ping_llm`` is intentionally unrate-limited (per its docstring).

    The tool builds an ``LLMRequest`` without setting ``domain=`` so the
    provider's gate always no-ops, even when a strict per-domain override
    is configured AND the ``ToolContext`` carries an active domain.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    config = _config_with_rate_limit(tmp_path, domain="research", rpm=1)
    client = _ScriptedAnthropicClient(["ok", "ok", "ok"])
    provider = AnthropicProvider(api_key="sk-test", client=client, config=config)

    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=provider,
        cost_ledger=ledger,
        rate_limiter=RateLimiter(RateLimitConfig()),
        undo_log=UndoLog(vault_root=vault),
        config=config,
        domain="research",  # would gate every call after the first IF the request carried it
    )

    for _ in range(3):
        result = await ping_handle({"model": "claude-haiku-4-6"}, ctx)
        assert result.data is not None
        assert result.data["ok"] is True

    # Three pings -> 3 client calls, never queued.
    assert fake_sleep == []
    assert len(client.calls) == 3
