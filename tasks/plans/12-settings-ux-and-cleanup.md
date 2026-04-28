# Plan 12 — Settings UX completion + Plan 11 correctness cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Plan 12 D11 locks **sequential per-task dispatch with two-stage review** (Plan 11 discipline) — do NOT parallelize even when the dependency graph allows it.

**Goal:** Close the six follow-ups carried forward from Plan 11's closure addendum. Two threads in one cohesive plan:

1. **#1 (cleanup) — DELETE `resolve_autonomous_mode`.** Plan 11 Task 5 landed `brain_core.llm.resolve_autonomous_mode(config, domain) -> bool` per D13's resolver pattern, but the autonomy gate at `brain_core.autonomy` reads per-category flags via `Config.autonomous.<category>` — not the coarse top-level `Config.autonomous_mode` bool the resolver guards. The resolver is dead code and the user-guide drift caught by Plan 11 Task 9 (lesson 351) flagged it. Plan 12 deletes the resolver and removes `DomainOverride.autonomous_mode` (no consumer remains).
2. **#10 (correctness) — `brain_mcp` Config-wiring fix.** Plan 11 Task 4 wired `save_config()` into five mutation tools assuming `ctx.config` is set. Plan 11 Task 7 fixed brain_api's `build_app_context()`; `brain_mcp/server.py:_build_ctx` (line 140) never got the same fix. Plan 11 mutations dispatched via Claude Desktop → brain_mcp silently fall to the `ctx.config is None` no-op branch (toast says "saved" but disk write never happens). Plan 12 ports the fix and adds a stdio MCP integration test as production-shape regression guard per lesson 343.
3. **#9 (correctness) — `brain_config_get` snapshot drift + read-tool audit.** `brain_config_get` constructs a fresh `Config()` instead of reading `ctx.config` (`tools/config_get.py:51`). Plan 11 lesson 353 named this category and recommended audit. Plan 12 audits all read tools in `brain_core/tools/`, fixes every `Config()` snapshot, and adds a regression-pin contract test asserting each read tool threads `ctx.config`.
4. **#11 (correctness) — `useDomains()` cross-instance pubsub.** Surfaced during Plan 11 Task 10 e2e closure (commit 7239bcf addendum). The hook caches its last response in module state; mutations via `panel-domains.tsx`'s `invalidateDomainsCache()` don't propagate to already-mounted consumers (topbar). Workaround today: `page.reload()` between mutation and cross-surface verification. Plan 12 promotes the hook to a zustand store entry; `useDomains()` becomes a selector; mutations push state via the store, eliminating cross-instance divergence.
5. **#7 (UX) — `active_domain` Settings UI.** Today the only way to change `Config.active_domain` is to hand-edit `config.json` (Plan 11 Task 8 verification used this workaround). Plan 11 lifted `active_domain` onto the `brain_list_domains` response and seeded scope on first mount, but `brain_config_set` still rejects the key by design. Plan 12 extends `_SETTABLE_KEYS` to allow `"active_domain"`, adds a typed `setActiveDomain(slug)` helper to `lib/api/tools.ts`, and surfaces a "Default active domain" dropdown at the top of `panel-domains.tsx`.
6. **#8 (UX) — Cross-domain confirmation modal.** Spec §4 line 187 mandates "a one-time confirmation warning" for cross-domain scope; the modal has never shipped (deferred from Plan 07 → Plan 11 → here). Plan 12 ships it: brain-ui-designer microcopy + interaction-state mocks (Task 7), `Config.cross_domain_warning_acknowledged: bool` field for per-vault acknowledgment storage (Task 1), modal frontend wired to chat/draft session creation (Task 9). **Trigger (D7):** scope has ≥2 domains AND ≥1 in `Config.privacy_railed`.

