"""Typed helpers for WS test files — Plan 05 Task 25.

The WS test files (``test_ws_chat_*.py``) build a fresh ``TestClient`` so
the lifespan runs and populates ``app.state.ctx`` with an ``AppContext``.
Every test then reaches into ``fresh.app.state.ctx.token`` (and, in cancel/
reconnect, ``fresh.app.state.ctx.tool_ctx.llm.queue(...)``).

Two typing issues make this hard:

1. ``TestClient.app`` is typed as the raw ASGI callable (``Callable[[Scope,
   Receive, Send], Awaitable[None]]``), not ``FastAPI`` — the stubs can't
   narrow it because ``TestClient`` accepts any ASGI app. So ``fresh.app.state``
   trips a ``[attr-defined]`` error 18 times across 4 files.

2. ``starlette.datastructures.State`` is ``Any``-typed: it permits any
   attribute assignment, but reading ``state.ctx`` is also unchecked. Even
   if we had the right ``FastAPI`` type, mypy wouldn't know ``ctx`` is an
   ``AppContext``.

Rather than sprinkle ``# type: ignore[attr-defined]`` on every line, funnel
all of these accesses through two helpers that carry the ``type: ignore``
pragmas in ONE place and return properly-typed values for every caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain_api.context import AppContext
    from fastapi.testclient import TestClient


def get_app_ctx(client: TestClient) -> AppContext:
    """Return the ``AppContext`` stashed on ``client.app.state.ctx``.

    ``client.app`` is typed as an opaque ASGI callable by the TestClient
    stubs; we know it's a ``FastAPI`` instance because our tests always
    pass one. Re-cast to ``AppContext`` so callers reading ``ctx.token`` /
    ``ctx.tool_ctx`` / ``ctx.vault_root`` get a typed value.

    Preconditions:
        The caller must have entered ``with TestClient(app) as client:``
        so the app's lifespan has fired and populated ``app.state.ctx``.
        Reading from a TestClient that was never used as a context manager
        raises ``AttributeError`` here.
    """
    # client.app has type Callable[Scope, ...] per TestClient stubs; we know
    # it's a FastAPI with state.ctx in our fixtures. Pin the cast in one
    # place rather than in every caller.
    return client.app.state.ctx  # type: ignore[attr-defined,no-any-return]


def get_app_token(client: TestClient) -> str:
    """Return the token string from ``client.app.state.ctx.token``.

    Thin wrapper over :func:`get_app_ctx` — 90% of WS tests only need the
    token string and never touch the rest of the context. Returning
    ``AppContext.token`` directly saves every caller a ``.token`` attribute
    access.

    ``AppContext.token`` is typed ``str | None`` because production boot can
    skip token generation (no-auth test modes). In the WS tests the lifespan
    always populates it; we assert non-None here so the return type is
    ``str`` and callers can use it in f-strings without narrowing.
    """
    token = get_app_ctx(client).token
    assert token is not None, "lifespan should have populated ctx.token before WS test ran"
    return token
