# Plan 13 — Cross-instance cleanup + pre-existing test debt closure

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Plan 13 D8 locks **sequential per-task dispatch with two-stage review** (Plan 11 + 12 discipline) — do NOT parallelize even when the dependency graph allows it (Tasks 1, 4-5, and 6 are nominally independent).

**Goal:** Close the architectural cross-instance / lifecycle-violation anti-pattern category that Plan 12 Task 5 + Task 6 partially addressed, AND clear the pre-existing test debt that has been masquerading as environment-dependent flake since Plan 11 era. Six threads in one cohesive plan:

1. **#A1 (correctness) — None-policy strictness on `list_domains` + `config_set.py:317-327`.** `config_get` raises `RuntimeError` on `ctx.config is None`; `list_domains._configured_slugs` and `_active_domain` silently fall back to `DEFAULT_DOMAINS`; `config_set.py:317-327` no-ops on the same condition. After Plan 11 Task 7 (brain_api) + Plan 12 Task 4 (brain_mcp) wired Config into both wrappers, the lenient branches are dead code in production-shape paths. Plan 11 lesson 343 named this anti-pattern category; Plan 13 kills it.

2. **#A2 (correctness) — Drop `panel-domains.tsx` local `domains: string[]` state.** Plan 12 Task 5 promoted `useDomains()` to a zustand store; `panel-domains.tsx` still maintains a parallel local state hydrated from a separate `refresh()` call. Both read paths land at the same backend so they've stayed coincidentally aligned, but the seam is drift-prone. Plan 13 reads from `useDomainsStore` directly and drops the local state.

3. **#A3 (correctness) — Promote `useCrossDomainGate` to `lib/state/cross-domain-gate-store.ts`.** Same shape as Plan 12 Task 5 fixed for `useDomains`: the gate hook holds local React state for `privacyRailed` + `acknowledged`; mutation via the Settings toggle's `setCrossDomainWarningAcknowledged` only updates the in-toggle state, not the gate hook in chat-screen. Same-tab re-mount works but cross-instance / cross-tab does not. Plan 13 promotes the gate to a dedicated zustand store mirroring Plan 12 D4's `domains-store.ts` split.

4. **#B1 (test debt) — brain_api 13-failure triage.** 13 unit-test failures pre-existed Plan 12 (verified by `git log d7dbf66..HEAD -- packages/brain_api/` returning zero commits): `test_errors.py` × 8, `test_auth_dependency.py` × 4, `test_context.py::test_get_ctx_dependency_resolves`, `test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id`. All assert response status codes that come back unexpectedly as 200 (vs expected 4xx/5xx). Playwright e2e (real subprocess) does NOT reproduce — likely TestClient/middleware-config drift since Plan 11 era, not production regression. Plan 13 Task 4 confirms (or refutes) the OriginHostMiddleware/TestClient drift hypothesis; Task 5 fixes + adds a regression-pin test.

5. **#B2 (test debt) — a11y color-contrast token sweep.** 8 axe-core color-contrast violations across `/chat`, `/inbox`, `/browse`, `/pending`, `/bulk`, `/settings/general`, `/settings/providers`, `/settings/domains` plus 1 setup-wizard welcome-step violation. Plan 07 Task 25C re-enabled the axe-core a11y gate with token nudges (`--text-muted` 0.60 → 0.70, `--text-dim` 0.38 → 0.58 dark / 0.40 → 0.56 light, `--accent: var(--surface-3)` → `var(--tt-cyan)`); somewhere between Plan 07 close and Plan 12 close those nudges regressed. Plan 13 re-applies the precedent: token sweep first, per-route follow-up only if any violation survives.

6. **(closure) — Demo + e2e + lessons closure.** 7-gate demo per D10. Plan 13 candidate-scope tail block in `tasks/todo.md` removed; Plan 14 candidate-scope tail block added with the deferred small cleanups (7 items from Plan 12 candidate scope) + bigger architectural moves.