**Architecture.** Two-track plan: correctness fixes (#1, #9, #10, #11) land as foundation; UX completion (#7, #8) builds on the fixed foundation. The zustand promotion of `useDomains()` (#11) is the load-bearing refactor — it must land before the active-domain Settings UI (#7) because the "save in Settings → topbar reflects" flow is exactly the cross-instance bug #11 fixes. brain-ui-designer microcopy for the cross-domain modal (#8) is the first task in the #8 sequence (D9); the Config acknowledgment field lands in the schema task (Task 1); the frontend modal implementation lands as Task 9. Spec §4 line 187 amendment + the new D7 trigger / D8 acknowledgment doc lines (D10) land in Task 10 alongside the demo and lessons closure, parallel to Plan 11 Task 9.

**Tech Stack.** Same gates as Plan 11 — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright. zustand is already a workspace dep (`apps/brain_web/src/lib/state/app-store.ts` etc.); Plan 12's #11 promotion uses an existing pattern. No new third-party deps.

**Demo gate.** `uv run python scripts/demo-plan-12.py` (or the chflags-prefixed variant per lesson 341) walks the seven gates: (1) `Config(cross_domain_warning_acknowledged=True)` round-trips through `save_config` + `load_config`; the new field is in `_PERSISTED_FIELDS`; `from brain_core.llm import resolve_autonomous_mode` raises ImportError; `DomainOverride.autonomous_mode` is gone. (2) Monkeypatch `ctx.config` to a sentinel-bearing `Config`; invoke `brain_config_get`; assert returned snapshot reflects sentinel (not `Config()` defaults); audit-loop assertion: every tool listed in `_READ_TOOLS_THAT_THREAD_CTX_CONFIG` passes the same sentinel test. (3) Spawn `brain_mcp` via stdio in a subprocess with a temp vault; dispatch a `brain_config_set log_llm_payloads=true` tool call; assert `<vault>/.brain/config.json` contains the change (not the in-memory-only no-op behavior). (4) jsdom test mounting `panel-domains` + `topbar` simultaneously; mutate domains via panel; assert topbar re-renders without `page.reload()`. (5) Playwright: open Settings → Domains; pick `work` in the "Default active domain" dropdown; reload; topbar scope chip shows `work`. (6) Playwright parametrized: open chat with scope=`[research, personal]` → modal fires; scope=`[research, work]` → no modal (cross-domain but no rail); scope=`[personal]` → no modal (single-domain, opt-in already given). (7) Playwright acknowledgment lifecycle: dismiss modal; reload; open same scope → no modal (`Config.cross_domain_warning_acknowledged=true`); toggle "Show cross-domain warning" in Settings → modal returns next time. Prints `PLAN 12 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents.**
- `brain-core-engineer` — Task 1 (schema), Task 2 (resolver DELETE), Task 3 (read-tool audit), Task 6 (active_domain allowlist + helper), Task 10 (spec/user-guide amend + demo)
- `brain-mcp-engineer` — Task 4 (brain_mcp Config-wiring fix; pairs with brain-test-engineer for the stdio integration test)
- `brain-test-engineer` — Task 4 stdio MCP integration test, Task 10 e2e specs + lessons capture
- `brain-frontend-engineer` — Task 5 (zustand refactor), Task 8 (active_domain dropdown), Task 9 (cross-domain modal frontend)
- `brain-ui-designer` — Task 7 (microcopy + 2 interaction-state mocks)
- `brain-installer-engineer` — no scope (install paths unchanged)
- `brain-prompt-engineer` — no scope (no prompt changes; cross-domain modal is a UI gate, not an LLM gate)

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 11 closed clean: `git tag --list | grep plan-11-persistent-config` exists.
- Confirm no uncommitted changes on `main`.
- Confirm `tasks/lessons.md` contains the Plan 11 closure section. Task 1 references lesson 357 (pydantic v2 cross-field validation pattern). Task 3 references lesson 353 (read-path snapshot anti-pattern). Task 4 references lesson 343 (brain_api Config-wiring oversight; brain_mcp is the same shape). Task 5 may reference lesson 339's "useDomains pubsub" addendum.
- **Plan 12 inverts a deliberate Plan 07-era policy.** `_SETTABLE_KEYS`'s comment at `tools/config_set.py:60` reads *"`active_domain` is deliberately excluded: scope is set per-session by the caller's allowed domains, not by a persisted mid-session toggle."* That rationale was correct for Plan 07 (no persistence, no Settings UI) but is no longer load-bearing post-Plan 11 (persistent disk config + scope hydrated from `active_domain` on first mount). Task 6 MUST update the comment AND the existing rejection test (`test_refuses_non_allowlisted_key` at `test_config_set.py:218` currently uses `active_domain` as the rejected key — pick a different non-allowlisted key like `vault_path` to keep the rejection-coverage assertion intact).
- Note the recurring uv `UF_HIDDEN .pth` workaround documented in lessons.md Plan 11 (lesson 341): the `chflags` step must be the IMMEDIATE prefix of the same command that runs python; do NOT use `uv run` (which re-syncs and re-hides). The Plan 12 demo command line is `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_brain_core.pth "/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_brain_core 2.pth" 2>/dev/null && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python scripts/demo-plan-12.py`. The Playwright webServer can't drop `uv run` cleanly; the workaround there is `PYTHONPATH=packages/.../src npx playwright test`.

---

## What Plan 12 explicitly does NOT do

These are tempting adjacent expansions filed for Plan 13+ (matching the user's brief Group C / "bigger architectural moves"):

- **Per-domain budget caps.** Per-domain caps need a separate cost-ledger schema change.
- **Per-domain rate limits.** Rate limits live in the provider client today.
- **Repair-config UI screen.** Plan 11 D7 landed the auto-fallback chain (`config.json → .bak → defaults`); the UI surface is a Plan 13+ iteration.
- **Hot-reload of config changes across processes.** Plan 11 reaffirmed: cross-process invalidation (e.g., brain_api notifying brain_mcp of a domain rename) is a future iteration.
- **`validate_assignment=True` on `Config` and sub-configs.** Plan 11 Task 4 added a KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`). Performance impact needs measurement first.
- **Wiring `resolve_autonomous_mode` into the autonomy gate.** D1 chose DELETE. Per-domain autonomy categories are a Plan 13+ architectural lift requiring `Config.autonomous` to grow per-domain-per-category structure.
- **"Set as default" button on the topbar scope picker.** D3 placed the editor on `panel-domains.tsx` to preserve the per-session vs persistent-default distinction Plan 11 Task 8 was careful to establish.
- **Per-thread cross-domain confirmation.** D8 chose per-vault `Config` field; per-thread violates spec §4's "one-time" wording.
- **Generic "tool reads ctx.config" lint rule.** D5's audit + regression-pin test is per-tool. A repo-wide ruff rule or AST check is Plan 13+ if the anti-pattern keeps re-appearing.
- **Migration tool for old `config.json` files missing `cross_domain_warning_acknowledged`.** Pydantic defaults handle this on read; `save_config` round-trips with the new field on next mutation. Same pattern as Plan 11's `domain_overrides` / `privacy_railed` defaults.
- **`useDomains` zustand promotion as a generic pattern for `useBudget` / `useDomainOverrides` / etc.** Plan 12 promotes `useDomains` only; generalizing the pattern across other hooks is Plan 13+ if/when the same cross-instance bug surfaces elsewhere.

If any of these come up during implementation, file a TODO and keep moving.

---

## Decisions (locked 2026-04-28)

User signed off on all 11 recommendations on 2026-04-28. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope.

### Group I — Scope cut

| # | Decision | Locked | Why |
|---|---|---|---|
| Scope | Plan 12 covers six items: #7 active_domain Settings UI, #8 cross-domain modal, #9 brain_config_get drift, #10 brain_mcp Config-wiring, #11 useDomains pubsub, #1 DELETE resolver. Closes A + B from the user's Plan 12 candidate-scope brief; defers C ("bigger architectural moves") to Plan 13+. | ✅ | "Maximum cleanup" cut: ships the active_domain Settings UI WITH its prerequisites (#9, #11) so the dropdown actually works on reload AND propagates cross-instance, plus closes the brain_mcp correctness regression and the dead-resolver cleanup. |

### Group II — Cleanup deletion (#1)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | DELETE `resolve_autonomous_mode` from `brain_core/llm/__init__.py`. Remove `DomainOverride.autonomous_mode` field. Remove resolver tests in `tests/llm/test_resolver.py`. Update `docs/user-guide/domain-overrides.md` to drop the per-domain-autonomy claim Plan 11 lesson 351 caught. | ✅ | Resolver is unused today; the autonomy gate reads per-category flags via `Config.autonomous.<category>`, not the coarse `autonomous_mode` bool. WIRE was the alternative (~5-6 tasks, Plan 13+ architectural lift); user picked DELETE consistent with the "Cleanup / unblock" framing. Re-adding later is cheap if per-domain autonomy gets requested. |

### Group III — Active-domain Settings UI (#7)

| # | Decision | Locked | Why |
|---|---|---|---|
| D2 | Extend `_SETTABLE_KEYS` allowlist with `"active_domain"`. Add `setActiveDomain(slug: string)` typed helper to `apps/brain_web/src/lib/api/tools.ts` as a thin wrapper over `brain_config_set`. | ✅ | Matches Plan 11 D14 precedent (extend `brain_config_set` allowlist with new keys / dotted paths). Tool count unchanged. Cross-field validator `_check_active_domain_in_domains` from Plan 10 already enforces "must be in `Config.domains`" — the allowlist relaxation inherits validation for free. |
| D3 | Active-domain dropdown lives at top of `apps/brain_web/src/components/settings/panel-domains.tsx`, above the existing per-domain rows. Topbar scope picker stays per-session-only. | ✅ | Matches Plan 11 D14 ("per-domain admin lives on panel-domains"). Mental model: Settings = persistent defaults, topbar = per-session override. New top-level Settings tab "Defaults" was rejected as orphan-tab IA churn. Topbar growing a "Set as default" button was rejected as muddling the distinction Plan 11 Task 8 was careful to establish. |

### Group IV — useDomains cross-instance pubsub (#11)

