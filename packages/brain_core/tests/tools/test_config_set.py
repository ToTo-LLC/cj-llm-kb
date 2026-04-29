"""Smoke test for brain_core.tools.config_set — ToolResult shape + refusals.

Covers: secret-like refusal, non-settable-key refusal, and a successful
in-memory "updated" write on an allowlisted key. brain_mcp's existing
test_tool_config_get_set.py covers the transport wrapper behavior.

Plan 13 Task 1 / D1: ``brain_config_set`` now raises ``RuntimeError`` when
``ctx.config is None`` for persisted keys. Refusal-path tests (secret-like,
non-allowlisted, wrong-shape domain-override) refuse BEFORE the cfg-None
check, so they remain valid without a real Config; persistence-path tests
seed a real ``Config`` to match the production shape (both wrappers thread
Config through post-Plan 12 D6).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_set import _SETTABLE_KEYS, NAME, handle


def _mk_ctx(vault: Path, *, config: Config | None = None) -> ToolContext:
    """Build a ToolContext for config_set tests.

    ``config`` defaults to ``None`` for backwards compatibility with refusal-path
    tests (secret-like, non-allowlisted) that refuse BEFORE the cfg-None check
    in ``handle``. Persistence-path tests pass an explicit ``Config(...)``.
    """
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


def test_name() -> None:
    assert NAME == "brain_config_set"


def test_settable_keys_match_plan_07_task_4() -> None:
    """Allowlist is deliberately narrow.

    Plan 04 baseline: ``budget.daily_usd`` + ``log_llm_payloads``.
    Plan 07 Task 1: adds the 5 ``autonomous.<category>`` flags.
    Plan 07 Task 2: adds the 3 per-mode ``{mode}_model`` overrides.
    Plan 07 Task 4: adds ``domain_order`` + 2 ``budget.override_*`` fields.
    Issue #23: adds 3 ``handlers.*`` per-handler tunables.
    Plan 11 Task 7: adds ``privacy_railed`` (whole-list write); the
    open-set ``domain_overrides.<slug>.<field>`` wildcard is matched
    dynamically by ``_is_settable_domain_override_key`` and is NOT in
    this static set.
    Plan 12 D2: adds ``active_domain`` (policy inversion — Settings UI
    is the new persistence path; Plan 10's cross-field validator
    enforces "must be in ``Config.domains``").
    Plan 12 D8 / Task 9: adds ``cross_domain_warning_acknowledged``
    (per-vault acknowledgment for the cross-domain confirmation modal;
    bound by both the modal's "Don't show this again" checkbox and the
    Settings → Domains "Show cross-domain warning" toggle).
    """
    assert (
        frozenset(
            {
                "active_domain",
                "budget.daily_usd",
                "log_llm_payloads",
                "autonomous.ingest",
                "autonomous.entities",
                "autonomous.concepts",
                "autonomous.index_rewrites",
                "autonomous.draft",
                "ask_model",
                "brainstorm_model",
                "draft_model",
                "domain_order",
                "budget.override_until",
                "budget.override_delta_usd",
                "handlers.url.timeout_seconds",
                "handlers.tweet.timeout_seconds",
                "handlers.pdf.min_chars",
                "privacy_railed",
                "cross_domain_warning_acknowledged",
            }
        )
        == _SETTABLE_KEYS
    )


def test_settable_keys_all_resolve_to_a_real_schema_field() -> None:
    """Issue #10 regression test — drift watchdog for ``_SETTABLE_KEYS``.

    For every dotted key in the allowlist, walk the path against the live
    Config / ChatSessionConfig pydantic models and assert the leaf is a
    real ``model_fields`` entry. Catches the kind of drift that bit Plan
    04 (commit ``3b107cd``): an allowlist entry that points at a renamed
    or removed schema field is silently allowed past the security check
    and only fails at apply time when persistence finally lands.

    Exceptions are documented inline below — they're keys whose
    persistence path is intentionally deferred (``domain_order`` waits on
    Plan 07 Task 5) or which live on a non-Config schema (the
    ``{ask,brainstorm,draft}_model`` overrides live on ChatSessionConfig
    because they're per-session, not global).
    """
    from brain_core.chat.types import ChatSessionConfig
    from brain_core.config.schema import Config

    # Keys that legitimately don't resolve against Config — see test
    # docstring. Adding to this set requires a comment justifying why the
    # key is allowlisted but not on Config.
    known_not_on_config = {
        # Per-session chat-mode model overrides — live on
        # ``ChatSessionConfig.{ask,brainstorm,draft}_model``, not on the
        # global Config. brain_config_set surfaces them so the Settings
        # UI can write them, but they're applied per-session at chat
        # construction time, not persisted on Config.
        "ask_model": ("ChatSessionConfig", "ask_model"),
        "brainstorm_model": ("ChatSessionConfig", "brainstorm_model"),
        "draft_model": ("ChatSessionConfig", "draft_model"),
        # Plan 07 Task 4: ``domain_order`` is documented as a list[str] of
        # the user's preferred sidebar order; the persistence path is
        # explicitly deferred to Plan 07 Task 5 (see create_domain.py:108).
        # The allowlist entry exists so the Settings page can call
        # brain_config_set on it without raising; the in-memory write is
        # currently a no-op acknowledgement. Resolves to Config when Task
        # 5 lands; until then this exception keeps the drift watchdog
        # honest about WHY it's allowlisted.
        "domain_order": ("PENDING", "Config.domain_order (Plan 07 Task 5)"),
    }

    def _resolve(model: type, dotted: str) -> object:
        """Walk a dotted path against pydantic model_fields. Returns the
        leaf field info or raises KeyError with the failing segment."""
        parts = dotted.split(".")
        current_model: type = model
        for i, part in enumerate(parts):
            fields = getattr(current_model, "model_fields", None)
            if fields is None or part not in fields:
                raise KeyError(
                    f"key {dotted!r} does not resolve: "
                    f"segment {parts[i]!r} not in {current_model.__name__}.model_fields"
                )
            field_info = fields[part]
            if i == len(parts) - 1:
                return field_info
            # Descend into nested model.
            annotation = field_info.annotation
            if not isinstance(annotation, type):
                raise KeyError(
                    f"key {dotted!r}: cannot descend through non-class "
                    f"annotation {annotation!r} at segment {part!r}"
                )
            current_model = annotation
        return None  # pragma: no cover — loop always returns

    unresolved: list[str] = []
    for key in sorted(_SETTABLE_KEYS):
        if key in known_not_on_config:
            continue
        try:
            _resolve(Config, key)
        except KeyError as exc:
            unresolved.append(f"{key!r} → {exc}")

    assert not unresolved, (
        "Some keys in _SETTABLE_KEYS no longer resolve to real schema "
        "fields. Add the field to Config (or document the exception in "
        "known_not_on_config with a justification):\n  " + "\n  ".join(unresolved)
    )

    # Sanity-check the exceptions still resolve where they're documented
    # to live (so the exception itself doesn't rot).
    for key, (where, _explanation) in known_not_on_config.items():
        if where == "ChatSessionConfig":
            assert key in ChatSessionConfig.model_fields, (
                f"exception for {key!r} claims it lives on ChatSessionConfig "
                f"but the field is no longer there"
            )
        # PENDING entries don't resolve anywhere yet — that's the point.


async def test_allows_handler_config_keys(tmp_path: Path) -> None:
    """Issue #23: ``handlers.<handler>.<field>`` paths flow through the
    allowlist + secret-substring check without raising. Plan 13 Task 1 /
    D1: persisted keys require a real ``Config`` on the context; the
    handler keys round-trip through ``persist_config_or_revert``.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, config=cfg)
    for key, value in (
        ("handlers.url.timeout_seconds", 60.0),
        ("handlers.tweet.timeout_seconds", 5.0),
        ("handlers.pdf.min_chars", 50),
    ):
        result = await handle({"key": key, "value": value}, ctx)
        assert result.data is not None
        assert result.data["status"] == "updated"
        assert result.data["key"] == key
        assert result.data["value"] == value


