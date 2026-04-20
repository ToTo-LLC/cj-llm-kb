"""WS auth smoke tests for ``check_ws_token``.

Plan 05 Task 9. Full WebSocket endpoints land in Group 6; the helper is
pure enough to test standalone by mocking the ``WebSocket`` surface.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from brain_api.auth import check_ws_token
from brain_api.context import AppContext


@pytest.mark.asyncio
async def test_check_ws_token_accepts_correct_token() -> None:
    ctx = MagicMock(spec=AppContext)
    ctx.token = "a" * 64

    ws = MagicMock()
    ws.query_params = {"token": "a" * 64}
    ws.close = AsyncMock()

    result = await check_ws_token(ws, ctx)
    assert result is True
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_ws_token_closes_on_missing_token() -> None:
    ctx = MagicMock(spec=AppContext)
    ctx.token = "a" * 64

    ws = MagicMock()
    ws.query_params = {}  # no token
    ws.close = AsyncMock()

    result = await check_ws_token(ws, ctx)
    assert result is False
    ws.close.assert_awaited_once()
    kwargs = ws.close.call_args.kwargs
    assert kwargs["code"] == 1008


@pytest.mark.asyncio
async def test_check_ws_token_closes_on_wrong_token() -> None:
    ctx = MagicMock(spec=AppContext)
    ctx.token = "a" * 64

    ws = MagicMock()
    ws.query_params = {"token": "b" * 64}
    ws.close = AsyncMock()

    result = await check_ws_token(ws, ctx)
    assert result is False
    ws.close.assert_awaited_once()
    kwargs = ws.close.call_args.kwargs
    assert kwargs["code"] == 1008