| # | Decision | Locked | Why |
|---|---|---|---|
| D4 | Promote the cached `Domain[]` + `activeDomain` from module-state cache in `lib/hooks/use-domains.ts` to a new entry in `lib/state/app-store.ts` (or a dedicated `lib/state/domains-store.ts` if `app-store.ts` is over-loaded — implementer's call at task time). `useDomains()` becomes a selector. Mutations update the store directly via `useDomainsStore.getState().refresh()`; subscribers re-render automatically. The existing `invalidateDomainsCache()` symbol either becomes a no-op alias (with a deprecation comment) or is removed entirely if no callers remain after the refactor. | ✅ | Matches the existing zustand-based pattern in `app-store.ts`; React-idiomatic. Tick-based event emitter was rejected as a parallel notification channel competing with zustand. "Mount-time refetch only" was rejected as not actually fixing the architecture — it would spread the workaround further and re-surface as a Plan 13 problem. |

### Group V — Read-tool audit (#9)

| # | Decision | Locked | Why |
|---|---|---|---|
| D5 | Audit every tool in `packages/brain_core/src/brain_core/tools/` for the `Config()` snapshot anti-pattern (constructing fresh `Config()` instead of reading `ctx.config`). Fix every offender. Add a regression-pin contract test (`tests/tools/test_read_tools_thread_ctx_config.py`) that builds a sentinel-bearing `Config`, monkeypatches `ctx.config` to it, invokes each read tool from a parametrized list, and asserts the return data reflects the sentinel (not defaults). | ✅ | Plan 11 lesson 353 explicitly named this audit. Just-fix-config_get was rejected as leaving the anti-pattern lurking. Audit-without-test was rejected as letting the anti-pattern re-grow on future read tools. The regression test is the same shape as Plan 11 Task 4's mutation-tool persistence pin test. |

### Group VI — brain_mcp Config-wiring fix (#10)

| # | Decision | Locked | Why |
|---|---|---|---|
| D6 | Mirror Plan 11 Task 7 brain_api fix on `brain_mcp/server.py:_build_ctx` (line 140) and the `ToolContext(...)` constructor at line 157: thread `Config` via `load_config(...)` at server-init time. Add a stdio MCP integration test (`packages/brain_mcp/tests/test_config_persistence_stdio.py`) that spawns brain_mcp via stdio, dispatches a `brain_config_set` tool call, and asserts `<vault>/.brain/config.json` contains the new value. Mirror the existing Plan 04 stdio-spawn test pattern. | ✅ | Plan 11 lesson 343 says "load-bearing wiring needs production-shape integration tests, not just unit-test-with-explicit-config tests." Unit-test-only was rejected as the same blind spot that hid the brain_api bug originally. Manual-test-checklist was rejected as not run in CI. |

### Group VII — Cross-domain confirmation modal (#8)

| # | Decision | Locked | Why |
|---|---|---|---|
| D7 | Modal fires when chat/draft session scope has ≥2 domains AND ≥1 of them is in `Config.privacy_railed`. Single-domain railed access does NOT fire the modal — Plan 11 D11 already requires explicit slug inclusion for railed access; that opt-in IS the consent. Pure cross-domain (e.g., `[research, work]`) without rails does NOT fire. | ✅ | Matches spec §4 literal reading ("cross-domain warning about [railed] content"). 8.B (any cross-domain) was rejected as noisy — would re-prompt every research+work scope without rail risk. 8.C (any railed) was rejected as re-prompting single-domain railed chats where Plan 11 D11 already serves as the gate. |
| D8 | Acknowledgment persists in a new `Config.cross_domain_warning_acknowledged: bool` field, default `False`. Surfaces as a "Show cross-domain warning" toggle in Settings → Domains (un-checking the toggle re-enables the modal next time the trigger fires). Field joins `_PERSISTED_FIELDS`. | ✅ | Per-vault scope matches spec §4 "one-time". Settings toggle gives the user a recovery path — Plan 11 lesson 351 caution about user-guide-vs-implementation drift means we surface the toggle so users can re-enable rather than discovering they're stuck. localStorage was rejected as not visible in Settings + lost on clear. Per-thread was rejected as violating spec §4 "one-time". |
| D9 | First task of the #8 implementation sequence is `brain-ui-designer` producing: (a) modal title + body + button labels, (b) "Show cross-domain warning" Settings toggle copy + helper text, (c) 2 interaction-state mocks (initial-trigger view, "after toggle re-enabled" Settings view). Subsequent task (Task 9) implements against the approved microcopy. | ✅ | Mirrors Plan 11 Task 9 spec-amend-first-within-plan precedent. Pre-flight option was rejected as gating Plan 12 dispatch on external work. Inline-microcopy option was rejected as risking Plan 11 lesson 351's drift category. |

### Group VIII — Spec amendment + dispatch (#0)

| # | Decision | Locked | Why |
|---|---|---|---|
| D10 | Spec amendment scope (Task 10): change §4 line 187 wording from "personal content" to "privacy-railed content"; append ~3 sentences documenting the D7 trigger rule + D8 acknowledgment storage. Spec self-contained for future readers. | ✅ | Matches Plan 11 D16 precedent (amend spec wording in same task as implementation). Wording-only was rejected as leaving the new rule undocumented in the spec. New §4.x subsection was rejected as bigger amendment than the change warrants. |
| D11 | Sequential per-task dispatch via `superpowers:subagent-driven-development`. Implementer → spec-reviewer → code-quality-reviewer → fix-loops between tasks. No parallelization even where the dependency graph allows it. | ✅ | Plan 11's review discipline caught lessons 343, 345, 347, 349, 351 — all real bugs surfaced at review checkpoints. Plan 12 is short enough that the catch-rate value outweighs wall-clock savings from parallelization. |

The implementer routes any unrecognized rule edge case (D2 alternative persistence path, D4 alternative pubsub pattern, D5 alternative audit scope, D7 alternative trigger semantics, D9 alternative microcopy ownership) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/
│   ├── config/
│   │   └── schema.py                        # MODIFY: + Config.cross_domain_warning_acknowledged, +_PERSISTED_FIELDS entry, − DomainOverride.autonomous_mode
│   ├── llm/
│   │   └── __init__.py                      # MODIFY: − resolve_autonomous_mode (DELETE)
│   └── tools/
│       ├── config_get.py                    # MODIFY: read ctx.config, not Config() defaults (the seed of the audit)
│       ├── config_set.py                    # MODIFY: + "active_domain" in _SETTABLE_KEYS; comment update; + path for cross_domain_warning_acknowledged
│       └── <other read tools>               # MODIFY: per Task 3 audit findings (could be 0–N tools)
└── tests/
    ├── config/
    │   └── test_schema_cross_domain_ack.py  # NEW: round-trip + _PERSISTED_FIELDS membership + DomainOverride.autonomous_mode removal pin
    ├── llm/
    │   └── test_resolver.py                 # MODIFY: − resolve_autonomous_mode test cases (D1)
    └── tools/
        ├── test_config_set.py               # MODIFY: replace test_refuses_non_allowlisted_key (use vault_path as new rejection target); + test_active_domain_settable_round_trip
        ├── test_config_get_threads_ctx_config.py  # NEW: sentinel-config round-trip, replaces the Config() snapshot drift
        └── test_read_tools_thread_ctx_config.py   # NEW: parametrized regression-pin contract test (D5)

packages/brain_mcp/
├── src/brain_mcp/
│   └── server.py                            # MODIFY: _build_ctx threads Config via load_config; ToolContext(config=...) at line ~157
└── tests/
    └── test_config_persistence_stdio.py     # NEW: spawn brain_mcp via stdio, dispatch brain_config_set, assert disk bytes (D6)

apps/brain_web/
├── src/lib/state/
│   └── app-store.ts                         # MODIFY: + domains store entry (or new domains-store.ts at implementer's call) — Domain[] + activeDomain + refresh()
├── src/lib/hooks/
│   └── use-domains.ts                       # MODIFY: rewrite as zustand selector; module-state cache removed; invalidateDomainsCache becomes alias-or-deleted
├── src/lib/api/
│   └── tools.ts                             # MODIFY: + setActiveDomain(slug) typed helper (D2)
├── src/components/settings/
│   └── panel-domains.tsx                    # MODIFY: + "Default active domain" dropdown atop existing rows; + "Show cross-domain warning" toggle bound to Config.cross_domain_warning_acknowledged
├── src/components/<chat-or-dialogs>/
│   └── cross-domain-modal.tsx               # NEW: confirmation modal component (D7 trigger + D9 microcopy). Implementer audits at task time whether `components/chat/`, `components/dialogs/`, or another existing folder is the cleanest home.
├── src/components/chat/
│   └── new-chat-dialog.tsx                  # MODIFY: gate session creation on the cross-domain modal when D7 trigger fires (or wherever scope-finalization lives — implementer audit at task time)
└── tests/
    ├── unit/
    │   ├── use-domains-store.test.ts        # NEW: zustand store mutations propagate to multiple subscribers
    │   ├── settings-active-domain.test.tsx  # NEW: dropdown value, save, validation, persistence call shape
    │   └── cross-domain-modal.test.tsx      # NEW: trigger logic for the four scope shapes (cross+rail, cross-only, rail-only, single non-rail)
    └── e2e/
        ├── active-domain.spec.ts            # NEW: Playwright — pick new active_domain in Settings, reload, topbar reflects
        └── cross-domain-modal.spec.ts       # NEW: Playwright — modal trigger + acknowledgment lifecycle

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md           # MODIFY: §4 line 187 wording + ~3 sentences for D7 trigger / D8 acknowledgment (D10)

docs/user-guide/
└── domain-overrides.md                      # MODIFY: drop the per-domain-autonomy claim (D1 fallout); + cross-domain-modal section

scripts/
└── demo-plan-12.py                          # NEW: 7-gate demo per the demo gate above

tasks/
├── plans/12-settings-ux-and-cleanup.md      # this file
├── lessons.md                               # MODIFY: + Plan 12 closure section
└── todo.md                                  # MODIFY: row 12 → ✅ Complete on closure; remove Plan 12 candidate-scope section (closed)
```

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 11. Every implementer task MUST end with this checklist before reporting DONE.

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core` (or whichever package)
3. **uv `UF_HIDDEN` workaround** (lesson 341): `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` — clamp BOTH `.pth` files in the SAME COMMAND LINE as the python invocation; do NOT rely on `uv run` (re-syncs and re-hides). When the `chflags`-then-pytest recipe still fails, escape hatch is `PYTHONPATH=packages/<pkg>/src .venv/bin/python -m pytest ...`.
4. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions
5. `cd packages/<pkg> && uv run mypy src tests && cd -` — strict clean
6. `uv run ruff check . && uv run ruff format --check .` — clean
7. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
8. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check in the spec is invariant-based, not total-based.
9. **Browser-in-the-loop verification** (CLAUDE.md "Verification Before Done") for any task that touches a UI surface (Tasks 5, 8, 9): start brain, take screenshots of the relevant flows pre and post change, attach to per-task review. **Production-shape integration test** (lesson 343) for Task 4: the stdio MCP test must spawn brain_mcp from a subprocess, not just call `_build_ctx()` in-process.
10. `git status` — clean after commit

Any failure in 4–9 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — Schema: `Config.cross_domain_warning_acknowledged` + `_PERSISTED_FIELDS` + remove `DomainOverride.autonomous_mode`

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py`
- Create: `packages/brain_core/tests/config/test_schema_cross_domain_ack.py`

**Goal:** Land the new persisted field that the cross-domain modal acknowledgment binds to (D8). Same task removes `DomainOverride.autonomous_mode` (D1 schema slice) so the resolver-DELETE in Task 2 is on a clean schema.

**What to do:**
1. Add `Config.cross_domain_warning_acknowledged: bool = Field(default=False)` with a one-line docstring referencing spec §4 and Plan 12 D8.
2. Add `"cross_domain_warning_acknowledged"` to the module-scope `_PERSISTED_FIELDS` `frozenset` (Plan 11 D4).
3. Remove the `autonomous_mode: bool | None = None` field from the `DomainOverride` model (D1). Adjust `model_config = ConfigDict(extra="forbid")` is already present — no change.
4. Verify no production code references `DomainOverride.autonomous_mode` (grep `grep -rn "autonomous_mode" packages/brain_core/src/`); fix any consumers (likely none — the resolver in Task 2 is the only known reader).

**Spec for `test_schema_cross_domain_ack.py`:**
- `Config()` defaults `cross_domain_warning_acknowledged == False`.
- `Config(cross_domain_warning_acknowledged=True).persisted_dict()` includes the field.
- `Config().persisted_dict()` round-trips through `save_config` / `load_config` preserving the bool (use the Plan 11 writer/loader fixtures).
- `_PERSISTED_FIELDS` includes the new key (pin against the frozenset).
- `DomainOverride(autonomous_mode=True)` raises (`extra="forbid"` after the field removal); `DomainOverride(temperature=0.5)` still validates.
- Plan 11 `test_schema_overrides.py` cases that previously asserted `autonomous_mode` validation (if any) are removed in this task; failing-fast on a removed field is the regression guard.

**Per-task review:** existing Plan 11 schema tests (`test_schema_privacy_rail.py`, `test_schema_overrides.py`) still pass minus the autonomous_mode-specific assertions removed here. `_PERSISTED_FIELDS` pin test from Plan 11 Task 1 still passes (with the new entry added). Per-task self-review checklist runs to completion before reporting DONE.

---

## Task 2 — DELETE `resolve_autonomous_mode` resolver + tests

**Files:**
- Modify: `packages/brain_core/src/brain_core/llm/__init__.py`
- Modify: `packages/brain_core/tests/llm/test_resolver.py`

**Goal:** Remove the unused resolver per D1. Plan 11 Task 5 added it speculatively; Plan 11 lesson 351 confirmed it has no consumer.

**What to do:**
1. Remove the `def resolve_autonomous_mode(config: Config, domain: str | None) -> bool` function from `brain_core/llm/__init__.py`. Remove its line from any `__all__` export list. Leave `resolve_llm_config` untouched (still actively used by classifier / pipeline / chat session per Plan 11 Task 5 audit).
2. Remove the `test_resolve_autonomous_mode_*` cases from `test_resolver.py`. Keep `test_resolve_llm_config_*` cases unchanged.
3. Defensive grep: `grep -rn "resolve_autonomous_mode" packages/ apps/ scripts/ docs/` and confirm zero non-test references remain. If any consumer is found unexpectedly, halt and surface to plan author per the D1 sign-off rule.

**Per-task review:** running `uv run pytest packages/brain_core/tests/llm/ -q` post-change must show fewer test cases (resolver tests removed) AND green. `from brain_core.llm import resolve_autonomous_mode` raises `ImportError` (used as a gate in the demo script). Lessons.md lesson 351's "user-guide accuracy" rule: confirm `docs/user-guide/domain-overrides.md` no longer claims per-domain autonomy is supported (Task 10 finishes the doc cleanup but Task 2 should grep for and flag any remaining mention).

---

## Task 3 — Read-tool audit + regression-pin contract test

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/config_get.py` (known offender per `tools/config_get.py:51`)
- Modify: any other tool surfaced by the audit (see Step 1)
- Create: `packages/brain_core/tests/tools/test_read_tools_thread_ctx_config.py`
- Create: `packages/brain_core/tests/tools/test_config_get_threads_ctx_config.py`

**Goal:** Per D5, eliminate the `Config()` snapshot anti-pattern from every read tool, and add a regression-pin contract test that future read tools inherit the right pattern.

**What to do:**
1. **Audit.** `grep -rn "Config()" packages/brain_core/src/brain_core/tools/`. Inspect each match. A read tool that constructs `Config()` and reads from it (instead of `ctx.config`) is an offender. False positives: tools that construct a `Config()` for *validation* (e.g., a partial `Config(**candidate)` to invoke validators on user input) are NOT offenders — leave those alone. Document the audit findings (file + line + offender-or-not) in the per-task review notes.
2. **Fix every offender.** Pattern: replace `Config()` with `ctx.config` (Plan 11 made `ctx.config: Config | None`; threading it through is the brain_api Task 7 / brain_mcp Task 4 contract). If `ctx.config is None`, raise a structured error referencing the lifecycle contract — don't silently fall back (Plan 11 lesson 343's anti-pattern category).
3. **Regression-pin contract test.** New `test_read_tools_thread_ctx_config.py` parametrizes over every read tool in a `_READ_TOOLS_THAT_THREAD_CTX_CONFIG` list. For each, build a sentinel-bearing `Config(active_domain="sentinel-domain", domains=["research", "work", "personal", "sentinel-domain"])`, monkeypatch `ctx.config` to it, invoke the tool, and assert the returned data includes the sentinel value somewhere identifiable (e.g., `active_domain == "sentinel-domain"` in the response). The test fails if a future read tool is added without the pattern.
4. Targeted `test_config_get_threads_ctx_config.py` for the seed offender: invoke `brain_config_get` with the sentinel `ctx.config` and assert the response payload reflects sentinel values (not `Config()` defaults).

