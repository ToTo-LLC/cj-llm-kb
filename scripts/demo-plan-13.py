"""Plan 13 end-to-end demo — cross-instance cleanup + pre-existing test debt closure.

Walks the seven gates locked in the Plan 13 demo-gate header (D10):

    1. None-policy gate: build a ``ToolContext(config=None)``; assert
       ``brain_list_domains`` and ``brain_config_set`` BOTH raise
       ``RuntimeError`` with the lifecycle-violation wording (matching
       ``config_get``'s strict policy). Sanity-check that
       ``config_get._snapshot_config(ToolContext(config=None))`` still
       raises the same way (regression guard against weakening the
       reference policy).
    2. panel-domains store-only gate: shell out to vitest with the
       Task 2 pin test (``panel-domains-store-only.test.tsx``); assert
       exit code 0 — ``panel-domains.tsx`` reads the rendered list
       from ``useDomainsStore`` only, no parallel local state.
    3. cross-domain-gate pubsub gate: shell out to vitest with the
       Task 3 pin test (``use-cross-domain-gate-store.test.ts``);
       assert exit code 0 — two consumers of ``useCrossDomainGate()``
       reflect store mutations within 100ms (no ``page.reload()``).
    4. brain_api re-pass gate: run the 13 previously-failing tests
       (``test_errors.py`` × 8, ``test_auth_dependency.py`` × 3,
       ``test_context.py::test_get_ctx_dependency_resolves``,
       ``test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id``);
       assert exit code 0 (Task 5's ``mount_static_ui=False`` flag
       on the test app fixture clears the SPA static-mount shadowing
       confirmed by Task 4).
    5. Envelope-shape parity gate: run
       ``packages/brain_api/tests/test_envelope_shape_parity.py``;
       assert exit code 0 (the regression-pin asserting 4xx/5xx
       envelope shape parity at the middleware/route/500 layers).
    6. a11y axe-core 8 routes gate: run
       ``apps/brain_web/tests/e2e/a11y.spec.ts`` via Playwright;
       assert exit code 0 — 0 color-contrast violations on each of
       ``/chat``, ``/inbox``, ``/browse``, ``/pending``, ``/bulk``,
       ``/settings/general``, ``/settings/providers``,
       ``/settings/domains`` (Task 6's brand-skin token sweep
       cleared the 8 routes; the gate has been hard-failing since
       Plan 07 Task 25C and stays that way).
    7. a11y setup-wizard gate: run
       ``apps/brain_web/tests/e2e/setup-wizard.spec.ts``; assert
       exit code 0 — 0 color-contrast violations on the welcome
       step (the 9th of 9 violations Task 6 cleared).

Prints ``PLAN 13 DEMO OK`` on exit 0; non-zero on any gate failure.
Uses ``FakeLLMProvider``-equivalent stubs and avoids any live LLM call.

Mirrors the Plan 11 + Plan 12 demo-gate split: gate 1 is in-process
Python and runs here; gates 2-7 shell out to vitest / pytest /
Playwright with the canonical chflags + PYTHONPATH execution prefix
per lesson 341. The script's exit-0 guarantee covers all seven gates
(unlike Plan 12's runner-hint convention for gates 4-7) — every
out-of-process gate's exit code is checked.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from brain_core.tools import config_set, list_domains
from brain_core.tools.base import ToolContext
from brain_core.tools.config_get import _snapshot_config


def _gate(label: str) -> None:
    print(f"  ✓ Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  ✗ Gate {label}: {why}", file=sys.stderr)
    return 1


def _scaffold_vault(root: Path) -> None:
    """Build a v0.1 default vault: research / work / personal + ``.brain/``."""
    root.mkdir(parents=True)
    (root / ".brain").mkdir()
    for domain in ("research", "work", "personal"):
        d = root / domain
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (d / sub).mkdir(parents=True)
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")


def _ctx_no_config(root: Path) -> ToolContext:
    """Build a deliberately-broken ``ToolContext`` with ``config=None``.

    Production-shape paths post-Plan 12 D6 always supply Config; this
    fixture exercises the lifecycle-violation contract Task 1 tightened.
    """
    return ToolContext(
        vault_root=root,
        allowed_domains=("research", "work", "personal"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=None,
    )


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_PATHS = (
    _REPO_ROOT / "packages" / "brain_core" / "src",
    _REPO_ROOT / "packages" / "brain_mcp" / "src",
    _REPO_ROOT / "packages" / "brain_api" / "src",
    _REPO_ROOT / "packages" / "brain_cli" / "src",
)
_PYTHONPATH = os.pathsep.join(str(p) for p in _SRC_PATHS)
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"


def _subprocess_env() -> dict[str, str]:
    """Mirror the canonical chflags + PYTHONPATH recipe (lesson 341)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _PYTHONPATH + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


