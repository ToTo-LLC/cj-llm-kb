"""Tests for brain_mcp resources (brain://BRAIN.md, brain://<domain>/index.md, brain://config/public).

The `mcp_session_ctx_with_vault` fixture from conftest.py is an async-context-manager
FACTORY (sync fixture returning a callable) rather than a yielded session, because
`mcp.shared.memory.create_connected_server_and_client_session` owns an internal
anyio task group that trips "exit cancel scope in a different task" if setup and
teardown run in different tasks. Tests therefore do:

    async with mcp_session_ctx_with_vault() as session:
        ...

which keeps the task group's __aenter__ and __aexit__ on the same task.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import pytest
from mcp.client.session import ClientSession
from pydantic import AnyUrl

SessionCtx = Callable[[], AbstractAsyncContextManager[ClientSession]]


async def test_list_resources_returns_three(mcp_session_ctx_with_vault: SessionCtx) -> None:
    async with mcp_session_ctx_with_vault() as session:
        result = await session.list_resources()
        uris = [str(r.uri) for r in result.resources]
        assert "brain://BRAIN.md" in uris
        assert any(u.startswith("brain://") and u.endswith("/index.md") for u in uris)
        assert "brain://config/public" in uris


async def test_read_brain_md(mcp_session_ctx_with_vault: SessionCtx) -> None:
    async with mcp_session_ctx_with_vault() as session:
        result = await session.read_resource(AnyUrl("brain://BRAIN.md"))
        assert len(result.contents) >= 1
        first = result.contents[0]
        text = getattr(first, "text", "")
        assert "You are brain" in text


async def test_read_domain_index(mcp_session_ctx_with_vault: SessionCtx) -> None:
    async with mcp_session_ctx_with_vault() as session:
        result = await session.read_resource(AnyUrl("brain://research/index.md"))
        assert any("karpathy" in getattr(c, "text", "") for c in result.contents)


async def test_read_config_public(mcp_session_ctx_with_vault: SessionCtx) -> None:
    async with mcp_session_ctx_with_vault() as session:
        result = await session.read_resource(AnyUrl("brain://config/public"))
        text = getattr(result.contents[0], "text", "")
        data = json.loads(text)
        # Must NOT contain secrets (deep-recursive keyword scan over the dumped payload).
        dumped = json.dumps(data).lower()
        assert "api_key" not in dumped
        assert "secret" not in dumped
        assert "password" not in dumped
        assert "token" not in dumped


async def test_read_out_of_scope_domain_index_raises(
    mcp_session_ctx_with_vault: SessionCtx,
) -> None:
    # Session is allowed_domains=("research",); 'personal' must refuse.
    # With `raise_exceptions=True`, the server's ScopeError crashes the anyio
    # task group and surfaces at the session context-manager's __aexit__ as
    # a nested BaseExceptionGroup (anyio wraps every task-group failure), not
    # at the read_resource call site — so we wrap the whole `async with`.
    # Production (`raise_exceptions=False`) converts this to an McpError
    # returned to the client; the scope guard is the behavior under test either way.
    with pytest.raises(BaseExceptionGroup) as excinfo:
        async with mcp_session_ctx_with_vault() as session:
            await session.read_resource(AnyUrl("brain://personal/index.md"))
    # Flatten nested ExceptionGroups to confirm our ScopeError specifically fired
    # (vs some unrelated TaskGroup crash from an SDK bug).
    flat = _flatten(excinfo.value)
    assert any("personal" in str(e) for e in flat)


async def test_read_unknown_resource_raises(mcp_session_ctx_with_vault: SessionCtx) -> None:
    # Same pattern as the out-of-scope test: unknown URI triggers a ValueError
    # server-side that surfaces via a nested BaseExceptionGroup at session teardown.
    with pytest.raises(BaseExceptionGroup) as excinfo:
        async with mcp_session_ctx_with_vault() as session:
            await session.read_resource(AnyUrl("brain://nonexistent"))
    flat = _flatten(excinfo.value)
    assert any("unknown resource" in str(e) for e in flat)


def _flatten(exc: BaseException) -> list[BaseException]:
    """Recursively flatten nested ExceptionGroups to a list of leaf exceptions."""
    if isinstance(exc, BaseExceptionGroup):
        out: list[BaseException] = []
        for sub in exc.exceptions:
            out.extend(_flatten(sub))
        return out
    return [exc]