**Per-task review:** the audit step's findings list is part of the review artifact — even if the audit finds zero additional offenders beyond `config_get`, that "swept these tools, found no new offenders" sweep IS the value. The contract test must be parametrized over a static list (mypy-strict friendly); avoid runtime tool-discovery via `__init__.py` introspection (introspection-driven test parametrization rotted in earlier plans — explicit list is the convention). Existing `tests/tools/test_config_get.py` cases must be re-evaluated post-change: any case that asserts default-Config values where the test fixture didn't set `ctx.config` is exposed by the audit; either fix the fixture or remove the case.

---

## Task 4 — `brain_mcp` Config-wiring fix + stdio MCP integration test

**Files:**
- Modify: `packages/brain_mcp/src/brain_mcp/server.py` (around `_build_ctx` at line 140 and `ToolContext(...)` constructor at line 157)
- Create: `packages/brain_mcp/tests/test_config_persistence_stdio.py`

**Goal:** Per D6, port Plan 11 Task 7's brain_api Config-wiring fix to brain_mcp. Add the production-shape stdio integration test that Plan 11 lesson 343 calls for.

**What to do:**
1. **Mirror brain_api fix.** In `_build_ctx()`, call `load_config(vault_root, ...)` (with the same kwargs Plan 11 brain_api uses — see `packages/brain_api/src/brain_api/lifespan.py` for the exact shape). Pass the resulting `Config` to `ToolContext(..., config=loaded_config)` at line 157. The lazy `_cached_ctx` singleton at line 138 means the load happens once per server lifetime — that matches the brain_api pattern.
2. **Comment hygiene.** Update the comment at line 188 (currently references `build_app_context`) to reflect the new symmetric wiring; remove any "TODO" or "issue #27" mentions left over from the Plan 11 era.
3. **Stdio integration test.** New test fixture spawns brain_mcp as a subprocess (`subprocess.Popen([".venv/bin/python", "-m", "brain_mcp", "--vault", str(tmp_vault)], ...)` or whatever the canonical Plan 04 invocation is — mirror `tests/test_server_smoke.py` for the spawn-and-handshake recipe). Send a `tools/call` JSON-RPC request for `brain_config_set` with `{key: "log_llm_payloads", value: true}`. Read the response. Assert `<tmp_vault>/.brain/config.json` on disk contains `"log_llm_payloads": true` (NOT the in-memory-only no-op behavior pre-fix). Tear down: terminate the subprocess in a finally block.

