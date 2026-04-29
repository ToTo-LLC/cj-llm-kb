# Plan 14 — Hardening + CI restoration

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Plan 14 D11 locks **sequential per-task dispatch with two-stage review** (Plan 11 + 12 + 13 discipline) — do NOT parallelize even when the dependency graph allows it (Tasks 1-2, 3-5, 6, and 7-8 are nominally independent).

**Goal:** Restore the hard CI gate so the cascade-shadowing class of regression Plan 13 Task 6 surfaced cannot slip through silently again, AND close the latent SPAStaticFiles non-http-scope bug Plan 13 Task 5 review M1 flagged, AND extend a11y coverage to populated states (where bugs actually live, not just empty-state routes), AND triage the pre-existing `ingest-drag-drop.spec.ts` flake that blocks "all Playwright specs in CI" from going green. Two tracks in one cohesive plan:

1. **#B1 (brain_api hardening) — `SPAStaticFiles` non-http scope guard.** Plan 13 Task 5 review M1: `static_ui.py:141-147`'s `SPAStaticFiles.get_response` inherits from `StaticFiles`, whose `__call__` does `assert scope["type"] == "http"`. Production today never reaches this path (real WS routes match before fall-through), but Task 4 findings line 400 explicitly noted the latent bug. Plan 14 D3 (locked 2026-04-29): override `SPAStaticFiles.__call__` to return 404 for non-http scopes. Defense-in-depth; future-proof against route-ordering changes.

2. **#B2 (brain_api hardening) — `request_id` pin in 500 envelope.** Plan 13 Task 5 review M3: the `test_envelope_shape_parity.py::test_route_500_envelope_shape` asserts the top-level keys but leaves `body["detail"]["request_id"]` unpinned. If `RequestIDMiddleware` silently stops attaching `request_id`, the test won't catch it. Plan 14 D4 (locked 2026-04-29): assert `'request_id' in body['detail']` AND `len(body['detail']['request_id']) > 0`. Future-proof if RequestIDMiddleware switches generators (don't over-specify UUID format). Audit `tests/test_request_id_middleware.py` first to confirm no pre-existing pin test.

3. **#C2.a (a11y populated dialogs) — extend coverage to dialog states.** Plan 13 Task 6 review #2 + #7: the existing `a11y.spec.ts` only tests empty-state routes (no seeded vault content beyond `BRAIN.md`); axe-core only flags rendered elements. Real users hit modals + dialogs constantly. Plan 14 D5 + D6 + D9 (locked 2026-04-29): new `apps/brain_web/tests/e2e/a11y-populated.spec.ts` covers dialog states. Task 3 lands the dialogs subset: rename-domain dialog, delete-domain dialog, fork-thread dialog, repair-config dialog, backup-restore dialog, cross-domain modal, patch-card edit dialog, autonomy modal.

4. **#C2.b (a11y populated menus + overlays) — extend coverage further.** Same spec file as Task 3; second task adds menus + overlays: topbar scope picker dropdown, Settings tab navigation, file-preview overlay, drop-zone hover state, toast notifications. Comprehensive coverage per D5.

5. **#C3 (a11y `.prose a` dark contrast) — route through `var(--tt-cyan)`.** Plan 13 Task 6 review #2: `.prose a` uses `var(--brand-ember)` (= `#C64B2E`) directly, NOT `var(--tt-cyan)`. In dark mode on `--surface-1` (`#141412`), this gives ~3.9:1 — fails 4.5:1 AA for body text. Existing a11y suite seeds an empty BRAIN.md vault — no chat thread, no rendered prose, so axe never sees `.prose a`. Plan 14 D7 (locked 2026-04-29): change `.prose a` to use `var(--tt-cyan)` (theme-aware: dark mode = `#E06A4A` bright, light mode = `#C64B2E` ember). Single source of truth; auto-fix when `--tt-cyan` is nudged in future. Also removes hardcoded `[data-theme="dark"] .prose a:hover` line 609 from brand-skin.css (consolidates with #E06A4A cleanup).

6. **#D8 (`ingest-drag-drop.spec.ts` flake) — diagnose + fix.** Plan 13 Task 7 closure noted `ingest-drag-drop.spec.ts` failed in the full Playwright suite (passes in isolation; flake). With D2's "all Playwright specs in CI" choice, this blocks CI from going green. Plan 14 D8 (locked 2026-04-29): diagnose root cause (likely a race condition between drag-drop event and pending-queue refetch); fix with proper `await` or `wait-for-network-idle`. Mirror Plan 13 Task 4's hypothesis-confirm-first pattern if non-trivial.

7. **#C1.a (Playwright on macOS-14 CI) — restore the structural gate.** Plan 13 Task 6 surfaced that CI doesn't include Playwright (only `pytest packages/brain_core` + ruff + mypy). The cascade-shadowing class of regression that hit Plan 13 was ONLY catchable via Playwright; without it in CI, future v5/v6 theme drops repeat the same regression. Plan 14 D1 + D2 (locked 2026-04-29): add Playwright to CI on macOS-14 GitHub runner. brain_api webServer bootstrap + chflags handling for editable installs + temp vault + cross-OS shell semantics. Run all Playwright specs (full e2e suite) per D2.

8. **#C1.b (Playwright on windows-2022 CI) — restore the structural gate, Windows side.** Mirror Task 7's macOS work on a Windows runner. PowerShell + tar.exe + Defender SmartScreen + Windows path quirks. Spec target says "Mac 13+ and Windows 11 are first class"; Plan 14 D1 (locked 2026-04-29) bundles both from start to preserve symmetry. Run all Playwright specs per D2.

