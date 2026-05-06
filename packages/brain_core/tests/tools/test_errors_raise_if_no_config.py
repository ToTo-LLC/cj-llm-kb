"""Pin tests for ``brain_core.tools._errors.raise_if_no_config``.

Plan 15 Task 8 / D7: the canonical ``ctx.config is None`` raise was
duplicated across 3 brain_core tool sites (``config_get``,
``list_domains``, ``config_set``). The shared helper unifies the
wording and centralizes maintenance. These tests:

1. Pin the helper's behavior — raises ``RuntimeError`` with the
   canonical wording when ``ctx.config is None``, no-ops when
   ``ctx.config`` is a real ``Config``, and preserves the
   ``tool_name`` token verbatim in the message.
2. Pin caller integration — each of the 3 callers actually USES
   the helper (not its own inline raise). Constructed by feeding
   each caller a ``ctx`` with ``config=None`` and asserting the
   tool-name token appears in the resulting ``RuntimeError``
   message.

The caller-integration tests overlap with each tool's own
``test_*_raises_when_ctx_config_none``-style smoke; this file is
deliberately the canonical pin for the *shared* behavior. If a
caller drifts back to a private inline raise (or rewords the
message), the tool-name-token assertion here fails and the regression
is named in the failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools._errors import raise_if_no_config
from brain_core.tools.base import ToolContext


def _mk_ctx(vault: Path, *, config: Config | None) -> ToolContext:
    """Build a ToolContext used by every test in this module."""
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
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


# ---------------------------------------------------------------------------
# Helper unit tests — wording, raise-vs-no-raise, tool-name interpolation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_name",
    ["brain_config_get", "brain_list_domains", "brain_config_set"],
)
def test_raises_runtime_error_when_config_is_none(tmp_path: Path, tool_name: str) -> None:
    """All three callers' tool names produce an actionable RuntimeError.

    Match assertion uses ``r"requires ctx\\.config"`` — escaped dot so the
    regex matches the literal string from the canonical message.
    """
    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError, match=r"requires ctx\.config to be a Config"):
        raise_if_no_config(ctx, tool_name)


@pytest.mark.parametrize(
    "tool_name",
    ["brain_config_get", "brain_list_domains", "brain_config_set"],
)
def test_message_carries_tool_name_token(tmp_path: Path, tool_name: str) -> None:
    """The leading ``{tool_name}`` token is interpolated into the message.

    Without this the LLM receives an anonymous error and can't tell which
    tool tripped the guard.
    """
    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError) as exc_info:
        raise_if_no_config(ctx, tool_name)
    assert str(exc_info.value).startswith(f"{tool_name} requires ctx.config")


def test_no_raise_when_config_is_real_config(tmp_path: Path) -> None:
    """Helper is a no-op when ``ctx.config`` is a real Config instance.

    The non-None path is exercised here so a future change that
    accidentally raises unconditionally is caught.
    """
    ctx = _mk_ctx(tmp_path, config=Config())
    # Should not raise — assertion is the absence of an exception.
    raise_if_no_config(ctx, "brain_config_get")


def test_canonical_wording_preserved_verbatim(tmp_path: Path) -> None:
    """Pin the canonical message body verbatim (modulo the tool-name token).

    Plan 15 Task 8: the wording is sourced from ``brain_config_get``
    (Plan 12 Task 3 / D5). If a future change rewords the message,
    this assertion fires and forces an explicit decision rather than a
    silent drift across the 3 callers.
    """
    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError) as exc_info:
        raise_if_no_config(ctx, "brain_config_get")
    assert str(exc_info.value) == (
        "brain_config_get requires ctx.config to be a Config instance, but "
        "got None. The brain_api lifespan (build_app_context) and brain_mcp "
        "_build_ctx are responsible for threading the loaded Config through "
        "ToolContext; a None config here means the wrapper hasn't wired it in. "
        "Falling back to Config() defaults would make Settings reads lie about "
        "the resolved configuration."
    )


# ---------------------------------------------------------------------------
# Caller integration tests — each public tool actually uses the helper.
# ---------------------------------------------------------------------------
#
# These three tests pin that the 3 callers route through the shared helper.
# They are deliberately minimal: each one constructs a ctx with
# ``config=None`` and invokes the public ``handle`` (or the equivalent
# private accessor for list_domains.handle's ``_configured_slugs``/
# ``_active_domain`` seam). The assertion is the same shape as the helper
# unit tests above — same tool-name token in the message — so a caller
# that re-introduces a private inline raise with different wording is
# caught.


async def test_config_get_uses_helper(tmp_path: Path) -> None:
    """``brain_config_get`` raises via the shared helper when config is None."""
    from brain_core.tools.config_get import handle as config_get_handle

    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError) as exc_info:
        await config_get_handle({"key": "active_domain"}, ctx)
    msg = str(exc_info.value)
    assert msg.startswith("brain_config_get requires ctx.config")
    assert "Falling back to Config() defaults" in msg


async def test_list_domains_uses_helper(tmp_path: Path) -> None:
    """``brain_list_domains`` raises via the shared helper when config is None.

    The helper is invoked twice in the call path (``_configured_slugs``
    + ``_active_domain``); the first one wins, so the test only sees one
    RuntimeError.
    """
    from brain_core.tools.list_domains import handle as list_domains_handle

    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError) as exc_info:
        await list_domains_handle({}, ctx)
    msg = str(exc_info.value)
    assert msg.startswith("brain_list_domains requires ctx.config")
    assert "Falling back to Config() defaults" in msg


async def test_config_set_uses_helper(tmp_path: Path) -> None:
    """``brain_config_set`` raises via the shared helper when config is None.

    Uses an allowlisted, persisted key (``log_llm_payloads``) so the
    refusal branches (secret-substring, non-settable, non-persisted) all
    pass before reaching the cfg-None check that the helper now owns.
    """
    from brain_core.tools.config_set import handle as config_set_handle

    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError) as exc_info:
        await config_set_handle({"key": "log_llm_payloads", "value": True}, ctx)
    msg = str(exc_info.value)
    assert msg.startswith("brain_config_set requires ctx.config")
    assert "Falling back to Config() defaults" in msg
