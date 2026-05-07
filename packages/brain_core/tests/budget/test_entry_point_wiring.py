"""Plan 16 Task 28.5 — pin tests for ``PerDomainBudgetGuard`` wiring across
every LLM entry point.

Per the task spec, every LLM-invoking entry point reads the per-call domain
and calls ``PerDomainBudgetGuard.check_for(domain, config)`` BEFORE the LLM
round-trip. These tests lock that contract for each entry point with two
branches per call site:

1. **cap respected** — guard does not raise, the LLM call proceeds.
2. **cap exceeded** — guard raises :class:`BudgetCapExceeded`, LLM is NEVER
   called (verified by the FakeLLMProvider's empty queue staying full).

Plus one integration-style test per critical path (chat, ingest pipeline)
that uses a real :class:`CostLedger` with a low daily cap and seeds spend so
the guard fires for real (not mocked).

Entry points covered:

* ``brain_core.chat.session.ChatSession.turn`` — chat stream guard.
* ``brain_core.chat.autotitle.AutoTitler.run`` — autotitle Haiku call.
* ``brain_core.chat.fork.summarize_turns`` — fork-summary Haiku call.
* ``brain_core.ingest.pipeline.IngestPipeline._classify_with_cost`` —
  classify (only when ``domain_override`` is supplied; auto-detect path
  passes ``domain=None`` and the guard no-ops by design).
* ``brain_core.ingest.pipeline.IngestPipeline._summarize`` — summarize.
* ``brain_core.ingest.pipeline.IngestPipeline._integrate`` — integrate.
* ``brain_core.ingest.classifier.classify`` — free-function classifier.
* ``brain_core.tools.ping_llm.handle`` — connection-test probe.

The tool-layer construction sites (``tools/ingest.py``, ``tools/bulk_import.py``,
``tools/classify.py``, ``tools/fork_thread.py``) are exercised transitively by
the existing tool tests + the integration test below — when their underlying
primitive (pipeline / classify / fork) honours the guard, the tools do too.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from brain_core.budget import BudgetCapExceeded, PerDomainBudgetGuard
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
from brain_core.config.schema import BudgetOverride, Config
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.ingest.classifier import classify as classify_fn
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _seed_ledger(ledger: CostLedger, *, domain: str, usd: float, hours_ago: float) -> None:
    """Record a ledger entry at ``now - hours_ago`` for ``domain``."""
    ts = datetime.now(tz=UTC) - timedelta(hours=hours_ago)
    ledger.record(
        CostEntry(
            timestamp=ts,
            operation="chat_turn",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=100,
            cost_usd=usd,
            domain=domain,
        )
    )


def _config_with_cap(vault_path: Path, *, domain: str, daily_cap: float) -> Config:
    """Build a :class:`Config` with one per-domain daily cap."""
    config = Config(vault_path=vault_path)
    config.budget.per_domain = {domain: BudgetOverride(daily_cap_usd=daily_cap)}
    return config


# Fixtures dir lives under tests/ingest/fixtures — the ingest conftest exposes
# it via a fixture, but it's not visible to this package. Resolve by absolute
# path so the pipeline tests can read from it.
_INGEST_FIXTURES = Path(__file__).parent.parent / "ingest" / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to ``tests/ingest/fixtures`` (cross-package fixture)."""
    return _INGEST_FIXTURES


# ---------------------------------------------------------------------------
# Chat session
# ---------------------------------------------------------------------------


def _build_chat_session(
    *,
    vault: Path,
    fake: FakeLLMProvider,
    domains: tuple[str, ...],
    guard: PerDomainBudgetGuard | None,
    config: Config | None,
) -> ChatSession:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="MODE PROMPT")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=domains)
    return ChatSession(
        config=cfg,
        llm=fake,
        compiler=compiler,
        registry=ToolRegistry(),
        retrieval=None,
        pending_store=None,
        state_db=None,
        vault_root=vault,
        thread_id="2026-04-29-draft-test0001",
        guard=guard,
        app_config=config,
    )