9. **(closure) — Demo + e2e + lessons closure + spec footnote.** 12-gate demo per D10. Plan 14 candidate-scope tail block in `tasks/todo.md` removed; Plan 15 candidate-scope tail block added. Per D11, append a lightweight spec footnote to `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` noting the CI gate now includes Playwright on Mac+Windows. Lessons capture (closure-summary hypotheses, cascade-shadowing class lesson, populated-state coverage lesson).

**Architecture.** Two-track plan: brain_api hardening (Tasks 1-2) + a11y/CI restoration (Tasks 3-9). Tasks 1-2 are independent of Tasks 3-9; Tasks 3-5 are the a11y data plumbing; Task 6 is the flake fix that gates CI; Tasks 7-8 are the CI workflow itself. D11 locks sequential dispatch anyway because Plan 11/12/13 review-discipline catch-rate justifies the wall-clock cost. Demo gate composition (D10) is one assertion per item plus per-populated-state group plus a closure sentinel = 12 gates.

**Tech Stack.** Same gates as Plan 11 + 12 + 13 — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright. Plus: GitHub Actions YAML, macOS-14 + windows-2022 runners, fnm bootstrap (Plan 08 patterns), chflags + PYTHONPATH workarounds (lesson 341 + Plan 12+13 refinements). No new third-party deps.

**Demo gate.** `uv run python scripts/demo-plan-14.py` (or chflags-prefixed variant per lesson 341) walks 12 gates:

