"""Plan 11 Task 6 — brain_list_domains exposes ``active_domain``.

Per D8 the response gained a third top-level data key so the frontend's
``useDomains()`` hook can hydrate scope on first mount without a second
round trip. These tests pin:

  (a) Default ``Config()`` → response ``active_domain == "research"``.
  (b) ``Config(active_domain="work")`` → response reflects it.
  (c) Read-after-write within a session: mutating ``ctx.config.active_domain``
      mid-session is visible on the *next* call (the tool reads
      ``ctx.config`` live, not a cached snapshot).

Plan 13 Task 1 / D1's ``ctx.config is None`` raise behavior is pinned in
``test_errors_raise_if_no_config.py`` (Plan 15 Task 8); the per-tool raise
test that previously lived here was dropped to avoid duplicate coverage.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.config.schema import DEFAULT_DOMAINS, Config
from brain_core.tools.base import ToolContext
from brain_core.tools.list_domains import handle


def _mk_ctx(vault: Path, *, config: Config) -> ToolContext:
    """Build a ToolContext for list_domains active-domain tests.

    Plan 15 D8: ``config`` is a required ``Config`` (no default, no Optional
    union). The None-config raise is pinned in
    ``test_errors_raise_if_no_config.py`` (Plan 15 Task 8); this fixture
    intentionally cannot construct a None-config context.
    """
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research", "work", "personal"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=config,
    )


async def test_default_config_active_domain_is_research(tmp_path: Path) -> None:
    """A freshly-constructed Config() defaults active_domain to 'research'
    (matches DEFAULT_DOMAINS[0] and the schema default literal)."""
    cfg = Config()
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))

    assert result.data is not None
    assert result.data["active_domain"] == "research"
    assert result.data["active_domain"] == DEFAULT_DOMAINS[0]
    # And it must be a member of the response's domains list (invariant
    # the Config validator enforces — pinned here so a future regression
    # in either side blows up loudly).
    assert result.data["active_domain"] in result.data["domains"]


async def test_config_active_domain_work_is_reflected(tmp_path: Path) -> None:
    """Constructing Config(active_domain='work') flows through to the response."""
    cfg = Config(active_domain="work")
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))

    assert result.data is not None
    assert result.data["active_domain"] == "work"
    assert "work" in result.data["domains"]


async def test_active_domain_read_after_write_within_session(tmp_path: Path) -> None:
    """Mutating ``ctx.config.active_domain`` mid-session is visible on the
    next ``handle()`` call. This pins that the tool reads ``ctx.config``
    LIVE (no cached snapshot) — important because brain_config_set
    mutates the same Config instance in-process before persisting it.
    """
    cfg = Config()  # active_domain defaults to "research"
    ctx = _mk_ctx(tmp_path, config=cfg)

    first = await handle({}, ctx)
    assert first.data is not None
    assert first.data["active_domain"] == "research"

    # Simulate brain_config_set flipping the active domain. We don't
    # invoke the config_set tool directly — the goal is to pin the
    # read-side contract, not couple to the write tool's API.
    assert ctx.config is not None  # narrow for mypy; we just constructed it
    ctx.config.active_domain = "work"

    second = await handle({}, ctx)
    assert second.data is not None
    assert second.data["active_domain"] == "work"