async def test_allows_autonomous_flag(tmp_path: Path) -> None:
    """Each new autonomy key accepts a bool without secret-refusal or allowlist-refusal.

    Plan 13 Task 1 / D1: persisted keys require a real ``Config`` on the
    context (production shape post-Plan 12 D6).
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, config=cfg)
    for key in (
        "autonomous.ingest",
        "autonomous.entities",
        "autonomous.concepts",
        "autonomous.index_rewrites",
        "autonomous.draft",
    ):
        result = await handle({"key": key, "value": True}, ctx)
        assert isinstance(result, ToolResult)
        assert result.data is not None
        assert result.data["status"] == "updated"
        assert result.data["value"] is True


async def test_refuses_secret_like_key(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="secret-like"):
        await handle({"key": "llm.api_key", "value": "nope"}, _mk_ctx(tmp_path))


async def test_refuses_non_allowlisted_vault_path(tmp_path: Path) -> None:
    """``vault_path`` is permanently non-settable via MCP — clients must
    not reroot the vault from a tool call (see ``_SETTABLE_KEYS`` comment).
    Was previously ``active_domain``; Plan 12 D2 added ``active_domain``
    to the allowlist, so this test was retargeted to the next-best
    permanently-excluded Config field.
    """
    with pytest.raises(PermissionError, match="not settable"):
        await handle({"key": "vault_path", "value": "/tmp/elsewhere"}, _mk_ctx(tmp_path))


async def test_domain_override_keys_pass_allowlist_via_wildcard(tmp_path: Path) -> None:
    """Plan 11 Task 7: ``domain_overrides.<slug>.<field>`` is a wildcard
    pattern, not a static ``_SETTABLE_KEYS`` entry. Each leaf field on
    DomainOverride should flow through the allowlist gate without
    raising. The actual mutation behavior is covered in
    ``test_config_set_persists.py``; this test only proves the security
    gate accepts the open-set shape.

    Plan 13 Task 1 / D1: a real ``Config`` is now required for the
    persistence branch. ``hobby`` must be in ``Config.domains`` because
    ``_apply_domain_override`` enforces slug-membership.
    """
    cfg = Config(domains=["research", "personal", "hobby"])
    ctx = _mk_ctx(tmp_path, config=cfg)
    for field in ("classify_model", "default_model", "temperature", "max_output_tokens"):
        result = await handle(
            {"key": f"domain_overrides.hobby.{field}", "value": None},
            ctx,
        )
        assert result.data is not None
        assert result.data["status"] == "updated"


async def test_domain_override_rejects_unknown_field(tmp_path: Path) -> None:
    """An unknown leaf field doesn't match the wildcard and is rejected
    at the static-allowlist gate. Without the third-segment field check
    in ``_is_settable_domain_override_key`` an attacker could write
    ``domain_overrides.x.api_key`` and bypass the secret-substring
    check (the substring check would catch ``api_key`` first, but the
    field-allowlist is the real defense)."""
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "domain_overrides.hobby.unknown_field", "value": "x"},
            _mk_ctx(tmp_path),
        )


async def test_domain_override_rejects_wrong_segment_count(tmp_path: Path) -> None:
    """Two-segment ``domain_overrides.hobby`` and four-segment
    ``domain_overrides.hobby.foo.bar`` both fail the wildcard shape
    check and end up at the static-allowlist gate.
    """
    with pytest.raises(PermissionError, match="not settable"):
        await handle({"key": "domain_overrides.hobby", "value": {}}, _mk_ctx(tmp_path))
    with pytest.raises(PermissionError, match="not settable"):
        await handle(
            {"key": "domain_overrides.hobby.foo.bar", "value": "x"},
            _mk_ctx(tmp_path),
        )


async def test_allows_budget_daily_usd(tmp_path: Path) -> None:
    """Plan 13 Task 1 / D1: persisted keys (``budget.daily_usd`` is a
    real Config field) require a real ``Config`` on the context; the
    response carries ``persisted=True`` once the round-trip lands on
    disk via ``persist_config_or_revert``.
    """
    cfg = Config()
    ctx = _mk_ctx(tmp_path, config=cfg)
    result = await handle(
        {"key": "budget.daily_usd", "value": 5.0},
        ctx,
    )

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "updated"
    assert result.data["persisted"] is True
    assert result.data["value"] == 5.0


async def test_raises_when_ctx_config_none(tmp_path: Path) -> None:
    """Plan 13 Task 1 / D1: ``brain_config_set`` raises ``RuntimeError``
    when ``ctx.config is None`` for persisted keys. Mirrors
    ``brain_config_get``'s strict policy (Plan 12 Task 3) — a None config
    is a lifecycle violation, not a fallback case. Pre-Plan-13 this branch
    no-op'd with ``persisted=False``, which was a unit-test escape hatch
    from before brain_api + brain_mcp wired Config; production-shape
    integration tests post-Plan 12 D6 always supply Config.
    """
    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError, match=r"ctx\.config to be a Config"):
        await handle({"key": "log_llm_payloads", "value": True}, ctx)


def test_non_persisted_keys_match_known_not_on_config_watchdog() -> None:
    """The production ``_NON_PERSISTED_KEYS`` set must match the test's
    ``known_not_on_config`` drift watchdog set, otherwise the two will
    diverge silently as Plan 11+ adds new keys.

    Without this assertion, a future addition to the production allowlist
    that should also be a non-persisted key (or vice versa) would slip
    past review — the schema-vs-allowlist watchdog would still pass
    because the test-side set acts as an allowlist of known exceptions,
    and production code would still run, but the two sets would drift
    until the next code-quality pass caught them.
    """
    from brain_core.tools.config_set import _NON_PERSISTED_KEYS

    # Re-derive the test-side keys by running the same known_not_on_config
    # logic but stripping the per-key explanation tuples. The test-side
    # set is defined inline inside ``test_settable_keys_all_resolve_to_a_real_schema_field``
    # — keeping the watchdog source-of-truth here means the two stay
    # mechanically tied even if either side moves.
    known_not_on_config = {
        "ask_model",
        "brainstorm_model",
        "draft_model",
        "domain_order",
    }
    assert known_not_on_config == _NON_PERSISTED_KEYS, (
        "_NON_PERSISTED_KEYS (production) and known_not_on_config (test) drifted: "
        f"in production not test: {_NON_PERSISTED_KEYS - known_not_on_config}; "
        f"in test not production: {known_not_on_config - _NON_PERSISTED_KEYS}"
    )