1. **SPAStaticFiles WS-scope guard** (B1): Build a fake WebSocket scope dict; pass to `SPAStaticFiles.__call__`; assert raises HTTPException(404) or returns 404 status.
2. **request_id 500 envelope pin** (B2): Run `pytest packages/brain_api/tests/test_envelope_shape_parity.py::test_route_500_envelope_shape_includes_request_id` (the new sub-test); assert exit code 0.
3. **a11y populated chat thread** (C2.a subset): Playwright walks chat thread with seeded prose; axe-core scan; 0 color-contrast violations.
4. **a11y populated dialogs** (C2.a): Playwright opens rename + delete + fork + cross-domain + patch-card + autonomy dialogs; axe-core scan each; 0 violations.
5. **a11y populated menus** (C2.b): Playwright opens topbar scope dropdown + Settings tabs; axe-core scan; 0 violations.
6. **a11y populated overlays** (C2.b): Playwright opens file-preview + drop-zone hover + toasts; axe-core scan; 0 violations.
7. **`.prose a` dark contrast** (C3): Render `.prose a` in dark mode; assert computed color is `--tt-cyan` (#E06A4A) and contrast vs `--surface-1` ≥ 4.5:1.
8. **ingest-drag-drop spec stability** (D8): Run `npx playwright test ingest-drag-drop.spec.ts --repeat-each=5`; assert all 5 runs pass.
9. **GitHub Actions workflow file shape** (C1): Parse `.github/workflows/playwright.yml`; assert `runs-on` matrix includes `macos-14` + `windows-2022`; assert step list includes `chflags` (Mac) + appropriate Windows shell handling; assert `npx playwright test` is the test step.
10. **Full local Playwright suite** (regression guard): Run all e2e specs; assert all pass.
11. **brain_api full pytest** (regression guard): Run `pytest packages/brain_api -q`; assert no regressions vs Plan 13 baseline (173 passed).
12. **`PLAN 14 DEMO OK`** sentinel.

Prints `PLAN 14 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents.**
- `brain-mcp-engineer` (role-overloaded brain-api-engineer per Plan 05 precedent) — Task 1 (SPAStaticFiles guard), Task 2 (request_id pin)
- `brain-frontend-engineer` — Task 3 (a11y populated dialogs), Task 4 (a11y populated menus + overlays), Task 5 (.prose a contrast)
- `brain-test-engineer` — Task 6 (ingest-drag-drop flake diagnose+fix), Task 9 (closure demo + e2e + lessons + spec footnote); pairs with `brain-installer-engineer` on Tasks 7+8
- `brain-installer-engineer` — Task 7 (Playwright on macOS-14 CI), Task 8 (Playwright on windows-2022 CI)
- `brain-ui-designer` — no scope (Task 5 is token re-mapping, not microcopy; Plan 13 Task 6 precedent)
- `brain-core-engineer` — no scope (no brain_core changes in Plan 14)
- `brain-prompt-engineer` — no scope (no prompt changes)

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 13 closed clean: `git tag --list | grep plan-13-cross-instance-cleanup-and-test-debt` exists.
- Confirm no uncommitted changes on `main`.
- Confirm `tasks/lessons.md` contains the Plan 13 closure section (7 lessons captured).
- Confirm `apps/brain_web/out/` exists (from Plan 13 Task 3's `npm run build`); CI workflow design assumes the build step is in CI, but Tasks 3-6 + 9 demo gate all require it locally.
- **Plan 14 inverts a passive Plan 09 policy.** Plan 09 close said "Plan 09 should not relax it" about the axe-core a11y gate but Plan 09 didn't add Playwright to CI either. Plan 14 makes the gate genuinely structural (CI-enforced), not just locally-runnable.
- Note the recurring uv `UF_HIDDEN .pth` workaround documented in lessons.md Plan 11 (lesson 341) and refined in Plan 12+13: the `chflags 0` step must be the IMMEDIATE prefix of the same command that runs python; do NOT use `uv run` (re-syncs and re-hides). Tasks 7+8 must encode this pattern in the CI workflow's step list.

---

## What Plan 14 explicitly does NOT do

These are tempting adjacent expansions filed for Plan 15+:

- **Architectural follow-throughs** carried from Plan 12+13 reviews: orphan listDomains consumers (bulk-screen + file-to-wiki-dialog migrations), `removeDomainOptimistic` action + delete-handler wiring, `useDomainsStore.error` inline banner, `domainsLoaded`→`loaded` naming alignment, drop/wire cross-domain-gate-store error field, BroadcastChannel cross-tab pubsub, `setAcknowledgedOptimistic` early-return pattern, split `panel-domains.tsx` into 3 files. Plan 15 polish thread.
- **Small cleanups carried from Plan 12+13** that didn't make Plan 13's scope: plan-text "topbar scope chip" inaccuracy drift watch (lesson, not code), `brain start` CLI chflags handling, modal/Settings jargon split, active-domain dropdown toast CTA wording, `pushToast` outside try-block, `pendingSendRef.mode` dead field. Plan 15 polish thread.
- **a11y populated state extensions** beyond Tasks 3+4: error-state routes, network-failure routes, mid-loading-spinner states, Drag-Drop-Active states, theme-transition mid-flight states. Plan 15+ if violations surface.
- **CSS structural cleanup**: `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in patch-card.tsx:117, `#E06A4A` consolidation across brand-skin.css (4 sites), tokens.css consolidation OR CSS lint rule for duplicate token defs. Plan 15 polish.
- **Test-quality follow-throughs**: `_NO_CONFIG_MESSAGE` extraction to `tools/_errors.py`, `_mk_ctx` signature alignment, `apply_patch._resolve_config` Plan 07 Task 5 deferral docstring. Plan 15 polish.
- **Bigger architectural moves**: per-domain budget caps, per-domain rate limits, repair-config UI, cross-process hot-reload, `validate_assignment=True` on Config, per-domain autonomy categories, "Set as default" topbar button, per-thread cross-domain confirmation, generic "tool reads ctx.config" lint rule, migration tool for old config.json files, generic zustand promotion across other hooks. Plan 15+ as separate plans.

If any of these come up during implementation, file a TODO and keep moving.

---

## Decisions (locked 2026-04-29)

User signed off on all 11 recommendations on 2026-04-29 across three batched rounds. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope.

### Group I — Scope cut

| # | Decision | Locked | Why |
|---|---|---|---|
| Scope | Plan 14 covers seven items + closure: #B1 SPAStaticFiles non-http guard, #B2 request_id pin in 500 envelope, #C2.a a11y populated dialogs, #C2.b a11y populated menus + overlays, #C3 `.prose a` dark contrast, #D8 ingest-drag-drop flake fix, #C1.a Playwright on macOS-14 CI, #C1.b Playwright on windows-2022 CI. Defers architectural cleanup + small cleanups + bigger moves to Plan 15+. | ✅ | "Hardening + CI" cut. Cohesive theme: restore the hard CI gate so a11y regressions can't slip silently again + close the latent SPAStaticFiles WS bug + extend a11y to populated states. Plan 15 starts with a clean CI surface. |

### Group II — brain_api hardening (#B1 + #B2)

| # | Decision | Locked | Why |
|---|---|---|---|
| D3 | `SPAStaticFiles` hardening shape: override `__call__` to return 404 for non-http scopes. One-line guard at the top of `SPAStaticFiles.__call__`: `if scope["type"] != "http": raise HTTPException(404)` (or equivalent ASGI 404 response). Defense-in-depth; production never reaches this path because real WS routes match first. | ✅ | Plan 13 Task 5 review M1 recommendation. "Delegate to next ASGI app" was rejected as more code with no behavior gain. "Skip — defer to Plan 15" was rejected as letting a known latent bug stay unfixed. |
| D4 | `request_id` pin scope: assert `'request_id' in body['detail']` AND `len(body['detail']['request_id']) > 0`. Don't over-specify format (UUID, len, prefix). Audit `packages/brain_api/tests/test_request_id_middleware.py` (or equivalent) first to confirm no pre-existing pin test; add only if grep confirms gap. | ✅ | Plan 13 Task 5 review M3 recommendation. "Stricter UUID-shaped" was rejected as locking RequestIDMiddleware's choice of generator (today UUID4, but could change to ulid/KSUID without behavior impact). "Skip — if Plan 11 already pins" requires the audit step regardless. |

### Group III — a11y populated states (#C2.a + #C2.b)

| # | Decision | Locked | Why |
|---|---|---|---|
| D5 | a11y populated states scope: comprehensive — every dialog + every menu + every overlay. Dialogs covered Task 3 (rename-domain, delete-domain, fork-thread, repair-config, backup-restore, cross-domain modal, patch-card edit, autonomy modal). Menus + overlays covered Task 4 (topbar scope picker, Settings tabs, file-preview overlay, drop-zone hover, toast notifications). | ✅ | "Minimum (chat + cross-domain + patch-card)" was rejected as leaving the long tail of dialogs uncovered. "Just chat + cross-domain modal" was rejected as deferring a real surface. Comprehensive matches the Plan 13 Task 6 review's framing of "the spec's scope is narrower than the app's a11y surface." |
| D6 | a11y harness file: new `apps/brain_web/tests/e2e/a11y-populated.spec.ts`. Existing `a11y.spec.ts` tests empty-state routes; populated-state tests have different lifecycle requirements (need to seed threads / patches / modals before scanning). Separate files keep each focused on one thing. | ✅ | "Extend a11y.spec.ts" was rejected as mixing empty-state + populated-state lifecycles in same file; harder to reason about test ordering and shared setup. Plan 13 Task 6 review #7 explicitly recommended a separate file. |

### Group IV — `.prose a` dark contrast (#C3)

| # | Decision | Locked | Why |
|---|---|---|---|
| D7 | `.prose a` dark-mode contrast fix: route through `var(--tt-cyan)`. Change `.prose a` to use `var(--tt-cyan)` (theme-aware: dark mode = `#E06A4A` bright, light mode = `#C64B2E` ember). Single source of truth; auto-fix when `--tt-cyan` is nudged in future. Also removes the hardcoded `[data-theme="dark"] .prose a:hover` from brand-skin.css line 609 (consolidates with `#E06A4A` cleanup deferred to Plan 15+). | ✅ | "Add explicit dark-mode override" was rejected as adding a 5th hardcoded `#E06A4A` site (technical debt). Plan 13 Task 6 review #2 recommended single-source-of-truth approach. |

### Group V — Pre-existing flake (#D8)

| # | Decision | Locked | Why |
|---|---|---|---|
| D8 | `ingest-drag-drop.spec.ts` flake handling: diagnose + fix in Plan 14. Add as a Plan 14 task. Diagnose (likely race between drag-drop event and pending-queue refetch); fix with proper `await` or `wait-for-network-idle`. Closes the gate-blocker. Mirror Plan 13 Task 4 hypothesis-confirm-first pattern if non-trivial. | ✅ | "Mark @flaky with retry=2" was rejected as letting the flake stay alive (may hide real regressions). "test.skip + Plan 15 candidate" was rejected as biggest coverage gap. |

### Group VI — CI restoration (#C1.a + #C1.b)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | CI matrix scope: both Mac + Windows from start. macOS-14 + windows-2022 GitHub runners simultaneously. Spec target says "Mac 13+ and Windows 11 are first class"; bundling both from start preserves symmetry. | ✅ | "Mac first, Windows in Plan 15" was rejected as deferring half the spec target. "Linux first" was rejected as not catching the Mac-specific bugs the project actually targets (chflags, Spotlight, .pth shadowing). |
| D2 | Which Playwright specs to add to CI: ALL specs (full e2e suite). Maximum coverage from CI; biggest gate-blocker surface. Implies that the existing `ingest-drag-drop.spec.ts` flake (D8) MUST be fixed to unblock CI go-green. | ✅ | "a11y + setup-wizard only" was rejected as smaller coverage; the spec target says "WCAG 2.2 AA + 14-gate demo are both hard gates" — covering more specs is more aligned. Implies D8 is a load-bearing precursor to C1.a/C1.b. |

### Group VII — Plan shape (#0)

| # | Decision | Locked | Why |
|---|---|---|---|
| D9 | Plan 14 task count: 9 tasks. Task 1 SPAStaticFiles guard (B1) + Task 2 request_id pin (B2) + Task 3 a11y populated dialogs (C2.a) + Task 4 a11y populated menus + overlays (C2.b) + Task 5 .prose a dark contrast (C3) + Task 6 ingest-drag-drop flake fix (D8) + Task 7 Playwright on macOS-14 CI (C1.a) + Task 8 Playwright on windows-2022 CI (C1.b) + Task 9 closure. Splits C2 into two tasks per D5's comprehensive scope; CI tasks split by OS so each can be reviewed independently. Mirrors Plan 13 (7 tasks) + 12 (10 tasks) cadence. | ✅ | "8 tasks" was rejected as combining C2 too coarsely. "7 tasks" was rejected as combining C1.a+C1.b makes the CI rollback story harder. |
| D10 | Demo gate composition: 12 gates per the demo gate description in the plan header. Splits a11y populated states by group (chat, dialogs, menus, overlays); separate gates for B1, B2, C3, D8, C1, full Playwright, brain_api regression. Mirrors Plan 11/12/13 cadence at the higher end. | ✅ | "5 gates collapsed" was rejected as less granular failure signal. "8 gates" was rejected as still collapsing the populated-state subgroups. |
| D11 | Sequential per-task dispatch via `superpowers:subagent-driven-development`. Implementer → spec-reviewer → code-quality-reviewer → fix-loops between tasks. No parallelization even where dep graph allows it. PLUS: lightweight spec footnote — append a brief footnote to `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` noting the CI gate now includes Playwright on Mac+Windows. Adds a small Task 9 sub-step to amend the spec. | ✅ | "Parallel where dep graph allows" was rejected as weakening review-discipline (Plan 11/12/13 caught real bugs at review checkpoints). "Sequential + skip spec amendment" was rejected as leaving the new CI contract undocumented in the canonical spec. |

The implementer routes any unrecognized rule edge case (D3 alternative SPAStaticFiles seam, D4 alternative request_id assertion, D5 alternative a11y populated state list, D7 alternative `.prose a` fix shape, D8 hypothesis falsified mid-diagnose, D9 alternative task split, D10 alternative gate composition) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_api/
├── src/brain_api/
│   └── static_ui.py                    # MODIFY: SPAStaticFiles.__call__ override returning 404 for non-http scopes (D3)
└── tests/
    ├── test_envelope_shape_parity.py   # MODIFY: + test_route_500_envelope_shape_includes_request_id (D4)
    └── test_static_ui_ws_guard.py      # NEW: pin SPAStaticFiles raises on WebSocket scope (D3)

apps/brain_web/
├── src/styles/
│   ├── tokens.css                      # MODIFY: route .prose a through var(--tt-cyan); update docstring (D7)
│   └── brand-skin.css                  # MODIFY: drop hardcoded [data-theme="dark"] .prose a:hover #E06A4A; consolidate to --tt-cyan (D7 scope-adjacent)
├── tests/e2e/
│   ├── a11y-populated.spec.ts          # NEW: comprehensive populated-state a11y coverage (D5 + D6)
│   ├── ingest-drag-drop.spec.ts        # MODIFY: fix race condition (D8 — implementer audit at task time for exact location)
│   └── fixtures.ts                     # MODIFY (likely): + populated-state fixture seeding (chat thread, pending patches, modals)

.github/
├── workflows/
│   └── playwright.yml                  # NEW: matrix on macOS-14 + windows-2022; chflags + brain_api bootstrap + npx playwright test (C1.a + C1.b)

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md      # MODIFY: lightweight spec footnote on CI gate (D11)

scripts/
└── demo-plan-14.py                     # NEW: 12-gate demo per the demo gate above

tasks/
├── plans/14-hardening-and-ci.md        # this file
├── lessons.md                          # MODIFY: + Plan 14 closure section
└── todo.md                             # MODIFY: row 14 → ✅ Complete; remove Plan 14 candidate-scope tail; add Plan 15 candidate-scope tail
```

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 11 + 12 + 13. Every implementer task MUST end with this checklist before reporting DONE.

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_api` (or whichever package)
3. **uv `UF_HIDDEN` workaround** (lesson 341 + Plan 12 + 13 refinements): `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` — clamp BOTH `.pth` files in the SAME COMMAND LINE as the python invocation; do NOT rely on `uv run` (re-syncs and re-hides). Spotlight re-hide cadence is sub-second under `~/Documents/Code/...`; escape hatch is `PYTHONPATH=packages/brain_core/src:packages/brain_mcp/src:packages/brain_api/src:packages/brain_cli/src .venv/bin/python -m pytest ...`.
4. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions (or chflags-prefixed equivalent)
5. `cd packages/<pkg> && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m mypy src tests && cd -` — strict clean (NOT `uv run mypy`)
6. `/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m ruff check packages/<pkg> && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m ruff format --check packages/<pkg>` — clean (no NEW issues; pre-existing OK)
7. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
8. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check is invariant-based, not total-based.
9. **Browser-in-the-loop verification** (CLAUDE.md "Verification Before Done") for any UI-touching task (Tasks 3, 4, 5): start brain, take screenshots of the relevant flows pre and post change, attach to per-task review. **Production-shape integration test** (lesson 343) for Task 1: the new SPAStaticFiles guard must be tested via real WebSocket scope construction, not just unit-test mock. **Multi-OS verification** for Tasks 7+8: the GitHub Actions workflow must be syntactically valid (`gh workflow run --validate` or YAML lint) AND the workflow steps must mirror the canonical local recipe (chflags + PYTHONPATH + npx playwright test).
10. `git status` clean after commit.

Any failure in 4–9 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — `SPAStaticFiles` non-http scope guard (B1)

**Files:**
- Modify: `packages/brain_api/src/brain_api/static_ui.py`
- Create: `packages/brain_api/tests/test_static_ui_ws_guard.py`

**Goal:** Per D3, harden `SPAStaticFiles` against non-http scopes. The latent bug (Plan 13 Task 5 review M1): `static_ui.py:141-147`'s `SPAStaticFiles.get_response` inherits from `StaticFiles`, whose `__call__` does `assert scope["type"] == "http"`. Production today never reaches this path (real WS routes match first), but Plan 13 Task 4 findings line 400 explicitly noted the latent bug. Defense-in-depth; future-proof against route-ordering changes.

**What to do:**
1. **Override `__call__`.** Open `packages/brain_api/src/brain_api/static_ui.py`. Add an override of `__call__` to `SPAStaticFiles` that checks `scope["type"]` first. If non-http (e.g., `"websocket"`, `"lifespan"`), return a 404 response (or raise `HTTPException(404)`). Otherwise delegate to `super().__call__(scope, receive, send)`.
2. **Pin test (production-shape).** New `test_static_ui_ws_guard.py` constructs a fake ASGI WebSocket scope dict (`{"type": "websocket", "path": "/anywhere", ...}`) and passes it to a `SPAStaticFiles(...)` instance via `__call__`. Assert the result is a 404 response (not an `AssertionError` from the parent class). Mirror Plan 11 Task 4's production-shape pattern.
3. **Audit for other non-http scope handlers.** `grep -rn "scope\[.type.\]" packages/brain_api/src/`. Confirm no other StaticFiles-derived classes exist that might have the same latent bug.

**Spec for `test_static_ui_ws_guard.py`:**
- `test_ws_scope_returns_404`: fake `{"type": "websocket", ...}` scope; assert 404.
- `test_lifespan_scope_returns_404` (or passes through cleanly): fake `{"type": "lifespan"}` scope; pin behavior (likely passthrough since lifespan is per-app, not per-mount).
- `test_http_scope_unchanged`: real http scope with valid path; asserts existing SPA fallback behavior unchanged.

**Per-task review:** Production-shape integration test discipline (lesson 343 + D6). The test must construct a real ASGI scope dict, NOT mock `__call__`. If the implementer is tempted to mock, halt and surface to plan-author. Per-task self-review checklist runs to completion before reporting DONE.

---

## Task 2 — `request_id` pin in 500 envelope (B2)

**Files:**
- Audit: `packages/brain_api/tests/` for existing `request_id` pin tests
- Modify: `packages/brain_api/tests/test_envelope_shape_parity.py` (if no pre-existing pin)
- Possibly modify: `packages/brain_api/src/brain_api/middleware/request_id.py` (or wherever RequestIDMiddleware lives — only if the audit surfaces a missing layer)

**Goal:** Per D4, pin the `request_id` slot in the 500 envelope's `detail` so RequestIDMiddleware regression is caught at unit-test time. Plan 13 Task 5 review M3 noted the 500 envelope test asserted top-level keys but left `body['detail']['request_id']` unpinned.

**What to do:**
1. **Audit.** `grep -rn "request_id" packages/brain_api/tests/`. Identify existing pin tests for RequestIDMiddleware. If a test asserting `body['detail']['request_id']` exists for the 500 envelope path, log the finding and skip step 2.
2. **Add the pin.** If gap confirmed, add a sub-test to `test_envelope_shape_parity.py::test_route_500_envelope_shape` (or as a separate test method): assert `'request_id' in body['detail']` AND `len(body['detail']['request_id']) > 0` AND `isinstance(body['detail']['request_id'], str)`. Don't over-specify format (UUID, len).
3. **Verify the assertion fails when removed.** Locally comment out the RequestIDMiddleware step; re-run; confirm the new test fails. Restore. (This proves the test is load-bearing, not coincidental.)

**Per-task review:** if the audit surfaces a comprehensive pre-existing pin test, this task may be a no-op; report findings. Otherwise the new sub-test is the artifact. Per-task self-review checklist runs to completion.

---

## Task 3 — a11y populated dialogs (C2.a)

**Files:**
- Create: `apps/brain_web/tests/e2e/a11y-populated.spec.ts`
- Modify: `apps/brain_web/tests/e2e/fixtures.ts` (likely; add populated-state fixture seeding)

**Goal:** Per D5 + D6, extend a11y coverage to dialog states. New `a11y-populated.spec.ts` mounts each dialog in turn and runs axe-core scan. Dialogs covered:
- Rename-domain dialog (open via Settings → Domains → row → Rename)
- Delete-domain dialog (open via Settings → Domains → row → Delete; the typed-confirm step is a separate dialog)
- Fork-thread dialog (open via Chat → thread menu → Fork)
- Repair-config dialog (open via Settings → ... → Repair config; note: may not have a UI surface today — confirm with implementer audit)
- Backup-restore dialog (open via Settings → Backups → Restore)
- Cross-domain modal (open via chat send with scope=`[research, personal]`; Plan 12 Task 9)
- Patch-card edit dialog (open via Pending → patch row → Edit)
- Autonomy modal (open via... — confirm trigger with implementer audit)

**What to do:**
1. **Audit dialog inventory.** `grep -rn "Dialog\|dialog\.tsx" apps/brain_web/src/components/dialogs/`. Confirm the 8 dialogs above all have UI surfaces; note any that don't (file as Plan 15 candidate).
2. **Build populated-state fixtures.** Extend `fixtures.ts` (or `a11y-populated.spec.ts` directly) to seed:
   - A vault with research + work + personal domains (for cross-domain modal trigger)
   - A chat thread with rendered prose + tool-calls + citations (for any dialog opened from chat context)
   - A pending patch (for patch-card edit dialog)
   - A backup tarball (for backup-restore dialog)
3. **Per-dialog test cases.** For each of the 8 dialogs, write a Playwright test that: (a) navigates to the trigger location, (b) opens the dialog, (c) waits for stable render, (d) runs `checkA11y(page)` per existing fixture pattern, (e) asserts 0 violations. Use `expect(...).toEqual([])` per existing `fixtures.ts` discipline (no `expect.soft`).
4. **Anti-regression.** Confirm all existing `a11y.spec.ts` cases still pass (no shared-state pollution from the new fixture).

**Spec for `a11y-populated.spec.ts` (Task 3 dialogs subset):**
- 8 test cases, one per dialog. Each: open + wait + scan + assert 0 violations.
- Shared `beforeEach` to seed populated state.
- `DISABLED_RULES = []` — same hard-fail discipline as `a11y.spec.ts`.

**Per-task review:** browser-in-the-loop verification — open brain, manually walk through each dialog, screenshot to confirm visual state matches what Playwright is scanning. If any dialog has axe-core violations (color-contrast, aria-valid, label-content-name-mismatch, etc.), fix the underlying component or document as Plan 15 candidate (only color-contrast is in Plan 14 scope per Plan 13 Task 6 precedent — other rule families may surface but are NOT Plan 14 commitments). Per-task self-review checklist runs to completion.

---

## Task 4 — a11y populated menus + overlays (C2.b)

**Files:**
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (extend Task 3's file)

**Goal:** Per D5, extend a11y coverage to menus + overlays:
- Topbar scope picker dropdown (open via topbar → click)
- Settings tab navigation (each tab in Settings)
- File-preview overlay (open via Browse → file → preview)
- Drop-zone hover state (drag a file over, axe-scan mid-drag — note: may need synthetic drag event)
- Toast notifications (trigger a toast, axe-scan while visible)

**What to do:**
1. **Audit menu/overlay inventory.** `grep -rn "Dropdown\|Popover\|Toast\|Overlay" apps/brain_web/src/components/`. Confirm the 5 menus/overlays above all have UI surfaces.
2. **Per-menu/overlay test cases.** Extend the spec from Task 3 with 5 more test cases. Each follows the same shape: trigger + wait + scan + 0 violations.
3. **Anti-regression.** Existing `a11y.spec.ts` + Task 3 dialog cases still pass.

**Spec for `a11y-populated.spec.ts` (Task 4 menus+overlays subset):**
- 5 additional test cases.

**Per-task review:** if any axe-core violations surface in non-color-contrast rule families during the menu/overlay scans, document and defer to Plan 15. Browser verification + per-task self-review checklist.

---

## Task 5 — `.prose a` dark contrast fix (C3)

**Files:**
- Modify: `apps/brain_web/src/styles/tokens.css` (route `.prose a` through `var(--tt-cyan)`)
- Modify: `apps/brain_web/src/styles/brand-skin.css` (drop hardcoded `[data-theme="dark"] .prose a:hover` — line 609)
- Possibly modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (assert chat thread populated with `.prose a` rendered now passes)

**Goal:** Per D7, fix the `.prose a` dark-mode contrast hole. `.prose a` currently uses `var(--brand-ember)` (= `#C64B2E`) directly; in dark mode on `--surface-1` (`#141412`), this gives ~3.9:1 — fails 4.5:1 AA. Route through `var(--tt-cyan)` which is theme-aware (dark = `#E06A4A` bright, light = `#C64B2E` ember). Single source of truth.

**What to do:**
1. **Audit `.prose a` definition.** `grep -rn ".prose a" apps/brain_web/src/styles/`. Identify the current rule + selector specificity.
2. **Route through `--tt-cyan`.** Change `.prose a { color: var(--brand-ember); }` to `.prose a { color: var(--tt-cyan); }`. Confirm the `--tt-cyan` token is defined in both light + dark modes (it is, post-Plan 13 Task 6).
3. **Drop hardcoded dark-mode override.** brand-skin.css line 609 has `[data-theme="dark"] .prose a:hover { color: #E06A4A; }`. Since `--tt-cyan` IS `#E06A4A` in dark mode now, this rule is redundant. Drop it.
4. **Visual verification.** Browser-load a chat thread with rendered prose links. Light + dark mode. Confirm links are visibly different from regular text + meet 4.5:1 contrast. Screenshot.
5. **a11y spec verification.** The chat-thread populated-state test from Task 3 should now NOT flag `.prose a` (it would have pre-fix). Re-run the spec; confirm 0 violations.

**Per-task review:** browser verification + screenshot triple (default zoom + 200% zoom + DOM snapshot) per Plan 13 Task 6 precedent.

---

## Task 6 — `ingest-drag-drop.spec.ts` flake fix (D8)

**Files:**
- Modify: `apps/brain_web/tests/e2e/ingest-drag-drop.spec.ts`
- Audit: related drag-drop component code (likely `apps/brain_web/src/components/bulk/drop-zone.tsx` or similar; implementer audit at task time)

**Goal:** Per D8, diagnose + fix the pre-existing flake. The spec passes in isolation but fails in the full Playwright suite. With D2's "all Playwright specs in CI" choice, this MUST be fixed for CI to go green.

**What to do (mirror Plan 13 Task 4 hypothesis-confirm-first if non-trivial):**
1. **Reproduce.** `cd apps/brain_web && PYTHONPATH=... npx playwright test ingest-drag-drop.spec.ts` (passes). Then `npx playwright test --reporter=list` (full suite; flakes). Capture full output.
2. **Hypothesis-test 1 (race condition):** Run `npx playwright test ingest-drag-drop.spec.ts --repeat-each=10`. If passes 10/10 in isolation but fails in full suite, race condition with a sibling spec is likely.
3. **Hypothesis-test 2 (fixture pollution):** Run `npx playwright test --reporter=list --grep "before ingest-drag-drop"` (or whatever specs run before it). Identify whether sibling specs leave state that pollutes the drag-drop fixture.
4. **Diagnose root cause.** Likely candidates: drag-drop event timing, pending-queue refetch timing, IndexedDB / localStorage pollution, brain_api temp vault not torn down.
5. **Fix.** Surgical edit: add proper `await` on the drag-drop event, OR add `waitForResponse(...)` for the pending-queue API call, OR add cleanup in afterEach. NOT a `test.fixme()` retry.
6. **Verify.** `npx playwright test --repeat-each=5`; assert ingest-drag-drop passes 5/5. Then full suite; assert no regressions.

**Per-task review:** if the diagnose surfaces a deeper flake category (multiple specs share the same race), surface to plan-author for Plan 14 scope expansion (could be a Task 6.5 or addendum). Per-task self-review checklist.

---

## Task 7 — Playwright on macOS-14 CI (C1.a)

**Files:**
- Create: `.github/workflows/playwright.yml` (or extend existing CI workflow)
- Possibly create: `.github/scripts/setup-mac-playwright.sh` (helper script for chflags + brain_api bootstrap)

**Goal:** Per D1 + D2, add Playwright to CI on macOS-14 GitHub runner. brain_api webServer bootstrap + chflags handling for editable installs + temp vault + cross-OS shell semantics. Run all Playwright specs (full e2e suite). The structural fix Plan 13 Task 6 review #1 called out — without this, future v5/v6 theme drops repeat the cascade-shadowing class of regression.

**What to do:**
1. **Audit existing CI.** Read `.github/workflows/`. Identify existing job structures. Plan 14 may reuse the `build` job's `setup-uv` step, OR create a fully-separate `playwright-mac` job.
2. **Workflow file.** Create `.github/workflows/playwright.yml` (or new job in existing file). Trigger on push + PR.
3. **macOS-14 job.** `runs-on: macos-14`. Steps:
   - `actions/checkout@v4`
   - `astral-sh/setup-uv@v3` (or equivalent)
   - `uv sync --all-packages`
   - chflags 0 on the editable .pth files (per lesson 341)
   - `pnpm --dir apps/brain_web install`
   - `pnpm --dir apps/brain_web build` (populates `out/` for static export tests)
   - `pnpm --dir apps/brain_web exec playwright install --with-deps chromium`
   - `cd apps/brain_web && PYTHONPATH=... npx playwright test`
4. **Local validation.** Use `gh workflow run --validate` or YAML lint to confirm the workflow is syntactically valid.
5. **Push + observe.** Push the workflow; observe the first CI run on a feature branch. Iterate fixes if any step fails (uv lockfile drift, pnpm cache issues, chflags semantics differences from local Mac).

**Per-task review:** the CI run is the artifact. Capture the green-CI run URL in per-task review notes. If the run takes >20min, surface to plan-author (may need to split or optimize).

---

## Task 8 — Playwright on windows-2022 CI (C1.b)

**Files:**
- Modify: `.github/workflows/playwright.yml` (add windows-2022 job)
- Possibly create: `.github/scripts/setup-windows-playwright.ps1`

**Goal:** Per D1 + D2, mirror Task 7's macOS work on windows-2022 runner. PowerShell + tar.exe + Defender SmartScreen + Windows path quirks. Same Playwright specs.

**What to do:**
1. **Windows-2022 job.** `runs-on: windows-2022`. Steps mirror Task 7 but adjust for Windows shell:
   - PowerShell instead of bash
   - Use `pwsh` shell where possible (same scripting on both platforms)
   - No chflags needed (Windows doesn't have UF_HIDDEN issue)
   - tar.exe (built-in to Windows 10+)
   - Watch for Defender SmartScreen on first-run executables
2. **Path differences.** Use `${{ github.workspace }}` consistently; avoid hardcoded `/` separators.
3. **brain_api bootstrap.** Confirm `uv sync` produces a working venv on Windows (it should; Plan 08 patterns work).
4. **Push + observe.** Same as Task 7.

**Per-task review:** Windows-specific surprises (line endings, path quirks, file locking) often surface here. Document and fix in-task; Plan 15 candidate only if non-trivial multi-task scope.

---

## Task 9 — Closure: 12-gate demo + lessons + spec footnote + todo.md

**Files:**
- Create: `scripts/demo-plan-14.py`
- Modify: `tasks/lessons.md` (Plan 14 closure section)
- Modify: `tasks/todo.md` (row 14 → ✅; remove Plan 14 candidate-scope; add Plan 15 candidate-scope)
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (lightweight spec footnote per D11)

**Goal:** Land the 12-gate demo from the plan header. Lessons capture. todo.md update. Spec footnote.

**What to do:**
1. **demo-plan-14.py.** Mirror `scripts/demo-plan-13.py`'s structure. Build the 12 gates (see plan header for full description).
2. **Lessons capture.** Mirror Plan 13 closure-section format. Likely candidates:
   - Latent-bug-in-passthrough-class lesson (B1) — `StaticFiles.__call__` accepted WS scopes silently; defense-in-depth via override is a generic pattern.
   - Test-as-pin-not-test-as-trigger lesson (B2) — pin the assertion shape but don't over-specify implementation details (UUID format).
   - Populated-state-coverage lesson (C2.a + C2.b) — empty-state a11y testing misses ~80% of the app surface; populated states are where bugs live.
   - Single-source-of-truth-token lesson (C3) — theme-aware tokens (`--tt-cyan`) are auto-fixing; hardcoded `#E06A4A` is drift-prone.
   - Race-condition-via-suite-isolation lesson (D8) — flakes that pass in isolation are race conditions, not Playwright bugs.
   - CI-as-structural-gate lesson (C1) — local "should not relax it" is wishful; CI enforcement is the structural fix.
3. **Spec footnote.** Append to `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (likely §8 or end of §7): "**CI gate (Plan 14):** all Playwright specs run on macOS-14 + windows-2022 GitHub Actions runners; the axe-core hard-fail a11y assertion is structurally enforced. Theme/skin changes that regress AA contrast cannot ship silently."
4. **todo.md update.** Row 14 → ✅. Remove Plan 14 candidate-scope; add Plan 15 candidate-scope (architectural cleanup + small cleanups + bigger moves; capture from Plan 13 + 14 NOT-DOING sections).

**Per-task review:** demo gates 1-12 all green. Lessons capture is the Plan 14 retrospective. todo.md update is the closure handoff. Spec footnote is the documentation seam. Per-task self-review checklist runs to completion.

---

## Review (pending)

To be filled in on closure following Plan 10 + 11 + 12 + 13 format:
- **Tag:** `plan-14-hardening-and-ci` (cut on green demo).
- **Closes:** the 7 hardening items from Plan 14 candidate scope (B1, B2, C1.a, C1.b, C2.a, C2.b, C3, D8). Plan 14 candidate-scope tail block in `tasks/todo.md` removed; Plan 15 candidate-scope tail added.
- **Bumps:** tool count unchanged. Schema unchanged. brain_api test count rises by ~3-5 new pin tests (B1 ws_guard + B2 request_id sub-test + audit-driven additions). brain_web Playwright count rises significantly (+13 a11y-populated cases). New CI workflow on Mac + Windows.
- **Verification:** all 12 demo gates green (`scripts/demo-plan-14.py` → `PLAN 14 DEMO OK`); pytest count + vitest count + Playwright count + first green CI run URLs to be filled in.
- **Backlog forward:** Plan 15 candidate scope pre-populated per Task 9 step 4. Themes: architectural cleanup (orphan listDomains, removeDomainOptimistic, naming alignment, panel-domains split) + small cleanups carried from Plan 12+13 (brain start chflags, jargon, toast wording, dead fields, tokens.css consolidation) + bigger architectural moves (per-domain budgets, validate_assignment, hot-reload).
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 14" feed Plan 15's authoring.

---

**End of Plan 14.**
