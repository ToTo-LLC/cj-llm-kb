# brain — Master Plan Index

> Master tracking board for the `brain` implementation. Each sub-plan is a self-contained, demoable unit. Plans are written **just-in-time**: plan N+1 is authored only after plan N is approved and reviewed, so lessons from earlier execution shape later plans.

**Spec:** [`docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`](../docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md)
**Orchestration:** [`.claude/ORCHESTRATION_GUIDE.md`](../.claude/ORCHESTRATION_GUIDE.md)
**Lessons:** [`lessons.md`](./lessons.md)

## Status

| # | Plan | Status | Demoable deliverable | Primary subagent(s) |
|---|---|---|---|---|
| 01 | [Foundation](./plans/01-foundation.md) | ✅ Complete (2026-04-13, tag `plan-01-foundation`) | Tested `brain_core` library (config, vault, llm, cost) green on Mac + Windows CI | brain-core-engineer, brain-test-engineer |
| 02 | [Ingestion](./plans/02-ingestion.md) | ✅ Complete (2026-04-14, tag `plan-02-ingestion`) | 9-stage ingest pipeline with 5-source demo passing (`PLAN 02 DEMO OK`); Tasks 21–22 VCR cassettes deferred until API key available | brain-core-engineer, brain-prompt-engineer |
| 03 | [Chat](./plans/03-chat.md) | ✅ Complete (2026-04-15, tag `plan-03-chat`) | `brain chat` Ask/Brainstorm/Draft modes working in terminal with 366 tests across brain_core + brain_cli; 7-gate demo passing (`PLAN 03 DEMO OK`); VCR chat cassettes deferred per D7a | brain-core-engineer, brain-prompt-engineer |
| 04 | [MCP](./plans/04-mcp.md) | ✅ Complete (2026-04-17, tag `plan-04-mcp`) | brain_mcp stdio server with 18 tools + 3 resource URIs; brain mcp install/uninstall/selftest/status CLI; 14-gate demo passing (`PLAN 04 DEMO OK`); VCR MCP cassettes deferred per D9a | brain-mcp-engineer, brain-core-engineer |
| 05 | [API](./plans/05-api.md) | ✅ Complete (2026-04-21, tag `plan-05-api`) | brain_api FastAPI REST (18 tool endpoints) + WebSocket chat (ChatSession-bridged, schema_version=1); Origin/Host/token auth; 14-gate demo passing (`PLAN 05 DEMO OK`); VCR chat cassettes deferred per D9a | brain-api-engineer (brain-mcp-engineer role-overloaded), brain-core-engineer |
| 06 | UI Design | ✅ Complete (2026-04-21, external design tool) | Design brief + 3 delta passes + v3 design artifacts at `docs/design/` (design-brief.md, design-delta.md, design-delta-v2.md, CJ Knowledge LLM v3 zip); 5 pre-flight backend decisions pinned at `docs/design/plan-07-preflight.md` (D1a/D2a/D3a/D4a/D5a) | external (brain-ui-designer replaced with Claude design tool) |
| 07 | [Frontend](./plans/07-frontend.md) | ✅ Complete (2026-04-21, tag `plan-07-frontend`) | brain_web Next.js 15 with 8 screens + setup wizard + 15+ dialogs/overlays + Playwright e2e (5 flows + axe-core AA) + 14-gate demo passing (`PLAN 07 DEMO OK`); tool surface 18 → 34 | brain-frontend-engineer, brain-core-engineer, brain-test-engineer |
| 08 | [Install + Packaging](./plans/08-install.md) | ✅ Complete (2026-04-23, tag `plan-08-install`) | Static-export pivot (brain_api serves UI); 10 CLI verbs (start/stop/status/doctor/upgrade/uninstall/backup/chat/mcp/patches); install.sh (Mac) + install.ps1 (Windows 11); launcher icons; 11-gate demo passing (`PLAN 08 DEMO OK`); VM dry-run harness ready (clean-Mac + clean-Windows receipts deferred to pre-release sweep) | brain-installer-engineer, brain-core-engineer, brain-frontend-engineer, brain-test-engineer |
| 09 | [Ship](./plans/09-ship.md) | ✅ Complete (2026-04-24, tags `plan-09-ship` + `v0.1.0`) | v0.1.0 GitHub release live (universal tarball, SHA256 `657f9fea…`); install.sh/.ps1 flipped to real URLs; update-check nudge shipped; README + LICENSE + CONTRIBUTING + privacy; 17/17-section QA sweep receipt (`docs/testing/v0.1.0-qa-receipt.md`); 12-gate demo passing (`PLAN 09 DEMO OK`); 947+18 Python + 231+1-skip frontend unit + 14/14 Playwright; Tasks 9+10 clean-VM dry runs harnessed-deferred to pre-release validation | brain-test-engineer, brain-installer-engineer |
| 10 | [Configurable Domains](./plans/10-configurable-domains.md) | ✅ Complete (2026-04-27, tag `plan-10-configurable-domains`) | `Config.domains: list[str]` replaces v0.1 `Domain` Literal; `scope_guard` widened; classify prompt templated; Settings → Domains panel + topbar + Browse + setup wizard all consume live `useDomains()`. 9 tasks all green; demo gate (`scripts/demo-plan-10.py`) passes 7/7 (`PLAN 10 DEMO OK`). 1022 backend tests + 247 frontend vitest cases + Playwright `domains.spec.ts` ready. Closes `docs/v0.1.0-known-issues.md` item #21. | brain-core-engineer, brain-prompt-engineer, brain-frontend-engineer, brain-test-engineer |
| 11 | [Persistent Config + Per-Domain Overrides + Privacy Rail Generalization](./plans/11-persistent-config.md) | ✅ Complete (2026-04-28, tag `plan-11-persistent-config`) | Atomic+locked+backup `save_config()` shipped (closes `#27`); five mutation tools (`brain_config_set`, `brain_create_domain`, `brain_rename_domain`, `brain_delete_domain`, `brain_budget_override`) persist to `<vault>/.brain/config.json`; loader gains `config.json → .bak → defaults` fallback chain with structlog warnings. `Config.privacy_railed: list[str]` generalizes the rail (validator requires `personal`); `Config.domain_overrides: dict[str, DomainOverride]` + `resolve_llm_config()` / `resolve_autonomous_mode()` resolvers thread per-domain LLM/autonomy overrides. Frontend: `panel-domains.tsx` grows per-row override editor + privacy-rail toggle; `app-store.scopeInitialized` + `useDomains().activeDomain` give first-mount scope hydration. 10 tasks all green; 8-gate demo (`scripts/demo-plan-11.py`) prints `PLAN 11 DEMO OK`. 1134 backend pytest + 273 brain_web vitest cases + Playwright `persistence.spec.ts` (1 test, 595 ms). Plan 12 candidate scope: 4 deferred items added below. | brain-core-engineer, brain-frontend-engineer, brain-test-engineer |
| 12 | [Settings UX completion + Plan 11 correctness cleanup](./plans/12-settings-ux-and-cleanup.md) | ✅ Complete (2026-04-28, tag `plan-12-settings-ux-and-cleanup`) | `Config.cross_domain_warning_acknowledged: bool` lands as the new persisted field; `DomainOverride.autonomous_mode` and `brain_core.llm.resolve_autonomous_mode` both DELETE'd as dead code (closes Plan 11 lesson 351 user-guide drift). `brain_mcp/server.py:_build_ctx` ports the Plan 11 brain_api Config-wiring fix + production-shape stdio integration test guards the regression. Read-tool audit lands `_READ_TOOLS_THAT_THREAD_CTX_CONFIG` regression-pin contract test + fixes `brain_config_get`'s `Config()` snapshot drift. `useDomains()` promoted to a zustand-backed selector via `domains-store.ts`; cross-instance pubsub eliminates `domains.spec.ts`'s `page.reload()` workaround. `_SETTABLE_KEYS` extended for `active_domain` + `cross_domain_warning_acknowledged`; `panel-domains.tsx` grows an "Active domain" dropdown above the per-domain rows + a "Show cross-domain warning" toggle. Cross-domain confirmation modal ships at `dialogs/cross-domain-modal.tsx` with `useCrossDomainGate()` + `shouldFireCrossDomainModal()` trigger; chat-screen send is gated on the modal when scope contains ≥2 domains AND ≥1 is in `Config.privacy_railed`. 10 tasks all green; 7-gate demo (`scripts/demo-plan-12.py`) prints `PLAN 12 DEMO OK`. 1140 backend pytest + 316 brain_web vitest passed + 11/11 Playwright specs (modulo 9 pre-existing failures from clean main HEAD, not caused by Plan 12). Plan 13 candidate scope: 11 deferred items added below. | brain-core-engineer, brain-mcp-engineer, brain-frontend-engineer, brain-ui-designer, brain-test-engineer |
| 13 | [Cross-instance cleanup + pre-existing test debt closure](./plans/13-cross-instance-cleanup-and-test-debt.md) | ✅ Complete (2026-04-29, tag `plan-13-cross-instance-cleanup-and-test-debt`) | None-policy strictness lands on `list_domains` + `config_set.py:317-327` matching `config_get`'s lifecycle-violation wording (closes #A1; scope-adjacent `apply_patch.py:_resolve_config` docstring sweep landed). `panel-domains.tsx` drops parallel local `domains: string[]` state and reads from `useDomainsStore` directly — single source of truth (closes #A2; `removeDomainOptimistic` failure-mode regression captured in Plan 14). `cross-domain-gate-store.ts` lands as a zustand store mirroring Plan 12 D4's `domains-store.ts` split; `useCrossDomainGate()` becomes a selector; cross-instance pubsub between Settings toggle + chat-screen gate works without `page.reload()` (closes #A3). brain_api 13-failure root cause confirmed (Task 4): NOT the OriginHostMiddleware drift Plan 12 closure hypothesized — it's Plan 08 Task 1's `SPAStaticFiles` mount shadowing synthetic test routes when `apps/brain_web/out/` exists. Task 5 lands `mount_static_ui: bool = True` keyword-only flag on `create_app`; conftest passes `False` for the API-only test surface. All 13 tests pass; envelope shape parity regression-pin test added (5 tests; closes #B1). a11y color-contrast root cause (Task 6): NOT the gate weakening Plan 12 closure suspected — it's the v4 brand-skin.css drop cascade-shadowing Plan 07 Task 25C's tokens.css nudges. Task 6 token sweep cleared 9 violations across 8 routes + setup-wizard welcome step (closes #B2). 7 tasks all green; 7-gate demo (`scripts/demo-plan-13.py`) prints `PLAN 13 DEMO OK`. 1164 backend pytest + 11 skipped + 334 brain_web vitest + 1 skipped + 20/21 Playwright e2e (1 pre-existing `ingest-drag-drop` flake passes in isolation). Plan 14 candidate scope: see tail block below. | brain-core-engineer, brain-frontend-engineer, brain-test-engineer, brain-mcp-engineer (role-overloaded as brain-api-engineer) |

Legend: ⏸ not yet written · 📝 ready for execution · 🚧 in progress · ✅ complete

## Gate discipline

- Every plan has an explicit demo gate. No plan is marked ✅ without a proof artifact (screenshot, recording, or test-run receipt) per the "Verification Before Done" rule in `CLAUDE.md`.
- Plan 07 is hard-blocked on plan 06 approval. All other sequencing is soft — earlier plans inform later ones but can overlap where contracts are stable.
- Lessons learned during plan N feed into [`lessons.md`](./lessons.md) and influence the authoring of plan N+1.
- After every plan completion: pause for user review before starting the next.

## Workflow per plan

1. Main loop authors (or refines) the plan file under `tasks/plans/`.
2. Execution via `superpowers:subagent-driven-development` — one fresh subagent per task, two-stage review between tasks.
3. Each step marked complete only with verification proof per the `CLAUDE.md` rule.
4. On plan completion: demo artifact captured → user review → mark ✅ here → update [`lessons.md`](./lessons.md) → author next plan.

## Review cadence

- **Section-by-section** feedback within a plan (per `CLAUDE.md` plan-mode directives).
- **Plan-by-plan** feedback at demo gates.
- Decisions surfaced as `AskUserQuestion` with ≤4 labeled options, recommended first, per the user's preference format (NUMBER.LETTER).

## Plan 14 candidate scope (forwarded from Plan 13)

Items deferred from Plan 13 that are candidate scope for Plan 14+. Plan 14 itself is not yet authored.

### Architectural / cross-instance follow-throughs from Plan 12 + 13 reviews

- **Migrate `bulk-screen.tsx` and `file-to-wiki-dialog.tsx` to `useDomains()`** (close orphan `listDomains` consumers — Plan 13 Task 2 review M3). Both still call `listDomains()` directly rather than reading from `useDomainsStore`; the seam Plan 12 + 13 just collapsed for `panel-domains.tsx` and `topbar.tsx` is still open at these two surfaces.
- **Add `removeDomainOptimistic(slug)` action to `domains-store.ts`** and use in `panel-domains.tsx` delete handler (Plan 13 Task 2 review I1). Pre-Task-2 used a local optimistic filter so deleted rows disappeared even on refresh-failure paths; post-Task-2 the row reappears after delete + refresh-failure. Mirrors `setActiveDomainOptimistic` precedent.
- **Surface `useDomainsStore.error` in `panel-domains.tsx` as inline banner** (Plan 13 Task 2 review I1 follow-up). The store carries an `error` field but the UI doesn't render it; failures are silent except for a missing-row.
- **Align `domainsLoaded` → `loaded` naming consistency** between `domains-store.ts` and `cross-domain-gate-store.ts` (Plan 13 Task 3 review I1).
- **Drop or wire the `error` field in `cross-domain-gate-store`** (Plan 13 Task 3 review I2). Beyond-spec field added so `loading` derivation could differentiate "still loading" from "errored-with-fallback"; either remove or surface in UI.
- **Cross-tab pubsub via `BroadcastChannel`** if optimistic-clobber race becomes user-visible (Plan 13 Task 3 review I3). zustand pubsub is in-tab only; cross-tab requires explicit messaging.
- **Align `setAcknowledgedOptimistic` to use early-return pattern** matching `setActiveDomainOptimistic` (Plan 13 Task 3 review M1 — minor style).
- **Split `panel-domains.tsx` into 3 files** (Plan 13 Task 3 review M3 — file size approaching uncomfortable territory). Suggested split: domain row + add-domain affordance + active-domain dropdown.

### brain_api hardening (from Plan 13 Task 5 reviews)

- **Harden `SPAStaticFiles` against non-http scopes** — add a guard that returns 404 for WS scopes regardless of route ordering (Plan 13 Task 5 review M1). Defense-in-depth on top of Task 5's `mount_static_ui=False` fix.
- **Pin `request_id` slot in 500 envelope's `detail`** (Plan 13 Task 5 review M3 — if Plan 11 didn't already cover this).