**Architecture.** Two-track plan: architectural correctness (#A1, #A2, #A3) + test-debt closure (#B1, #B2). The architectural items share a single root cause (cross-instance / lifecycle anti-pattern; Plan 12 Task 5 + Task 6 + lessons 343/353 framed the category). Test-debt items share the "Plan 09 said don't relax these gates; somewhere they regressed" theme. No interdependencies between the two tracks; D8 locks sequential dispatch anyway because Plan 11 + 12 review-discipline catch-rate justifies the wall-clock cost. Demo gate composition (D10) is one assertion per item plus a closure sentinel.

**Tech Stack.** Same gates as Plan 11 + 12 — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright. zustand already a workspace dep. No new third-party deps.

**Demo gate.** `uv run python scripts/demo-plan-13.py` (or the chflags-prefixed variant per lesson 341) walks the seven gates: (1) `list_domains` raises `RuntimeError` on `ctx.config is None` AND `config_set.py:317-327`'s lenient branch raises the same; both error messages match `config_get`'s wording. (2) Render `panel-domains.tsx` in a jsdom test harness; assert `useDomainsStore.getState().domains` is the only source of the rendered domain list (no local state initialized parallel to it). (3) Mount two `useCrossDomainGate()` consumers simultaneously in a jsdom test (or Playwright if more reliable); mutate `acknowledged` via one consumer's `setCrossDomainWarningAcknowledged`; assert the other consumer re-renders with the new value within 100ms (no `page.reload()` workaround). (4) Run all 13 previously-failing brain_api tests; assert each passes with the expected 4xx/5xx status code (not 200). (5) Run a new regression-pin test asserting 4xx/5xx response envelope shape parity across the suspected drift point identified by Task 4 — pinned at the OriginHostMiddleware (or wherever Task 4 confirms the root cause); the envelope shape is `{"error": str, "message": str, "detail": dict | None}` per Plan 05 Batch A. (6) Run Playwright `tests/e2e/a11y.spec.ts` axe-core sweep across `/chat`, `/inbox`, `/browse`, `/pending`, `/bulk`, `/settings/general`, `/settings/providers`, `/settings/domains`; assert 0 color-contrast violations on each route. (7) Run Playwright `tests/e2e/setup-wizard.spec.ts` axe-core sweep on the welcome step; assert 0 color-contrast violations. Prints `PLAN 13 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents.**
- `brain-core-engineer` — Task 1 (None-policy strictness)
- `brain-test-engineer` — Task 4 (brain_api hypothesis-confirm), Task 7 (closure demo + e2e + lessons)
- `brain-mcp-engineer` (role-overloaded brain-api-engineer per Plan 05 precedent) — Task 5 (brain_api fix + regression-pin test)
- `brain-frontend-engineer` — Task 2 (panel-domains local state drop), Task 3 (cross-domain-gate-store), Task 6 (a11y color-contrast token sweep)
- `brain-ui-designer` — no scope (Task 6 is token-tier, not microcopy; Plan 07 Task 25C precedent was a brain-frontend-engineer task without designer co-ownership)
- `brain-installer-engineer` — no scope (install paths unchanged)
- `brain-prompt-engineer` — no scope (no prompt changes)

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 12 closed clean: `git tag --list | grep plan-12-settings-ux-and-cleanup` exists.
- Confirm no uncommitted changes on `main`.
- Confirm `tasks/lessons.md` contains the Plan 12 closure section. Task 1 references lesson 343 (brain_api Config-wiring oversight; production-shape integration tests are the regression guard) + lesson 353 (read-path snapshot anti-pattern). Task 3 references Plan 12 Task 5 lessons (zustand pubsub for `useDomains`). Task 4 references Plan 05 BaseHTTPMiddleware lesson (middleware that enforces policy must be ASGI-level, not BaseHTTPMiddleware-level, if app exposes WebSockets) + Plan 05 TestClient WS hardcoded `ws://testserver` lesson.
- **Plan 13 inverts a deliberate Plan 11-era escape hatch.** `config_set.py:317-327`'s lenient `cfg is None` branch was explicitly added so unit tests with `ctx.config=None` could exercise the validation path without a full Config fixture. That pattern was tolerable pre-Plan-11-Task-7 (brain_api wired Config) and pre-Plan-12-Task-4 (brain_mcp wired Config), but is now untestable in production-shape integration tests because both wrappers always supply Config. Task 1 MUST update any unit tests that explicitly seeded `ctx.config=None` to seed a real Config instead (the production shape post-Plan 12 D6).
- **Plan 13 inverts a probable Plan 09-era gate hardening.** Plan 09 said *"Plan 09 should not relax it. WCAG 2.2 AA + 14-gate demo are both hard gates for v0.1.0."* about the axe-core a11y gate. The fact that 9 violations now exist means the gate has been bypassed, weakened, or regressed somewhere between Plan 09 close and Plan 12 close. Task 6 must (a) clear the existing violations AND (b) confirm the gate is genuinely hard-failing in `tests/e2e/a11y.spec.ts` so future regressions can't slip past silently.
- Note the recurring uv `UF_HIDDEN .pth` workaround documented in lessons.md Plan 11 (lesson 341) and refined in Plan 12: the `chflags 0` step must be the IMMEDIATE prefix of the same command that runs python; do NOT use `uv run` (which re-syncs and re-hides). The Plan 13 demo command line is `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python scripts/demo-plan-13.py`. The Playwright webServer can't drop `uv run` cleanly; the workaround there is `PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src npx playwright test`.

---

## What Plan 13 explicitly does NOT do

These are tempting adjacent expansions filed for Plan 14+:

- **The 7 small cleanups from Plan 13 candidate scope.** `apply_patch.py:_resolve_config` docstring stale (Task 1 picks this up scope-adjacent because it's the same anti-pattern category); plan-text "topbar scope chip" inaccuracy drift watch (lesson, not code); `brain start` CLI chflags handling (escape hatch was direct uvicorn — install-path concern, deferred); modal "private" vs Settings "Privacy-railed" jargon split (microcopy alignment, brain-ui-designer task); active-domain dropdown toast CTA wording (transport vs validator error split); active-domain dropdown `pushToast` outside try-block (defensive); Task 9 `pendingSendRef.mode` dead field (cleanup or use). Plan 14 polish pass picks these up as a single small-cleanups thread.
- **Per-domain budget caps.** Per-domain caps need a separate cost-ledger schema change.
- **Per-domain rate limits.** Rate limits live in the provider client today.
- **Repair-config UI screen.** Plan 11 D7 landed the auto-fallback chain (`config.json → .bak → defaults`); the UI surface is a Plan 14+ iteration.
- **Hot-reload of config changes across processes.** Cross-process invalidation (e.g., brain_api notifying brain_mcp of a domain rename) is a Plan 14+ iteration.
- **`validate_assignment=True` on `Config` and sub-configs.** Plan 11 Task 4 added a KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`). Performance impact needs measurement first.
- **Per-domain autonomy categories.** Plan 12 D1 chose DELETE for `resolve_autonomous_mode`. Re-introducing per-domain autonomy is a Plan 14+ architectural lift requiring `Config.autonomous` to grow per-domain-per-category structure.
- **"Set as default" button on the topbar scope picker.** Plan 12 D3 placed the editor on `panel-domains.tsx` to preserve the per-session vs persistent-default distinction Plan 11 Task 8 was careful to establish.
- **Per-thread cross-domain confirmation.** Plan 12 D8 chose per-vault `Config` field; per-thread violates spec §4 "one-time".
- **Generic "tool reads ctx.config" lint rule.** Plan 12 D5's audit + regression-pin test is per-tool. A repo-wide ruff rule or AST check is Plan 14+ if the anti-pattern keeps re-appearing.
- **Migration tool for old `config.json` files.** Pydantic defaults handle missing fields on read; `save_config` round-trips with the new shape on next mutation.
- **Generic zustand promotion across other hooks (`useBudget`, `useDomainOverrides`, etc.).** Plan 12 promoted `useDomains` and Plan 13 promotes `useCrossDomainGate`; generalizing the pattern across other hooks is Plan 14+ if/when the same cross-instance bug surfaces elsewhere.
- **Spec amendment.** Plan 13 D7 explicitly skips spec text changes — the items are internal correctness / test-debt fixes that don't change user-facing surface area.

If any of these come up during implementation, file a TODO and keep moving.

---

## Decisions (locked 2026-04-28)

User signed off on all 11 recommendations on 2026-04-28. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope.

### Group I — Scope cut

| # | Decision | Locked | Why |
|---|---|---|---|
| Scope | Plan 13 covers six items: #A1 None-policy strictness, #A2 panel-domains local state drop, #A3 cross-domain-gate-store cross-instance pubsub, #B1 brain_api 13-failure triage, #B2 a11y color-contrast token sweep, plus closure (demo + e2e + lessons). Closes A + B + a11y from the Plan 13 candidate-scope brief. Defers C (7 small cleanups, Plan 14 polish) and D (bigger architectural moves, Plan 14+). | ✅ | "All pre-existing test debt cleared in one plan" cut. Cohesive theme: fix the cross-instance/lifecycle anti-pattern category once and for all + close pre-existing brain_api regression + restore a11y discipline. Plan 14 starts with a clean test surface. |

### Group II — Architectural None-policy (#A1)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | Tighten BOTH `list_domains` (replace silent fallback to `DEFAULT_DOMAINS` with `raise RuntimeError`) AND `config_set.py:317-327`'s lenient `cfg is None` no-op (replace with `raise RuntimeError`). Match `config_get`'s exact error message wording for consistency. Pin tests for both; rewrite existing unit tests that explicitly seeded `ctx.config=None` to seed a real Config (production shape post-Plan 12 D6). Scope-adjacent: update `apply_patch.py:_resolve_config` docstring (stale "Mirrors brain_config_get approach" reference; Plan 13 candidate scope item #1) — same anti-pattern category, captured in this task. | ✅ | Plan 11 lesson 343 + Plan 12 D5 audit established that `ctx.config` SHOULD always be set in production-shape paths. Silent fallback is the bug, not the contract (Plan 11 Task 7 framing). "Tighten only one" was rejected as inconsistent across the same file family. "Keep both lenient" was rejected as letting the anti-pattern category re-grow on future read tools. |

### Group III — Frontend cross-instance state (#A2 + #A3)

| # | Decision | Locked | Why |
|---|---|---|---|
| D2 | `panel-domains.tsx` drops its local `domains: string[]` state entirely; reads directly from `useDomainsStore` (Plan 12 Task 5). Single source of truth. Mirrors the simplification Plan 12 Task 5 did for `useDomains()`. | ✅ | Two read paths landed at the same backend coincidentally — drift-prone seam Task 5 + Task 8 reviews flagged. "Keep local state, sync from store" was rejected as defense-in-depth that doubles the maintenance surface for no behavior gain. |
| D3 | New `apps/brain_web/src/lib/state/cross-domain-gate-store.ts` for the gate's `privacyRailed: string[]` + `acknowledged: boolean` + `refresh(): Promise<void>` + `setAcknowledgedOptimistic(value: boolean)`. `useCrossDomainGate()` becomes a zustand selector. Mirrors Plan 12 D4's `domains-store.ts` split (dedicated store file rather than overloading `app-store.ts`). | ✅ | Symmetric with what Plan 12 just shipped for `useDomains` → `domains-store.ts`. Co-locates the gate's state with its concern. "Extend `domains-store.ts`" was rejected as one store doing two jobs. "Add to `app-store.ts`" was rejected as risking the kitchen-sink pattern Plan 12 D4 explicitly punted away from. |

### Group IV — brain_api triage (#B1)

| # | Decision | Locked | Why |
|---|---|---|---|
| D4 | brain_api 13-failure scope: diagnose root cause + fix all 13 + add a regression-pin test asserting 4xx/5xx response envelope shape parity at the suspected drift point. Closes the test debt fully; matches Plan 11 Task 4's mutation-tool persistence pin-test discipline. | ✅ | "Diagnose + fix only" was rejected as letting the same drift category re-grow on future middleware/auth work. "Diagnose only" was rejected as deferring user-signed-off cleanup; pytest output stays noisy with 13 expected failures until Plan 14. Plan 11 lesson 343 said production-shape integration tests are the regression guard; the pin test IS that guard. |
| D5 | brain_api investigation discipline: hypothesis-confirm-first as Task 4 (separate task from the fix). Confirm (or refute) the OriginHostMiddleware/TestClient drift hypothesis BEFORE locking fix shape in Task 5. If hypothesis is wrong, fix shape pivots and Task 5 dispatches against new findings. | ✅ | Plan 05 BaseHTTPMiddleware lesson + Plan 12 lesson on production-shape integration tests both said surgical investigation before remediation is the right discipline for middleware-shaped bugs. "One-shot diagnose-and-fix" was rejected as letting findings short-circuit review-loop; if the diagnose surfaces a deeper architectural drift, the fix-shape balloon happens mid-task without plan-author sign-off. |

### Group V — a11y color-contrast triage (#B2)

| # | Decision | Locked | Why |
|---|---|---|---|
| D6 | a11y color-contrast triage approach: token sweep first (mirror Plan 07 Task 25C precedent — nudge `--text-muted` / `--text-dim` / `--accent` tokens in `globals.css`). If all 8 routes + setup-wizard clear with one token pass, done. If any violations survive after the sweep, follow-up per-route fixes within the same task. | ✅ | Plan 07 Task 25C established the single-source-of-truth pattern. "Per-route diagnosis from start" was rejected as risking inconsistent fixes across 9 surfaces. "Both in parallel" was rejected as biggest review burden + risk of merge conflicts in `globals.css` if both threads touch overlapping tokens. |

### Group VI — Plan shape (#0)

| # | Decision | Locked | Why |
|---|---|---|---|
| D7 | Plan 13 skips spec amendment. No spec text is touched by Plan 13 scope (architectural None-policy + panel-domains state + gate-store + brain_api triage + a11y are all internal correctness / test-debt fixes). Plan 12 D10 amended spec for the cross-domain modal trigger; Plan 13 has no analogous user-facing spec-relevant change. | ✅ | "Lightweight footnote" was rejected as signal-only documentation that adds maintenance surface. "Spec section on None-policy contract" was rejected as bigger amendment than Plan 13's internal-correctness scope warrants — a future plan that introduces a new user-facing tool surface can document the contract there. |
| D8 | Sequential per-task dispatch via `superpowers:subagent-driven-development`. Implementer → spec-reviewer → code-quality-reviewer → fix-loops between tasks. No parallelization even where the dependency graph allows it (Tasks 1, 4-5, and 6 are nominally independent). | ✅ | Plan 11 caught lessons 343/345/347/349/351 at review checkpoints; Plan 12 caught D2 whitelist drift, D5 sentinel test, D9 jargon split. Plan 13 is short enough that catch-rate value outweighs wall-clock savings. "Parallel where dep graph allows" was rejected for the same reason. |
| D9 | Plan 13 task count: 7 tasks. Tasks 1-3 architectural (None-policy / panel-domains drop / cross-domain-gate-store) + Task 4 brain_api hypothesis-confirm + Task 5 brain_api fix + Task 6 a11y token sweep + Task 7 closure. Splits brain_api diagnose+fix per D5 — lets findings reach plan-author before fix-shape locks. Mirrors Plan 12's 10-task scale. | ✅ | "6 tasks (one-shot brain_api)" was rejected per D5 reasoning. "8 tasks (pre-emptive a11y per-route split)" was rejected as defensive — if the token sweep clears all 9 violations, the per-route task is empty work. |
| D10 | Demo gate composition: 7 gates (one per item). (1) None-policy raises on both `list_domains` + `config_set` lenient branch; (2) `panel-domains.tsx` reads from `useDomainsStore`, no local domains state; (3) cross-domain-gate cross-instance pubsub jsdom or Playwright assertion; (4) all 13 brain_api failures pass after fix; (5) brain_api 4xx/5xx envelope shape regression-pin test passes; (6) Playwright a11y axe-core 0 color-contrast violations across all 8 routes; (7) Playwright a11y axe-core 0 violations on setup-wizard welcome step. Prints `PLAN 13 DEMO OK`. Mirrors Plan 11 (8 gates) / Plan 12 (7 gates) cadence. | ✅ | "5 gates (collapsed)" was rejected as less granular failure signal — collapsing makes diagnosis harder when a gate fails. "9 gates (most granular)" was rejected as higher gate-maintenance cost + longer demo runtime. |
| D11 | Owning subagents: brain-core-engineer (Task 1), brain-frontend-engineer (Tasks 2, 3, 6), brain-test-engineer (Task 4 diagnose, Task 7 closure), brain-mcp-engineer role-overloaded as brain-api-engineer per Plan 05 precedent (Task 5 brain_api fix). brain-ui-designer / brain-installer-engineer / brain-prompt-engineer no scope. | ✅ | Conservative split. "Pull brain-ui-designer into a11y" was rejected — Plan 07 Task 25C precedent says token-tier a11y fixes don't need designer co-ownership; if the implementer wants design review mid-task, brain-ui-designer can be pulled in ad hoc. "Split brain_api diagnose onto general-purpose" was rejected — brain-test-engineer has the testing-architecture context (TestClient / middleware patterns / fixture shapes) that the diagnose task needs to be efficient. |

The implementer routes any unrecognized rule edge case (D1 alternative None-policy seam discovered mid-audit, D3 alternative store shape, D4 alternative regression-pin pinning location, D5 hypothesis falsified mid-diagnose, D6 alternative token-vs-route fix shape, D9 alternative task split) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/tools/
│   ├── list_domains.py                 # MODIFY: tighten _configured_slugs + _active_domain to raise on ctx.config is None (D1)
│   ├── config_set.py                   # MODIFY: tighten lines 317-327 lenient cfg is None branch to raise (D1)
│   └── apply_patch.py                  # MODIFY: drop stale "Mirrors brain_config_get approach" docstring (D1 scope-adjacent)
└── tests/tools/
    ├── test_list_domains.py            # MODIFY: + strict-policy pin test; rewrite cases that seeded ctx.config=None
    ├── test_config_set.py              # MODIFY: + strict-policy pin test; rewrite cases that seeded ctx.config=None
    └── test_apply_patch.py             # MODIFY: docstring assertion if any test pinned the old wording

packages/brain_api/
├── src/brain_api/                      # MODIFY: TBD per Task 4 hypothesis-confirm findings (likely middleware or TestClient setup; expected: OriginHostMiddleware drift since Plan 11 era)
└── tests/
    ├── test_errors.py                  # MODIFY: 8 failures should pass after fix
    ├── test_auth_dependency.py         # MODIFY: 4 failures should pass after fix
    ├── test_context.py                 # MODIFY: 1 failure should pass after fix (test_get_ctx_dependency_resolves)
    ├── test_ws_chat_handshake.py       # MODIFY: 1 failure should pass after fix (test_handshake_rejects_bad_thread_id)
    └── test_envelope_shape_parity.py   # NEW: regression-pin asserting 4xx/5xx envelope shape parity at the drift point (D4)

apps/brain_web/
├── src/lib/state/
│   └── cross-domain-gate-store.ts      # NEW: zustand store for privacyRailed + acknowledged (D3)
├── src/lib/hooks/
│   └── use-cross-domain-gate.ts        # MODIFY: rewrite as zustand selector
├── src/components/settings/
│   └── panel-domains.tsx               # MODIFY: drop local domains state, read from useDomainsStore (D2)
├── src/styles/
│   └── globals.css                     # MODIFY: token nudges per Plan 07 Task 25C precedent (D6)
└── tests/
    ├── unit/
    │   ├── panel-domains-store-only.test.tsx   # NEW: assert no local state, only store reads (D2)
    │   └── use-cross-domain-gate-store.test.ts  # NEW: cross-instance pubsub assertion (D3)
    └── e2e/
        └── a11y.spec.ts                # MODIFY: re-affirm hard fail on color-contrast across 8 routes + setup-wizard (D6)

scripts/
└── demo-plan-13.py                     # NEW: 7-gate demo per the demo gate above

tasks/
├── plans/13-cross-instance-cleanup-and-test-debt.md   # this file
├── lessons.md                          # MODIFY: + Plan 13 closure section
└── todo.md                             # MODIFY: row 13 → ✅ Complete; remove Plan 13 candidate-scope tail; add Plan 14 candidate-scope tail
```

Spec / user-guide files NOT modified per D7.

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 11 + 12. Every implementer task MUST end with this checklist before reporting DONE.

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core` (or whichever package)
3. **uv `UF_HIDDEN` workaround** (lesson 341 + Plan 12 refinement): `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` — clamp BOTH `.pth` files in the SAME COMMAND LINE as the python invocation; do NOT rely on `uv run` (re-syncs and re-hides). When the `chflags`-then-pytest recipe still fails (Spotlight re-hide cadence is sub-second under `~/Documents/Code/...`), escape hatch is `PYTHONPATH=packages/brain_core/src:packages/brain_mcp/src:packages/brain_api/src:packages/brain_cli/src .venv/bin/python -m pytest ...`.
4. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions (or equivalent chflags-prefixed invocation)
5. `cd packages/<pkg> && uv run mypy src tests && cd -` — strict clean
6. `uv run ruff check . && uv run ruff format --check .` — clean
7. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
8. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check in the spec is invariant-based, not total-based.
9. **Browser-in-the-loop verification** (CLAUDE.md "Verification Before Done") for any task that touches a UI surface (Tasks 2, 3, 6): start brain, take screenshots of the relevant flows pre and post change, attach to per-task review. **Production-shape integration test** (lesson 343) for Task 5: the regression-pin test must be production-shape — assert against the real middleware stack, not a mock.
10. `git status` — clean after commit

Any failure in 4–9 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — None-policy strictness on `list_domains` + `config_set.py:317-327`

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/list_domains.py`
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py` (lines 317-327)
- Modify: `packages/brain_core/src/brain_core/tools/apply_patch.py` (`_resolve_config` docstring; D1 scope-adjacent)
- Modify: `packages/brain_core/tests/tools/test_list_domains.py`
- Modify: `packages/brain_core/tests/tools/test_config_set.py`
- Modify: `packages/brain_core/tests/tools/test_apply_patch.py` (only if a test pins the old docstring wording)

**Goal:** Eliminate the lenient `ctx.config is None` branches that Plan 11 lesson 343 + Plan 12 D5 audit named. Match `config_get`'s strict policy (raise `RuntimeError` with the same wording). Production-shape paths post-Plan 12 D6 always supply Config; the lenient branches are dead code.

**What to do:**
1. **list_domains audit.** Open `packages/brain_core/src/brain_core/tools/list_domains.py`. Locate `_configured_slugs` and `_active_domain` (or whatever the helper functions are named in the current file — read first). Each one currently has a branch like `if ctx.config is None: return DEFAULT_DOMAINS` or similar. Replace with `if ctx.config is None: raise RuntimeError("ctx.config is not set; this is a lifecycle violation. brain_core tools require a Config-bearing ToolContext.")` — match `config_get.py`'s exact error message verbatim (read `config_get.py` first to copy the wording).
2. **config_set strict branch.** Open `packages/brain_core/src/brain_core/tools/config_set.py`. Locate the lenient `cfg is None` no-op branch around lines 317-327 (read first to confirm the exact line range — it may have shifted). Replace the no-op with the same `raise RuntimeError(...)` wording from step 1.
3. **apply_patch docstring (scope-adjacent cleanup, Plan 13 candidate scope item #1).** Open `packages/brain_core/src/brain_core/tools/apply_patch.py`. Locate `_resolve_config` (function signature: probably `def _resolve_config(ctx: ToolContext) -> Config`). The docstring includes a stale phrase like "Mirrors the brain_config_get approach" — Plan 12 Task 3 changed `brain_config_get` to read `ctx.config` directly, so the mirror reference is no longer accurate. Update the docstring to describe the function's actual behavior (resolves config from `ctx.config` with defensive defaults if needed) and drop the cross-tool reference.
4. **Unit-test audit.** `grep -rn "ctx.config=None\|ctx.config = None\|ctx_with_no_config\|ToolContext(config=None)" packages/brain_core/tests/` — any test fixture that explicitly seeds `ctx.config=None` to exercise the lenient branch needs rewriting. Replace each with a real `Config(...)` fixture matching the production shape; if the test was specifically testing the no-op behavior (which is now incorrect behavior), delete the test and replace with a positive test asserting the new strict raise.
5. **New pin tests.**
   - In `test_list_domains.py`: `test_list_domains_raises_when_ctx_config_none` — calls `list_domains(...)` with `ctx.config=None`, asserts `RuntimeError` with the matching error message.
   - In `test_config_set.py`: `test_config_set_raises_when_ctx_config_none` — same shape, against `brain_config_set`.
6. **Defensive grep after edits.** `grep -rn "DEFAULT_DOMAINS" packages/brain_core/src/brain_core/tools/list_domains.py` should return zero (or one — only if a comment references the removed branch); confirm the silent fallback is gone. `grep -rn "if cfg is None\|if ctx.config is None" packages/brain_core/src/brain_core/tools/{list_domains,config_set}.py` should each return one match (the new raise) — not multiple.

**Spec for the new pin tests:**
- Both new tests construct a `ToolContext(config=None, ...)` (or whatever the canonical shape is — read existing tests first for the fixture pattern).
- Both assert `pytest.raises(RuntimeError, match="ctx.config is not set")`.
- Error message wording matches `config_get.py`'s wording exactly (a `test_error_messages_match_config_get` parametrized over the three tools is a nice-to-have if it doesn't double the file size).

**Per-task review:** the audit step's findings list is part of the review artifact — even if zero additional tests need rewriting beyond the obvious, the sweep IS the value. Existing tests in `test_list_domains.py` and `test_config_set.py` that pre-existed Plan 13 must still pass post-edit (they assert positive paths, not the lenient-branch behavior; the rewrite only touches tests that explicitly seeded `ctx.config=None`). `apply_patch.py` docstring change is a cosmetic edit; if `test_apply_patch.py` doesn't pin the docstring, no test edit needed there. Per-task self-review checklist runs to completion before reporting DONE.

---

## Task 2 — Drop `panel-domains.tsx` local `domains: string[]` state

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx`
- Create: `apps/brain_web/tests/unit/panel-domains-store-only.test.tsx`

**Goal:** Per D2, eliminate the parallel local `domains: string[]` state Plan 12 Task 5 + Task 8 reviews flagged. Read directly from `useDomainsStore` (Plan 12 Task 5 zustand store). Single source of truth; matches the simplification Plan 12 made for `useDomains()` itself.

**What to do:**
1. **Audit local state.** Open `panel-domains.tsx`. `grep` for `useState<.*omain` and `useState<string\[\]>` — identify the local state declaration that holds the parallel `domains: string[]`. Note its hydration source (likely a separate `refresh()` or `useEffect` call to `listDomains()`).
2. **Replace reads.** Every site in `panel-domains.tsx` that reads the local state replaces with `const { domains } = useDomains();` (the Plan 12 Task 5 selector). Audit downstream consumers in the file (per-row override editor, rename/delete dialogs, the active-domain dropdown from Plan 12 Task 8) — verify each works against the store-backed read.
3. **Drop hydration.** Remove the `useState` declaration, the `useEffect` (or `refresh()` call) that hydrated it, and any imports that become unused.
4. **Mutation paths.** Existing mutation paths (rename/delete/create) currently call `invalidateDomainsCache()` or equivalent. Plan 12 Task 5's zustand pattern: mutations should call `useDomainsStore.getState().refresh()` to re-fetch, OR `useDomainsStore.getState().setActiveDomainOptimistic(slug)` for active-domain changes. Audit and align — any mutation path that doesn't update the store after mutation is a bug; surface in per-task review.
5. **New pin test.** `panel-domains-store-only.test.tsx`: jsdom mount of `panel-domains.tsx` with a mocked `useDomainsStore` (set the store state directly via `useDomainsStore.setState(...)` in test setup); assert the rendered DOM reflects the store state without any `useEffect`-driven local hydration. Mutate the store mid-test; assert the DOM re-renders. Pin assertion: `screen.queryAllByTestId("domain-row")` count matches `useDomainsStore.getState().domains.length`.

**Per-task review:** browser verification — open brain, navigate to Settings → Domains, screenshot the panel rendering correctly. Rename a domain via the per-row editor; screenshot the panel updating in-place without a full page-reload (cross-instance pubsub from Plan 12 Task 5). Compare against pre-Plan-13 screenshot from `panel-domains.tsx` git history at HEAD~1 (any rendering difference indicates a regression). Existing Playwright `domains.spec.ts` should still pass (Plan 12 Task 5 already removed its `page.reload()` workaround; Task 2 should not re-introduce any).

---

## Task 3 — `cross-domain-gate-store.ts` new + `useCrossDomainGate` zustand refactor

**Files:**
- Create: `apps/brain_web/src/lib/state/cross-domain-gate-store.ts`
- Modify: `apps/brain_web/src/lib/hooks/use-cross-domain-gate.ts`
- Audit: `apps/brain_web/src/components/dialogs/cross-domain-modal.tsx`, chat-screen / new-chat-dialog (mountpoints from Plan 12 Task 9), Settings toggle on `panel-domains.tsx`
- Create: `apps/brain_web/tests/unit/use-cross-domain-gate-store.test.ts`

**Goal:** Per D3, eliminate the cross-instance state divergence Plan 12 Task 9 review flagged on `useCrossDomainGate`. Same shape as Plan 12 Task 5 fixed for `useDomains`: promote module-state cache to a zustand store; hook becomes a selector; mutations via the Settings toggle propagate to the chat-screen gate without remount.

**What to do:**
1. **Store creation.** New file `apps/brain_web/src/lib/state/cross-domain-gate-store.ts`. State shape: `{ privacyRailed: string[]; acknowledged: boolean; loaded: boolean; }`. Actions: `refresh: () => Promise<void>` (calls the existing API helper that returns these fields — likely `brainConfigGet` or a dedicated endpoint; read `lib/api/tools.ts` to confirm), `setAcknowledgedOptimistic: (value: boolean) => void` (for the Settings toggle to call before the round-trip completes). Mirror Plan 12 Task 5's `domains-store.ts` shape and conventions.
2. **Hook rewrite.** `use-cross-domain-gate.ts` becomes a thin selector: `export function useCrossDomainGate() { return useCrossDomainGateStore((state) => ({ privacyRailed: state.privacyRailed, acknowledged: state.acknowledged, ...derivedHelpers })); }`. The `shouldFireCrossDomainModal()` helper Plan 12 Task 9 introduced stays — it now reads from the store-backed selector instead of local state. On first mount in any consumer, if `state.loaded === false` it calls `useCrossDomainGateStore.getState().refresh()`.
3. **Settings toggle update.** In `panel-domains.tsx` (the "Show cross-domain warning" toggle from Plan 12 Task 9), after calling `setCrossDomainWarningAcknowledged(value)` API helper successfully, call `useCrossDomainGateStore.getState().setAcknowledgedOptimistic(value)` so the chat-screen's `useCrossDomainGate()` reflects the change immediately without remount.
4. **Audit chat-screen consumers.** Plan 12 Task 9 wired the modal trigger at chat-send time. Confirm the trigger reads from `useCrossDomainGate()` (now the store-backed selector); any path that read from local state needs to flow through the store.
5. **New pin test.** `use-cross-domain-gate-store.test.ts`: parametrized test with two consumer harnesses; each calls `useCrossDomainGate()` in a separate hook context; mutate via one consumer's `setAcknowledgedOptimistic`; assert the other consumer re-renders within the test tick with the new value. This is the cross-instance pubsub assertion D3 requires.

**Spec for `use-cross-domain-gate-store.test.ts`:**
- Fresh store: `useCrossDomainGateStore.getState()` returns `{ privacyRailed: [], acknowledged: false, loaded: false }`.
- After `refresh()` resolves with mock fetch returning `{ privacy_railed: ["personal"], cross_domain_warning_acknowledged: true }`, store reflects the response and `loaded === true`.
- Mounting two consumers; `setAcknowledgedOptimistic(false)` from one; assert the other re-renders with `acknowledged === false` (cross-instance pubsub).
- `refresh()` while a previous `refresh()` is in flight: serialize via store action (no double-fetch); pin the inFlight-flag-or-Promise-cache choice in implementer notes.
- `shouldFireCrossDomainModal(scope, store)` table: scope=`["research", "personal"]`, store has `privacyRailed=["personal"]` + `acknowledged=false` → returns `true`; same scope but `acknowledged=true` → `false`; scope=`["research", "work"]`, no rail in scope → `false`; scope=`["personal"]`, single-domain → `false`.

**Per-task review:** browser verification — open brain in two tabs (or a tab + Settings sidebar). Tab A: open chat with scope=`[research, personal]`, observe the modal fires. Acknowledge via the modal's "Don't show again" checkbox. Tab B: open Settings → Domains, observe the "Show cross-domain warning" toggle reflects the new state (toggle OFF / acknowledged ON). Toggle the switch back ON in Tab B. Tab A: attempt the same scope again; observe the modal returns. The screenshot triple is the verification artifact. Pre-Plan-13 screenshot would show Tab A NOT reflecting Tab B's change without a manual reload — Plan 13 fixes that. Existing Playwright `cross-domain-modal.spec.ts` should still pass (it acknowledges then reloads; the cross-instance pubsub is additive coverage).

---

## Task 4 — brain_api 13-failure hypothesis-confirm

**Files:**
- Read-only audit: `packages/brain_api/src/brain_api/middleware/origin_host.py` (or wherever OriginHostMiddleware lives — confirm path), `packages/brain_api/src/brain_api/lifespan.py`, `packages/brain_api/tests/_helpers.py` (TestClient setup), the 4 failing test files
- Document: `tasks/plans/13-cross-instance-cleanup-and-test-debt.md` (this file's per-task review section, populated at task close)

**Goal:** Per D5, confirm (or refute) the OriginHostMiddleware/TestClient drift hypothesis from Plan 12 closure. This is a **diagnose-only** task — no production code changes; no test fixes. The artifact is a findings document that locks Task 5's fix shape.

**What to do:**
1. **Reproduce.** Run the failing tests in isolation: `chflags 0 .../_editable_impl_*.pth && PYTHONPATH=... .venv/bin/python -m pytest packages/brain_api/tests/test_errors.py packages/brain_api/tests/test_auth_dependency.py packages/brain_api/tests/test_context.py::test_get_ctx_dependency_resolves packages/brain_api/tests/test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id -v`. Capture the full output. Confirm 13 failures, all asserting expected 4xx/5xx status codes (or WS close codes) but receiving 200.
2. **Bisect.** `git log --oneline d7dbf66..HEAD -- packages/brain_api/` returns zero commits during Plan 12 (confirmed in Plan 12 closure). Step further back: `git log --oneline plan-10-configurable-domains..plan-12-settings-ux-and-cleanup -- packages/brain_api/` — identify commits during Plan 11 that touched brain_api middleware, auth, or test fixtures. Particularly: any commit that touched `OriginHostMiddleware`, `BaseHTTPMiddleware`, `TestClient` setup, `Host` / `Origin` header handling, or response envelope shape.
3. **Hypothesis-test 1: OriginHostMiddleware drift.** Read the current `OriginHostMiddleware` implementation. Plan 05 lessons (`BaseHTTPMiddleware silently skips non-HTTP scopes`, `TestClient WS hardcoded ws://testserver`) say middleware enforcement should be ASGI-level, not BaseHTTPMiddleware-level. Compare against the Plan 05 close shape: did anyone re-introduce `BaseHTTPMiddleware` for this middleware in Plan 11? If so, that explains why HTTP-only tests pass (BaseHTTPMiddleware works for HTTP) but Origin-rejection or auth-rejection paths fail (when they're tested via the TestClient HTTP path with explicit headers, the middleware behavior may have shifted).
4. **Hypothesis-test 2: TestClient configuration drift.** Read `tests/_helpers.py` (or wherever the TestClient fixture lives). Plan 05 pinned `headers={"Host": "localhost"}` for WS tests; if HTTP fixtures in test_errors / test_auth_dependency lost their Host or Origin headers somewhere in Plan 11, the middleware now lets requests through that pre-Plan-11 it would have rejected (status 200 instead of 4xx). Confirm by inspecting the failing tests' fixture usage.
5. **Hypothesis-test 3: Response envelope shape drift.** Plan 05 Batch A landed `{"error", "message", "detail"}` envelope shape parity at middleware + route + 500 layer. If a Plan 11 commit re-broke the parity (e.g., middleware emits two-key body again), tests that assert specific error envelope keys would fail with status 200 if the route layer's 4xx body got mistakenly served as 200 elsewhere — less likely but check.
6. **Hypothesis-test 4: dependency_overrides drift.** FastAPI test fixtures often use `app.dependency_overrides[get_ctx] = ...` to inject test contexts. If a Plan 11 commit changed the `get_ctx` dependency's signature or behavior, tests that override it might silently pass through a "default" context that doesn't enforce auth, returning 200.
7. **Categorize the 13 failures.** For each of the 13 tests, pin the hypothesis it best matches. If all 13 share one root cause → confirm the single-fix shape. If 2-3 hypotheses each explain different subsets → document the multi-fix shape and surface to plan-author for D5 sign-off on whether to split Task 5 into multiple sub-fixes.
8. **Findings document.** Append a "Task 4 findings" subsection to this plan file's per-task review section. Include: (a) confirmed root cause(s); (b) commit(s) that introduced the regression; (c) proposed Task 5 fix shape (concrete edits to specific files); (d) regression-pin test design (which assertions, against which middleware/route layer); (e) any open questions for plan-author sign-off.

**Per-task review:** no code changes; no test fixes. The findings document IS the artifact. Plan-author reviews findings before Task 5 dispatches; if the hypothesis is wrong or the fix shape is non-trivial, plan-author signs off on the new D-locked decision before Task 5 starts. Re-running the failing tests after Task 5 lands is gate 4 of the demo; Task 4 doesn't re-run them.

---

## Task 5 — brain_api fix + 4xx/5xx envelope shape regression-pin test

**Files:**
- Modify: TBD per Task 4 findings (likely `packages/brain_api/src/brain_api/middleware/origin_host.py` or `tests/_helpers.py` or both)
- Modify: `packages/brain_api/tests/test_errors.py`, `tests/test_auth_dependency.py`, `tests/test_context.py`, `tests/test_ws_chat_handshake.py` (only if the fixtures themselves need updating — production code change should make all 13 tests pass without touching test logic)
- Create: `packages/brain_api/tests/test_envelope_shape_parity.py`

**Goal:** Per D4, fix all 13 brain_api failures + add a regression-pin test asserting 4xx/5xx response envelope shape parity at the suspected drift point. Closes the Plan 11-era test debt fully. Production-shape integration test (Plan 11 lesson 343 + Plan 12 D6) is the regression guard.

**What to do:**
1. **Apply Task 4's locked fix shape.** Read the Task 4 findings document. Apply the proposed edits to the specific files Task 4 identified. If Task 4 surfaced multiple root causes and the fix shape is non-trivial, this task may dispatch as 2 sub-fixes within sequential review — confirm with plan-author before splitting.
2. **Run the 13 failing tests.** `chflags 0 .../_editable_impl_*.pth && PYTHONPATH=... .venv/bin/python -m pytest packages/brain_api/tests/test_errors.py packages/brain_api/tests/test_auth_dependency.py packages/brain_api/tests/test_context.py::test_get_ctx_dependency_resolves packages/brain_api/tests/test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id -v`. All 13 should pass with the expected status codes.
3. **Run full brain_api pytest suite.** `chflags 0 .../_editable_impl_*.pth && PYTHONPATH=... .venv/bin/python -m pytest packages/brain_api -q`. Assert no new regressions introduced by the fix. Pin pass count.
4. **Regression-pin test.** New `test_envelope_shape_parity.py` in `packages/brain_api/tests/`. Asserts the `{"error": str, "message": str, "detail": dict | None}` envelope shape at three layers: (a) middleware-level rejection (e.g., bad Origin → asserts the 403 body shape); (b) route-level rejection (e.g., bad input → asserts the 400 body shape); (c) 500 path (e.g., trigger a route error via dependency_overrides → asserts the 500 body shape). Each assertion: `assert set(body.keys()) == {"error", "message", "detail"}`. The "drift point" Task 4 identifies determines which middleware/layer gets the most assertion coverage. Mirror Plan 05 Batch A's envelope shape pin test pattern.
5. **Playwright e2e re-run.** Existing `tests/e2e/` Playwright suite should still pass (production-shape — Plan 11/12 era didn't reproduce the 13 failures). Confirm via `cd apps/brain_web && PYTHONPATH=... npx playwright test`. Production behavior is unchanged; only test-time configuration drift is fixed.

**Spec for `test_envelope_shape_parity.py`:**
- `test_origin_host_middleware_envelope_shape`: bad Origin → 403 → `set(body.keys()) == {"error", "message", "detail"}`.
- `test_route_400_envelope_shape`: invalid input to a known route → 400 → same shape.
- `test_route_500_envelope_shape`: dependency_override raises → 500 → same shape.
- `test_ws_handshake_close_code_parity`: bad thread_id → WS close 1008 (matches `test_handshake_rejects_bad_thread_id` post-fix expectation).
- `test_auth_403_envelope_shape`: missing token → 403 → same shape.

**Per-task review:** production-shape integration test discipline (lesson 343 + D6). The regression-pin test must build the real app via `create_app()` and exercise it through TestClient with production-shape fixtures (real Headers, real middleware stack). NOT mocked/patched at the middleware layer — the whole point is asserting the middleware does the right thing. If the implementer is tempted to mock something to make the test pass, halt and surface to plan-author. Browser verification not applicable (no UI surface); the production-shape integration test IS the verification artifact. Run pytest with `--tb=short` and capture passing output for the per-task review log.

---

## Task 6 — a11y color-contrast token sweep

**Files:**
- Modify: `apps/brain_web/src/styles/globals.css` (token nudges per D6)
- Audit: `apps/brain_web/src/styles/` (any other CSS file that could shadow the token nudges — Tailwind config, theme files)
- Modify: `apps/brain_web/tests/e2e/a11y.spec.ts` (re-affirm hard fail)
- Audit: `apps/brain_web/tests/e2e/setup-wizard.spec.ts` (or wherever the setup-wizard a11y assertion lives — confirm path)

**Goal:** Per D6, clear all 9 axe-core color-contrast violations (8 routes + 1 setup-wizard) via token sweep. Mirror Plan 07 Task 25C precedent. Re-affirm the e2e a11y gate is genuinely hard-failing so future regressions can't slip past silently.

**What to do:**
1. **Reproduce.** Run `cd apps/brain_web && npx playwright test e2e/a11y.spec.ts e2e/setup-wizard.spec.ts -v`. Capture the per-route violation details: which CSS variable / color combination is failing the WCAG 2.2 AA 4.5:1 (normal text) or 3:1 (large text) ratio, and by how much. axe-core reports the foreground/background hex values + the actual contrast ratio + the required ratio.
2. **Identify the smallest token-set fix.** From the per-route output, the violations likely cluster around `--text-muted` / `--text-dim` / `--accent` / `--surface-3` (Plan 07 Task 25C's domain). Decide on the minimal set of token nudges that brings all violations above the threshold. Use a contrast-ratio calculator (axe-core reports the current ratio; aim for ratio + 10% margin to avoid borderline cases).
3. **Apply nudges.** Edit `globals.css`. For each token to nudge, update both light-mode and dark-mode values. Mirror Plan 07 Task 25C's pattern: alpha-channel adjustments on muted/dim tokens, hex-replacement on the `--accent` mapping if needed.
4. **Re-run.** `npx playwright test e2e/a11y.spec.ts e2e/setup-wizard.spec.ts -v`. If all 9 violations clear, done. If any survive, follow up per-route within the same task — use route-specific CSS overrides ONLY if the token nudge breaks something visually elsewhere (the per-route override is a last resort; the token approach is single-source-of-truth).
5. **Hard-fail gate.** Open `tests/e2e/a11y.spec.ts`. Confirm the spec is configured to FAIL (not warn) on color-contrast violations. If the gate has been weakened to a warning at any point post-Plan-07-Task-25C, restore it to hard fail. Document the find in per-task review notes (the regression that allowed 9 violations to land must have either bypassed CI or been silenced; identifying which is part of the fix).
6. **CI check.** Confirm `tests/e2e/a11y.spec.ts` is in the CI run set. If not, add it. The Plan 09 close note said "Plan 09 should not relax it" — Plan 13 re-instates that contract.

**Spec for the a11y verification post-fix:**
- 8 routes pass axe-core with 0 color-contrast violations.
- 1 setup-wizard welcome step passes with 0 color-contrast violations.
- Other axe-core rule families (aria-valid-attr-value, label-content-name-mismatch, etc.) — Plan 13 does NOT extend coverage; only color-contrast is in scope. If other rules surface during the sweep, document and defer.

**Per-task review:** browser verification — load the 8 routes + setup-wizard in the actual browser, screenshot each at default zoom + 200% zoom (a11y best practice). Confirm visual aesthetics didn't degrade — the token nudges should be subtle; if any UI element looks "off" post-nudge, design review. Pre-Plan-13 screenshots from `apps/brain_web/` git history at HEAD~1 are the comparison baseline. Existing Playwright a11y spec must pass without `expect.soft` or `test.skip` modifiers anywhere — the gate is hard fail per D6.

---

## Task 7 — Closure: demo + e2e + lessons

**Files:**
- Create: `scripts/demo-plan-13.py`
- Modify: `tasks/lessons.md` (Plan 13 closure section)
- Modify: `tasks/todo.md` (row 13 → ✅; remove Plan 13 candidate-scope; add Plan 14 candidate-scope)
- Audit: existing Playwright specs for any test that should be added or strengthened by Plan 13 (e.g., a cross-tab pubsub spec for Task 3, a None-policy spec for Task 1)

**Goal:** Land the 7-gate demo from the plan header. Lessons capture. todo.md update. No new test files in this task — Tasks 1, 2, 3, 5, 6 already added their own pin tests; Task 7's Playwright walks (if any) are coverage extensions, not new contract tests.

**What to do:**
1. **demo-plan-13.py.** Mirror `scripts/demo-plan-12.py`'s structure. Build the 7 gates:
   - **Gate 1 (None-policy):** Import `list_domains` and `brain_config_set`; build a `ToolContext(config=None)`; assert each raises `RuntimeError` with the matching error message wording. Also assert `from brain_core.tools.config_get import _resolve_config; _resolve_config(ToolContext(config=None))` raises (sanity check that `config_get`'s policy is unchanged).
   - **Gate 2 (panel-domains store-only):** This is a frontend assertion. Either (a) run a vitest test that mounts `panel-domains.tsx` and asserts the rendered DOM tracks `useDomainsStore.getState().domains` count exactly, or (b) run a Playwright assertion that mutates the store via a test hook and observes the panel re-render. Implementer's call at task time — mirror gate 4 from Plan 12 demo.
   - **Gate 3 (cross-domain-gate pubsub):** jsdom test (or Playwright) that mounts two `useCrossDomainGate()` consumers; mutates `acknowledged` via one; asserts the other reflects the change within 100ms. Mirror Plan 12 demo gate 4.
   - **Gate 4 (brain_api re-pass):** Run `pytest packages/brain_api/tests/test_errors.py packages/brain_api/tests/test_auth_dependency.py packages/brain_api/tests/test_context.py::test_get_ctx_dependency_resolves packages/brain_api/tests/test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id`; assert exit code 0 and 13/13 passing.
   - **Gate 5 (envelope shape parity):** Run `pytest packages/brain_api/tests/test_envelope_shape_parity.py`; assert exit code 0 and full pass.
   - **Gate 6 (a11y axe-core 8 routes):** Run `npx playwright test apps/brain_web/tests/e2e/a11y.spec.ts`; assert exit code 0 and 0 color-contrast violations on each of `/chat`, `/inbox`, `/browse`, `/pending`, `/bulk`, `/settings/general`, `/settings/providers`, `/settings/domains`.
   - **Gate 7 (a11y setup-wizard):** Run `npx playwright test apps/brain_web/tests/e2e/setup-wizard.spec.ts`; assert exit code 0 and 0 color-contrast violations on the welcome step.

   Demo script prints `PLAN 13 DEMO OK` on exit 0. Use the same temp-vault fixture pattern as `scripts/demo-plan-12.py` for any gate that needs an isolated vault.
2. **Demo script execution prefix** for the implementer: `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python scripts/demo-plan-13.py` per lesson 341. The Playwright e2e specs run via `cd apps/brain_web && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src npx playwright test` to bypass `uv run`'s re-hide behavior on the brain_api webServer.
3. **Lessons capture.** Mirror the Plan 11 + Plan 12 closure-section format. Closure summary, then one paragraph per lesson worth carrying forward. Likely lesson candidates (implementer surfaces actuals):
   - Whether the Task 1 None-policy audit found additional offenders beyond `list_domains` + `config_set:317-327` (e.g., did `apply_patch.py:_resolve_config` actually have the same lenient branch under the docstring wording, or was the docstring stale only?).
   - What Task 4's hypothesis-confirm actually surfaced (OriginHostMiddleware drift, TestClient fixture drift, dependency_override drift, or something else). The diagnose-first discipline (D5) will either prove or disprove the Plan 12 closure hypothesis; the actual root cause is the lesson.
   - Whether any chflags / uv quirks surfaced during demo execution that weren't already captured in lessons 341 + Plan 12 refinements.
   - Whether the a11y token sweep needed any per-route fixes (D6's "follow-up per-route if needed" path) — if yes, what made those routes' violations route-specific rather than token-addressable.
   - Whether the cross-domain-gate-store promotion (Task 3) needed touch-ups beyond the `useCrossDomainGate` hook (e.g., did the chat-screen trigger gate or the Settings toggle need any wiring updates beyond the hook rewrite?).
   - Whether the e2e a11y gate's hard-fail discipline was actually re-instated (Task 6 step 5) or the gate was already hard-failing and the regression had a different cause.
4. **`tasks/todo.md` update.** Row 13 → ✅ Complete with the same shape as row 12. Remove the "Plan 13 candidate scope (forwarded from Plan 12)" tail section (closed). If implementer-surfaced backlog items remain, add a fresh "Plan 14 candidate scope (forwarded from Plan 13)" tail block in the same shape. Pre-populate Plan 14 candidate scope with: (a) the 7 small cleanups from Plan 12 candidate scope (NOT covered by Plan 13: docstring stale was Task 1 scope-adjacent so DROP it from carry-forward; plan-text drift watch is a lesson; brain start chflags; jargon split; toast wording; pushToast defensive; pendingSendRef.mode); (b) the bigger architectural moves from Plan 13's NOT-DOING section (per-domain budget caps; per-domain rate limits; repair-config UI; hot-reload; validate_assignment=True; per-domain autonomy categories; "Set as default" topbar button; per-thread cross-domain confirmation; generic ctx.config lint rule; migration tool; generic zustand promotion across other hooks).

**Per-task review:** demo gates 1-7 all green; gate failures during the demo are debugging blockers, not "ship as-is" outcomes. The lessons capture is the Plan 13 retrospective; the todo.md update is the closure handoff. Per-task self-review checklist runs to completion before reporting DONE. Final test counts: pytest pass count + vitest pass count + Playwright pass count, all to be filled in (Plan 13 is expected to RAISE pytest count by 13 brain_api tests + ~5 new pin tests; vitest count by ~3 new pin tests; Playwright count unchanged but a11y route coverage extends to 0-violation hard fail).

---

## Review (pending)

To be filled in on closure following the Plan 10 + 11 + 12 format:
- **Tag:** `plan-13-cross-instance-cleanup-and-test-debt` (cut on green demo).
- **Closes:** the four cross-instance / lifecycle anti-pattern items from Plan 13 candidate scope (#A1 None-policy strictness on list_domains + config_set; #A2 panel-domains local state drop; #A3 cross-domain-gate-store pubsub; scope-adjacent: apply_patch docstring), AND the brain_api 13-failure pre-existing test debt (#B1), AND the 9 axe-core a11y color-contrast violations (#B2). Plan 13 candidate-scope tail block in `tasks/todo.md` removed; Plan 14 candidate-scope tail added.
- **Bumps:** tool count unchanged. Schema unchanged (Plan 13 is pure correctness + test debt; no field add/remove). brain_api test count rises by 13 newly-passing tests + ~5 new envelope-shape-parity assertions. brain_web vitest count rises by ~3 new pin tests (panel-domains store-only + use-cross-domain-gate-store cross-instance + any others surfaced). Playwright count unchanged but axe-core a11y gate is now genuinely hard-failing across 8 routes + setup-wizard.
- **Verification:** all 7 demo gates green (`scripts/demo-plan-13.py` → `PLAN 13 DEMO OK`); pytest count + vitest count + Playwright count to be filled in.
- **Backlog forward:** Plan 14 candidate scope pre-populated per Task 7 step 4. Themes: small-cleanup polish thread + bigger architectural moves (per-domain budget caps; per-domain rate limits; repair-config UI; cross-process hot-reload; validate_assignment=True; per-domain autonomy if requested; generic ctx.config lint rule).
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 13" feed Plan 14's authoring.

---

**End of Plan 13.**