# ---------------------------------------------------------------------------
# Gate 1 — None-policy strictness (Task 1)
# ---------------------------------------------------------------------------


_LIFECYCLE_TOKEN = "lifecycle violation"
_GENERIC_NONE_TOKEN = "ctx.config to be a Config instance"


def _matches_none_policy_wording(message: str) -> bool:
    """Plan 13 Task 1 / D1: error wording is the LITERAL match.

    We accept either the exact 'lifecycle violation' phrase Task 1
    matched against (some implementations) OR the canonical
    `config_get`-prefixed wording ('requires ctx.config to be a
    Config instance, but got None') that lessons 343/353 named.
    Both paths assert the lifecycle-violation contract; the substring
    match is intentionally lenient to catch wording drift while
    still pinning the contract semantics.
    """
    return _LIFECYCLE_TOKEN in message.lower() or _GENERIC_NONE_TOKEN in message


async def _gate_1_none_policy(root: Path) -> int:
    """None-policy gate (D10 #1)."""
    ctx = _ctx_no_config(root)

    # ---- 1a — brain_list_domains raises ------------------------------
    try:
        await list_domains.handle({}, ctx)
    except RuntimeError as exc:
        if not _matches_none_policy_wording(str(exc)):
            return _fail(
                "1",
                f"brain_list_domains raised but wrong wording: {exc!r}; "
                "expected the lifecycle-violation phrasing matching "
                "config_get's strict policy.",
            )
    else:
        return _fail(
            "1",
            "brain_list_domains accepted ctx.config=None — Plan 13 Task 1 "
            "None-policy tightening did not land (silent fall-through "
            "to DEFAULT_DOMAINS regressed).",
        )

    # ---- 1b — brain_config_set raises --------------------------------
    try:
        await config_set.handle({"key": "log_llm_payloads", "value": True}, ctx)
    except RuntimeError as exc:
        if not _matches_none_policy_wording(str(exc)):
            return _fail(
                "1",
                f"brain_config_set raised but wrong wording: {exc!r}; "
                "expected the lifecycle-violation phrasing matching "
                "config_get's strict policy.",
            )
    else:
        return _fail(
            "1",
            "brain_config_set accepted ctx.config=None — Plan 13 Task 1 "
            "None-policy tightening of config_set.py:317-327 lenient "
            "branch did not land.",
        )

    # ---- 1c — config_get._snapshot_config raises (sanity) -------------
    # The plan text references ``_resolve_config`` but the actual function
    # in config_get.py is ``_snapshot_config`` (Task 7 plan-text drift,
    # captured as a Plan 14 candidate-scope item). The sanity-check is
    # that config_get's strict policy is unchanged: a None config must
    # raise RuntimeError BEFORE any model_dump traversal.
    try:
        _snapshot_config(ctx)
    except RuntimeError as exc:
        if not _matches_none_policy_wording(str(exc)):
            return _fail(
                "1",
                f"config_get._snapshot_config raised but wrong wording: {exc!r}",
            )
    else:
        return _fail(
            "1",
            "config_get._snapshot_config accepted ctx.config=None — "
            "Plan 12 D5's strict-policy reference contract regressed.",
        )

    _gate(
        "1 — None-policy: list_domains + config_set + config_get._snapshot_config "
        "all raise RuntimeError on ctx.config=None (lifecycle-violation contract)"
    )
    return 0


# ---------------------------------------------------------------------------
# Out-of-process gate runner
# ---------------------------------------------------------------------------


