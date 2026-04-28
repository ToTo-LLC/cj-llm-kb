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

## Plan 12 candidate scope (forwarded from Plan 11)

Items deferred from Plan 11 that are candidate scope for Plan 12+. Plan 12 itself is not yet authored.

- **`resolve_autonomous_mode` consumer wiring** — Plan 11 Task 5 landed `brain_core.llm.resolve_autonomous_mode(config, domain) -> bool` per D13's resolver pattern, but no production code reads the coarse `Config.autonomous_mode` bool today (the autonomy gate at `brain_core.autonomy` reads per-category flags via `Config.autonomous.<category>`). Plan 12+ should either (a) wire `resolve_autonomous_mode` into the autonomy gate (likely needs `Config.autonomous` to grow per-domain-per-category structure), or (b) delete the resolver as dead code. Right now it's tested but unused.
- **Per-domain budget caps** — Plan 11 D4 persists `Config.budget` as a sub-config but the cap fields are global. Per-domain caps need a separate ledger schema change.
- **Per-domain rate limits** — `LLMConfig` has no rate-limit field today; rate limits live in the provider client.
- **Repair-config UI** — Spec §10 mentions a "Repair config" UI screen for corrupt `config.json`. Plan 11 D7 landed the auto-fallback chain (`config.json → .bak → defaults`); the UI surface is a deeper iteration.
- **Hot-reload of config changes across processes** — Plan 11 persists changes; downstream processes that have cached `Config` see the change on next restart only. Cross-process invalidation (e.g., brain_api notifying brain_mcp of a domain rename) is a future iteration.
- **`validate_assignment=True` on `Config` and sub-configs** — Plan 11 Task 4 added a KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`). Enabling `validate_assignment` would catch silent bad writes at the setattr point rather than next-load. Has performance implications for hot paths; needs measurement.
- **Settings UI for `active_domain` editing** — Plan 11 Task 8 implementer flagged this gap: `brain_config_set` rejects the `active_domain` key (treated as session-scoped today). To verify Task 8's screenshot 3 the implementer hand-edited `config.json`. Plan 12 should add an "Active domain" selector in Settings → Domains with a path through to persistence (likely a separate tool or a relaxation of the `_SETTABLE_KEYS` guard for `active_domain` specifically, with the cross-field-must-be-in-domains validator catching errors).
- **Cross-domain confirmation modal copy is TBD** — deferred from Plan 11 Task 9: the spec line 187 wording "warning about personal content" was deferred to defer with the actual UI string. The UI string itself doesn't exist yet — needs design + microcopy from `brain-ui-designer` before implementation. Confirmation modal triggers when the user opens a chat / draft session whose scope includes a privacy-railed domain.
- **`brain_config_get` snapshots `Config()` defaults instead of `ctx.config`** — Task 7 implementer flagged: read-only so no data loss, but Settings UI may show stale values until process restart. The Plan 11 Task 10 Playwright spec (`persistence.spec.ts`) explicitly does NOT assert the input value re-renders post-reload because of this drift; the disk bytes ARE correct. Fix: thread `ctx.config` through `brain_config_get` so the snapshot reflects live state.
- **`brain_mcp/server.py:_build_ctx` has the same Config-wiring gap brain_api Task 7 closed** — Task 7 reviewer flagged: same fix pattern (load_config → build context with config=). The MCP transport doesn't currently thread Config through to ToolContext, so any Plan 11 mutation dispatched via Claude Desktop → brain_mcp falls to the `ctx.config is None` no-op branch (silent persistence failure). Production users hitting brain via Claude Desktop will not get the persistence guarantee Plan 11 ships until this is fixed.
- **`useDomains()` lacks cross-instance pubsub** — surfaced during Plan 11 Task 10's e2e closure (the `domains.spec.ts` failure was misdiagnosed as a Task 8 regression, but `git checkout` to pre-Task-8 SHAs reproduced the same failure — it's a Plan 10-era latent bug). The hook caches its last response in module state; when `panel-domains.tsx` calls `invalidateDomainsCache()` after a mutation, already-mounted hook instances on OTHER components (e.g., the topbar) keep their stale React state — they only re-fetch on next mount. Today's workaround is `page.reload()` between mutation and cross-surface verification (used in the fixed `domains.spec.ts`). Plan 12 fix: promote to a real subscriber pattern (zustand store entry or a tiny event emitter that bumps a `tick` to force re-fetch on all consumers).

These are NOT a Plan 12 commitment — Plan 12 will be authored just-in-time once Plan 11 closes. They're seed items so future-Claude doesn't re-discover them from scratch.
