"""Shared fixtures and helpers for brain_mcp tests.

We expose `mcp_session_ctx` via a pytest fixture as an async-context-manager
factory, rather than as a yielding async fixture that holds the session open,
because `mcp.shared.memory.create_connected_server_and_client_session` owns an
internal `anyio` task group. When wrapped inside a pytest-asyncio
async-generator fixture, setup and teardown can execute in different tasks,
tripping anyio's "Attempted to exit cancel scope in a different task" guard.

Tests therefore do:

    async def test_foo(mcp_session_ctx, tmp_path):
        async with mcp_session_ctx(tmp_path) as session:
            ...

which keeps the task group's `__aenter__` and `__aexit__` on the same task.
Verified against mcp==1.27.0, pytest-asyncio==1.3.0.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.config.schema import Config
from brain_core.cost.ledger import CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.state.db import StateDB
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from brain_mcp.server import create_server
from brain_core.tools.base import ToolContext
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session


@asynccontextmanager
async def _make_session(vault_root: Path) -> AsyncIterator[ClientSession]:
    server = create_server(vault_root=vault_root)
    async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
        yield session


@pytest.fixture
def mcp_session_ctx() -> Callable[[Path], AbstractAsyncContextManager[ClientSession]]:
    """Return a factory that produces an async-context-managed ClientSession.

    Using a factory (sync fixture returning a callable) rather than an async
    yielding fixture avoids cross-task cancel-scope errors from anyio.
    """
    return _make_session


# ---------------------------------------------------------------------------
# Task 4+ shared helpers: seeded_vault, make_tool_context, make_ctx fixture,
# mcp_session_ctx_with_vault factory.
# ---------------------------------------------------------------------------


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def seeded_vault(tmp_path: Path) -> Path:
    """A small research + work + personal vault used by all read-tool tests."""
    vault = tmp_path / "vault"
    _write_note(
        vault,
        "research/notes/karpathy.md",
        title="Karpathy",
        body="Andrej Karpathy wrote about the LLM wiki pattern.",
    )
    _write_note(
        vault,
        "research/notes/rag.md",
        title="RAG",
        body="Retrieval augmented generation.",
    )
    _write_note(
        vault,
        "research/notes/filler.md",
        title="Filler",
        body="Cooking recipes and gardening tips.",
    )
    (vault / "research" / "index.md").write_text(
        "# research\n- [[karpathy]]\n- [[rag]]\n", encoding="utf-8"
    )
    _write_note(vault, "work/notes/meeting.md", title="Meeting", body="Q4 planning.")
    (vault / "work" / "index.md").write_text("# work\n- [[meeting]]\n", encoding="utf-8")
    _write_note(vault, "personal/notes/secret.md", title="Secret", body="never read me")
    (vault / "BRAIN.md").write_text("# BRAIN\n\nYou are brain.\n", encoding="utf-8")
    return vault


def make_tool_context(
    vault: Path,
    *,
    allowed_domains: tuple[str, ...] = ("research",),
) -> ToolContext:
    """Build a real ToolContext wired to all the Plan 01-03 primitives.

    Uses a FakeLLMProvider so no network calls. Rate limiter is generous
    (1000/min both buckets) so tests never trip it unless they mean to.
    """
    brain_dir = vault / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    db = StateDB.open(brain_dir / "state.sqlite")
    writer = VaultWriter(vault_root=vault)
    pending = PendingPatchStore(brain_dir / "pending")
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(allowed_domains)
    undo = UndoLog(vault_root=vault)
    ledger = CostLedger(db_path=brain_dir / "costs.sqlite")
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=1000, tokens_per_minute=1_000_000))
    # Plan 12 Task 3: brain_config_get / brain_list_domains and other read
    # tools now read live ``ctx.config`` and raise ``RuntimeError`` if it's
    # ``None``. Wire a default ``Config()`` here so the conftest stays a
    # production-shape fixture rather than triggering the lifecycle-violation
    # raise on every direct-tool test that doesn't care about Config.
    return ToolContext(
        vault_root=vault,
        allowed_domains=allowed_domains,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        writer=writer,
        llm=FakeLLMProvider(),
        cost_ledger=ledger,
        rate_limiter=limiter,
        undo_log=undo,
        config=Config(),
    )


@pytest.fixture
def make_ctx() -> Callable[..., ToolContext]:
    """Return the `make_tool_context` callable as a fixture."""
    return make_tool_context


@pytest.fixture
def mcp_session_ctx_with_vault(
    seeded_vault: Path,
) -> Callable[[], AbstractAsyncContextManager[ClientSession]]:
    """Factory returning an MCP session bound to a seeded vault (allowed=('research',))."""

    @asynccontextmanager
    async def _make() -> AsyncIterator[ClientSession]:
        server = create_server(vault_root=seeded_vault, allowed_domains=("research",))
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as session:
            yield session

    return _make