### a11y (from Plan 13 Task 6 reviews)

- **Add Playwright (a11y + setup-wizard at minimum) to CI.** Mac + Windows runners. brain_api webServer bootstrap. chflags handling for editable installs (the wildcard glob `_editable_impl_*.pth` is the canonical form). (Plan 13 Task 6 step 6 deferred — explicitly captured here.) THIS IS THE STRUCTURAL FIX for the cascade-shadowing class of a11y regression Task 6 surfaced.
- **Extend a11y route coverage to populated states** (Plan 13 Task 6 review I2 + #7): chat thread with rendered prose, citations, tool-calls; cross-domain modal; patch-card edit dialog. Current sweep is empty/skeleton-state only.
- **Fix `.prose a` dark-mode contrast** (route through `--tt-cyan` or add explicit override) (Plan 13 Task 6 review #2).
- **Replace `text-[var(--bg)]` with `text-[var(--accent-foreground)]` in `patch-card.tsx:117`** (Plan 13 Task 6 review #3 — semantic correctness).
- **Consolidate dark-mode `#E06A4A` hardcoded hex usages** in `brand-skin.css` to `var(--tt-cyan)` (Plan 13 Task 6 review #5).
- **Move all token primitives to `tokens.css`** OR add CSS lint rule that flags duplicate token definitions across files (structural fix for cascade-shadowing class of bug; Plan 13 Task 6 review #6).

### Cleanup carried forward (small cleanups from Plan 12 candidate scope NOT picked up by Plan 13)

- **Plan-text "topbar scope chip" inaccuracy drift watch** (lesson, not code; Plan 12 Task 8).
- **`brain start` CLI doesn't handle chflags gracefully** (Plan 12 Task 8). Escape hatch was direct uvicorn invocation. CLI's supervisor should retry with a chflags-prepared subshell OR drop `uv run` entirely.
- **Modal "private" vs Settings "Privacy-railed" jargon split** (Plan 12 Task 7 deliberately deferred).
- **Active-domain dropdown toast "Pick a different domain" CTA wording** misleading on transport failures (Plan 12 Task 8 I2).
- **Active-domain dropdown `pushToast` outside try-block defensive cleanup** (Plan 12 Task 8 I1).
- **Task 9 `pendingSendRef.mode` dead field** (Plan 12 Task 9 review).

### Plan 13 plan-file archival cleanup (already landed)

- **Update plan file lines 13, 133, 459 from "× 4" to "× 3"** for `test_auth_dependency.py` (plan author miscount; ground truth is 3 tests). LANDED in Task 7 closure commit.

### Test-quality follow-throughs

- **`_NO_CONFIG_MESSAGE` extraction to `tools/_errors.py`** as `raise_if_no_config(ctx, tool_name)` helper (Plan 13 Task 1 review I2 — three sites + a known-pattern, threshold met).
- **Align `_mk_ctx` signatures across `test_list_domains.py` / `test_list_domains_active.py` / `test_config_set.py`** (Plan 13 Task 1 review M3 — style consistency).
- **`apply_patch._resolve_config` Plan 07 Task 5 deferral docstring** (separate scope-adjacent followup; not in Plan 13 Task 1 scope).

### Bigger architectural moves (forwarded from Plan 12 + 13 NOT-DOING)

- **Per-domain budget caps** — separate cost-ledger schema change.
- **Per-domain rate limits** — rate limits live in the provider client today.
- **Repair-config UI screen** — Plan 11 D7 landed the auto-fallback chain; the UI surface is a deeper iteration.
- **Hot-reload of config changes across processes** — cross-process invalidation (brain_api notifying brain_mcp of a domain rename) is a future iteration.
- **`validate_assignment=True` on `Config` and sub-configs** — KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`). Performance impact needs measurement first.
- **Per-domain autonomy categories** — Plan 12 D1 chose DELETE for `resolve_autonomous_mode`. Re-introducing per-domain autonomy is a Plan 14+ architectural lift requiring `Config.autonomous` to grow per-domain-per-category structure.
- **"Set as default" button on the topbar scope picker** — Plan 12 D3 placed the editor on `panel-domains.tsx`.
- **Per-thread cross-domain confirmation** — Plan 12 D8 chose per-vault `Config` field; per-thread violates spec §4 "one-time".
- **Generic "tool reads ctx.config" lint rule** — Plan 12 D5's audit + Plan 13 strict-policy pins are per-tool. A repo-wide ruff rule or AST check is Plan 14+ if the anti-pattern keeps re-appearing.
- **Migration tool for old `config.json` files** — Pydantic defaults handle missing fields on read; `save_config` round-trips with the new shape on next mutation.
- **Generic zustand promotion across other hooks** (`useBudget`, `useDomainOverrides`, etc.) — Plan 12 promoted `useDomains` and Plan 13 promoted `useCrossDomainGate`; generalizing the pattern across other hooks is Plan 14+ if/when the same cross-instance bug surfaces elsewhere.

These are NOT a Plan 14 commitment — Plan 14 will be authored just-in-time once Plan 13 closes. They're seed items so future-Claude doesn't re-discover them from scratch.
