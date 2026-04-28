"""Plan 12 Task 3 / D5 — regression-pin contract test for read tools.

Read tools that surface configuration-derived state (``active_domain``,
``domains``, etc.) must read it from the LIVE ``ctx.config`` rather than
constructing a fresh ``Config()`` snapshot. The seed offender was
``brain_core.tools.config_get`` (Plan 11 lesson 343 anti-pattern category):
the tool returned schema defaults instead of the actual session state, so
the Settings UI rendered stale values regardless of what was loaded.

This contract test parametrizes over a STATIC list of read tools
(``_READ_TOOLS_THAT_THREAD_CTX_CONFIG``). For each entry we:

  1. Build a sentinel-bearing ``Config(active_domain="sentinel-domain", ...)``.
  2. Construct a ``ToolContext`` with that Config attached.
  3. Invoke the tool's ``handle`` with the entry's prepared arguments.
  4. Assert the response payload reflects the SENTINEL value, not the schema
     default ``"research"`` — proving the tool actually read ``ctx.config``.

The list is intentionally STATIC (not introspection-driven via
``__init__.py`` walking — that approach rotted in earlier plans). When a
new read tool is added that surfaces config-derived state, the author MUST
add it to this list explicitly; otherwise the new tool can silently
regress to a fresh-Config snapshot without the test catching it.

Sentinel choice: ``"sentinel-domain"`` is a memorable string that is NOT
a Config default, NOT a member of ``DEFAULT_DOMAINS``, and trivially
greppable in test output. A future test reader who sees this string in an
assertion failure knows it isn't an accidental default.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from brain_core.config.schema import Config
from brain_core.tools import config_get, list_domains
from brain_core.tools.base import ToolContext, ToolResult

_SENTINEL_DOMAIN = "sentinel-domain"


@dataclass(frozen=True)
class _ReadToolCase:
    """One row of the contract-test parametrize table.

    Attributes:
        name: human-readable label for pytest IDs (matches the tool's
            ``NAME`` constant — useful in test output).
        handle: the async ``handle`` callable from the tool module.
        arguments: the dict to pass as the tool's ``arguments`` parameter.
            Each tool gets the minimal valid input that exercises the
            config-reading code path.
        sentinel_assertion: a callable taking the tool's ``ToolResult.data``
            and asserting the sentinel surfaced in the response. Returns
            None on success; raises ``AssertionError`` on failure.
    """

    name: str
    handle: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    arguments: dict[str, Any]
    sentinel_assertion: Callable[[dict[str, Any]], None]


def _assert_config_get_active_domain(data: dict[str, Any]) -> None:
    """``brain_config_get`` with key=``active_domain`` returns the sentinel."""
    assert data["key"] == "active_domain"
    assert data["value"] == _SENTINEL_DOMAIN, (
        f"brain_config_get returned {data['value']!r} — expected the sentinel "
        f"{_SENTINEL_DOMAIN!r}. The tool is reading a fresh Config() snapshot "
        f"instead of ctx.config; see Plan 12 Task 3 / D5."
    )


def _assert_list_domains_active_domain(data: dict[str, Any]) -> None:
    """``brain_list_domains`` surfaces ``ctx.config.active_domain`` in
    ``data["active_domain"]`` (Plan 11 Task 6).
    """
    assert data["active_domain"] == _SENTINEL_DOMAIN, (
        f"brain_list_domains returned active_domain={data['active_domain']!r} — "
        f"expected the sentinel {_SENTINEL_DOMAIN!r}. The tool is falling back "
        f"to a default instead of reading ctx.config.active_domain."
    )
    # Also sanity-check that the sentinel domain shows up in the union
    # (configured side) — this proves ``Config.domains`` was threaded too.
    assert _SENTINEL_DOMAIN in data["domains"], (
        f"brain_list_domains.domains={data['domains']!r} did not include the "
        f"sentinel domain {_SENTINEL_DOMAIN!r} — the tool isn't reading "
        f"ctx.config.domains."
    )


# Static parametrize list — the gate. Adding a new read tool that surfaces
# config-derived state requires an explicit entry here. Do NOT auto-discover
# this via __init__.py introspection (rotted in earlier plans).
_READ_TOOLS_THAT_THREAD_CTX_CONFIG: tuple[_ReadToolCase, ...] = (
    _ReadToolCase(
        name=config_get.NAME,
        handle=config_get.handle,
        arguments={"key": "active_domain"},
        sentinel_assertion=_assert_config_get_active_domain,
    ),
    _ReadToolCase(
        name=list_domains.NAME,
        handle=list_domains.handle,
        arguments={},
        sentinel_assertion=_assert_list_domains_active_domain,
    ),
)


def _mk_ctx(vault: Path, config: Config) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research", "work", "personal", _SENTINEL_DOMAIN),
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


@pytest.mark.parametrize(
    "case",
    _READ_TOOLS_THAT_THREAD_CTX_CONFIG,
    ids=lambda c: c.name,
)
async def test_read_tool_threads_ctx_config(case: _ReadToolCase, tmp_path: Path) -> None:
    """Contract: every read tool in the static list reads its config-derived
    response data from ``ctx.config``, NOT from a fresh ``Config()`` snapshot.

    Building a sentinel ``Config(active_domain=...)`` and asserting the
    sentinel propagates into the response would FAIL if any tool reverted
    to ``Config()``-snapshot reads — which is the regression we're pinning.
    """
    cfg = Config(
        active_domain=_SENTINEL_DOMAIN,
        domains=["research", "work", "personal", _SENTINEL_DOMAIN],
    )
    ctx = _mk_ctx(tmp_path, cfg)

    result = await case.handle(case.arguments, ctx)
    assert isinstance(result, ToolResult), (
        f"{case.name}.handle returned {type(result).__name__}, not ToolResult"
    )
    assert result.data is not None, f"{case.name}.handle returned ToolResult with no data"

    case.sentinel_assertion(result.data)


def test_static_list_is_explicit_and_handles_are_async() -> None:
    """Sanity check on the parametrize table itself: every entry's ``handle``
    is an async function and every ``name`` matches the tool's ``NAME``
    constant. Catches typos / drift in the static list before the
    parametrize-driven test runs.
    """
    seen_names: set[str] = set()
    for case in _READ_TOOLS_THAT_THREAD_CTX_CONFIG:
        assert case.name not in seen_names, f"duplicate entry in list: {case.name}"
        seen_names.add(case.name)
        assert inspect.iscoroutinefunction(case.handle), (
            f"{case.name}.handle is not an async function — the contract test "
            f"awaits it, so a sync handler would silently pass."
        )