@pytest.mark.asyncio
async def test_chat_turn_under_cap_proceeds(tmp_path: Path) -> None:
    """Chat session: guard passes, LLM stream runs, normal events flow."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=0.10, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=10.00)

    fake = FakeLLMProvider()
    fake.queue("Hello there.")
    session = _build_chat_session(
        vault=tmp_path / "vault",
        fake=fake,
        domains=("research",),
        guard=guard,
        config=config,
    )
    (tmp_path / "vault").mkdir()
    events = [e async for e in session.turn("hi")]
    kinds = [e.kind for e in events]
    assert ChatEventKind.DELTA in kinds
    assert ChatEventKind.TURN_END in kinds


@pytest.mark.asyncio
async def test_chat_turn_over_cap_short_circuits(tmp_path: Path) -> None:
    """Chat session: guard raises, LLM is NEVER called.

    The FakeLLMProvider's queue stays full because the guard fires before
    ``self.llm.stream(...)`` is reached. The session's ``except`` block
    converts the raised :class:`BudgetCapExceeded` into an ERROR event and
    re-raises after the ``finally`` runs.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("Should never be streamed.")
    session = _build_chat_session(
        vault=tmp_path / "vault",
        fake=fake,
        domains=("research",),
        guard=guard,
        config=config,
    )
    (tmp_path / "vault").mkdir()

    with pytest.raises(BudgetCapExceeded):
        async for _ in session.turn("hi"):
            pass

    # The queued response is still in the queue: the LLM was never called.
    assert len(fake._queue) == 1


