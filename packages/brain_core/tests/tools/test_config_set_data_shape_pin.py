"""Plan 19 T4.4 — pin the data-shape key set of brain_config_set's ToolResult.

The Plan 18 T2 audit surfaced a cosmetic-severity DRIFT row on the
``brain_config_set`` handler: backend emits
``{status, key, value, persisted, note}`` (across BOTH the
non-persisted session-scoped branch at config_set.py:832-845 and the
persisted Config-field branch at config_set.py:901-910 — same 5 keys
in both branches, only the values differ — ``persisted=False`` vs
``True``, branch-specific ``note`` text) but the TS wrapper in
``apps/brain_web/src/lib/api/tools.ts`` declared ``{key, value}`` only.
Plan 19 T4.4 widened the TS wrapper to a named
``ConfigSetData = {status, key, value, persisted, note}`` interface
shared by the 7 ``configSet``-routed wrappers; this pin locks the
backend's data shape so a future refactor cannot silently drop /
rename / add a key without the TS side lighting up RED first.

Per-branch coverage: one pin per branch ensures a future refactor
that drifts ONE branch without the other is also caught (the audit
snapshot pinned both share the same key set; this test enforces the
invariant going forward). Mirrors the Plan 18 T3 pin pattern.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext
from brain_core.tools.config_set import handle

_EXPECTED_KEYS: frozenset[str] = frozenset(
    {"status", "key", "value", "persisted", "note"}
)


def _mk_ctx(vault: Path, cfg: Config | None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research", "personal"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=cfg,
    )


async def test_config_set_data_keys_pin_persisted_branch(tmp_path: Path) -> None:
    """Plan 19 T4.4: persisted Config-field branch emits exactly
    ``{status, key, value, persisted, note}``.

    Exercises config_set.py:901-910 (the ``return ToolResult(...)`` after
    ``persist_config_or_revert`` for a real Config field).
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "log_llm_payloads", "value": True}, ctx)

    assert result.data is not None
    assert set(result.data.keys()) == _EXPECTED_KEYS
    # Sanity-check branch-discriminator values so a swap of branches
    # (which would still pass the key-set check) is also caught.
    assert result.data["persisted"] is True
    assert result.data["status"] == "updated"
    assert result.data["key"] == "log_llm_payloads"
    assert result.data["value"] is True


async def test_config_set_data_keys_pin_non_persisted_branch(tmp_path: Path) -> None:
    """Plan 19 T4.4: non-persisted session-scoped branch emits exactly
    ``{status, key, value, persisted, note}``.

    Exercises config_set.py:832-845 (the ``return ToolResult(...)`` for
    a key in ``_NON_PERSISTED_KEYS`` — chat-mode model overrides /
    domain_order). The two branches share the same key set today; this
    pin enforces the invariant so a future refactor that diverges them
    fails RED.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "ask_model", "value": "claude-haiku-5"}, ctx)

    assert result.data is not None
    assert set(result.data.keys()) == _EXPECTED_KEYS
    # Sanity-check the branch-discriminator value.
    assert result.data["persisted"] is False
    assert result.data["status"] == "updated"
    assert result.data["key"] == "ask_model"
    assert result.data["value"] == "claude-haiku-5"
