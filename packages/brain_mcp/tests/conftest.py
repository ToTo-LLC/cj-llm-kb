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
from brain_mcp.server import create_server
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