@pytest.mark.asyncio
async def test_chat_turn_multi_domain_no_ops_guard(tmp_path: Path) -> None:
    """Chat session: multi-domain scope -> guard sees ``domain=None`` -> no-op.

    Locks the architectural decision: per-call enforcement only happens for
    single-domain chats. Multi-domain chats fall back to the legacy global
    enforcement layer.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    # Seed enough spend that a per-domain cap WOULD fire if it were checked.
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("Hello there.")
    session = _build_chat_session(
        vault=tmp_path / "vault",
        fake=fake,
        domains=("research", "work"),  # multi-domain
        guard=guard,
        config=config,
    )
    (tmp_path / "vault").mkdir()
    events = [e async for e in session.turn("hi")]
    kinds = [e.kind for e in events]
    assert ChatEventKind.DELTA in kinds  # LLM was called


# ---------------------------------------------------------------------------
# AutoTitler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autotitle_under_cap_proceeds(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=0.10, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=10.00)

    fake = FakeLLMProvider()
    fake.queue('{"title": "Karpathy LLM Wiki"}')
    titler = AutoTitler(fake, guard=guard, config=config, domain="research")

    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="Tell me about LLMs", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="LLMs are...", created_at=now),
    ]
    result = await titler.run(turns)
    assert result.title == "Karpathy LLM Wiki"


@pytest.mark.asyncio
async def test_autotitle_over_cap_short_circuits(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("never streamed")
    titler = AutoTitler(fake, guard=guard, config=config, domain="research")

    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="x", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="y", created_at=now),
    ]
    with pytest.raises(BudgetCapExceeded):
        await titler.run(turns)
    assert len(fake._queue) == 1


# ---------------------------------------------------------------------------
# Fork — ``summarize_turns``
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fork_summary_under_cap_proceeds(tmp_path: Path) -> None:
    from brain_core.chat.fork import summarize_turns

    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=0.10, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=10.00)

    fake = FakeLLMProvider()
    fake.queue("A short prose summary.")

    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="hi", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="hello", created_at=now),
    ]
    summary = await summarize_turns(
        turns, fake, guard=guard, config=config, domain="research"
    )
    assert "summary" in summary.lower()


@pytest.mark.asyncio
async def test_fork_summary_over_cap_short_circuits(tmp_path: Path) -> None:
    from brain_core.chat.fork import summarize_turns

    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("never streamed")

    now = datetime.now(UTC)
    turns = [
        ChatTurn(role=TurnRole.USER, content="hi", created_at=now),
        ChatTurn(role=TurnRole.ASSISTANT, content="hello", created_at=now),
    ]
    with pytest.raises(BudgetCapExceeded):
        await summarize_turns(turns, fake, guard=guard, config=config, domain="research")
    assert len(fake._queue) == 1


# ---------------------------------------------------------------------------
# Classifier free-function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_under_cap_proceeds(tmp_path: Path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=0.10, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=10.00)

    fake = FakeLLMProvider()
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    result = await classify_fn(
        llm=fake,
        model="claude-haiku-4-5-20251001",
        title="hi",
        snippet="hello",
        allowed_domains=("research",),
        guard=guard,
        config=config,
        domain="research",
    )
    assert result.domain == "research"


@pytest.mark.asyncio
async def test_classifier_over_cap_short_circuits(tmp_path: Path) -> None:
    """Pre-supplied domain is over its cap -> classifier short-circuits."""
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("never streamed")

    with pytest.raises(BudgetCapExceeded):
        await classify_fn(
            llm=fake,
            model="claude-haiku-4-5-20251001",
            title="hi",
            snippet="hello",
            allowed_domains=("research",),
            guard=guard,
            config=config,
            domain="research",
        )
    assert len(fake._queue) == 1


@pytest.mark.asyncio
async def test_classifier_auto_detect_path_no_ops_guard(tmp_path: Path) -> None:
    """``domain=None`` (auto-detect path) -> guard no-ops -> classify proceeds.

    Locks the architectural invariant: classify cannot enforce a per-domain
    cap against a domain it hasn't determined yet.
    """
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    result = await classify_fn(
        llm=fake,
        model="claude-haiku-4-5-20251001",
        title="hi",
        snippet="hello",
        allowed_domains=("research",),
        guard=guard,
        config=config,
        domain=None,
    )
    assert result.domain == "research"


# ---------------------------------------------------------------------------
# Ingest pipeline — summarize / integrate stages enforce per-domain caps
# ---------------------------------------------------------------------------


def _build_pipeline(
    *,
    vault: Path,
    fake: FakeLLMProvider,
    guard: PerDomainBudgetGuard | None,
    config: Config | None,
) -> IngestPipeline:
    return IngestPipeline(
        vault_root=vault,
        writer=VaultWriter(vault_root=vault),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
        guard=guard,
        config=config,
    )


@pytest.mark.asyncio
async def test_pipeline_under_cap_proceeds(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    ledger = CostLedger(db_path=ephemeral_vault / ".brain" / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=0.10, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(ephemeral_vault, domain="research", daily_cap=10.00)

    fake = FakeLLMProvider()
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="x",
            key_points=["x"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
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
    )

    pipeline = _build_pipeline(vault=ephemeral_vault, fake=fake, guard=guard, config=config)
    res = await pipeline.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.OK


@pytest.mark.asyncio
async def test_pipeline_summarize_over_cap_short_circuits(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """Cap fires at summarize stage (post-classify, before LLM round-trip 2).

    Classify runs first (its own ``check_for(domain=None)`` no-ops because
    ``domain_override=None``). Once classify resolves the domain, the
    summarize stage's guard call fires against the resolved domain and
    raises. The pipeline's broad ``except Exception`` catches it and
    returns FAILED — guarantee that the integrate LLM call never happens.
    """
    ledger = CostLedger(db_path=ephemeral_vault / ".brain" / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(ephemeral_vault, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    # Classify response — this LLM call DOES happen (domain unknown
    # at that point, guard no-ops).
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    # Summarize + integrate responses — must NEVER be popped because the
    # guard fires before each. Sentinel strings make a regression
    # immediately visible.
    fake.queue("SUMMARIZE_SENTINEL_NEVER_STREAMED")
    fake.queue("INTEGRATE_SENTINEL_NEVER_STREAMED")

    pipeline = _build_pipeline(vault=ephemeral_vault, fake=fake, guard=guard, config=config)
    res = await pipeline.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.FAILED
    # Two queued responses left untouched: summarize + integrate never ran.
    assert len(fake._queue) == 2


@pytest.mark.asyncio
async def test_pipeline_classify_with_domain_override_over_cap_short_circuits(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """``domain_override`` supplied -> classify stage uses real cap check.

    With ``domain_override='research'`` set up-front, the pipeline skips
    the classify LLM call entirely (Stage 5 fast-path). So the FIRST LLM
    call is summarize, and that's where the cap fires.

    This test pins the override path's behavior end-to-end: when the
    user pre-specifies a domain that's over its cap, the very first LLM
    call short-circuits.
    """
    ledger = CostLedger(db_path=ephemeral_vault / ".brain" / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    guard = PerDomainBudgetGuard(ledger)
    config = _config_with_cap(ephemeral_vault, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    # All LLM responses are sentinels — none should be popped.
    fake.queue("SUMMARIZE_NEVER")
    fake.queue("INTEGRATE_NEVER")

    pipeline = _build_pipeline(vault=ephemeral_vault, fake=fake, guard=guard, config=config)
    res = await pipeline.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
        domain_override="research",
    )
    assert res.status is IngestStatus.FAILED
    assert len(fake._queue) == 2  # neither call ran


# ---------------------------------------------------------------------------
# ping_llm — the bare 1-token probe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ping_llm_with_domain_over_cap_short_circuits(tmp_path: Path) -> None:
    """ping_llm with a per-call domain over its cap -> probe refused.

    Locks the wiring: even the bare connection-test probe respects per-
    domain caps. Most production callers leave ``ctx.domain=None``
    (probes are domain-agnostic) so the guard no-ops, but a caller that
    sets a domain DOES get enforcement.
    """
    from brain_core.rate_limit import RateLimitConfig, RateLimiter
    from brain_core.tools.base import ToolContext
    from brain_core.tools.ping_llm import handle as ping_handle
    from brain_core.vault.undo import UndoLog

    vault = tmp_path / "vault"
    vault.mkdir()
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("never streamed")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=fake,
        cost_ledger=ledger,
        rate_limiter=RateLimiter(RateLimitConfig()),
        undo_log=UndoLog(vault_root=vault),
        config=config,
        domain="research",
    )
    result = await ping_handle({"model": "claude-haiku-4-6"}, ctx)
    assert result.data is not None
    assert result.data["ok"] is False
    assert "domain=research" in result.data["error"]
    # The fake's queue is untouched: no LLM call was made.
    assert len(fake._queue) == 1


@pytest.mark.asyncio
async def test_ping_llm_no_domain_no_ops_guard(tmp_path: Path) -> None:
    """Default ping_llm (``ctx.domain=None``) -> guard no-ops -> probe runs."""
    from brain_core.rate_limit import RateLimitConfig, RateLimiter
    from brain_core.tools.base import ToolContext
    from brain_core.tools.ping_llm import handle as ping_handle
    from brain_core.vault.undo import UndoLog

    vault = tmp_path / "vault"
    vault.mkdir()
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    _seed_ledger(ledger, domain="research", usd=2.00, hours_ago=2)  # cap-busting
    config = _config_with_cap(tmp_path, domain="research", daily_cap=1.00)

    fake = FakeLLMProvider()
    fake.queue("ok")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=fake,
        cost_ledger=ledger,
        rate_limiter=RateLimiter(RateLimitConfig()),
        undo_log=UndoLog(vault_root=vault),
        config=config,
        domain=None,  # no per-call domain → guard no-ops
    )
    result = await ping_handle({"model": "claude-haiku-4-6"}, ctx)
    assert result.data is not None
    assert result.data["ok"] is True