**Spec for the test cases in `test_config_persistence_stdio.py`:**
- `test_brain_config_set_persists_via_stdio_transport`: the canonical happy path described above.
- `test_brain_create_domain_persists_via_stdio_transport`: spawn brain_mcp; dispatch `brain_create_domain` with a fresh slug; assert the slug appears in the on-disk `config.json`'s `domains` array.
- `test_build_ctx_loads_config_from_existing_disk_file`: pre-write a `config.json` to the temp vault before spawning brain_mcp; spawn; dispatch `brain_config_get`; assert response reflects the pre-written values (not `Config()` defaults). This is the regression test for the original bug — pre-fix, the response would mirror `Config()` defaults.

**Per-task review:** the stdio integration test is slow (subprocess spawn + JSON-RPC handshake per case). Use `pytest-xdist` only if the rest of the suite already does; otherwise mark these tests with `@pytest.mark.slow` and run them in the regular pytest invocation. Browser verification not applicable (no UI surface in this task) — the production-shape integration test IS the Plan 12 equivalent.

---

## Task 5 — `useDomains()` zustand store refactor

**Files:**
- Modify: `apps/brain_web/src/lib/state/app-store.ts` (or create `lib/state/domains-store.ts` if app-store is at the implementer's threshold for "too big")
- Modify: `apps/brain_web/src/lib/hooks/use-domains.ts`
- Create: `apps/brain_web/tests/unit/use-domains-store.test.ts`

**Goal:** Per D4, eliminate the cross-instance state divergence by promoting `useDomains()` from a module-state cache to a zustand store + selector.

**What to do:**
1. **Store entry.** Add `domains: Domain[]`, `activeDomain: string`, `domainsLoaded: boolean` to the chosen store. Add a `refresh: () => Promise<void>` action that calls `listDomains()` (the existing API helper), updates the store fields, and resolves once the response is in. Add a `setActiveDomainOptimistic: (slug: string) => void` action for the active_domain dropdown to call before the round-trip completes (so the UI reflects the change immediately; the round-trip's `refresh()` reconciles).
2. **Hook rewrite.** `useDomains()` becomes a selector returning the four fields. On first mount in any consumer, if `domainsLoaded === false` it calls `useDomainsStore.getState().refresh()` to seed the store. Subsequent consumers re-use the cached store state — no duplicate fetches. The existing `invalidateDomainsCache()` symbol either becomes a thin alias (`() => useDomainsStore.getState().refresh()`) or is removed and call sites updated. Pin the choice in the implementer's per-task review notes.
3. **Audit consumers.** Grep for `useDomains(` and `invalidateDomainsCache(` across `apps/brain_web/src/`. Confirm every consumer reads only the four exposed fields. The active_domain dropdown (Task 8) and topbar scope picker are the load-bearing consumers; verify both compile against the new selector shape.

**Spec for `use-domains-store.test.ts`:**
- Fresh store: `useDomainsStore.getState()` returns `{domains: [], activeDomain: "", domainsLoaded: false}`.
- After `refresh()` resolves with mock fetch returning `{domains: [...], active_domain: "research"}`, store reflects the response and `domainsLoaded === true`.
- Mounting two `useDomains()` consumers in jsdom; `setActiveDomainOptimistic("work")` from one consumer; assert the other consumer re-renders with `activeDomain === "work"` (no `page.reload()` analog needed — direct subscription test).
- `refresh()` while a previous `refresh()` is in flight: serialize via the store action (no double-fetch). Either an `inFlight` flag or a `Promise<void>` cache; pin the choice.

**Per-task review:** browser-in-the-loop verification per Plan 12 self-review checklist item 9: open brain, change a domain (via `panel-domains.tsx` rename or create), screenshot the topbar updating in real-time without manual reload. Pre-Plan-12, the topbar lagged until manual reload; post-Plan-12 it doesn't. The screenshot pair is the verification artifact. Existing Playwright `domains.spec.ts` (which used `page.reload()` between mutations as a workaround) should be re-run with the reload removed — it should still pass; if it doesn't, the zustand wiring missed a subscriber.

---

## Task 6 — Extend `_SETTABLE_KEYS` for `active_domain` + `setActiveDomain` typed helper

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py` (lines 60–66 — comment + allowlist)
- Modify: `packages/brain_core/tests/tools/test_config_set.py` (line 218 area — replace rejection test target)
- Modify: `apps/brain_web/src/lib/api/tools.ts` (add `setActiveDomain` typed helper)
- Create: test cases in `test_config_set.py` for the active_domain settable path

**Goal:** Per D2, invert the Plan 07-era policy that excluded `active_domain` from `_SETTABLE_KEYS`. Reading and writing land in the same task because the policy inversion needs the comment update + test reversal in one atomic commit.

**What to do:**
1. **Allowlist.** Add `"active_domain"` to `_SETTABLE_KEYS` at `config_set.py:66`. Update the explanatory comment block at line 60: replace the "deliberately excluded" rationale with a Plan 12 D2 reference noting the policy inversion (Settings UI is the new persistence path; cross-field validator from Plan 10 enforces "must be in `Config.domains`" on the persisted value).
2. **Replace existing rejection test.** `test_refuses_non_allowlisted_key` at line 218 currently uses `"active_domain"` as the rejected key. Pick a different non-allowlisted key — `"vault_path"` is the cleanest choice (it's permanently non-settable per the existing rationale) — and update both the test name and the assertion.
3. **New positive test.** `test_active_domain_settable_round_trip`: `await handle({"key": "active_domain", "value": "work"}, ctx)` succeeds; `ctx.config.active_domain == "work"`; the on-disk `config.json` contains `"active_domain": "work"` (uses the Plan 11 writer round-trip pattern).
4. **New cross-field-validation negative test.** `test_active_domain_must_be_in_domains`: `await handle({"key": "active_domain", "value": "ghost-domain"}, ctx)` raises a structured validation error; `ctx.config.active_domain` unchanged. The cross-field validator from Plan 10's `_check_active_domain_in_domains` does the heavy lifting; this test pins the surfaced error path.
5. **Frontend typed helper.** In `apps/brain_web/src/lib/api/tools.ts`, add `export async function setActiveDomain(slug: string): Promise<void> { return brainConfigSet({ key: "active_domain", value: slug }); }` (matching the existing helper conventions in that file). The helper exists for self-documenting consumers in the Settings panel (Task 8); the inline `brainConfigSet` call works too but is less clear.

**Per-task review:** per the pre-flight policy-inversion note, this is the task that breaks the Plan 07-era invariant. The comment update IS the documentation handoff to future readers — it must reference Plan 12 D2 explicitly so a future audit doesn't re-discover the apparent contradiction with the Plan 07 comment. Existing `test_settable_keys_all_resolve_to_a_real_schema_field` (Plan 04 schema-vs-allowlist regression test) must still pass — `active_domain` IS a real Config field, so this test stays green by construction.

---

## Task 7 — `brain-ui-designer` microcopy + interaction-state mocks for cross-domain modal

**Files:**
- Create: `docs/design/cross-domain-modal/microcopy.md` (modal + Settings toggle text)
- Create: `docs/design/cross-domain-modal/state-1-initial.png` (or `.svg` — implementer's call)
- Create: `docs/design/cross-domain-modal/state-2-settings-after-toggle.png`

**Goal:** Per D9, produce the user-facing microcopy + 2 interaction-state mocks BEFORE Task 9's frontend implementation. Plan 11 Task 9 is the pattern to mirror.

**What to do:**
1. **Modal microcopy.** Draft: (a) modal title — short, no jargon; (b) modal body — explains that the chosen scope crosses into a privacy-railed domain, calls out which slug(s) are railed, references the `BRAIN.md` for context if the user wants to read more; (c) two button labels — "Continue" (primary, fires the session creation) and "Cancel" (secondary, returns to scope picker); (d) "Don't show again" checkbox label and its tooltip (the checkbox sets `Config.cross_domain_warning_acknowledged=true` on Continue).
2. **Settings toggle copy.** Draft: (a) toggle label — matches the modal's "Don't show again" affordance; (b) helper text under the toggle — explains what happens when the toggle is OFF (modal returns next time D7 trigger fires) and what's already happened when ON (acknowledgment recorded; modal suppressed).
3. **Interaction mocks.** State 1: the modal as it appears when D7 trigger fires (with placeholder scope slugs `[research, personal]` so it's concrete). State 2: the Settings → Domains panel with the "Show cross-domain warning" toggle in its OFF state and a inline note like "You won't see the cross-domain warning until you toggle this back on."
4. **Voice/style.** Per `docs/design/copy.md` (Plan 06 microcopy spec) — non-technical, plain-English, calm not alarming. The modal is a confirmation, not a warning page; phrasing should respect the user as someone who knows what they're doing and wants the option to skip the prompt next time.

**Per-task review:** mocks live under `docs/design/cross-domain-modal/` so Task 9's implementer has a self-contained reference. No code changes in Task 7; the artifact IS the design doc + image pair. User reviews the microcopy + mocks before Task 8 dispatches (the implementer-driven `superpowers:subagent-driven-development` review checkpoint). If the user sends back changes, Task 7 re-runs without blocking Tasks 8 / 9 / 10's parallel-feasible work — but per D11 we stay sequential, so re-runs delay everything downstream.

---

## Task 8 — Active-domain dropdown frontend on `panel-domains.tsx`

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx`
- Create: `apps/brain_web/tests/unit/settings-active-domain.test.tsx`

**Goal:** Per D3, surface the active_domain dropdown at the top of the Settings → Domains panel. Uses Task 5 zustand for cross-instance reactivity (#11 + #7 finally working together).

**What to do:**
1. **Dropdown.** New `<ActiveDomainSelector />` component rendered at the top of `panel-domains.tsx` above the existing per-domain rows. Uses `useDomains()` (now zustand-backed per Task 5) for the live `domains` list and current `activeDomain`. On change, calls `setActiveDomain(slug)` from `lib/api/tools.ts` (Task 6 helper); on success, calls `useDomainsStore.getState().setActiveDomainOptimistic(slug)` for immediate UI feedback; on failure, reverts and shows a toast via `system-store`.
2. **Cross-field validation surfacing.** If the backend rejects (e.g., `active_domain` isn't in `Config.domains` because of a race with a concurrent delete), the toast surfaces the structured error with a "Pick a different domain" call to action. Cross-field validator can't realistically fire on the dropdown's own submissions (the dropdown options are populated from `domains`), but defensively handles the race.
3. **A11y.** Standard `<select>` (or shadcn `<Select>`) with proper label association, keyboard navigation, screen-reader-friendly current-value announcement. WCAG 2.2 AA per spec §8.

**Spec for `settings-active-domain.test.tsx`:**
- Renders the dropdown with current `activeDomain` selected; options match the `domains` list from the store.
- Selecting a different domain calls `setActiveDomain(slug)` with the new value.
- After the API helper resolves, the dropdown selection reflects the new value (driven by zustand store update from Task 5's `setActiveDomainOptimistic`).
- API failure: dropdown reverts to the original `activeDomain`; toast appears with the error.
- Domain-list mutation (e.g., user deletes a domain in another tab): the dropdown's options update without re-mounting — a key Task 5 zustand assertion in this consumer's context.

**Per-task review:** browser verification — pre-Plan-12 screenshot showing user had to hand-edit `config.json` (Plan 11 Task 8 implementer's verification artifact); post-Plan-12 screenshot showing the same change via the dropdown + topbar reflecting the new active_domain on the next page render. Hand-edit-of-config.json is no longer the only path. Existing `panel-domains.tsx` per-row override editor (Plan 11 D14) is unchanged; the active_domain dropdown is additive. Hooks back into Task 5 — if the Task 5 zustand wiring is incomplete, this task surfaces the gap (cross-instance reactivity is the load-bearing assumption for the dropdown's UX).

---

## Task 9 — Cross-domain modal frontend + Settings toggle

**Files:**
- Create: `apps/brain_web/src/components/<chat-or-dialogs>/cross-domain-modal.tsx` (implementer chooses the best home folder at task start — likely `components/chat/` since chat is the primary trigger source, or `components/dialogs/` if that's the existing convention for cross-feature modals)
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (add the "Show cross-domain warning" toggle)
- Modify: `apps/brain_web/src/components/chat/new-chat-dialog.tsx` (or whichever component finalizes scope before session creation — implementer audit at task start)
- Create: `apps/brain_web/tests/unit/cross-domain-modal.test.tsx`

**Goal:** Per D7 + D8 + D9, ship the cross-domain confirmation modal. Trigger logic, microcopy, acknowledgment plumbing, Settings toggle for re-enable.

**What to do:**
1. **Modal component.** New `<CrossDomainModal />` consuming Task 7's microcopy. Props: `open: boolean`, `scope: string[]`, `railedSlugsInScope: string[]` (computed by the trigger source), `onContinue: (alsoAcknowledge: boolean) => void`, `onCancel: () => void`. Internal state: a "Don't show again" checkbox bound to the `alsoAcknowledge` parameter.
2. **Trigger.** Audit where chat / draft / brainstorm session creation happens. The trigger gate computes: `scope.length >= 2 && scope.some(s => privacyRailed.includes(s))`. If trigger fires AND `Config.cross_domain_warning_acknowledged === false`, show the modal before finalizing the session; otherwise let session creation proceed unchanged. The data-loading mechanism for `Config.cross_domain_warning_acknowledged` and `Config.privacy_railed` is implementer's call at task time: options include extending the Task 5 zustand store with a wider config slice, lifting these fields onto an existing API helper, or adding a dedicated `useCrossDomainGate()` hook. The contract is "trigger gate has access to both fields at scope-finalization time"; the wiring shape is open.
3. **`onContinue` handler.** If `alsoAcknowledge === true`, call `setCrossDomainWarningAcknowledged(true)` (a new typed helper in `lib/api/tools.ts` — same shape as `setActiveDomain`). Then proceed with session creation. If false, just proceed with session creation; modal will fire again next time.
4. **`onCancel` handler.** Returns the user to the scope picker; no session created.
5. **Settings toggle.** In `panel-domains.tsx`, below the active-domain dropdown (Task 8) and above per-domain rows, render a "Show cross-domain warning" toggle bound to `Config.cross_domain_warning_acknowledged` (inverted — toggle ON means `acknowledged === false`, modal still fires; toggle OFF means `acknowledged === true`, modal suppressed). Helper text per Task 7 microcopy. On change, calls the same `setCrossDomainWarningAcknowledged` typed helper.

**Spec for `cross-domain-modal.test.tsx`:**
- Trigger logic table (parametrized): scope=`[research, personal]` → modal fires; scope=`[research, work]` → no modal; scope=`[personal]` → no modal; scope=`[research]` → no modal; scope=`[]` → no modal.
- `onContinue(false)` proceeds with session creation; doesn't call `setCrossDomainWarningAcknowledged`.
- `onContinue(true)` proceeds with session creation; calls `setCrossDomainWarningAcknowledged(true)`.
- `onCancel` doesn't proceed; doesn't call `setCrossDomainWarningAcknowledged`.
- When `Config.cross_domain_warning_acknowledged === true`, the modal does NOT fire even when the trigger condition would otherwise match.
- Settings toggle: toggling OFF calls `setCrossDomainWarningAcknowledged(true)`; toggling ON calls `setCrossDomainWarningAcknowledged(false)`.

**Per-task review:** browser verification — fresh-vault walk: open brain, attempt to start a chat with scope=`[research, personal]`, screenshot the modal at trigger (state 1 from Task 7 mocks). Click "Continue" with the checkbox checked; reload; attempt the same scope again, screenshot the absence of the modal. Toggle the Settings switch ON; attempt the scope again, screenshot the modal returning. The screenshot triple is the verification artifact. No accessibility regression: keyboard-only flow through the modal works (tab to checkbox, tab to Continue, Enter); axe-core sweep clean.

---

## Task 10 — Spec amendment + user-guide + demo + e2e + lessons closure

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§4 line 187 + 3 new sentences per D10)
- Modify: `docs/user-guide/domain-overrides.md` (drop per-domain-autonomy claim per D1; add cross-domain-modal section per D7 + D8)
- Create: `scripts/demo-plan-12.py`
- Create: `apps/brain_web/tests/e2e/active-domain.spec.ts`
- Create: `apps/brain_web/tests/e2e/cross-domain-modal.spec.ts`
- Modify: `tasks/lessons.md` (Plan 12 closure section)
- Modify: `tasks/todo.md` (row 12 → ✅; remove Plan 12 candidate-scope tail block)

**Goal:** Land the 7-gate demo from the plan header. Add Playwright walks for the two new UX surfaces. Spec amendment per D10. User-guide cleanup per D1. Lessons capture.

**Spec amendment (D10).** Replace §4 line 187 wording from *"Every query/chat thread has an active scope: one domain, or cross-domain (requires a one-time confirmation warning about personal content)."* with: *"Every query/chat thread has an active scope: one domain, or cross-domain (requires a one-time confirmation warning when the scope crosses into a privacy-railed domain). The modal fires only when the scope contains ≥2 domains AND ≥1 of them is in `Config.privacy_railed`; single-domain railed access is already gated by §7's explicit-inclusion rule. Acknowledgment persists in `Config.cross_domain_warning_acknowledged: bool` (default `False`); a "Show cross-domain warning" toggle in Settings → Domains lets users re-enable the prompt."*

**User-guide cleanup (D1 fallout + D7/D8 new doc).** Open `docs/user-guide/domain-overrides.md`. Remove any sentence referencing per-domain `autonomous_mode` overrides (the lesson 351 drift). Add a new short section "Cross-domain confirmation modal" covering: (a) when the modal fires (per D7), (b) how to dismiss permanently (the "Don't show again" checkbox), (c) how to re-enable (Settings → Domains toggle), (d) why this matters (the privacy_railed rail).

**Demo script gates** (re-stated):
1. Schema gate: `Config(cross_domain_warning_acknowledged=True)` round-trips through `save_config` + `load_config`; `_PERSISTED_FIELDS` includes the new key (assert via Plan 11 fixture pattern); `from brain_core.llm import resolve_autonomous_mode` raises `ImportError`; `DomainOverride(autonomous_mode=True)` raises (`extra="forbid"` after field removal).
2. Read-tool audit gate: build a sentinel-bearing `Config(active_domain="sentinel-domain", domains=[..., "sentinel-domain"])`; monkeypatch `ctx.config` to it; invoke `brain_config_get`; assert response `active_domain == "sentinel-domain"` (not `"research"` default); also walk the parametrized list of audited tools and assert each reflects sentinel.
3. brain_mcp gate: spawn brain_mcp via stdio in a subprocess with a temp vault; dispatch `brain_config_set` with `{key: "log_llm_payloads", value: true}`; read response; assert `<vault>/.brain/config.json` on disk contains `"log_llm_payloads": true`.
4. zustand pubsub gate: in a jsdom test (or run as a Playwright test if more reliable), mount `panel-domains.tsx` AND a topbar test harness simultaneously; mutate domains via panel; assert topbar re-renders with the updated list within 100ms (no `page.reload()` workaround).
5. active_domain Settings UI persistence gate: Playwright walk in `active-domain.spec.ts`. Open brain, navigate to Settings → Domains, pick `work` in the "Default active domain" dropdown, reload page, assert the topbar scope chip displays `work` (post-reload). Live-reactivity (no-reload-needed) is covered by gate 4; this gate is the persistence-after-reload assertion.
6. Cross-domain modal trigger parametrized gate: Playwright walk in `cross-domain-modal.spec.ts` with three sub-cases — scope=`[research, personal]` modal visible; scope=`[research, work]` no modal; scope=`[personal]` no modal.
7. Acknowledgment lifecycle gate: continued in `cross-domain-modal.spec.ts`. Click "Continue" with "Don't show again" checked; reload; attempt scope=`[research, personal]` again; assert no modal. Toggle "Show cross-domain warning" ON in Settings → Domains; attempt the scope again; assert modal returns.

Print `PLAN 12 DEMO OK` on exit 0; non-zero on any gate failure. Use the same temp-vault fixture pattern as `scripts/demo-plan-11.py`.

**Lessons capture.** Mirror the Plan 11 closure-section format. Closure summary, then one paragraph per lesson worth carrying forward. Likely lesson candidates (implementer surfaces actuals):
- Whether the read-tool audit (Task 3) found additional offenders beyond `config_get` — if yes, what made them blend in.
- Any new chflags / uv quirks surfaced during demo execution.
- Whether the zustand promotion (Task 5) needed touch-ups beyond the `useDomains()` hook (e.g., did invalidateDomainsCache callers need updates? Did the topbar's existing reactive bindings just work, or was there friction?).
- Whether the brain_mcp stdio integration test (Task 4) caught any other Config-wiring blind spots adjacent to the one D6 named.
- Whether the cross-domain modal's trigger logic needed adjustments after browser verification (Task 9) — was the D7 rule cleanly implementable, or did edge cases surface?

**Demo script execution prefix** for the implementer: `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python scripts/demo-plan-12.py` per lesson 341. The Playwright e2e specs run via `cd apps/brain_web && PYTHONPATH=packages/brain_core/src:packages/brain_api/src npx playwright test e2e/active-domain.spec.ts e2e/cross-domain-modal.spec.ts` to bypass `uv run`'s re-hide behavior on the brain_api webServer.

**`tasks/todo.md` update.** Row 12 → ✅ Complete with the same shape as row 11. Remove the "Plan 12 candidate scope (forwarded from Plan 11)" tail section (closed). If implementer-surfaced backlog items remain (e.g., genericizing the zustand pattern across other hooks; per-domain budget caps; etc.), add a fresh "Plan 13 candidate scope (forwarded from Plan 12)" tail block in the same shape.

---

## Review (pending)

To be filled in on closure following the Plan 10 + Plan 11 format:
- **Tag:** `plan-12-settings-ux-and-cleanup` (cut on green demo).
- **Closes:** the four explicit Plan 11 closure-addendum items (#7, #8, #9, #10), the late-addendum cross-instance pubsub (#11), and the dead-resolver cleanup (#1). Plan 12 candidate-scope tail block in `tasks/todo.md` removed.
- **Bumps:** tool count unchanged (D2 extends `brain_config_set` allowlist; no new MCP tools). Schema gains 1 field (`cross_domain_warning_acknowledged`). Schema loses 1 field (`DomainOverride.autonomous_mode`). One module deletion (`resolve_autonomous_mode`).
- **Verification:** all 7 demo gates green (`scripts/demo-plan-12.py` → `PLAN 12 DEMO OK`); pytest count + vitest count + Playwright count to be filled in.
- **Backlog forward:** TBD per implementer-surfaced backlog items; candidate Plan 13 themes documented in NOT-DOING (per-domain budget caps; per-domain rate limits; repair-config UI; cross-process hot-reload; `validate_assignment=True`; per-domain autonomy if requested).
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 12" feed Plan 13's authoring.

---

**End of Plan 12.**
