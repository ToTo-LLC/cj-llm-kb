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

## Plan 13 candidate scope (forwarded from Plan 12)

Items deferred from Plan 12 that are candidate scope for Plan 13+. Plan 13 itself is not yet authored.

- **`apply_patch.py:_resolve_config` docstring stale** (Task 3 review). The docstring says "Mirrors the brain_config_get approach" but Task 3 removed that approach (`brain_config_get` now reads `ctx.config` directly). 1-line follow-up edit to drop the stale reference.
- **`list_domains` None-policy asymmetry** (Task 3 review). `config_get` raises `RuntimeError` on `ctx.config is None` (lifecycle violation); `list_domains._configured_slugs` and `_active_domain` silently fall back to `DEFAULT_DOMAINS`. After Task 4 confirmed brain_api + brain_mcp wrappers wire Config correctly, evaluate tightening `list_domains` to match the strict policy — silent fall-through is the same anti-pattern Plan 11 lesson 343 named.
- **`config_set.py:317-327` lenient `cfg is None` branch** (Task 3 review). Same asymmetry as `list_domains`. The fall-through here is intentional pre-Task-4 (so unit tests with `ctx.config=None` exercised the validation path), but the post-fix wrappers always supply Config. Plan 11 Task 7 framing: "the BUG, not the contract" — the lenient branch is now untestable in production-shape integration tests.
- **`panel-domains.tsx` local `domains: string[]` state** (Task 5 + Task 8 confirmed). Parallel to the zustand `useDomainsStore`. The local state is hydrated from a separate `refresh()` rather than reading the store; it's been correct because both code paths fetch the same backend, but it's drift-prone. Should read from `useDomainsStore` directly and drop the local state.
- **Plan 12 plan-text "topbar scope chip" inaccuracy** (Task 8 lesson). The plan said "topbar scope chip updates without page reload" — that's wrong. The topbar is per-session (post-`scopeInitialized` flip), NOT live-bound to `Config.active_domain`. Plan 11 D9 deliberately drew that distinction. Plan 13 should either: (a) make the topbar live-bound to `active_domain` (with its own opt-out for in-session edits), or (b) leave the distinction and update plan-author drift-watch lessons.
- **`brain start` CLI doesn't handle chflags gracefully** (Task 8). Implementer had to fall back to direct `python -m uvicorn` invocation because `brain start` re-syncs uv mid-bootstrap and re-hides the editable `.pth`. The CLI's supervisor should retry with a chflags-prepared subshell, OR `brain start` should drop `uv run` from the supervisor entirely.
- **Modal "private" vs Settings "Privacy-railed" jargon split** (Task 7). Implementer left this asymmetric: the cross-domain modal copy uses "private domain" / "kept private by default" (plain-language); Settings → Domains uses "Privacy rail" + "Privacy-railed" (power-user). Plan 13 should pick one term and align both surfaces.
- **Active-domain dropdown toast CTA "Pick a different domain"** (Task 8 I2). The toast surfaces `${detail} Pick a different domain.` on any error, but transport failures (network drop, 502, CORS) don't have a different-domain remedy. Either drop the CTA or make it conditional on the validator-error path.
- **Active-domain dropdown toast `pushToast` outside try-block** (Task 8 I1). The `pushToast({...danger...})` call sits inside the `catch` block. `pushToast` can't realistically throw (it's a zustand setter), but defensively the catch should not wrap a fallible-looking call — easy to mis-read. Move outside try-block or document why it's inside.
- **Task 9 `pendingSendRef.mode` dead field** (Task 9 review). The `mode` field is captured into `pendingSendRef.current.mode` but never read — `dispatchSend` reads live closure `mode`. Either remove the field (cleanup) or use it explicitly (the comment says "captured at click time, not at render time" — that intent isn't honored).
- **Task 9 `useCrossDomainGate` cross-instance gap** (Task 9 review). Same shape as Plan 12 Task 5 fixed for `useDomains`: the gate hook holds local React state for `privacyRailed` + `acknowledged`; mutation via the Settings toggle's `setCrossDomainWarningAcknowledged` only updates the in-toggle state, not the gate hook in chat-screen. Same-tab re-mount works but BroadcastChannel/storage-event would be the real fix, OR promote the gate fields to a zustand store like Plan 12 Task 5 did for domains.

Also forwarded from Plan 12's NOT-DOING section (matches the "bigger architectural moves" Group C from Plan 11 candidate scope):

- **Per-domain budget caps** — separate cost-ledger schema change.
- **Per-domain rate limits** — rate limits live in the provider client today.
- **Repair-config UI screen** — Plan 11 D7 landed the auto-fallback chain; the UI surface is a deeper iteration.
- **Hot-reload of config changes across processes** — cross-process invalidation (brain_api notifying brain_mcp of a domain rename) is a future iteration.
- **`validate_assignment=True` on `Config` and sub-configs** — KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`). Enabling validate_assignment would catch silent bad writes at the setattr point. Performance impact needs measurement first.
- **Per-domain autonomy categories** — D1 chose DELETE for `resolve_autonomous_mode`. Re-introducing per-domain autonomy is a Plan 13+ architectural lift requiring `Config.autonomous` to grow per-domain-per-category structure.
- **"Set as default" button on the topbar scope picker** — D3 placed the editor on `panel-domains.tsx`. Topbar growing the affordance was rejected as muddling the per-session vs persistent-default distinction Plan 11 Task 8 was careful to establish.
- **Per-thread cross-domain confirmation** — D8 chose per-vault `Config` field; per-thread violates spec §4 "one-time".
- **Generic "tool reads ctx.config" lint rule** — D5's audit + regression-pin test is per-tool. A repo-wide ruff rule or AST check is Plan 13+ if the anti-pattern keeps re-appearing.
- **Migration tool for old `config.json` files missing `cross_domain_warning_acknowledged`** — Pydantic defaults handle this on read; `save_config` round-trips with the new field on next mutation.
- **`useDomains` zustand promotion as a generic pattern for `useBudget` / `useDomainOverrides` / etc.** — Plan 12 promoted `useDomains` only; generalizing the pattern across other hooks is Plan 13+ if/when the same cross-instance bug surfaces elsewhere.

Pre-existing test failures NOT caused by Plan 12 (verified by reproducing on clean main HEAD pre-Task-10):

- 8 a11y color-contrast violations on `/chat`, `/inbox`, `/browse`, `/pending`, `/bulk`, `/settings/general`, `/settings/providers`, `/settings/domains`. Plan 13 should re-verify the Plan 07 Task 25C token nudges are still in effect; current state suggests they regressed at some point post-Plan-09.
- 1 setup-wizard a11y violation on the welcome step (color-contrast). Same root cause as the above.
- 13 brain_api unit-test failures: 4 in `test_auth_dependency.py`, 8 in `test_errors.py`, 1 in `test_context.py::test_get_ctx_dependency_resolves`, 1 in `test_ws_chat_handshake.py::test_handshake_rejects_bad_thread_id`. All of them assert response status codes that come back unexpectedly as 200 — likely an OriginHostMiddleware regression from Plan 11/12 brain_api changes. The Playwright e2e suite (which exercises the same paths through the real subprocess) does NOT reproduce these, so the tests are likely TestClient/middleware-config drift, not a real production regression. Plan 13 should triage.

These are NOT a Plan 13 commitment — Plan 13 will be authored just-in-time once Plan 12 closes. They're seed items so future-Claude doesn't re-discover them from scratch.