def _run_subprocess(label: str, cmd: list[str], *, cwd: Path | None = None) -> int:
    """Run ``cmd``; return 0 on success, 1 on failure (printing tail of output)."""
    try:
        result = subprocess.run(  # noqa: S603 — cmd is a fixed list, no shell
            cmd,
            cwd=str(cwd) if cwd else None,
            env=_subprocess_env(),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return _fail(label, f"subprocess invocation failed: {exc!r}")
    if result.returncode != 0:
        # Print the tail of stdout + stderr so failures are diagnosable.
        tail = "\n".join(
            (result.stdout or "").splitlines()[-25:]
            + (result.stderr or "").splitlines()[-15:]
        )
        return _fail(
            label,
            f"exit code {result.returncode}; tail:\n{tail}",
        )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — panel-domains store-only (Task 2 pin test)
# ---------------------------------------------------------------------------


def _gate_2_panel_domains_store_only() -> int:
    """Run vitest with the Task 2 pin test."""
    rc = _run_subprocess(
        "2",
        [
            "npx",
            "vitest",
            "run",
            "tests/unit/panel-domains-store-only.test.tsx",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "2 — panel-domains.tsx reads from useDomainsStore only "
        "(no parallel local state; Task 2 pin test green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — cross-domain-gate pubsub (Task 3 pin test)
# ---------------------------------------------------------------------------


def _gate_3_cross_domain_gate_pubsub() -> int:
    """Run vitest with the Task 3 pin test."""
    rc = _run_subprocess(
        "3",
        [
            "npx",
            "vitest",
            "run",
            "tests/unit/use-cross-domain-gate-store.test.ts",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "3 — cross-domain-gate-store cross-instance pubsub: "
        "two useCrossDomainGate() consumers reflect mutations within 100ms "
        "(Task 3 pin test green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — brain_api 13-failure re-pass (Task 5 fix)
# ---------------------------------------------------------------------------


def _gate_4_brain_api_repass() -> int:
    """Run the 13 previously-failing brain_api tests."""
    rc = _run_subprocess(
        "4",
        [
            str(_VENV_PYTHON),
            "-m",
            "pytest",
            "packages/brain_api/tests/test_errors.py",
            "packages/brain_api/tests/test_auth_dependency.py",
            "packages/brain_api/tests/test_context.py::test_get_ctx_dependency_resolves",
            "packages/brain_api/tests/test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id",
            "-q",
        ],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return rc
    _gate(
        "4 — brain_api 13-failure re-pass: test_errors × 8 + "
        "test_auth_dependency × 3 + test_context × 1 + test_ws_chat_handshake × 1 "
        "all green (Task 5 mount_static_ui=False landed)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — envelope shape parity (Task 5 regression-pin)
# ---------------------------------------------------------------------------


def _gate_5_envelope_shape_parity() -> int:
    """Run the envelope shape parity regression-pin test file."""
    rc = _run_subprocess(
        "5",
        [
            str(_VENV_PYTHON),
            "-m",
            "pytest",
            "packages/brain_api/tests/test_envelope_shape_parity.py",
            "-q",
        ],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return rc
    _gate(
        "5 — envelope shape parity: 4xx/5xx response envelope "
        "{error, message, detail} pinned at middleware + route + 500 layers "
        "(Task 5 regression-pin green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — a11y axe-core 8 routes (Task 6 token sweep)
# ---------------------------------------------------------------------------


def _gate_6_a11y_8_routes() -> int:
    """Run the Playwright a11y axe-core sweep across 8 routes."""
    rc = _run_subprocess(
        "6",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/a11y.spec.ts",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "6 — a11y axe-core: 0 color-contrast violations across "
        "/chat, /inbox, /browse, /pending, /bulk, "
        "/settings/general, /settings/providers, /settings/domains "
        "(Task 6 brand-skin token sweep cleared all 8 routes)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — a11y setup-wizard welcome step (Task 6 token sweep)
# ---------------------------------------------------------------------------


def _gate_7_a11y_setup_wizard() -> int:
    """Run the Playwright a11y axe-core sweep on the setup-wizard."""
    rc = _run_subprocess(
        "7",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/setup-wizard.spec.ts",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "7 — a11y axe-core: 0 color-contrast violations on "
        "setup-wizard welcome step (9th of 9 Task 6 violations cleared)"
    )
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def _run() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "brain"
        _scaffold_vault(root)

        rc = await _gate_1_none_policy(root)
        if rc != 0:
            return rc

    rc = _gate_2_panel_domains_store_only()
    if rc != 0:
        return rc

    rc = _gate_3_cross_domain_gate_pubsub()
    if rc != 0:
        return rc

    rc = _gate_4_brain_api_repass()
    if rc != 0:
        return rc

    rc = _gate_5_envelope_shape_parity()
    if rc != 0:
        return rc

    rc = _gate_6_a11y_8_routes()
    if rc != 0:
        return rc

    rc = _gate_7_a11y_setup_wizard()
    if rc != 0:
        return rc

    print()
    print("PLAN 13 DEMO OK")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
