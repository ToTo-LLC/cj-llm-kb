# brain — Master Plan Index

> Master tracking board for the `brain` implementation. Each sub-plan is a self-contained, demoable unit. Plans are written **just-in-time**: plan N+1 is authored only after plan N is approved and reviewed, so lessons from earlier execution shape later plans.

**Spec:** [`docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`](../docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md)
**Orchestration:** [`.claude/ORCHESTRATION_GUIDE.md`](../.claude/ORCHESTRATION_GUIDE.md)
**Lessons:** [`lessons.md`](./lessons.md)

## Status

| # | Plan | Status | Demoable deliverable | Primary subagent(s) |
|---|---|---|---|---|
| 01 | [Foundation](./plans/01-foundation.md) | ✅ Complete (2026-04-13, tag `plan-01-foundation`) | Tested `brain_core` library (config, vault, llm, cost) green on Mac + Windows CI | brain-core-engineer, brain-test-engineer |
| 02 | [Ingestion](./plans/02-ingestion.md) | 📝 Ready for execution | `brain add <url>` produces a wiki note via full pipeline | brain-core-engineer, brain-prompt-engineer |
| 03 | Chat | ⏸ Not yet written | `brain chat` Ask / Brainstorm / Draft working in terminal | brain-core-engineer, brain-prompt-engineer |
| 04 | MCP + Claude Desktop | ⏸ Not yet written | Claude Desktop reads / searches / ingests over MCP | brain-mcp-engineer |
| 05 | API | ⏸ Not yet written | FastAPI + WebSocket backend, curl-driven end-to-end | brain-core-engineer |
| 06 | UI Design | ⏸ Not yet written | Approved design artifacts at `docs/design/` (hard gate) | brain-ui-designer |
| 07 | Frontend | ⏸ Not yet written, **blocked on #06** | Full web app on localhost | brain-frontend-engineer |
| 08 | Install + Packaging | ⏸ Not yet written | One-command install on clean Mac + Windows VMs | brain-installer-engineer |
| 09 | Ship | ⏸ Not yet written | v0.1.0 tagged, documented, manual-QA green | brain-test-engineer |

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
