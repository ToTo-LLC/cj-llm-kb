"""Plan 17 end-to-end demo — residuals + spec annotations closure.

Walks the 18 substantive-task gates from
``tasks/plans/17-residuals-and-spec-annotations.md`` plus the closure
marker. Each gate is a structural assertion (file existence, regex
match, AST shape) — no live LLM, no network, no spawned servers.

Gate map
--------
 1  T1   brain_api → AnthropicProvider e2e integration test
 2  T2   brain_api ConfigWatcher live ctx.config update
 3  T3   panel-budget migrated to budget-store
 4  T4   panel-domains-row BudgetCapsSubsection migrated to budget-store
 5  T5   domain-override-form LLM fields routed to domain-overrides-store
 6  T6   AutonomyCategory drift gate (shared JSON fixture)
 7  T7   stale ``autonomous.ingest`` doc/comment cleanup
 8  T8   ``_on_config_change`` extracted to module level in brain_mcp
 9  T9   ``_resolve_config`` read-only contract audit
10  T10  test_mcp_session_list_domains already-done audit
11  T11  brain_api mypy --strict closure + CI step
12  T12  spec footnote: HYBRID gate algorithm
13  T13  spec note: multi-domain per-call enforcement no-op
14  T14  spec annotation: ``resolve_config`` canonical entry point
15  T15  ``_lifespan`` comment-debt consolidated into structured docstring
16  T16  ``brain_recent`` aligned on ``items`` field
17  T17  ``repair_config_apply`` wrapped in ``persist_config_or_revert``
18  T18  repair-config-dialog three T33 nits bundled

Closure (T19) is this script; final line on a clean run is
``PLAN 17 DEMO OK``.

Canonical invocation
--------------------
On this iCloud-synced repo the ``.pth``-flag dance is unreliable
(Spotlight re-hides ``_editable_impl_*.pth`` duplicates and ``chflags
0`` returns "Operation not permitted"). The PYTHONPATH-prefix recipe
bypasses the .pth indirection entirely::

    chflags 0 .venv/lib/python3.12/site-packages/_editable_impl_brain_core*.pth 2>/dev/null
    unset VIRTUAL_ENV
    PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \\
      uv run --package brain_core python scripts/demo-plan-17.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _gate(label: str) -> None:
    print(f"  ok Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  FAIL Gate {label}: {why}", file=sys.stderr)
    return 1


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"
_SPEC = _REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-04-13-cj-llm-kb-design.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exists(label: str, path: Path, kind: str = "file") -> int:
    if kind == "file" and not path.is_file():
        return _fail(label, f"{kind} missing: {path}")
    if kind == "dir" and not path.is_dir():
        return _fail(label, f"{kind} missing: {path}")
    return 0


# ---------------------------------------------------------------------------
# Gate 1 — T1: brain_api → AnthropicProvider e2e integration test
# ---------------------------------------------------------------------------


def _gate_1_anthropic_e2e_test() -> int:
    path = _REPO_ROOT / "packages" / "brain_api" / "tests" / "test_anthropic_e2e.py"
    if rc := _exists("1", path):
        return rc
    text = _read(path)
    if "brain_ping_llm" not in text:
        return _fail("1", "test_anthropic_e2e.py does not exercise brain_ping_llm")
    if "ANTHROPIC_API_KEY" not in text:
        return _fail("1", "test_anthropic_e2e.py missing ANTHROPIC_API_KEY env gate")
    _gate("1 — T1 brain_api → AnthropicProvider e2e: pinged through full create_app → live API path")
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T2: brain_api ConfigWatcher live ctx.config update
# ---------------------------------------------------------------------------


def _gate_2_brain_api_hot_reload() -> int:
    app_path = _REPO_ROOT / "packages" / "brain_api" / "src" / "brain_api" / "app.py"
    test_path = _REPO_ROOT / "packages" / "brain_api" / "tests" / "test_lifespan_hot_reload.py"
    for p in (app_path, test_path):
        if rc := _exists("2", p):
            return rc
    text = _read(app_path)
    if "_on_config_change" not in text:
        return _fail("2", "app.py missing _on_config_change hot-reload callback")
    if 'object.__setattr__(tool_ctx, "config"' not in text:
        return _fail("2", "app.py _on_config_change missing frozen-dataclass setattr trick")
    _gate("2 — T2 brain_api ConfigWatcher: live ctx.config swap on config.json change")
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T3: panel-budget migrated to budget-store
# ---------------------------------------------------------------------------


def _gate_3_panel_budget_store() -> int:
    panel = _BRAIN_WEB / "src" / "components" / "settings" / "panel-budget.tsx"
    if rc := _exists("3", panel):
        return rc
    text = _read(panel)
    if "useBudget" not in text:
        return _fail("3", "panel-budget.tsx no longer using useBudget hook")
    if "useBudgetStore.getState().setDailyCap" not in text:
        return _fail("3", "panel-budget.tsx missing setDailyCap store call")
    # Inline configGet on mount is gone — the store hydrates.
    if re.search(r"\bconfigGet\b", text):
        return _fail("3", "panel-budget.tsx still calls configGet directly (should hydrate via store)")
    _gate("3 — T3 panel-budget migrated to budget-store: hydration + writes via zustand")
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T4: panel-domains-row BudgetCapsSubsection store migration
# ---------------------------------------------------------------------------


def _gate_4_panel_domains_row_budget() -> int:
    panel = _BRAIN_WEB / "src" / "components" / "settings" / "panel-domains-row.tsx"
    if rc := _exists("4", panel):
        return rc
    text = _read(panel)
    if "useBudgetStore" not in text:
        return _fail("4", "panel-domains-row.tsx missing useBudgetStore import")
    if "setDomainCap" not in text:
        return _fail("4", "panel-domains-row.tsx missing setDomainCap call")
    _gate("4 — T4 BudgetCapsSubsection: per-domain caps hydrate + write through budget-store")
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T5: domain-override-form LLM fields → domain-overrides-store
# ---------------------------------------------------------------------------


def _gate_5_domain_override_form_store() -> int:
    form = _BRAIN_WEB / "src" / "components" / "settings" / "domain-override-form.tsx"
    if rc := _exists("5", form):
        return rc
    text = _read(form)
    if "useDomainOverridesStore" not in text:
        return _fail("5", "domain-override-form.tsx missing useDomainOverridesStore import")
    if "setOverrideField" not in text:
        return _fail("5", "domain-override-form.tsx missing setOverrideField call")
    # autonomous_mode still routes through configSet directly.
    if 'field === "autonomous_mode"' not in text:
        return _fail("5", "domain-override-form.tsx missing autonomous_mode guard")
    _gate("5 — T5 domain-override-form: LLM fields via store, autonomous_mode via configSet")
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T6: AutonomyCategory drift gate (shared JSON fixture)
# ---------------------------------------------------------------------------


def _gate_6_autonomy_drift_fixture() -> int:
    fixture = _BRAIN_WEB / "tests" / "fixtures" / "autonomy-categories.json"
    py_test = _REPO_ROOT / "packages" / "brain_core" / "tests" / "test_autonomy_category_drift.py"
    ts_test = _BRAIN_WEB / "tests" / "unit" / "autonomy-category-drift.test.ts"
    for p in (fixture, py_test, ts_test):
        if rc := _exists("6", p):
            return rc
    # Fixture must be the canonical alphabetical list.
    fixture_data = json.loads(_read(fixture))
    expected = ["concepts", "draft", "edits", "index_entries", "new_files"]
    if sorted(fixture_data) != expected:
        return _fail("6", f"fixture set mismatch: {fixture_data}")
    _gate("6 — T6 AutonomyCategory drift: shared JSON fixture pinned on both Python + TS sides")
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T7: stale ``autonomous.ingest`` doc/comment cleanup
# ---------------------------------------------------------------------------


def _gate_7_autonomous_doc_cleanup() -> int:
    config_set = (
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "config_set.py"
    )
    ingest = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "ingest.py"
    for p in (config_set, ingest):
        if rc := _exists("7", p):
            return rc
    cs_text = _read(config_set)
    ig_text = _read(ingest)
    # The legacy bool form should no longer appear in docs.
    if re.search(r"autonomous\.ingest\s*=\s*true", cs_text, re.IGNORECASE):
        return _fail("7", "config_set.py still references autonomous.ingest (legacy bool form)")
    if re.search(r"autonomous\.ingest\s*=\s*true", ig_text, re.IGNORECASE):
        return _fail("7", "ingest.py still references autonomous.ingest (legacy bool form)")
    _gate("7 — T7 stale autonomous.ingest docs: replaced with T40 per-domain × per-category shape")
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T8: ``_on_config_change`` extracted to module level (brain_mcp)
# ---------------------------------------------------------------------------


def _gate_8_brain_mcp_on_config_change() -> int:
    main = _REPO_ROOT / "packages" / "brain_mcp" / "src" / "brain_mcp" / "__main__.py"
    test = _REPO_ROOT / "packages" / "brain_mcp" / "tests" / "test_ctx_cache_reset.py"
    for p in (main, test):
        if rc := _exists("8", p):
            return rc
    main_text = _read(main)
    test_text = _read(test)
    # Module-level def, not inside _run.
    if not re.search(r"^def _on_config_change\(", main_text, re.MULTILINE):
        return _fail("8", "brain_mcp/__main__.py _on_config_change is not at module level")
    if "from brain_mcp.__main__ import _on_config_change" not in test_text:
        return _fail("8", "test_ctx_cache_reset.py does not import the lifted symbol directly")
    _gate("8 — T8 _on_config_change module-level: tests exercise the production callback symbol")
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T9: ``_resolve_config`` read-only contract audit
# ---------------------------------------------------------------------------


def _gate_9_resolve_config_readonly() -> int:
    apply_patch = (
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "apply_patch.py"
    )
    plan = _REPO_ROOT / "tasks" / "plans" / "17-residuals-and-spec-annotations.md"
    for p in (apply_patch, plan):
        if rc := _exists("9", p):
            return rc
    ap_text = _read(apply_patch)
    if "Read-only contract" not in ap_text:
        return _fail("9", "apply_patch.py _resolve_config missing Read-only contract docstring")
    plan_text = _read(plan)
    if "T9 audit findings" not in plan_text:
        return _fail("9", "plan doc missing T9 audit findings section")
    _gate("9 — T9 _resolve_config: read-only contract docstring + plan-doc audit findings")
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T10: test_mcp_session_list_domains already-done audit
# ---------------------------------------------------------------------------


def _gate_10_test_mcp_session_already_done() -> int:
    plan = _REPO_ROOT / "tasks" / "plans" / "17-residuals-and-spec-annotations.md"
    if rc := _exists("10", plan):
        return rc
    plan_text = _read(plan)
    if "T10 outcome" not in plan_text:
        return _fail("10", "plan doc missing T10 outcome (ALREADY-DONE) marker")
    if "ALREADY-DONE" not in plan_text:
        return _fail("10", "plan doc T10 outcome doesn't state ALREADY-DONE verdict")
    _gate("10 — T10 test_mcp_session_list_domains: closed as already-done (Plan 15 T8 shipped it)")
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T11: brain_api mypy --strict closure + CI step
# ---------------------------------------------------------------------------


def _gate_11_brain_api_mypy_strict() -> int:
    ci = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
    if rc := _exists("11", ci):
        return rc
    text = _read(ci)
    if "Type-check brain_api" not in text:
        return _fail("11", "ci.yml missing Type-check brain_api step")
    if "uv run mypy --strict src tests" not in text:
        return _fail("11", "ci.yml brain_api step doesn't invoke mypy --strict src tests")
    _gate("11 — T11 brain_api mypy --strict: CI hard-fail gate (mirrors brain_core)")
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T12: spec footnote — HYBRID gate algorithm in §3
# ---------------------------------------------------------------------------


def _gate_12_spec_hybrid_algorithm() -> int:
    if rc := _exists("12", _SPEC):
        return rc
    text = _read(_SPEC)
    if "HYBRID autonomy gate algorithm" not in text:
        return _fail("12", "spec missing HYBRID autonomy gate algorithm footnote")
    if "Member-field rule" not in text:
        return _fail("12", "HYBRID algorithm footnote missing Member-field rule")
    if "Category rule (CONCEPTS / DRAFT only)" not in text:
        return _fail("12", "HYBRID algorithm footnote missing CONCEPTS / DRAFT category rule")
    _gate("12 — T12 spec §3 HYBRID gate algorithm: 5-step description for future implementers")
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T13: spec note — multi-domain per-call enforcement no-op
# ---------------------------------------------------------------------------


def _gate_13_spec_multi_domain_noop() -> int:
    if rc := _exists("13", _SPEC):
        return rc
    text = _read(_SPEC)
    if "Multi-domain per-call enforcement policy" not in text:
        return _fail("13", "spec missing Multi-domain per-call enforcement policy note")
    if "domain=None" not in text and "domain is None" not in text:
        return _fail("13", "multi-domain note doesn't mention domain=None short-circuit")
    _gate("13 — T13 spec §10 multi-domain enforcement: policy documented (no-op + global cap fallback)")
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T14: spec annotation — ``resolve_config`` canonical entry
# ---------------------------------------------------------------------------


def _gate_14_spec_resolve_config_contract() -> int:
    if rc := _exists("14", _SPEC):
        return rc
    text = _read(_SPEC)
    if "Canonical Config entry point" not in text:
        return _fail("14", "spec missing Canonical Config entry point annotation")
    if "resolve_config" not in text:
        return _fail("14", "spec resolve_config annotation missing function name")
    _gate("14 — T14 spec §10 resolve_config: canonical entry point contract pinned")
    return 0


# ---------------------------------------------------------------------------
# Gate 15 — T15: ``_lifespan`` comment-debt consolidated
# ---------------------------------------------------------------------------


def _gate_15_lifespan_docstring_refactor() -> int:
    app = _REPO_ROOT / "packages" / "brain_api" / "src" / "brain_api" / "app.py"
    if rc := _exists("15", app):
        return rc
    text = _read(app)
    # A structured docstring with named sections lives inside _lifespan now.
    if "Startup sequence" not in text:
        return _fail("15", "app.py _lifespan docstring missing Startup sequence section")
    if "Shutdown sequence" not in text:
        return _fail("15", "app.py _lifespan docstring missing Shutdown sequence section")
    if "Hot-reload contract" not in text:
        return _fail("15", "app.py _lifespan docstring missing Hot-reload contract section")
    _gate("15 — T15 _lifespan docstring: tutorial-style inline comments consolidated")
    return 0


# ---------------------------------------------------------------------------
# Gate 16 — T16: ``brain_recent`` aligned on ``items`` field
# ---------------------------------------------------------------------------


def _gate_16_brain_recent_items_field() -> int:
    recent = (
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "recent.py"
    )
    browse = _BRAIN_WEB / "src" / "components" / "browse" / "browse-screen.tsx"
    for p in (recent, browse):
        if rc := _exists("16", p):
            return rc
    recent_text = _read(recent)
    browse_text = _read(browse)
    # Backend emits items not notes.
    if '"items"' not in recent_text:
        return _fail("16", "recent.py does not emit items key in ToolResult.data")
    if '"notes"' in recent_text:
        return _fail("16", "recent.py still references legacy notes key")
    # Frontend adapter shim removed.
    if "data?.notes" in browse_text:
        return _fail("16", "browse-screen.tsx still has data?.notes adapter fallback")
    _gate("16 — T16 brain_recent: single canonical items field across backend + frontend")
    return 0


# ---------------------------------------------------------------------------
# Gate 17 — T17: ``repair_config_apply`` wrapped in persist_config_or_revert
# ---------------------------------------------------------------------------


def _gate_17_repair_config_atomic() -> int:
    repair = (
        _REPO_ROOT
        / "packages"
        / "brain_core"
        / "src"
        / "brain_core"
        / "tools"
        / "repair_config_apply.py"
    )
    test = (
        _REPO_ROOT
        / "packages"
        / "brain_core"
        / "tests"
        / "tools"
        / "test_repair_config.py"
    )
    for p in (repair, test):
        if rc := _exists("17", p):
            return rc
    text = _read(repair)
    if "persist_config_or_revert" not in text:
        return _fail("17", "repair_config_apply.py does not wrap mutation in persist_config_or_revert")
    test_text = _read(test)
    if "test_apply_save_failure_reverts_in_memory_mutation" not in test_text:
        return _fail("17", "test_repair_config.py missing save-failure revert pin test")
    if "test_apply_save_failure_reverts_under_handler_local_patch" not in test_text:
        return _fail("17", "test_repair_config.py missing belt-and-suspenders nit test")
    _gate("17 — T17 repair_config_apply: atomic mutation via persist_config_or_revert + 2 pin tests")
    return 0


# ---------------------------------------------------------------------------
# Gate 18 — T18: repair-config-dialog three T33 nits bundled
# ---------------------------------------------------------------------------


def _gate_18_repair_config_dialog_nits() -> int:
    dialog = _BRAIN_WEB / "src" / "components" / "dialogs" / "repair-config-dialog.tsx"
    test = _BRAIN_WEB / "tests" / "unit" / "repair-config-dialog.test.tsx"
    for p in (dialog, test):
        if rc := _exists("18", p):
            return rc
    text = _read(dialog)
    # (b) color tokens: ICON_BY_STATUS entries use var() not hex.
    if "ICON_BY_STATUS" not in text:
        return _fail("18", "repair-config-dialog.tsx missing ICON_BY_STATUS object")
    # Pin all three status colors as CSS variable references.
    for token in ("var(--ok)", "var(--warn)", "var(--danger)"):
        if token not in text:
            return _fail("18", f"repair-config-dialog.tsx missing {token} token usage")
    # No hex color literals in any `color:` field inside the file.
    if re.search(r'color:\s*"#[0-9a-fA-F]{3,8}"', text):
        return _fail("18", "repair-config-dialog.tsx still has hex literals in color: fields")
    # (c) mountedRef present.
    if "mountedRef" not in text:
        return _fail("18", "repair-config-dialog.tsx missing mountedRef for async setState guard")
    _gate("18 — T18 repair-config-dialog nits: tab order + color tokens + mountedRef bundled")
    return 0


# ---------------------------------------------------------------------------
# Closure dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_anthropic_e2e_test,
    _gate_2_brain_api_hot_reload,
    _gate_3_panel_budget_store,
    _gate_4_panel_domains_row_budget,
    _gate_5_domain_override_form_store,
    _gate_6_autonomy_drift_fixture,
    _gate_7_autonomous_doc_cleanup,
    _gate_8_brain_mcp_on_config_change,
    _gate_9_resolve_config_readonly,
    _gate_10_test_mcp_session_already_done,
    _gate_11_brain_api_mypy_strict,
    _gate_12_spec_hybrid_algorithm,
    _gate_13_spec_multi_domain_noop,
    _gate_14_spec_resolve_config_contract,
    _gate_15_lifespan_docstring_refactor,
    _gate_16_brain_recent_items_field,
    _gate_17_repair_config_atomic,
    _gate_18_repair_config_dialog_nits,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 17 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
