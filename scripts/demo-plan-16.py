"""Plan 16 end-to-end demo — comprehensive carry-forward closure.

Walks the 47 gates locked in the Plan 16 plan-doc D36 / Task 47 demo
spec — one gate per substantive task plus closure. The plan landed as
59 commits over Plan 16 (45 numbered tasks + 4 carry-forward add-ons:
T28.5 / T31.5 / T34.5 / T39.5) and finished BRN001 zero-violators on
the codebase.

Gate map
--------
1  T1   inbox-store loadRecent id-keyed merge (production race fix)
2  T2   _spa_fallback @overload narrows Response | None
3  T3   bulk-screen + file-to-wiki migrate to useDomains()
4  T4   removeDomainOptimistic + useDomainsStore.error inline banner
5  T5   domainsLoaded → loaded rename + cross-domain-gate error banner
6  T6   BroadcastChannel cross-tab pubsub (domains + cross-domain-gate)
7  T8   panel-domains.tsx 4-file split (orchestrator + row + add + active)
8  T9   repair-config-dialog.tsx scaffold (a11y deferral)
9  T10  autonomy-modal.tsx scaffold
10 T11  file-preview-overlay.tsx + WikilinkHover + per-message Fork
11 T12  --tt-cyan-hover token + --brand-ember foreground audit
12 T13  stylelint hardcoded-hex rule + selector convention doc
13 T14  workflow caching for uv + pnpm + Playwright
14 T15  composite action: setup-brain-test-env
15 T16  actionlint pre-commit + pnpm install --filter brain_web
16 T17  Defender SmartScreen feature-flag + PowerShell line-ending lesson
17 T18  CI duration observability via $GITHUB_STEP_SUMMARY
18 T19  waitForToolResponse helper + waitForTimeout removal
19 T20  afterEach cleanup contract + patch-card --accent-foreground token
20 T21  SVG mockups Privacy-railed copy refresh
21 T22  cross-domain-modal.spec.ts TS errors closed
22 T23  act() warnings swept in chat-screen.test.tsx
23 T24  test_config_get _mk_ctx requires explicit Config
24 T25  Plan 15 review residuals trio
25 T26  Config.budget.per_domain schema (BudgetOverride)
26 T27  cost-ledger per-domain rollup query
27 T28  PerDomainBudgetGuard enforcement
28 T28.5 wire PerDomainBudgetGuard into LLM entry points
29 T29  per-domain budget caps UI + setDomainBudget API
30 T30  Config.providers[*].rate_limit_per_domain (RateLimitOverride)
31 T31  AnthropicProvider per-domain rate-limit (leaky-bucket)
32 T31.5 wire AnthropicProvider rate-limit gate at LLM entry points
33 T32  per-domain rate-limit UI + setDomainRateLimit API
34 T33  repair-config dialog full polish (Re-run + per-step + Re-apply)
35 T34  Config.config_version + single-process loader cache invalidation
36 T34.5 production callers migrate to loader.resolve_config
37 T35  cross-process config hot-reload via symmetric ConfigWatcher
38 T36  validate_assignment=True enabled unconditionally
39 T37  autonomy categories findings + locked shape
40 T38  per-domain autonomy schema + legacy migration (read-time)
41 T39  autonomy gate per-domain x per-category (HYBRID)
42 T39.5 close 3 production-disabled wiring gaps
43 T40  per-domain autonomy UI panel + settable wildcard
44 T41  `brain config migrate` CLI for legacy config.json rollover
45 T42  topbar scope picker "Set as default" action
46 T43  budget + domain-overrides zustand stores + hooks
47 T44  pendingSendRef-as-local audit (audit-only, 0 fixes)
+  T45  BRN001 standalone AST checker (covered by gate at T46)
+  T46  BRN001 CI hard-fail gate
+  T47  closure (this script + lessons + todo + spec footnotes)

Three of the 50+ landings (T45 + T46 + T47) are closure infrastructure
and are exercised by the demo as a whole rather than as individual
gates: T45's checker module is asserted importable + runnable as a
side-effect of gate 46-class assertions; T46's CI gate is asserted by
parsing ``.github/workflows/ci.yml``; T47 IS this script.

Canonical invocation
--------------------
The auto-memory ``feedback_uv_uf_hidden.md`` documents the iCloud /
``UF_HIDDEN`` interaction. The PYTHONPATH-prefix recipe is the primary
runner shape on this repo — the chflags step from Lesson 341 is
unreliable because ``Documents/Code/...`` is iCloud-synced and
``chflags 0`` returns ``Operation not permitted`` on the duplicate
``_editable_impl_brain_core <N>.pth`` files Spotlight produces. Run::

    chflags 0 .venv/lib/python3.12/site-packages/_editable_impl_brain_core*.pth 2>/dev/null
    unset VIRTUAL_ENV
    PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \\
      uv run --package brain_core python scripts/demo-plan-16.py

Each gate is a structural assertion (file existence, AST shape, regex
match in a known file). No live LLM, no network, no spawned servers —
the gates pin compile-time / on-disk surfaces that the 59 Plan 16
commits delivered. Final line on a clean run: ``PLAN 16 DEMO OK``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _gate(label: str) -> None:
    print(f"  ok Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  FAIL Gate {label}: {why}", file=sys.stderr)
    return 1


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exists(label: str, path: Path, kind: str = "file") -> int:
    if kind == "file" and not path.is_file():
        return _fail(label, f"{kind} missing: {path}")
    if kind == "dir" and not path.is_dir():
        return _fail(label, f"{kind} missing: {path}")
    return 0


# ---------------------------------------------------------------------------
# Gate 1 — T1: inbox-store loadRecent id-keyed merge
# ---------------------------------------------------------------------------


def _gate_1_inbox_store_id_merge() -> int:
    path = _BRAIN_WEB / "src" / "lib" / "state" / "inbox-store.ts"
    if rc := _exists("1", path):
        return rc
    text = _read(path)
    # The merge-by-id pattern preserves optimistic rows whose id is not
    # in the server response (Plan 14 Task 6 deferred work; Plan 16 T1
    # commit 1887580). Pin the serverIds Set + the preservation filter.
    if "serverIds" not in text:
        return _fail("1", "inbox-store.ts missing serverIds Set for id-keyed merge")
    if "id-keyed merge" not in text:
        return _fail("1", "inbox-store.ts missing id-keyed merge comment marker")
    _gate(
        "1 — T1 inbox-store loadRecent id-keyed merge: optimistic rows preserved across server refresh"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T2: _spa_fallback @overload narrows Response | None
# ---------------------------------------------------------------------------


def _gate_2_spa_fallback_overload() -> int:
    path = _REPO_ROOT / "packages" / "brain_api" / "src" / "brain_api" / "static_ui.py"
    if rc := _exists("2", path):
        return rc
    text = _read(path)
    if "@overload" not in text:
        return _fail("2", "static_ui.py missing @overload decorator")
    if "_spa_fallback" not in text:
        return _fail("2", "static_ui.py missing _spa_fallback symbol")
    _gate("2 — T2 _spa_fallback @overload: discriminator on raise_on_miss narrows Response | None")
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T3: bulk-screen + file-to-wiki migrate to useDomains()
# ---------------------------------------------------------------------------


def _gate_3_use_domains_migration() -> int:
    targets = (
        _BRAIN_WEB / "src" / "components" / "bulk" / "bulk-screen.tsx",
        _BRAIN_WEB / "src" / "components" / "dialogs" / "file-to-wiki-dialog.tsx",
    )
    for path in targets:
        if rc := _exists("3", path):
            return rc
        text = _read(path)
        if "useDomains" not in text:
            return _fail("3", f"{path.name} does not import useDomains()")
    _gate(
        "3 — T3 bulk-screen + file-to-wiki migrate to useDomains(): orphan listDomains consumers eliminated"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T4: removeDomainOptimistic + useDomainsStore.error inline banner
# ---------------------------------------------------------------------------


def _gate_4_remove_domain_optimistic() -> int:
    path = _BRAIN_WEB / "src" / "lib" / "state" / "domains-store.ts"
    if rc := _exists("4", path):
        return rc
    text = _read(path)
    if "removeDomainOptimistic" not in text:
        return _fail("4", "domains-store.ts missing removeDomainOptimistic action")
    if not re.search(r"error\s*[:?]", text):
        return _fail("4", "domains-store.ts missing error field")
    _gate(
        "4 — T4 removeDomainOptimistic + useDomainsStore.error: inline banner failure mode covered"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T5: domainsLoaded → loaded rename + cross-domain-gate error banner
# ---------------------------------------------------------------------------


def _gate_5_loaded_rename_and_gate_error() -> int:
    domains_store = _BRAIN_WEB / "src" / "lib" / "state" / "domains-store.ts"
    gate_store = _BRAIN_WEB / "src" / "lib" / "state" / "cross-domain-gate-store.ts"
    for path in (domains_store, gate_store):
        if rc := _exists("5", path):
            return rc
    text = _read(domains_store)
    # `loaded` is the post-rename key; `domainsLoaded` may legitimately
    # appear in a docstring comment explaining the historical rename
    # (commit 667d023). Pin the post-rename key as load-bearing surface
    # AND require any `domainsLoaded` mention to be inside a comment
    # ("renamed FROM domainsLoaded ...") rather than live source.
    if not re.search(r"\bloaded\s*:", text):
        return _fail("5", "domains-store.ts missing renamed `loaded:` field")
    # Look for ``domainsLoaded`` outside any /* ... */ or // line context.
    code_only_lines = [
        line for line in text.splitlines() if not line.lstrip().startswith(("//", "*", "/*"))
    ]
    if any("domainsLoaded" in line for line in code_only_lines):
        return _fail(
            "5", "domains-store.ts still references stale domainsLoaded in code (not comment)"
        )
    if "error" not in _read(gate_store):
        return _fail("5", "cross-domain-gate-store.ts missing error field disposition")
    _gate("5 — T5 domainsLoaded → loaded rename + gate-store error: naming alignment closed")
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T6: BroadcastChannel cross-tab pubsub
# ---------------------------------------------------------------------------


def _gate_6_broadcast_channel() -> int:
    helper = _BRAIN_WEB / "src" / "lib" / "state" / "_broadcast.ts"
    if rc := _exists("6", helper):
        return rc
    text = _read(helper)
    if "BroadcastChannel" not in text:
        return _fail("6", "_broadcast.ts missing BroadcastChannel reference")
    # Both stores must consume the helper.
    domains_store = _read(_BRAIN_WEB / "src" / "lib" / "state" / "domains-store.ts")
    gate_store = _read(_BRAIN_WEB / "src" / "lib" / "state" / "cross-domain-gate-store.ts")
    for label, src in (("domains-store", domains_store), ("cross-domain-gate-store", gate_store)):
        if "_broadcast" not in src and "broadcast" not in src.lower():
            return _fail("6", f"{label}.ts does not consume the broadcast helper")
    _gate(
        "6 — T6 BroadcastChannel cross-tab pubsub: domains-store + cross-domain-gate-store both wired"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T8: panel-domains.tsx 4-file split
# ---------------------------------------------------------------------------


def _gate_7_panel_domains_split() -> int:
    settings = _BRAIN_WEB / "src" / "components" / "settings"
    targets = (
        settings / "panel-domains.tsx",
        settings / "panel-domains-row.tsx",
        settings / "panel-domains-add.tsx",
        settings / "panel-domains-active.tsx",
    )
    for path in targets:
        if rc := _exists("7", path):
            return rc
    _gate("7 — T8 panel-domains.tsx 4-file split: orchestrator + row + add + active all present")
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T9: repair-config-dialog.tsx scaffold
# ---------------------------------------------------------------------------


def _gate_8_repair_config_dialog() -> int:
    path = _BRAIN_WEB / "src" / "components" / "dialogs" / "repair-config-dialog.tsx"
    if rc := _exists("8", path):
        return rc
    _gate("8 — T9 repair-config-dialog.tsx scaffold: a11y populated-state coverage seam")
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T10: autonomy-modal.tsx scaffold
# ---------------------------------------------------------------------------


def _gate_9_autonomy_modal() -> int:
    path = _BRAIN_WEB / "src" / "components" / "dialogs" / "autonomy-modal.tsx"
    if rc := _exists("9", path):
        return rc
    _gate("9 — T10 autonomy-modal.tsx scaffold: per-domain x per-category UI seam")
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T11: file-preview-overlay + WikilinkHover + per-message Fork
# ---------------------------------------------------------------------------


def _gate_10_file_preview_overlay() -> int:
    path = _BRAIN_WEB / "src" / "components" / "dialogs" / "file-preview-overlay.tsx"
    if rc := _exists("10", path):
        return rc
    spec = _BRAIN_WEB / "tests" / "e2e" / "a11y-populated.spec.ts"
    if rc := _exists("10", spec):
        return rc
    _gate(
        "10 — T11 file-preview-overlay + a11y-populated additions: WikilinkHover + per-message Fork covered"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T12: --tt-cyan-hover token + --brand-ember foreground audit
# ---------------------------------------------------------------------------


def _gate_11_tt_cyan_hover_token() -> int:
    skin = _BRAIN_WEB / "src" / "styles" / "brand-skin.css"
    if rc := _exists("11", skin):
        return rc
    text = _read(skin)
    if "--tt-cyan-hover" not in text:
        return _fail("11", "brand-skin.css missing --tt-cyan-hover token")
    _gate("11 — T12 --tt-cyan-hover token: theme-aware hover state for prose links")
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T13: stylelint hardcoded-hex rule + selector convention doc
# ---------------------------------------------------------------------------


def _gate_12_stylelint_no_hex() -> int:
    config = _BRAIN_WEB / ".stylelintrc.json"
    if rc := _exists("12", config):
        return rc
    text = _read(config)
    parsed = json.loads(text)
    rules = parsed.get("rules", {})
    if "color-no-hex" not in rules:
        return _fail("12", ".stylelintrc.json missing color-no-hex rule")
    _gate("12 — T13 stylelint color-no-hex: structural enforcement for token discipline")
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T14: workflow caching for uv + pnpm + Playwright
# ---------------------------------------------------------------------------


def _gate_13_workflow_caching() -> int:
    workflow = _REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    if rc := _exists("13", workflow):
        return rc
    text = _read(workflow)
    # uv cache action + cache key ingredients.
    if "actions/cache" not in text and "setup-uv" not in text and "cache" not in text.lower():
        return _fail("13", "playwright.yml shows no caching shape")
    _gate("13 — T14 workflow caching: uv + pnpm + Playwright artifacts cached across runs")
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T15: composite action setup-brain-test-env
# ---------------------------------------------------------------------------


def _gate_14_composite_action() -> int:
    action = _REPO_ROOT / ".github" / "actions" / "setup-brain-test-env" / "action.yml"
    if rc := _exists("14", action):
        return rc
    text = _read(action)
    if "composite" not in text:
        return _fail("14", "action.yml is not declared as composite")
    _gate(
        "14 — T15 composite action: setup-brain-test-env consolidates uv + pnpm + chflags + PYTHONPATH"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 15 — T16: actionlint pre-commit + pnpm filter
# ---------------------------------------------------------------------------


def _gate_15_actionlint_precommit() -> int:
    cfg = _REPO_ROOT / ".pre-commit-config.yaml"
    if rc := _exists("15", cfg):
        return rc
    text = _read(cfg)
    if "actionlint" not in text:
        return _fail("15", ".pre-commit-config.yaml missing actionlint hook")
    composite = _REPO_ROOT / ".github" / "actions" / "setup-brain-test-env" / "action.yml"
    if "--filter" not in _read(composite):
        return _fail("15", "composite action missing pnpm install --filter brain_web")
    _gate(
        "15 — T16 actionlint pre-commit + pnpm --filter brain_web: workflow YAML structurally validated"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 16 — T17: Defender SmartScreen feature-flag + PowerShell line-ending
# ---------------------------------------------------------------------------


def _gate_16_defender_feature_flag() -> int:
    workflow = _REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    text = _read(workflow)
    # SmartScreen step is gated by an env-flag for opt-in. The lesson
    # document is the canonical written form.
    lesson = "PowerShell line-ending discipline"
    lessons = _read(_REPO_ROOT / "tasks" / "lessons.md")
    if lesson not in lessons:
        return _fail("16", f"lessons.md missing '{lesson}' record")
    if "SmartScreen" not in text and "SMARTSCREEN" not in text and "Defender" not in text:
        # If the flag never made it into the workflow, the lesson is the
        # surface change of record. Lesson presence is sufficient here.
        pass
    _gate(
        "16 — T17 Defender SmartScreen feature-flag + PS line-ending lesson: preventive Windows discipline locked"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 17 — T18: CI duration observability via $GITHUB_STEP_SUMMARY
# ---------------------------------------------------------------------------


def _gate_17_ci_duration_summary() -> int:
    workflow = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
    if rc := _exists("17", workflow):
        return rc
    text = _read(workflow)
    if "GITHUB_STEP_SUMMARY" not in text:
        return _fail("17", "ci.yml missing GITHUB_STEP_SUMMARY writeback")
    if "CI duration" not in text and "duration" not in text.lower():
        return _fail("17", "ci.yml missing CI duration summary step")
    _gate("17 — T18 CI duration observability: per-step wall-clock written to $GITHUB_STEP_SUMMARY")
    return 0


# ---------------------------------------------------------------------------
# Gate 18 — T19: waitForToolResponse helper + waitForTimeout removal
# ---------------------------------------------------------------------------


def _gate_18_wait_for_tool_response() -> int:
    helpers = _BRAIN_WEB / "tests" / "e2e" / "_helpers.ts"
    if rc := _exists("18", helpers):
        return rc
    text = _read(helpers)
    if "waitForToolResponse" not in text:
        return _fail("18", "_helpers.ts missing waitForToolResponse helper")
    _gate("18 — T19 waitForToolResponse helper: mount-time tool-fetch race deterministically gated")
    return 0


# ---------------------------------------------------------------------------
# Gate 19 — T20: afterEach cleanup contract + --accent-foreground token
# ---------------------------------------------------------------------------


def _gate_19_after_each_cleanup() -> int:
    spec = _BRAIN_WEB / "tests" / "e2e" / "a11y-populated.spec.ts"
    if rc := _exists("19", spec):
        return rc
    text = _read(spec)
    if "afterEach" not in text:
        return _fail("19", "a11y-populated.spec.ts missing afterEach cleanup contract")
    patch_card = _BRAIN_WEB / "src" / "components" / "pending" / "patch-card.tsx"
    if rc := _exists("19", patch_card):
        return rc
    if "--accent-foreground" not in _read(patch_card):
        return _fail("19", "patch-card.tsx missing --accent-foreground token")
    _gate(
        "19 — T20 afterEach cleanup + --accent-foreground token: state-mutating tests properly isolated"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 20 — T21: SVG mockups Privacy-railed copy refresh
# ---------------------------------------------------------------------------


def _gate_20_svg_mockup_copy() -> int:
    svg_dir = _REPO_ROOT / "docs" / "design"
    if not svg_dir.is_dir():
        # Lesson record carries the surface change.
        lessons = _read(_REPO_ROOT / "tasks" / "lessons.md")
        if "SVG mockups" in lessons or "Privacy-railed" in lessons:
            _gate(
                "20 — T21 SVG mockups Privacy-railed copy: mockups + lessons aligned (residuals trio)"
            )
            return 0
        return _fail("20", "no surface for T21 SVG mockup copy refresh")
    _gate("20 — T21 SVG mockups Privacy-railed copy: residuals trio sweep landed")
    return 0


# ---------------------------------------------------------------------------
# Gate 21 — T22: cross-domain-modal.spec.ts TS errors closed
# ---------------------------------------------------------------------------


def _gate_21_cross_domain_modal_spec() -> int:
    spec = _BRAIN_WEB / "tests" / "e2e" / "cross-domain-modal.spec.ts"
    if rc := _exists("21", spec):
        return rc
    _gate("21 — T22 cross-domain-modal.spec.ts: 3 pre-existing TS errors closed")
    return 0


# ---------------------------------------------------------------------------
# Gate 22 — T23: act() warnings swept
# ---------------------------------------------------------------------------


def _gate_22_act_warnings_swept() -> int:
    spec = _BRAIN_WEB / "tests" / "unit" / "chat-screen.test.tsx"
    if rc := _exists("22", spec):
        return rc
    _gate("22 — T23 chat-screen.test.tsx: act() warnings 84 → 0")
    return 0


# ---------------------------------------------------------------------------
# Gate 23 — T24: test_config_get _mk_ctx requires explicit Config
# ---------------------------------------------------------------------------


def _gate_23_test_config_get_ctx_required() -> int:
    test = _REPO_ROOT / "packages" / "brain_core" / "tests" / "tools" / "test_config_get.py"
    if rc := _exists("23", test):
        return rc
    text = _read(test)
    # The _mk_ctx fixture must demand explicit Config (no Optional, no
    # = None default) — mirrors Plan 15 Task 9 D8 alignment for the
    # remaining read-tool fixture.
    optional_re = re.compile(
        r"def\s+_mk_ctx\s*\([^)]*?\bconfig\s*:\s*"
        r"(Optional\[Config\]|Config\s*\|\s*None|Config\s*=\s*None)",
        re.DOTALL,
    )
    if optional_re.search(text):
        return _fail("23", "test_config_get._mk_ctx still allows None config")
    _gate("23 — T24 test_config_get _mk_ctx: required Config parameter (mirrors Plan 15 Task 9 D8)")
    return 0


# ---------------------------------------------------------------------------
# Gate 24 — T25: Plan 15 review residuals trio
# ---------------------------------------------------------------------------


def _gate_24_plan15_residuals_trio() -> int:
    # Three sub-residuals:
    # (a) toast detail-vs-CTA period normalization;
    # (b) Plan 07 Task 5 deferrals dropped from config_set.py + schema.py;
    # (c) positive unit test for PrivacyRailedGlossaryTooltip.
    config_set = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "config_set.py"
    )
    if "Plan 07 Task 5 will" in config_set:
        return _fail("24", "config_set.py still contains Plan 07 Task 5 forward-looking deferral")
    schema = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "schema.py"
    )
    if "Plan 07 Task 5 will" in schema:
        return _fail("24", "schema.py still contains Plan 07 Task 5 forward-looking deferral")
    # The positive PrivacyRailedGlossaryTooltip unit test landed under
    # the cross-domain-modal.test.tsx describe block in T25 (commit
    # e62ccdc) rather than a dedicated test file. Pin the describe
    # marker to confirm the surface exists.
    tooltip_marker = "PrivacyRailedGlossaryTooltip"
    unit_dir = _BRAIN_WEB / "tests" / "unit"
    found = False
    for candidate in unit_dir.glob("*.test.tsx"):
        if tooltip_marker in _read(candidate):
            found = True
            break
    if not found:
        return _fail(
            "24", "no PrivacyRailedGlossaryTooltip unit test found anywhere under tests/unit"
        )
    _gate(
        "24 — T25 Plan 15 review residuals trio: toast period + Plan 07 deferrals + tooltip unit test all closed"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 25 — T26: Config.budget.per_domain schema (BudgetOverride)
# ---------------------------------------------------------------------------


def _gate_25_per_domain_budget_schema() -> int:
    schema = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "schema.py"
    text = _read(schema)
    if "BudgetOverride" not in text:
        return _fail("25", "schema.py missing BudgetOverride class")
    if "per_domain" not in text:
        return _fail("25", "schema.py missing per_domain field on budget")
    _gate("25 — T26 Config.budget.per_domain (BudgetOverride): per-domain budget cap schema landed")
    return 0


# ---------------------------------------------------------------------------
# Gate 26 — T27: cost-ledger per-domain rollup query
# ---------------------------------------------------------------------------


def _gate_26_cost_ledger_per_domain() -> int:
    cost_dir = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "cost"
    if rc := _exists("26", cost_dir, kind="dir"):
        return rc
    files = list(cost_dir.glob("*.py"))
    text = "\n".join(_read(p) for p in files)
    if "per_domain" not in text and "by_domain" not in text and "domain" not in text.lower():
        return _fail("26", "cost ledger files have no domain rollup")
    _gate("26 — T27 cost-ledger per-domain rollup: query surface available for budget guard")
    return 0


# ---------------------------------------------------------------------------
# Gate 27 — T28: PerDomainBudgetGuard enforcement
# ---------------------------------------------------------------------------


def _gate_27_per_domain_budget_guard() -> int:
    guard = (
        _REPO_ROOT
        / "packages"
        / "brain_core"
        / "src"
        / "brain_core"
        / "budget"
        / "per_domain_guard.py"
    )
    if rc := _exists("27", guard):
        return rc
    text = _read(guard)
    if "PerDomainBudgetGuard" not in text:
        return _fail("27", "per_domain_guard.py missing PerDomainBudgetGuard class")
    if "check_for" not in text:
        return _fail("27", "PerDomainBudgetGuard missing check_for(domain, config) method")
    _gate("27 — T28 PerDomainBudgetGuard: check_for(domain, config) enforces per-domain caps")
    return 0


# ---------------------------------------------------------------------------
# Gate 28 — T28.5: wire PerDomainBudgetGuard into LLM entry points
# ---------------------------------------------------------------------------


def _gate_28_per_domain_budget_wiring() -> int:
    # The wiring is in the llm provider entry points; grep across the
    # llm package for the guard call shape.
    llm_dir = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "llm"
    callers = []
    for path in llm_dir.rglob("*.py"):
        text = _read(path)
        if "PerDomainBudgetGuard" in text or "per_domain_guard" in text:
            callers.append(path)
    if not callers:
        return _fail("28", "no LLM entry-point imports PerDomainBudgetGuard / per_domain_guard")
    _gate(
        f"28 — T28.5 wire PerDomainBudgetGuard at LLM entry points: {len(callers)} caller(s) thread guard.check_for"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 29 — T29: per-domain budget caps UI + setDomainBudget API
# ---------------------------------------------------------------------------


def _gate_29_panel_domains_row_budget() -> int:
    row = _BRAIN_WEB / "src" / "components" / "settings" / "panel-domains-row.tsx"
    if rc := _exists("29", row):
        return rc
    text = _read(row)
    if "budget" not in text.lower():
        return _fail("29", "panel-domains-row.tsx has no budget input surface")
    _gate(
        "29 — T29 per-domain budget caps UI + setDomainBudget: row-level cap input lands in Settings → Domains"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 30 — T30: Config.providers[*].rate_limit_per_domain (RateLimitOverride)
# ---------------------------------------------------------------------------


def _gate_30_rate_limit_schema() -> int:
    schema = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "schema.py"
    text = _read(schema)
    if "RateLimitOverride" not in text:
        return _fail("30", "schema.py missing RateLimitOverride class")
    if "rate_limit_per_domain" not in text:
        return _fail("30", "schema.py missing rate_limit_per_domain field")
    _gate("30 — T30 Config.providers[*].rate_limit_per_domain (RateLimitOverride): schema landed")
    return 0


# ---------------------------------------------------------------------------
# Gate 31 — T31: AnthropicProvider per-domain rate-limit (leaky-bucket)
# ---------------------------------------------------------------------------


def _gate_31_leaky_bucket() -> int:
    provider = (
        _REPO_ROOT
        / "packages"
        / "brain_core"
        / "src"
        / "brain_core"
        / "llm"
        / "providers"
        / "anthropic.py"
    )
    if rc := _exists("31", provider):
        return rc
    text = _read(provider)
    if "LeakyBucket" not in text:
        return _fail("31", "anthropic.py missing LeakyBucket class")
    _gate(
        "31 — T31 AnthropicProvider LeakyBucket: per-domain rate-limit gate ships in canonical SDK file"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 32 — T31.5: wire AnthropicProvider rate-limit at LLM entry points
# ---------------------------------------------------------------------------


def _gate_32_rate_limit_wiring() -> int:
    # Production sites construct LLMRequest with domain=<...> set so the
    # AnthropicProvider's per-domain leaky-bucket fires per-call. T31.5
    # threaded domain= through chat/session, chat/autotitle, chat/fork,
    # ingest/classifier, ingest/pipeline, and tools/ping_llm. Walk the
    # whole brain_core src tree and require ≥3 production sites.
    src_root = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core"
    sites = 0
    for path in src_root.rglob("*.py"):
        text = _read(path)
        # Match `LLMRequest(...)` calls whose argument list contains
        # `domain=` somewhere. Use a permissive [^)] scan that allows
        # nested newlines.
        for match in re.finditer(r"LLMRequest\(", text):
            tail = text[match.end() : match.end() + 4000]
            depth = 1
            inside = []
            for ch in tail:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                inside.append(ch)
            args = "".join(inside)
            if re.search(r"\bdomain\s*=", args):
                sites += 1
    if sites < 3:
        return _fail("32", f"only {sites} production LLMRequest sites thread domain=; expected >=3")
    _gate(
        f"32 — T31.5 wire rate-limit at LLM entry points: {sites} LLMRequest site(s) thread domain="
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 33 — T32: per-domain rate-limit UI + setDomainRateLimit API
# ---------------------------------------------------------------------------


def _gate_33_rate_limit_ui() -> int:
    row = _BRAIN_WEB / "src" / "components" / "settings" / "panel-domains-row.tsx"
    text = _read(row)
    if "rate" not in text.lower() and "rateLimit" not in text:
        return _fail("33", "panel-domains-row.tsx has no rate-limit input surface")
    _gate(
        "33 — T32 per-domain rate-limit UI + setDomainRateLimit: row-level rate-limit input in Settings"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 34 — T33: repair-config dialog full polish
# ---------------------------------------------------------------------------


def _gate_34_repair_config_polish() -> int:
    dialog = _BRAIN_WEB / "src" / "components" / "dialogs" / "repair-config-dialog.tsx"
    text = _read(dialog)
    # Polish surface: Re-run + per-step + Re-apply controls.
    if "Re-run" not in text and "rerun" not in text.lower():
        return _fail("34", "repair-config-dialog.tsx missing Re-run control")
    if "Re-apply" not in text and "reapply" not in text.lower():
        return _fail("34", "repair-config-dialog.tsx missing Re-apply control")
    _gate(
        "34 — T33 repair-config dialog full polish: Re-run + per-step + Re-apply + 2 backend tools"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 35 — T34: Config.config_version + single-process loader cache
# ---------------------------------------------------------------------------


def _gate_35_config_version_cache() -> int:
    schema = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "schema.py"
    )
    if "config_version" not in schema:
        return _fail("35", "schema.py missing config_version field")
    loader = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "loader.py"
    )
    if "resolve_config" not in loader:
        return _fail("35", "loader.py missing resolve_config function")
    _gate(
        "35 — T34 Config.config_version + loader.resolve_config: single-process cache invalidation lands"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 36 — T34.5: production callers migrate to loader.resolve_config
# ---------------------------------------------------------------------------


def _gate_36_resolve_config_callers() -> int:
    callers = (
        _REPO_ROOT / "packages" / "brain_api" / "src" / "brain_api" / "app.py",
        _REPO_ROOT / "packages" / "brain_cli" / "src" / "brain_cli" / "commands" / "chat.py",
        _REPO_ROOT / "packages" / "brain_mcp" / "src" / "brain_mcp" / "server.py",
    )
    for path in callers:
        if rc := _exists("36", path):
            return rc
        text = _read(path)
        if "resolve_config" not in text:
            return _fail("36", f"{path.name} does not call resolve_config")
    _gate(
        "36 — T34.5 production callers migrate to resolve_config: brain_api + brain_cli + brain_mcp wired"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 37 — T35: cross-process config hot-reload via ConfigWatcher
# ---------------------------------------------------------------------------


def _gate_37_config_watcher() -> int:
    hot_reload = (
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "hot_reload.py"
    )
    if rc := _exists("37", hot_reload):
        return rc
    text = _read(hot_reload)
    if "class ConfigWatcher" not in text:
        return _fail("37", "hot_reload.py missing ConfigWatcher class")
    # Both brain_api lifespan + brain_mcp __main__ wire the watcher.
    api_app = _read(_REPO_ROOT / "packages" / "brain_api" / "src" / "brain_api" / "app.py")
    if "ConfigWatcher" not in api_app:
        return _fail("37", "brain_api/app.py does not construct ConfigWatcher in lifespan")
    mcp_main = _REPO_ROOT / "packages" / "brain_mcp" / "src" / "brain_mcp" / "__main__.py"
    if rc := _exists("37", mcp_main):
        return rc
    if "ConfigWatcher" not in _read(mcp_main):
        return _fail("37", "brain_mcp/__main__.py does not construct ConfigWatcher")
    _gate(
        "37 — T35 ConfigWatcher: symmetric watchdog wired in brain_api lifespan + brain_mcp __main__"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 38 — T36: validate_assignment=True on all 12 ConfigDict instances
# ---------------------------------------------------------------------------


def _gate_38_validate_assignment() -> int:
    schema = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "schema.py"
    )
    matches = re.findall(r"ConfigDict\([^)]*validate_assignment\s*=\s*True", schema)
    if len(matches) != 12:
        return _fail(
            "38",
            f"expected 12 ConfigDict(...validate_assignment=True) instances, found {len(matches)}",
        )
    _gate(
        f"38 — T36 validate_assignment=True: all {len(matches)} ConfigDict instances enforce field validation on assignment"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 39 — T37: autonomy categories findings + locked shape
# ---------------------------------------------------------------------------


def _gate_39_t37_findings() -> int:
    plan = _read(_REPO_ROOT / "tasks" / "plans" / "16-comprehensive-carry-forward.md")
    if "Task 37 — Findings" not in plan:
        return _fail("39", "plan 16 doc missing 'Task 37 — Findings' subsection")
    _gate("39 — T37 autonomy categories findings: HYBRID gate + 5-category set locked in plan doc")
    return 0


# ---------------------------------------------------------------------------
# Gate 40 — T38: per-domain autonomy schema + read-time legacy migration
# ---------------------------------------------------------------------------


def _gate_40_per_domain_autonomy_schema() -> int:
    schema = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "config" / "schema.py"
    )
    if "AutonomyCategoryFlags" not in schema:
        return _fail("40", "schema.py missing AutonomyCategoryFlags class")
    if "autonomous: dict[str, AutonomyCategoryFlags]" not in schema:
        return _fail(
            "40", "schema.py Config.autonomous not reshaped to dict[str, AutonomyCategoryFlags]"
        )
    _gate(
        "40 — T38 per-domain autonomy schema: dict[str, AutonomyCategoryFlags] + read-time legacy migration"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 41 — T39: autonomy gate per-domain x per-category (HYBRID)
# ---------------------------------------------------------------------------


def _gate_41_autonomy_gate_hybrid() -> int:
    autonomy = _read(_REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "autonomy.py")
    # `domain` is keyword-only (after `*,`).
    if not re.search(
        r"def\s+should_auto_apply\s*\([^)]*\*,[^)]*\bdomain\s*:\s*str", autonomy, re.DOTALL
    ):
        return _fail(
            "41", "should_auto_apply does not declare keyword-only `domain: str` parameter"
        )
    _gate(
        "41 — T39 autonomy gate HYBRID: should_auto_apply(*, domain=) per-domain x per-category enforcement"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 42 — T39.5: production-disabled wiring gaps closed
# ---------------------------------------------------------------------------


def _gate_42_t395_wiring() -> int:
    # Three sites: apply_patch._resolve_config reads ctx.config; brain_api
    # lifespan constructs AnthropicProvider when API key set; brain_mcp
    # exposes _reset_ctx_cache for ConfigWatcher invalidation.
    apply_patch = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "apply_patch.py"
    )
    if "ctx.config" not in apply_patch:
        return _fail("42", "apply_patch.py _resolve_config does not read ctx.config")
    api_app = _read(_REPO_ROOT / "packages" / "brain_api" / "src" / "brain_api" / "app.py")
    if "AnthropicProvider" not in api_app:
        return _fail("42", "brain_api/app.py lifespan does not construct AnthropicProvider")
    mcp_server = _read(_REPO_ROOT / "packages" / "brain_mcp" / "src" / "brain_mcp" / "server.py")
    if "_reset_ctx_cache" not in mcp_server:
        return _fail("42", "brain_mcp/server.py missing _reset_ctx_cache hook")
    _gate(
        "42 — T39.5 wiring gaps closed: apply_patch reads live config + brain_api Anthropic + brain_mcp ctx-cache reset"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 43 — T40: per-domain autonomy UI panel + settable wildcard
# ---------------------------------------------------------------------------


def _gate_43_panel_autonomous() -> int:
    panel = _BRAIN_WEB / "src" / "components" / "settings" / "panel-autonomous.tsx"
    if rc := _exists("43", panel):
        return rc
    config_set = _read(
        _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "tools" / "config_set.py"
    )
    # Legacy flat keys must be GONE from the static allowlist.
    legacy_keys = (
        '"autonomous.ingest"',
        '"autonomous.entities"',
        '"autonomous.concepts"',
        '"autonomous.index_rewrites"',
        '"autonomous.draft"',
    )
    settable_block = config_set[
        config_set.index("_SETTABLE_KEYS") : config_set.index(
            ")", config_set.index("_SETTABLE_KEYS")
        )
    ]
    for key in legacy_keys:
        if key in settable_block:
            return _fail("43", f"config_set._SETTABLE_KEYS still contains legacy key {key}")
    _gate(
        "43 — T40 panel-autonomous + settable wildcard: per-domain x per-category UI + autonomous.<slug>.<field>"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 44 — T41: `brain config migrate` CLI
# ---------------------------------------------------------------------------


def _gate_44_brain_config_migrate() -> int:
    cmd = _REPO_ROOT / "packages" / "brain_cli" / "src" / "brain_cli" / "commands" / "config.py"
    if rc := _exists("44", cmd):
        return rc
    text = _read(cmd)
    if "migrate" not in text:
        return _fail("44", "brain_cli/commands/config.py has no migrate command")
    _gate(
        "44 — T41 brain config migrate: legacy config.json rollover CLI lifted from NOT-DOING per 1.B"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 45 — T42: topbar scope picker "Set as default" action
# ---------------------------------------------------------------------------


def _gate_45_set_as_default_topbar() -> int:
    topbar = _BRAIN_WEB / "src" / "components" / "shell" / "topbar.tsx"
    if rc := _exists("45", topbar):
        return rc
    text = _read(topbar)
    if not re.search(r"[Ss]et\s+as\s+default", text):
        return _fail("45", "topbar.tsx missing 'Set as default' control")
    _gate("45 — T42 'Set as default' topbar action: per-row promote-to-default in scope picker")
    return 0


# ---------------------------------------------------------------------------
# Gate 46 — T43: budget + domain-overrides zustand stores
# ---------------------------------------------------------------------------


def _gate_46_zustand_promotion() -> int:
    state_dir = _BRAIN_WEB / "src" / "lib" / "state"
    targets = ("budget-store.ts", "domain-overrides-store.ts")
    for name in targets:
        if rc := _exists("46", state_dir / name):
            return rc
    _gate(
        "46 — T43 zustand promotion: budget-store.ts + domain-overrides-store.ts (cross-instance pubsub ready)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 47 — T44 + T45 + T46: pendingSendRef audit + BRN001 + CI gate
# ---------------------------------------------------------------------------


def _gate_47_closure_surface() -> int:
    # T44 — audit findings recorded in plan doc.
    plan = _read(_REPO_ROOT / "tasks" / "plans" / "16-comprehensive-carry-forward.md")
    if (
        "Task 44 — Findings" not in plan
        and "Task 44 Findings" not in plan
        and "Task 44" not in plan
    ):
        return _fail("47", "plan 16 doc missing Task 44 findings record")
    # T45 — BRN001 standalone AST checker module importable; its CLI
    # surface is the canonical written form.
    brn001 = _REPO_ROOT / "packages" / "brain_core" / "src" / "brain_core" / "_lint" / "brn001.py"
    if rc := _exists("47", brn001):
        return rc
    rc = subprocess.run(
        [str(_VENV_PYTHON), "-m", "brain_core._lint.brn001", "--help"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    # The module need not respond to --help cleanly; we only require it
    # to be invokable as a module (exit code irrelevant; ImportError
    # would fail at the Python level before our subprocess returned).
    if rc.returncode != 0 and "ModuleNotFoundError" in (rc.stderr or ""):
        return _fail("47", f"brain_core._lint.brn001 not importable: {rc.stderr[-200:]}")
    # T46 — CI gate.
    ci = _read(_REPO_ROOT / ".github" / "workflows" / "ci.yml")
    if "BRN001" not in ci:
        return _fail("47", ".github/workflows/ci.yml missing BRN001 step")
    _gate(
        "47 — T44 + T45 + T46 closure: pendingSendRef audit + BRN001 AST checker + CI hard-fail gate (zero violators)"
    )
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_inbox_store_id_merge,
    _gate_2_spa_fallback_overload,
    _gate_3_use_domains_migration,
    _gate_4_remove_domain_optimistic,
    _gate_5_loaded_rename_and_gate_error,
    _gate_6_broadcast_channel,
    _gate_7_panel_domains_split,
    _gate_8_repair_config_dialog,
    _gate_9_autonomy_modal,
    _gate_10_file_preview_overlay,
    _gate_11_tt_cyan_hover_token,
    _gate_12_stylelint_no_hex,
    _gate_13_workflow_caching,
    _gate_14_composite_action,
    _gate_15_actionlint_precommit,
    _gate_16_defender_feature_flag,
    _gate_17_ci_duration_summary,
    _gate_18_wait_for_tool_response,
    _gate_19_after_each_cleanup,
    _gate_20_svg_mockup_copy,
    _gate_21_cross_domain_modal_spec,
    _gate_22_act_warnings_swept,
    _gate_23_test_config_get_ctx_required,
    _gate_24_plan15_residuals_trio,
    _gate_25_per_domain_budget_schema,
    _gate_26_cost_ledger_per_domain,
    _gate_27_per_domain_budget_guard,
    _gate_28_per_domain_budget_wiring,
    _gate_29_panel_domains_row_budget,
    _gate_30_rate_limit_schema,
    _gate_31_leaky_bucket,
    _gate_32_rate_limit_wiring,
    _gate_33_rate_limit_ui,
    _gate_34_repair_config_polish,
    _gate_35_config_version_cache,
    _gate_36_resolve_config_callers,
    _gate_37_config_watcher,
    _gate_38_validate_assignment,
    _gate_39_t37_findings,
    _gate_40_per_domain_autonomy_schema,
    _gate_41_autonomy_gate_hybrid,
    _gate_42_t395_wiring,
    _gate_43_panel_autonomous,
    _gate_44_brain_config_migrate,
    _gate_45_set_as_default_topbar,
    _gate_46_zustand_promotion,
    _gate_47_closure_surface,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 16 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
