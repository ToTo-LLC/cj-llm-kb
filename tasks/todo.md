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
| 10 | [Configurable Domains](./plans/10-configurable-domains.md) | 📝 Ready for execution (drafted 2026-04-27, awaiting D1–D10 sign-off) | Replace `Domain = Literal["research","work","personal"]` with a runtime list driven by `Config.domains`; widen `scope_guard` + classify prompt template; surface real Add/Rename/Delete in Settings → Domains. Closes known-issue #21. 9 tasks; demo gate walks add → ingest → rename → reject `personal` rename → delete → restart. | brain-core-engineer, brain-prompt-engineer, brain-frontend-engineer, brain-test-engineer |

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
