# Plan 15 — CI green + polish pass

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Plan 15 D11 locks **sequential per-task dispatch with two-stage review** (Plan 11 + 12 + 13 + 14 discipline) — do NOT parallelize even when the dependency graph allows it (Tasks 1, 2-3, 4, 5, 6, 7, 8, 9, 10 are mostly independent).

**Goal:** Restore green CI on BOTH workflow files (the existing `CI` ruff+mypy+pytest gate has been red since Plan 11; the new `Playwright` gate failed Windows on Plan 14's first push) AND sweep the deferred small cleanups carried from Plan 12 + Plan 13 reviews. Two threads in one cohesive plan:

1. **#A1 (CI green) — Clear pre-existing ruff debt.** 76 ruff violations on `main` (67 auto-fixable + 9 manual). Predates Plan 11 close; implementer reports across Plan 11/12/13/14 said "ruff clean" each time because they ran `ruff check packages/<changed-pkg>/` (current package only) but CI runs `ruff check .` (whole repo) — per-package vs whole-repo dev/CI gap. **D1 (locked 2026-04-29):** auto-fix + manual fix to clear all 76 (3 `match="ctx.config"` → `match=r"ctx\.config"` in test files; 6 `×` → `x` in `scripts/demo-plan-{10,11,13}.py` strings/docstrings).

2. **#A2 (CI green) — Windows Playwright chat composer fix.** Plan 14's first CI push surfaced Windows-specific failure on 2 specs (`a11y-populated.spec.ts:223` fork-thread dialog + `chat-turn.spec.ts:40`). Both share `getByRole('textbox', { name: 'Message brain' })` not found within timeout. Mac CI ✅ on first try; Windows ❌. Backend started cleanly on Windows (e2e-backend.ps1 ran, vault created, e2e_mode=1) — so brain_api boot ✅ but the static-export rendered chat screen doesn't surface the composer. Hypotheses: hydration error / static-export Windows quirk / accessible-name locale diff / WS upgrade timing. **D2 (locked 2026-04-29):** Plan 13 Task 4/5 hypothesis-confirm-first pattern — Task 2 diagnose-only; Task 3 fix per locked findings.

3. **#B1 (polish) — `brain start` CLI drops `uv run` from supervisor.** Plan 12 Task 8 implementer's escape-hatch was direct `python -m uvicorn` invocation because `brain start` re-syncs uv mid-bootstrap and re-hides the editable .pth files (lesson 341). **D3 (locked 2026-04-29):** replace `uv run uvicorn` in `brain_cli.commands.start` with direct `.venv/bin/python -m uvicorn` invocation (matches the chflags+PYTHONPATH escape hatch every other tool already uses).

4. **#B2 (polish) — Modal vs Settings jargon split.** Plan 12 Task 7 implementer left this asymmetric: cross-domain modal copy uses "private domain" / "kept private by default" (plain-language); Settings → Domains uses "Privacy rail" + "Privacy-railed" (power-user term-of-art). **D4 (locked 2026-04-29):** "Privacy-railed" everywhere; aligns with Plan 11 D11's `Config.privacy_railed: list[str]` field; adds a one-line glossary tooltip ("domains marked as private; never appear in default queries").

5. **#B3 (polish) — Active-domain dropdown toast: conditional CTA + pushToast outside catch.** Plan 12 Task 8 review I1+I2 flagged: (a) toast surfaces `${detail} Pick a different domain.` on ALL errors but transport failures (network drop, 502, CORS) don't have a different-domain remedy; (b) `pushToast({...danger...})` sits inside the catch block but pushToast is a zustand setter that can't realistically throw. **D5 (locked 2026-04-29):** conditional CTA (validator-error → "Pick a different domain"; transport-error → "Try again") + move pushToast outside catch (defensive scoping).

6. **#B4 (polish) — `pendingSendRef.mode` dead field used explicitly.** Plan 12 Task 9 review caught this: `pendingSendRef.current.mode` is captured at click-time but never read by `dispatchSend` (which reads live closure `mode`). **D6 (locked 2026-04-29):** use it explicitly. The captured-at-click-time intent is load-bearing for cross-domain modal acknowledgment timing — `mode` could change between modal-show and modal-acknowledge, and the click-time value is the right one to honor.

7. **#B5 (polish + architectural) — `_NO_CONFIG_MESSAGE` extraction to `tools/_errors.py`.** Plan 13 Task 1 review I2 flagged the threshold met: 3 sites (`config_get.py`, `list_domains.py`, `config_set.py:317-327`) plus a 4th similar pattern in Plan 14 Task 1's `SPAStaticFiles.__call__` non-http guard. **D7 (locked 2026-04-29):** new private module `packages/brain_core/src/brain_core/tools/_errors.py` with `raise_if_no_config(ctx, tool_name)` helper. The 3 brain_core call sites refactor to call the helper. SPAStaticFiles stays separate (different package; different scope-type guard).

8. **#B6 (polish + test discipline) — `_mk_ctx` test fixture signature alignment.** Plan 13 Task 1 review M3 flagged inconsistency: `test_list_domains.py` defaults `config=None`; `test_list_domains_active.py` requires `config: Config | None`; `test_config_set.py` defaults `config=None`. **D8 (locked 2026-04-29):** all three test files require explicit `config: Config` (no default). Mirrors Plan 13 Task 1's None-policy strictness; every test call site declares its config shape.

9. **#B7 (polish + lessons) — `apply_patch._resolve_config` Plan 07 deferral docstring.** Plan 13 Task 1 review M5 flagged: `apply_patch.py:121` says "Plan 07 Task 5 will replace the body with a real loader call" — that TODO has been deferred since Plan 07. **D9 (implicit, no decision needed):** drop the Plan 07 reference; describe the function's actual current behavior (snapshot Config with vault_root overlay). The "real loader call" deferral is genuine Plan 16+ territory — separate task from this docstring cleanup.

10. **(closure) — Demo + e2e + lessons closure.** 12-gate demo per D10. Plan 15 candidate-scope tail block in `tasks/todo.md` removed; Plan 16 candidate-scope tail block added. Per D11, Plan 15 does NOT touch spec text (CI + polish only).

**Architecture.** Two-track plan: CI green (#A1, #A2 — Tasks 1+2+3) + small-cleanup polish pass (#B1–B7 — Tasks 4-10). Tasks are mostly independent; D11 locks sequential dispatch anyway because Plan 11/12/13/14 review-discipline catch-rate justifies the wall-clock cost. Demo gate composition (D10) is one assertion per item plus regression + sentinel = 12 gates.

**Tech Stack.** Same gates as Plan 11 + 12 + 13 + 14 — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright. GitHub Actions (Plan 14 Task 7+8). No new third-party deps.

**Demo gate.** `scripts/demo-plan-15.py` (chflags-prefixed per lesson 341) walks 12 gates:

1. **ruff clean** (A1): `uv run ruff check . && uv run ruff format --check .` exit 0; assert 0 violations across whole repo.
2. **brain_api full pytest** (regression guard): assert 1169+ passed, no new regressions vs Plan 14 baseline.
3. **brain_web vitest** (regression guard): assert 334+ passed.
4. **Local Playwright suite** (regression): full e2e suite green; ingest-drag-drop stable (Plan 14 Task 6's waitForResponse fix unchanged).
5. **Windows Playwright on CI** (A2 verification): the explicit gate Plan 14 Task 9 deferred to first-CI-run observation; Plan 15 Task 3 fix lands; assert windows-2022 leg of `25xxxxx` workflow run completes green (the gate is the CI run conclusion; demo script can `gh run view --json conclusion`).
6. **`brain start` works without manual chflags** (B1): start brain in temp env (no chflags pre-step); assert HTTP `GET /api/healthz` responds 200; assert no `ImportError: brain_core` on stderr.
7. **Modal + Settings jargon consistency** (B2): grep both surfaces for "private domain" vs "Privacy-railed"; assert only "Privacy-railed" appears post-Task 5.
8. **Active-domain toast CTA conditional** (B3): unit test asserting validator-error → "Pick a different domain"; transport-error → "Try again"; pushToast call outside catch block.
9. **`pendingSendRef.mode` used** (B4): unit test asserting `dispatchSend` reads `pendingSendRef.current.mode` not live closure `mode`.
10. **`raise_if_no_config` helper + 3 callers** (B5): import the helper from `brain_core.tools._errors`; assert 3 brain_core tools call it (config_get, list_domains, config_set); assert 4th similar pattern (SPAStaticFiles non-http guard) is INTENTIONALLY separate (different scope-type contract).
11. **`_mk_ctx` requires config** (B6): grep all three test files; assert no test calls `_mk_ctx(...)` without `config=` kwarg.
12. **`PLAN 15 DEMO OK`** sentinel.

Prints `PLAN 15 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents** (D11 conservative split).
- `brain-test-engineer` — Task 1 (ruff debt; mechanical lint cleanup), Task 2 (Windows Playwright diagnose; Plan 13 Task 4 pattern), Task 11 (closure demo + e2e + lessons)
- `brain-mcp-engineer` (role-overloaded brain-api-engineer per Plan 05 precedent) — Task 3 (Windows Playwright fix; per Task 2 findings)
- `brain-installer-engineer` — Task 4 (brain start CLI drops uv run)
- `brain-ui-designer` — Task 5 microcopy half (jargon glossary tooltip text)
- `brain-frontend-engineer` — Task 5 (apply jargon to modal + Settings), Task 6 (active-domain toast), Task 7 (pendingSendRef.mode)
- `brain-core-engineer` — Task 8 (raise_if_no_config helper), Task 9 (_mk_ctx alignment), Task 10 (apply_patch docstring)
- `brain-prompt-engineer` — no scope (no prompt changes)

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 14 closed clean: `git tag --list | grep plan-14-hardening-and-ci` exists.
- Confirm no uncommitted changes on `main`.
- Confirm `tasks/lessons.md` contains the Plan 14 closure section (7 lessons captured).
- **Plan 15 explicitly inverts a passive workflow rule.** Plan 11/12/13/14 implementers all reported "ruff clean" because they ran ruff against the changed package only (`ruff check packages/<pkg>/`); CI runs `ruff check .` (whole repo). Plan 15 Task 1 closes the per-package vs whole-repo gap; the per-task self-review checklist below adds an explicit `uv run ruff check .` (whole repo) step that all future plans must run.
- Note the recurring uv `UF_HIDDEN .pth` workaround (lesson 341 + Plan 12+13+14 refinements): chflags + PYTHONPATH same-line python invocation; do NOT use `uv run` (re-syncs and re-hides). Task 4 (`brain start` CLI) makes this rule first-class in the supervisor.

---

## What Plan 15 explicitly does NOT do

These are tempting adjacent expansions filed for Plan 16+:

- **Production race fix:** `inbox-store.loadRecent` overwrite race at `apps/brain_web/src/lib/state/inbox-store.ts:158`. `set({ sources: items })` unconditionally replaces store on loadRecent resolution, which races `addOptimistic` (line 163). Plan 14 Task 6 captured this; Plan 15 didn't pick it up because user chose "polish + CI" (1.D) over "production correctness" (1.A). Fix shape: merge that preserves optimistic rows whose id is not in server response, OR sequence-id check.
- **`_spa_fallback Response | None` mypy `@overload` fix.** Plan 14 Task 5 review M2 flagged the pre-existing mypy hole. Plan 16+ polish.
- **Architectural follow-throughs from Plan 13 reviews:** orphan `listDomains` consumers (bulk-screen + file-to-wiki-dialog), `removeDomainOptimistic` action + delete-handler wiring, `useDomainsStore.error` inline banner, `domainsLoaded`→`loaded` naming alignment, drop/wire cross-domain-gate-store error field, BroadcastChannel cross-tab pubsub, `setAcknowledgedOptimistic` early-return pattern, split `panel-domains.tsx` into 3 files.
- **Plan 14 a11y deferrals:** repair-config dialog UI surface, autonomy modal, file-preview overlay, WikilinkHover tooltip a11y, per-message Fork dialog smoke case.
- **CSS structural cleanup:** hover-state token unification (`--tt-cyan-hover`); audit other `var(--brand-ember)` foreground sites for dark-mode contrast trap; codify "no hardcoded hex outside `:root` blocks" via stylelint; document `.prose` / `.msg-body` selector convention; consolidate `#E06A4A` hardcoded usages.
- **CI follow-throughs from Plan 14 reviews:** workflow caching (uv + pnpm + Playwright browsers), composite action / DRY for chflags + PYTHONPATH + npx playwright test, `gh workflow run --validate` in pre-commit, `pnpm install --filter brain_web...` consistency, Defender SmartScreen pre-step, PowerShell line-ending discipline lesson, CI duration observability.
- **Test-quality follow-throughs:** `waitForToolResponse` helper for mount-time tool fetch races, `waitForTimeout` removal (deterministic waits across `a11y-populated.spec.ts` ~11 sleep calls), test cleanup contract (`test.afterEach` for state-mutating tests), helper extraction once 5th caller appears (`seedBrainMd` / `seedScope`), `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in `patch-card.tsx:117`.
- **Bigger architectural moves:** per-domain budget caps; per-domain rate limits; repair-config UI; cross-process hot-reload; `validate_assignment=True` on Config; per-domain autonomy categories; "Set as default" topbar button; per-thread cross-domain confirmation; generic "tool reads ctx.config" lint rule; migration tool for old config.json files; generic zustand promotion across other hooks.

If any of these come up during implementation, file a TODO and keep moving.

---

## Decisions (locked 2026-04-29)

User signed off on all 11 recommendations on 2026-04-29 across three batched rounds. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope.

### Group I — Scope cut

| # | Decision | Locked | Why |
|---|---|---|---|
| Scope | Plan 15 covers ten items + closure: #A1 ruff debt clear, #A2 Windows Playwright (diagnose+fix), #B1 brain start CLI, #B2 jargon split, #B3 active-domain toast, #B4 pendingSendRef.mode, #B5 raise_if_no_config helper, #B6 _mk_ctx alignment, #B7 apply_patch docstring. Defers production loadRecent race, mypy @overload, architectural cleanup, a11y deferrals, CSS structural cleanup, CI polish, test-quality follow-throughs, bigger architectural moves to Plan 16+. | ✅ | "CI + polish pass" cut. Cohesive theme: green up the CI gate AND sweep the small cleanups Plan 12+13 reviews deferred. Plan 16 starts with a clean CI surface and known production-correctness work. |

### Group II — CI green (#A1 + #A2)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | Ruff debt fix completeness: auto-fix + manual fix (full green). `uv run ruff check --fix .` clears 67 auto-fixable; manual fix the 9 remaining (3 `match="ctx.config"` → `match=r"ctx\.config"` in test files; 6 `×` → `x` in `scripts/demo-plan-{10,11,13}.py`). Single commit clears all 76 violations; CI goes green for the first time in 4 plans. | ✅ | "Auto-fix only" was rejected as leaving visible debt that gets deferred indefinitely. "Per-package fix only" was rejected as not restoring green CI. Full green is the load-bearing CI contract. |
| D2 | Windows Playwright Task structure: diagnose-only Task 2 + fix Task 3 (Plan 13 Task 4/5 split pattern). Task 2 produces findings document; plan-author signs off Task 3 fix shape before dispatch. | ✅ | "One-shot diagnose-and-fix" was rejected because Windows-specific failure root cause is unknown (hydration / static-export quirk / accessible-name locale / WS upgrade — multiple plausible hypotheses). "Skip Windows fix" was rejected as negating Plan 14 Tasks 7+8's investment. |

### Group III — `brain start` CLI (#B1)

| # | Decision | Locked | Why |
|---|---|---|---|
| D3 | `brain start` CLI fix shape: drop `uv run` from supervisor. Replace `uv run uvicorn` in `brain_cli.commands.start` with direct `.venv/bin/python -m uvicorn` invocation (matches the chflags+PYTHONPATH escape hatch every other tool uses). | ✅ | "Retry with chflags-prepared subshell" was rejected as adding complexity for a workaround. "Document only" was rejected as keeping the bug live. Direct invocation is consistent with Plan 11 lesson 341 + Plan 12/13/14 refinements. |

### Group IV — Modal/Settings jargon (#B2)

| # | Decision | Locked | Why |
|---|---|---|---|
| D4 | Modal + Settings jargon: "Privacy-railed" everywhere. Aligns with Plan 11 D11's `Config.privacy_railed: list[str]` field; technical term but accurate. Modal switches from "private" to "Privacy-railed"; one-line glossary tooltip on hover ("domains marked as private; never appear in default queries"). | ✅ | "Private everywhere" was rejected as losing the term-of-art Plan 11 D11 established. "Distinct terms with linked help text" was rejected as cognitive overhead and the same ambiguity Plan 12 Task 9 review flagged as 'jargon split.' |

### Group V — Active-domain toast (#B3)

| # | Decision | Locked | Why |
|---|---|---|---|
| D5 | Active-domain dropdown toast: conditional CTA + move pushToast outside catch. Validator-error → "Pick a different domain"; transport-error (network, 502, CORS) → "Try again". Move `pushToast({...danger...})` outside the catch block (defensive scoping; pushToast is a zustand setter that can't realistically throw, but keeping it in catch reads as fallible). | ✅ | "Drop CTA entirely" was rejected as losing user-actionable hint on validator errors. "Keep CTA + just move pushToast" was rejected as keeping the misleading-on-transport-failure problem Plan 12 Task 8 review I2 flagged. |

### Group VI — `pendingSendRef.mode` (#B4)

| # | Decision | Locked | Why |
|---|---|---|---|
| D6 | `pendingSendRef.mode` disposition: use it explicitly in dispatchSend. The captured-at-click-time intent IS load-bearing for cross-domain modal acknowledgment timing — `mode` could change between modal-show and modal-acknowledge; the click-time value is the right one to honor. | ✅ | "Remove field entirely" was rejected as losing the click-time intent the comment names. The Plan 12 Task 9 review left the field as TODO; Plan 15 honors the original intent. |

### Group VII — `raise_if_no_config` helper (#B5)

| # | Decision | Locked | Why |
|---|---|---|---|
| D7 | Helper location + shape: new `packages/brain_core/src/brain_core/tools/_errors.py` with `raise_if_no_config(ctx, tool_name)`. Three current call sites (config_get.py, list_domains.py, config_set.py:317-327) refactor to call the helper. SPAStaticFiles non-http guard (Plan 14 Task 1) stays separate (different package; different scope-type contract; not covered). | ✅ | "Add to existing tools/__init__.py" was rejected as risking kitchen-sink. "Skip extraction" was rejected because Plan 13 Task 1 review I2 said the threshold met (3 sites + drift-prone). Dedicated module matches Plan 04's `_helpers.py` / `_errors.py` precedent. |

### Group VIII — `_mk_ctx` alignment (#B6)

| # | Decision | Locked | Why |
|---|---|---|---|
| D8 | `_mk_ctx` test fixture signature alignment: all required `config: Config`. Three test files (test_list_domains.py, test_list_domains_active.py, test_config_set.py) require explicit `config=` kwarg on every call site. Removes the implicit `config=None` defaulting. | ✅ | "All default config=None" was rejected as preserving the implicit-None behavior that hides intent — Plan 13 Task 1 audit found this hides the anti-pattern category that Plan 13 D1 explicitly killed. |

### Group IX — Plan shape (#0)

| # | Decision | Locked | Why |
|---|---|---|---|
| D9 | Plan 15 task count: 11 tasks. Task 1 ruff + Task 2 Windows diagnose + Task 3 Windows fix + Task 4 brain start + Task 5 jargon split + Task 6 toast + Task 7 pendingSendRef + Task 8 raise_if_no_config + Task 9 _mk_ctx + Task 10 apply_patch docstring + Task 11 closure. Each narrowly scoped. Mirrors Plan 14 (9 tasks) cadence at the polish-heavy upper end. | ✅ | "10 tasks (combine 5+6 into one panel-domains task)" was rejected as muddying review attribution. "8 tasks (combine more)" was rejected as bigger task review surface; harder per-task TDD. |
| D10 | Demo gate composition: 12 gates. (1) ruff clean. (2) brain_api pytest regression. (3) brain_web vitest regression. (4) local Playwright regression. (5) Windows Playwright on CI (post-Task-3 fix; observed via `gh run view`). (6) brain start without manual chflags. (7) jargon consistency. (8) active-domain toast CTA conditional. (9) pendingSendRef.mode used. (10) raise_if_no_config helper + 3 callers. (11) _mk_ctx requires config. (12) PLAN 15 DEMO OK sentinel. | ✅ | "8 gates collapsed" was rejected as less granular failure signal. "10 gates without explicit Windows CI" was rejected because Windows Playwright gate is the load-bearing #A2 verification — must be explicit in the demo script (gate-wise CI poll). |
| D11 | Sequential per-task dispatch via `superpowers:subagent-driven-development`. Implementer → spec-reviewer → code-quality-reviewer → fix-loops between tasks. No parallelization. NO spec text touched (CI + polish only — no D11 footnote like Plan 14). Owners: brain-test-engineer (1, 2, 11); brain-mcp-engineer role-overloaded (3); brain-installer-engineer (4); brain-ui-designer (5 microcopy half); brain-frontend-engineer (5 apply, 6, 7); brain-core-engineer (8, 9, 10). | ✅ | "Sequential + spec footnote" was rejected as no spec text actually changes in Plan 15 (vs Plan 14 added a CI gate footnote). "Parallel where dep graph allows" was rejected for review-discipline reasons (Plan 11-14 all caught real bugs at sequential checkpoints). |

The implementer routes any unrecognized rule edge case (D2 hypothesis falsified mid-diagnose, D3 alternative supervisor refactor, D5 alternative toast-error classification, D7 alternative helper signature, D8 alternative test-rewrite scope, D9 alternative task split) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/tools/
│   ├── _errors.py                      # NEW: raise_if_no_config(ctx, tool_name) helper (D7)
│   ├── config_get.py                   # MODIFY: call raise_if_no_config (D7)
│   ├── list_domains.py                 # MODIFY: call raise_if_no_config (D7)
│   ├── config_set.py                   # MODIFY: call raise_if_no_config at line 317-327 (D7)
│   └── apply_patch.py                  # MODIFY: drop Plan 07 deferral docstring; describe actual behavior (D9 implicit)
└── tests/tools/
    ├── test_list_domains.py            # MODIFY: _mk_ctx requires config (D8)
    ├── test_list_domains_active.py     # MODIFY: _mk_ctx requires config (D8) — already required; just enforce consistency
    ├── test_config_set.py              # MODIFY: _mk_ctx requires config (D8)
    ├── test_config_get.py              # MODIFY: match=r"ctx\.config" raw-string fix (D1)
    ├── test_config_get_threads_ctx_config.py  # MODIFY: match=r"ctx\.config" raw-string fix (D1)
    └── test_errors_raise_if_no_config.py  # NEW: pin tests for the helper (D7)

packages/brain_api/
├── src/brain_api/                      # MODIFY: TBD per Task 2 findings (D2; expected: hydration / static-export / WS / accessible-name)
└── tests/                              # MODIFY: TBD per Task 2 findings

packages/brain_cli/
└── src/brain_cli/commands/
    └── start.py                        # MODIFY: drop uv run; direct .venv/bin/python -m uvicorn (D3)

apps/brain_web/
├── src/components/
│   ├── dialogs/cross-domain-modal.tsx  # MODIFY: "private" → "Privacy-railed" jargon (D4)
│   ├── settings/panel-domains.tsx      # MODIFY: glossary tooltip on Privacy-railed term (D4); active-domain toast conditional CTA + pushToast outside catch (D5)
│   └── chat/chat-screen.tsx            # MODIFY: dispatchSend reads pendingSendRef.current.mode not closure mode (D6)
└── tests/unit/
    └── (new pin tests as needed for D5, D6)

scripts/
├── demo-plan-10.py                     # MODIFY: × → x (D1 manual fix)
├── demo-plan-11.py                     # MODIFY: × → x (D1 manual fix)
├── demo-plan-13.py                     # MODIFY: × → x (D1 manual fix)
└── demo-plan-15.py                     # NEW: 12-gate demo per the demo gate above

tasks/
├── plans/15-ci-and-polish.md           # this file
├── lessons.md                          # MODIFY: + Plan 15 closure section
└── todo.md                             # MODIFY: row 15 → ✅ Complete; remove Plan 15 candidate-scope; add Plan 16 candidate-scope
```

Spec / user-guide files NOT modified per D11.

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 11 + 12 + 13 + 14, **PLUS one new step (item 7) that closes the per-package vs whole-repo ruff gap.**

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core` (or whichever package)
3. **uv `UF_HIDDEN` workaround** (lesson 341 + Plan 12+13+14 refinements): `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` — clamp BOTH `.pth` files in the SAME COMMAND LINE as the python invocation; do NOT rely on `uv run`. Escape hatch: `PYTHONPATH=packages/brain_core/src:packages/brain_mcp/src:packages/brain_api/src:packages/brain_cli/src .venv/bin/python -m pytest ...`.
4. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions (or chflags-prefixed equivalent)
5. `cd packages/<pkg> && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m mypy src tests && cd -` — strict clean
6. `/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m ruff check packages/<pkg> && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m ruff format --check packages/<pkg>` — clean (per-package; matches dev recipe)
7. **NEW (Plan 15 Task 1 + onward):** `uv run ruff check . && uv run ruff format --check .` — **whole-repo clean**. Closes the per-package vs whole-repo gap that hid 76 violations across Plans 11–14. Mandatory after every commit going forward.
8. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
9. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check is invariant-based, not total-based.
10. **Browser-in-the-loop verification** for any UI-touching task (Tasks 5, 6, 7): start brain, take screenshots pre and post change, attach to per-task review.
11. `git status` — clean after commit.

Any failure in 4–10 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — Clear pre-existing ruff debt (#A1)

**Files:**
- Modify: every file ruff flags (~62 files based on baseline; run `uv run ruff check .` for live count)
- Possibly modify: `scripts/demo-plan-{10,11,13}.py` (× → x manual fix)
- Possibly modify: 3 brain_core test files (`match="ctx.config"` → `match=r"ctx\.config"`)

**Goal:** Per D1, clear all 76 ruff violations. Auto-fix 67 + manual-fix 9. Restore green CI on the existing `CI` workflow for the first time since Plan 11.

**What to do:**
1. **Reproduce baseline.** `uv run ruff check . 2>&1 | tail -3` should report `Found 76 errors. [*] 67 fixable with the --fix option.`
2. **Auto-fix.** `uv run ruff check --fix .`. Should report `Found 76 errors (67 fixed, 9 remaining).`
3. **Manual fix RUF043** (3 occurrences). Files: `packages/brain_core/tests/tools/test_config_get.py:80:44`, `test_config_get_threads_ctx_config.py:127:44`, `test_config_set.py:121:5`. Each is `match="ctx.config"` (or similar with `.` literal); change to `match=r"ctx\.config"` (raw-string + escaped dot). Run `uv run ruff check . 2>&1 | grep RUF043` after; should report 0.
4. **Manual fix RUF001/RUF002** (6 occurrences in `scripts/demo-plan-{10,11,13}.py`). Each is the `×` (multiplication sign U+00D7) used in strings/docstrings like "test_errors × 8". Change to `x` (LATIN SMALL LETTER X U+0078). Run `uv run ruff check . 2>&1 | grep RUF00` after; should report 0.
5. **Format check.** `uv run ruff format .` then `uv run ruff format --check .` — should report all-clean.
6. **Verify.** `uv run ruff check .` reports `All checks passed!`. Whole-repo green.
7. **Test regression.** Run full pytest + vitest + Playwright local suite; assert no new failures.

**Per-task review:** the auto-fix touched ~62 files but is purely removing unused imports + minor cosmetics. Sample 5 files post-fix to confirm nothing important was removed. No production behavior change. Per-task self-review checklist runs to completion.

---

## Task 2 — Windows Playwright chat composer diagnose-only (#A2)

**Files:**
- Read-only audit: `apps/brain_web/playwright.config.ts` webServer block, `apps/brain_web/scripts/start-backend-for-e2e.ps1`, `apps/brain_web/src/components/chat/composer.tsx` (or wherever the textbox lives), `apps/brain_web/tests/e2e/chat-turn.spec.ts:40`, `apps/brain_web/tests/e2e/a11y-populated.spec.ts:223`, GitHub Actions Windows job log
- Document: append a "Task 2 findings" subsection to this plan file's per-task review section

**Goal:** Per D2, confirm (or refute) the hypotheses from Plan 14 first-CI observation. **DIAGNOSE-ONLY** — no production code changes; no test fixes. Findings document IS the artifact.

**What to do (mirror Plan 13 Task 4 hypothesis-confirm-first):**
1. **Reproduce.** Re-trigger the Plan 14 Playwright workflow on the existing tag OR push a new commit; observe windows-2022 leg fails the same way.
2. **Hypothesis-test 1: hydration error.** Download the test artifacts from the failed run. Open `error-context.md` for both failures. Look for hydration mismatch errors in console output.
3. **Hypothesis-test 2: static-export Windows quirk.** Compare `apps/brain_web/out/` produced by Mac CI vs Windows CI. Look for path differences (backslash vs forward-slash in baked-in routes), line-ending differences (CRLF vs LF), or chunk-loading differences.
4. **Hypothesis-test 3: accessible-name locale.** The textbox locator is `getByRole('textbox', { name: 'Message brain' })`. Windows Chromium may use a different locale for accessible-name computation. Check via `page.getByRole('textbox').first().getAttribute('aria-label')` in a debug step.
5. **Hypothesis-test 4: WS upgrade timing.** brain_api WS upgrade may stall on Windows runner network/firewall config. Check `playwright.config.ts` webServer logs from Windows run for any WS-related errors.
6. **Hypothesis-test 5: composer-not-mounting.** The composer component may not render at all on Windows (e.g., a `process.env.IS_WINDOWS` branch hits an unintended path). `grep -rn "process.platform\|navigator.platform" apps/brain_web/src/`.
7. **Categorize the failure.** For each of the 2 failing tests (a11y-populated + chat-turn), pin the hypothesis it best matches.
8. **Findings document.** Append a "Task 2 findings" subsection to this plan file's Review section. Include: (a) confirmed root cause(s); (b) hypotheses refuted; (c) proposed Task 3 fix shape; (d) any open questions for plan-author sign-off.

**Per-task review:** no code changes. Findings document IS the artifact. Plan-author reviews findings before Task 3 dispatches.

---

## Task 3 — Windows Playwright chat composer fix (#A2)

**Files:**
- Modify: TBD per Task 2 findings (likely `apps/brain_web/src/components/chat/composer.tsx` OR `playwright.config.ts` webServer block OR `start-backend-for-e2e.ps1`)
- Possibly create: regression-pin test asserting the fix is load-bearing

**Goal:** Per D4, fix the Windows-specific chat composer rendering issue per Task 2's locked findings. CI on windows-2022 leg of Playwright workflow goes green.

**What to do:**
1. **Apply Task 2's locked fix shape.** Implementer reads Task 2 findings from this plan file. If findings reveal multiple root causes, this task may dispatch as 2 sub-fixes within sequential review — confirm with plan-author.
2. **Push to a feature branch + observe CI.** Don't push directly to main (the CI is the verification). Create `plan-15-task-3-windows-fix` branch; push; observe windows-2022 leg goes green.
3. **Add regression-pin test** if the fix is in production code (e.g., a unit test asserting composer renders with the right aria-label across platforms; OR a Playwright spec that's locale-explicit).
4. **Merge to main** after CI confirms windows-2022 green.

**Per-task review:** the CI run is the artifact. Capture the green-CI run URL in per-task review notes. Production-shape verification (lesson 343) — the regression-pin test must NOT mock the failing layer; it must assert against the real component / config.

---

## Task 4 — `brain start` CLI drops `uv run` from supervisor (#B1)

**Files:**
- Modify: `packages/brain_cli/src/brain_cli/commands/start.py` (or wherever the supervisor lives — `grep -rn "uv run uvicorn"` to confirm)
- Modify: `packages/brain_cli/tests/test_command_start.py` (or equivalent — pin the new invocation shape)

**Goal:** Per D3, replace `uv run uvicorn` in the supervisor with direct `.venv/bin/python -m uvicorn` invocation. Eliminates the chflags re-hide issue that forces direct uvicorn as the dev escape hatch.

**What to do:**
1. **Locate the supervisor.** `grep -rn "uv run\|uvicorn" packages/brain_cli/src/`.
2. **Replace.** Change `subprocess.Popen(["uv", "run", "uvicorn", ...])` to `subprocess.Popen([f"{venv_root}/bin/python", "-m", "uvicorn", ...])` (Mac/Linux) and `[f"{venv_root}/Scripts/python.exe", "-m", "uvicorn", ...]` (Windows). Use `pathlib.Path` for cross-platform venv path.
3. **Update brain_cli tests.** `test_command_start.py` (or equivalent) probably mocks subprocess; update mock expected-args.
4. **Browser verification.** Start brain via `brain start` in a fresh shell (no chflags pre-step); verify HTTP `GET /api/healthz` responds 200; verify no `ImportError: brain_core` on stderr.

**Per-task review:** browser verification is the load-bearing check. The pre-Plan-15 failure mode is `brain start` → uv re-syncs → .pth re-hides → uvicorn fails to import brain_core. Post-Plan-15: direct python invocation; no uv re-sync; .pth stays clamped.

---

## Task 5 — Modal/Settings 'Privacy-railed' jargon alignment (#B2)

**Files:**
- Modify: `apps/brain_web/src/components/dialogs/cross-domain-modal.tsx` (modal copy)
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (Settings glossary tooltip add)
- Possibly: brain-ui-designer microcopy artifact at `docs/design/cross-domain-modal/microcopy.md` (Plan 12 Task 7 home)

**Goal:** Per D4, replace "private" / "kept private by default" in the cross-domain modal with "Privacy-railed" + glossary tooltip. Settings already uses "Privacy-railed" — Plan 15 makes both surfaces consistent.

**What to do:**
1. **Modal copy.** Open `cross-domain-modal.tsx`. Replace any "private domain" / "kept private" → "Privacy-railed". Add a small `(?)` icon next to the term that opens a tooltip: "Domains marked as private; never appear in default queries."
2. **Settings tooltip.** Open `panel-domains.tsx`. The "Privacy rail" toggle column already uses the term; ensure the same tooltip is available there (or use a shared `<PrivacyRailedTerm>` component).
3. **Microcopy doc.** Update `docs/design/cross-domain-modal/microcopy.md` (Plan 12 Task 7's home) to reflect the new terminology.

**Per-task review:** browser verification — open the modal with scope=`[research, personal]`; screenshot showing "Privacy-railed" + tooltip; open Settings → Domains; screenshot showing the same term and tooltip. brain-ui-designer reviews the tooltip copy before merge.

---

## Task 6 — Active-domain toast: conditional CTA + pushToast outside catch (#B3)

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (the `ActiveDomainSelector` component or wherever the active-domain mutation toast lives)

**Goal:** Per D5, conditional CTA based on error type + pushToast outside catch. Two small changes, one task.

**What to do:**
1. **Classify error in catch.** Determine if the caught error is a validator error (e.g., `error.code === "VALIDATION_ERROR"` or response status 400 with `body.error === "validation"`) vs a transport error (network, 502, CORS). Use existing `error.code`/`response.status` discriminator.
2. **Conditional CTA.**
   - Validator error: toast = `${detail} Pick a different domain.`
   - Transport error: toast = `${detail} Try again.`
3. **Move pushToast outside catch.** The current code has `pushToast({...danger...})` inside the catch block. Move outside — e.g., set a state variable inside catch, then call pushToast at the end of the function.
4. **Pin test.** Unit test asserting the two error-class paths produce the right CTA.

**Per-task review:** the test is the artifact. Plan 12 Task 8 review I1+I2 captured the bug; Plan 15 closes both.

---

## Task 7 — `pendingSendRef.mode` used explicitly in dispatchSend (#B4)

**Files:**
- Modify: `apps/brain_web/src/components/chat/chat-screen.tsx` (the `dispatchSend` function reads `mode` from live closure; should read from `pendingSendRef.current.mode`)
- Modify: any test file that asserts `dispatchSend` behavior on cross-domain modal acknowledgment

**Goal:** Per D6, honor the click-time intent. `mode` could change between modal-show and modal-acknowledge; the click-time captured value is the right one.

**What to do:**
1. **Locate `dispatchSend`.** `grep -n "dispatchSend\|pendingSendRef" apps/brain_web/src/components/chat/chat-screen.tsx`.
2. **Read pendingSendRef.current.mode.** Replace `mode` (live closure) with `pendingSendRef.current.mode` (click-time captured) inside `dispatchSend`.
3. **Pin test.** Unit test: simulate `mode` changing between modal-show and modal-acknowledge; assert `dispatchSend` uses the captured-at-show value.

**Per-task review:** the test is the artifact. The bug is rare-but-real (mode change between show + ack); test pins the captured-at-show contract.

---

## Task 8 — `raise_if_no_config` helper extraction (#B5)

**Files:**
- Create: `packages/brain_core/src/brain_core/tools/_errors.py`
- Modify: `packages/brain_core/src/brain_core/tools/config_get.py`
- Modify: `packages/brain_core/src/brain_core/tools/list_domains.py`
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py`
- Create: `packages/brain_core/tests/tools/test_errors_raise_if_no_config.py`

**Goal:** Per D7, extract the canonical `_NO_CONFIG_MESSAGE` raise pattern from 3 sites into a single helper. Consistent error wording; single point of maintenance.

**What to do:**
1. **New `_errors.py`.** Define `def raise_if_no_config(ctx: ToolContext, tool_name: str) -> None:` that raises `RuntimeError(f"{tool_name} requires ctx.config to be a Config instance, but got None. ...")` (use existing canonical wording from `config_get.py`). Import inside callers as `from brain_core.tools._errors import raise_if_no_config`.
2. **Refactor 3 callers.** Each currently has a `_NO_CONFIG_MESSAGE` constant + raise. Replace with `raise_if_no_config(ctx, "brain_<tool_name>")`. The constant goes away.
3. **Pin tests.** New `test_errors_raise_if_no_config.py`: assert helper raises with correct wording for each `tool_name` value; assert the 3 callers each invoke it.

**Per-task review:** the contract test is the artifact — it pins that 3 callers use the helper. Future tools that need the same rail can call the helper directly.

---

## Task 9 — `_mk_ctx` test fixture alignment (required `config: Config`) (#B6)

**Files:**
- Modify: `packages/brain_core/tests/tools/test_list_domains.py` (`_mk_ctx` requires `config=`)
- Modify: `packages/brain_core/tests/tools/test_list_domains_active.py` (already required; verify consistency)
- Modify: `packages/brain_core/tests/tools/test_config_set.py` (`_mk_ctx` requires `config=`)

**Goal:** Per D8, all three test fixtures align on requiring explicit `config: Config`. Removes the implicit `config=None` defaulting that hides intent.

**What to do:**
1. **Audit each `_mk_ctx`.** Read the three files. Identify which currently default `config=None` vs require `config: Config`.
2. **Make required.** Change function signature to `def _mk_ctx(vault, *, config: Config, ...)` — no default for `config`.
3. **Update every call site.** Each test that previously called `_mk_ctx(vault, ...)` now must pass `config=Config(...)` (or whatever real Config the test wants). Tests that explicitly tested the lenient `ctx.config=None` branch were already rewritten in Plan 13 Task 1; verify none remain.

**Per-task review:** the diff is mechanical. After alignment, run `pytest packages/brain_core -q` to confirm no regressions. Per-task self-review checklist.

---

## Task 10 — `apply_patch._resolve_config` Plan 07 deferral docstring cleanup (#B7)

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/apply_patch.py:121` (docstring)

**Goal:** Per D9 (implicit), drop the stale "Plan 07 Task 5 will replace the body with a real loader call" reference. Describe the function's actual current behavior.

**What to do:**
1. **Open `apply_patch.py:_resolve_config`.** Read the current docstring.
2. **Rewrite docstring.** Drop the Plan 07 reference. New docstring describes the actual snapshot-Config-with-vault_root-overlay behavior. Example: "Resolve a Config snapshot for the apply_patch path. Constructs a fresh `Config(vault_path=ctx.vault_root)` rather than reading `ctx.config` because apply_patch operates on the vault directly and doesn't need persisted config state."
3. **No body change.** The function body is unchanged.

**Per-task review:** trivial cosmetic edit. Plan 16+ candidate scope tracks the actual "real loader call" deferral if/when it's ever needed.

---

## Task 11 — Closure: 12-gate demo + lessons + todo.md

**Files:**
- Create: `scripts/demo-plan-15.py`
- Modify: `tasks/lessons.md` (Plan 15 closure section)
- Modify: `tasks/todo.md` (row 15 → ✅ Complete; remove Plan 15 candidate-scope; add Plan 16 candidate-scope)

**Goal:** Land the 12-gate demo. Lessons capture. todo.md update. NO spec amendment per D11.

**What to do:**
1. **demo-plan-15.py.** Mirror `scripts/demo-plan-14.py` structure. Build the 12 gates per the demo gate description in plan header.
2. **Demo script execution prefix:** `chflags 0 .../_editable_impl_*.pth && .venv/bin/python scripts/demo-plan-15.py` per lesson 341.
3. **Lessons capture.** Mirror Plan 14 closure-section format. Closure summary, then one paragraph per lesson:
   - **Per-package vs whole-repo ruff gap.** 4 plans of "ruff clean" reports masked 76 violations because the implementer recipe ran `ruff check packages/<pkg>/` (current package only) but CI runs `ruff check .` (whole repo). The new per-task self-review checklist item 7 closes this gap going forward.
   - **Plan 14 first-CI lessons.** Mac green on first try; Windows surfaced 2 chat-composer-rendering failures specific to its runtime. Plan 13 Task 4/5 hypothesis-confirm-first pattern paid off again — Task 2 diagnose-only kept Plan 15 Task 3 fix-shape locked before dispatch.
   - **Drop `uv run` from supervisor.** Lesson 341 is now first-class in `brain start`. Future supervisors should default to direct `.venv/bin/python` invocation.
   - **Privacy-railed term-of-art.** Plan 11 D11 named the field; Plan 12 Task 7 deferred the alignment; Plan 15 D4 closes it. Lesson: technical-precision-first; user-facing tooltip translates.
   - **Toast error classification.** Validator vs transport vs other — error-class discriminator should drive UX hint copy. Plan 12 Task 8 review captured this; Plan 15 D5 closes.
   - **Click-time captured intent.** `pendingSendRef.mode` is the click-time-captured value; reading live closure violates the captured intent. Plan 12 Task 9 review captured this; Plan 15 D6 closes.
   - **Rule of three for helper extraction.** Plan 13 Task 1 review I2 said the threshold met; Plan 15 D7 closes via `tools/_errors.py`. Future polish: 4th similar pattern (SPAStaticFiles non-http guard) stays separate as different scope-type contract.
4. **`tasks/todo.md` update.** Row 15 → ✅ Complete. Remove "Plan 15 candidate scope" tail section. Add fresh "Plan 16 candidate scope (forwarded from Plan 15)" tail block — pre-populate with the deferred items from Plan 15 NOT-DOING (production loadRecent race, mypy @overload, architectural cleanup, a11y deferrals, CSS structural, CI polish, test-quality follow-throughs, bigger architectural moves).

**Per-task review:** demo gates 1-12 all green. Lessons capture is the Plan 15 retrospective. todo.md update is the closure handoff. Per-task self-review checklist runs to completion.

---

## Review (pending)

To be filled in on closure following Plan 10 + 11 + 12 + 13 + 14 format:
- **Tag:** `plan-15-ci-and-polish` (cut on green demo).
- **Closes:** ruff debt (76 violations → 0; first green CI in 4 plans), Windows Playwright chat composer fix (Plan 14 Task 9 deferred verification), 7 polish cleanups carried from Plan 12+13. Plan 15 candidate-scope tail block in `tasks/todo.md` removed; Plan 16 candidate-scope tail block added.
- **Bumps:** tool count unchanged. Schema unchanged. New module: `brain_core.tools._errors`. Test fixture refactor: `_mk_ctx` requires `config=`. brain_cli supervisor switches from `uv run uvicorn` to direct `.venv/bin/python -m uvicorn`. Modal/Settings jargon aligned to "Privacy-railed."
- **Verification:** all 12 demo gates green (`scripts/demo-plan-15.py` → `PLAN 15 DEMO OK`); pytest count + vitest count + Playwright count + first green-Windows CI run URL to be filled in.
- **Backlog forward:** Plan 16 candidate scope pre-populated per Task 11 step 4. Themes: production loadRecent race fix; architectural follow-throughs from Plan 13 reviews; Plan 14 a11y deferrals; CSS structural cleanup; CI polish; test-quality follow-throughs; bigger architectural moves (per-domain budgets, validate_assignment=True, hot-reload).
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 15" feed Plan 16's authoring.

---

## Task 2 findings (diagnose-only, locked 2026-04-29)

**Confirmed root cause:** `SPAStaticFiles._spa_fallback` extracts the URL's first path segment via `path.split("/", 1)[0]`, but Starlette's `StaticFiles.get_path()` runs `os.path.normpath(os.path.join(*route_path.split("/")))` on the incoming URL. On Windows `os.path` is `ntpath`, so `os.path.join(*"/chat/abc-123/".split("/"))` becomes `"chat\\abc-123\\"` and `normpath` collapses it to `"chat\\abc-123"`. There is no forward slash left, so `path.split("/", 1)[0]` returns the entire backslash-joined string. `first_segment in _RESERVED_PREFIXES` is False, `first_segment in _DYNAMIC_PLACEHOLDERS` is False, and the fallback drops to "Generic SPA fallback — serve the repo-root `index.html`."

For real chat threads (`/chat/<thread_id>/`) the live URL is not pre-rendered, so the static lookup misses; on Mac the dynamic-segment branch then serves `out/chat/_/index.html` (the `<ChatThreadClient />` placeholder) and the chat screen mounts. On Windows it serves `out/index.html` (the root `<RootPage />`) instead, which returns `null` because `pathname !== "/"` short-circuits the redirect effect — so the AppShell layout (banner + nav + drop-overlay) renders into the layout chrome and `<main>` is left empty. The composer never mounts; `getByRole('textbox', { name: 'Message brain' })` times out exactly as observed.

**Production-shape verification:**

```python
# Reproduced in /tmp via Python's ntpath module (Windows path semantics):
>>> import ntpath
>>> p = "/chat/e2e-chat-foo/"
>>> joined = ntpath.join(*p.split("/"))  # exactly Starlette's transform
'chat\\e2e-chat-foo\\'
>>> norm = ntpath.normpath(joined)
'chat\\e2e-chat-foo'
>>> norm.split("/", 1)[0]                # exactly _spa_fallback's transform
'chat\\e2e-chat-foo'                     # ← whole string; no segment match
>>> norm.split("/", 1)[0] in ("chat", "browse")
False                                    # ← misses _DYNAMIC_PLACEHOLDERS
```

This matches the failed run's page snapshot exactly: scope chip + nav links + drop-overlay are rendered (those live in `app/layout.tsx` + `<AppShell />`) but `- main [ref=e44]` is empty (the chat-screen never gets a chance to render because `<RootPage />` is what got hydrated, and it returns `null` on non-root pathnames).

**Hypothesis-test results:**
- **H1 (hydration error in console output):** REFUTED. Page snapshot in both `error-context.md` files shows a fully rendered AppShell — banner, scope button, mode radios, theme toggle, primary nav, context rail. If hydration had failed, none of those would render. `suppressHydrationWarning` on `<html>` is a deliberate Plan 07 affordance for theme + density flicker, not a hydration-mismatch silencer for chat-screen.
- **H2 (static-export Windows path quirk in `out/`):** REFUTED. The `out/` directory is generated by `pnpm --dir apps/brain_web build` on each runner; Mac and Windows produce the same content. The bug is server-side (Python static_ui.py path normalization), not in the bundle itself. The static export's chat placeholder file `out/chat/_/index.html` exists on both platforms; it's just never *served* on Windows.
- **H3 (accessible-name locale):** REFUTED. `composer.tsx:199` uses `aria-label="Message brain"` (raw string, not locale-bound). Windows Chromium computes the accessible name from the literal `aria-label` per the ARIA spec — locale-independent. The test fails because the textbox is *not in the DOM at all*, not because the accessible name differs.
- **H4 (WS upgrade timing):** REFUTED. The composer is rendered by `<ChatScreen />` synchronously regardless of WS state; no `if (wsReady) return composer` gate exists in `chat-screen.tsx`. `useChatWebSocket` only opens the socket when `threadId !== null && token !== null` — the composer renders first either way.
- **H5 (composer-not-mounting via Windows JS branch):** REFUTED. `grep -rn "process.platform\|navigator.platform\|navigator.userAgent\|win32" apps/brain_web/src/` returned zero hits. No platform branch.
- **H6 (static-export route mismatch / SPA fallback path-separator bug):** **CONFIRMED.** `packages/brain_api/src/brain_api/static_ui.py:196` (`first_segment = path.split("/", 1)[0]`) is the exact site of the bug. The fix is one-line scope.

**The 2 failures share the same root cause** — both navigate to `/chat/<thread_id>/` (a non-pre-rendered dynamic-segment URL) and both look for the composer that lives inside `<ChatScreen />`. `chat-turn.spec.ts:33` is the cleanest reproducer (single-purpose chat round-trip); `a11y-populated.spec.ts:223` (fork-thread dialog) reproduces the same condition because Case 3 also drives a real chat turn before opening the Fork dialog. Cases 1, 2, 4, 5, 6, 7, 8, 9, 10, 11 in the same spec file all PASS on Windows because they navigate to statically-pre-rendered routes (`/settings/domains/`, `/chat/` (no thread id), `/settings/backups/`, etc.) that hit `lookup_path`'s `S_ISDIR + index.html` branch directly without exercising `_spa_fallback`. This explains the 30 passed / 2 failed split exactly.

**Bug pre-dates Plan 14.** The line `first_segment = path.split("/", 1)[0]` was introduced in Plan 08 Task 1 (commit `982abd2`). It went undetected for four plans because Windows CI didn't exist until Plan 14 Task 8 (commit `1d07ff0`). The first-CI Windows run is what surfaced it. This is a textbook latent cross-platform bug that the `cross-platform from day one` non-negotiable principle (`CLAUDE.md` rule 8) is meant to prevent — the rule says "no hardcoded forward slashes," but the violation here is the inverse: assuming `path` will *retain* its forward slashes after Starlette's normalize step. Either way, the lesson is the same: in any code path that takes a path from a third-party framework, normalize to the OS-independent shape before structural inspection.

**Existing test that masks the bug:** `packages/brain_api/tests/test_static_ui.py:88::test_spa_fallback_for_dynamic_segment` is a pure Mac test. It builds a fixture with a single `out/index.html` (no `out/chat/_/index.html`), calls `GET /chat/abc-123`, and asserts "BRAIN_ROOT" appears in the response. On Mac and Windows the response IS `out/index.html` (because the dynamic-placeholder file doesn't exist in the fixture; both branches converge to the generic root fallback). The test passes on both platforms but doesn't catch the bug because the fixture never exercises the Mac-vs-Windows branch divergence. The regression-pin design below fixes this gap.

**Proposed Task 3 fix shape (single edit + 2 regression-pin tests):**

**The fix.** Two lines in `packages/brain_api/src/brain_api/static_ui.py` — one for `_spa_fallback`'s segment extraction, one for `_DYNAMIC_PLACEHOLDERS` lookup. Replace `path.split("/", 1)[0]` with a separator-agnostic split that handles both Windows backslash and POSIX forward-slash. Recommendation: use `Path(path).parts[0]` (the standard-library `pathlib` parser handles both separators because the os-specific Path class is in scope on each platform) — or, more simply, normalize once at the top of `_spa_fallback` with `path = path.replace("\\", "/")` and keep the rest unchanged. The latter is one line, surgical, and obviously correct.

```python
# packages/brain_api/src/brain_api/static_ui.py
def _spa_fallback(self, path: str, *, raise_on_miss: bool) -> Response | None:
    """Pick the best SPA fallback HTML for a given client-route path.

    ...
    """
    # Starlette's StaticFiles.get_path() runs os.path.normpath() over the
    # URL before we see it. On Windows that converts forward slashes to
    # backslashes (ntpath behavior). Normalize to forward slashes here so
    # the segment / placeholder dictionaries (defined in URL terms) match.
    path = path.replace("\\", "/")
    first_segment = path.split("/", 1)[0] if path else ""
    ...
```

The single `path = path.replace("\\", "/")` line at the top of `_spa_fallback` is sufficient. No other changes needed (the `_DYNAMIC_PLACEHOLDERS` keys are bare segment names; the `_RESERVED_PREFIXES` tuple is also bare segments).

**Why this fix shape (vs alternatives):**
- **Option A (RECOMMENDED, surgical, one line):** `path = path.replace("\\", "/")` at the top of `_spa_fallback`. One line, no new imports, semantically clear (we're un-doing what `os.path.normpath` did to a value that the framework gave us in URL terms). Cross-platform correct.
- **Option B (rejected, framework-fight):** Override `get_path` to skip the `os.path.normpath` step. Brittle — Starlette's `lookup_path` later in the same chain expects OS-shaped paths, so we'd need to re-introduce the OS conversion in `lookup_path` AND keep URL semantics in `_spa_fallback`. Two edits in two layers; doesn't compose.
- **Option C (rejected, type-shift):** Use `pathlib.PurePosixPath(path).parts[0]`. Adds an import, hides the intent ("we want URL semantics") behind a Path abstraction. Equivalent at runtime but less obvious in the diff.

**Regression-pin test design (`packages/brain_api/tests/test_static_ui_path_separator.py`, NEW file):**

Two unit tests, one parametrized integration test:

1. `test_spa_fallback_handles_backslash_separator` — direct call to `SPAStaticFiles._spa_fallback("chat\\abc-123", raise_on_miss=True)`. Asserts the returned `FileResponse` points at the dynamic-placeholder file (`chat/_/index.html`), not the root `index.html`. Fixture builds a tiny `out/` with both files containing distinguishable content (`CHAT_PLACEHOLDER` vs `BRAIN_ROOT`).

2. `test_spa_fallback_handles_forward_slash_separator` — same as above with `path="chat/abc-123"`. Pinned-positive on the Mac shape (regression guard against accidentally breaking the Mac path while fixing Windows).

3. `test_spa_fallback_for_dynamic_segment_serves_placeholder_not_root` — parametrized integration test using a real `TestClient` + a fixture `out/` with both root `index.html` (`BRAIN_ROOT`) and `chat/_/index.html` (`CHAT_PLACEHOLDER`). Calls `GET /chat/abc-123` and asserts the response body contains `CHAT_PLACEHOLDER`, not `BRAIN_ROOT`. **This is the fixture upgrade that the existing `test_spa_fallback_for_dynamic_segment` lacked** (its fixture has no chat placeholder, so both Mac and Windows converge to root-index — a false negative either way). Add a second parametrize case for `/browse/foo/bar/` → `BROWSE_PLACEHOLDER`.

(Optional 4th: a unit test that imports `os.path.normpath` and explicitly asserts on the URL transform on the platform under test — but this is redundant with #1 and over-pins on Starlette internals; recommend skipping.)

**Production-shape verification (lesson 343):** the regression-pin tests must NOT mock `os.path.normpath` or pre-shape the path argument. The unit tests pass `"chat\\abc-123"` as a string literal so the assertion runs the real `_spa_fallback` body unchanged. The integration test passes through the full FastAPI app stack and exercises the real Starlette mount.

**Open questions for plan-author sign-off:**

1. **Should the fix be the surgical one-liner (`path.replace("\\", "/")`) or a wider audit of every `os.path` call in `static_ui.py` that takes a URL-shaped string?** Recommendation: the one-liner. The other `os.path` calls in `static_ui.py` (`out_root / _DYNAMIC_PLACEHOLDERS[first_segment]`, `out_root / _SETTINGS_FALLBACK`, `out_root / "index.html"`) all use `pathlib.Path` `/` operators with bare URL segments and are correct on both platforms because `Path("out") / "chat/_/index.html"` resolves to `out/chat/_/index.html` on POSIX and `out\chat\_\index.html` on Windows — `pathlib` handles the OS shape transparently. No other call site has the `os.path.normpath`-then-`split("/")` mismatch.

2. **Should this fix include a broader cross-platform audit of `packages/brain_api/src/`?** Recommendation: out of scope for Task 3. The Plan 14 Task 8 Windows CI run is now the audit gate going forward — any other latent Windows path bug would surface as a CI failure. Filing a Plan 16+ candidate scope item for "audit other `path.split("/")` call sites" would be over-scope; the test fix here pins the regression and the CI gate catches the next one.

3. **Should the regression-pin test also assert backslash handling on Mac via `monkeypatch.setattr(os, "path", ntpath)`?** Recommendation: skip. The unit tests #1 and #2 already exercise both separator shapes by passing literal strings; monkeypatching `os.path` would be Mac-specific test code that drifts from production semantics. The CI Windows leg is the real cross-platform gate.

4. **Should the existing `test_spa_fallback_for_dynamic_segment` test be deleted or upgraded?** Recommendation: upgrade (add the chat placeholder file to its fixture; rename the assertion from `"BRAIN_ROOT"` to `"CHAT_PLACEHOLDER"`). Deleting it would lose the route-shape pin (`GET /chat/<x>` returns 200, not 404). One existing test, one upgraded assertion.

**Surfaces inspected (read-only audit):**
- `packages/brain_api/src/brain_api/static_ui.py` (mount class, lines 111-223; bug at line 196)
- `packages/brain_api/src/brain_api/app.py` (mount registration; verified mount is post-API-routers per Plan 08 contract)
- `apps/brain_web/playwright.config.ts` (webServer + Windows pwsh branch verified clean)
- `apps/brain_web/scripts/start-backend-for-e2e.ps1` (vault seed + uvicorn launch verified clean; backend boots fine per the failed run's stdout)
- `apps/brain_web/src/app/page.tsx` (root page returns `null` for non-root pathnames — confirms why `<main>` is empty on the wrong-page-served scenario)
- `apps/brain_web/src/app/chat/[thread_id]/page.tsx` (`generateStaticParams()` pre-renders `_` placeholder)
- `apps/brain_web/src/app/chat/[thread_id]/chat-thread-client.tsx` (`usePathname` → real thread id; design comment confirms intent)
- `apps/brain_web/src/components/chat/chat-screen.tsx` (composer renders synchronously; not gated on WS state)
- `apps/brain_web/src/components/chat/composer.tsx` (raw `aria-label="Message brain"`; locale-stable)
- `apps/brain_web/src/components/system/drop-overlay.tsx` (always mounted; explains "Drop to attach" overlay in page snapshot YAML — it's the hidden state with `inert`)
- `apps/brain_web/tests/e2e/chat-turn.spec.ts:33` and `apps/brain_web/tests/e2e/a11y-populated.spec.ts:223` (both navigate to `/chat/<id>/`)
- `apps/brain_web/tests/e2e/a11y-populated.spec.ts:305` (Case 5 navigates to `/chat`, no thread id — explains why it passes on Windows)
- `packages/brain_api/tests/test_static_ui.py` (existing test masks the bug; fixture lacks dynamic-placeholder file)
- Failed-run artifacts at `/tmp/plan14-artifacts/playwright-report-windows-2022/test-results/` — `error-context.md` page snapshots confirm empty `<main>` on both failures.
- Reproduced the path-separator transform via Python's `ntpath` module on Mac, demonstrating the exact transform Starlette applies on Windows.

---

**End of Plan 15.**
