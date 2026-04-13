# brain — Agent Orchestration Guide

> Cross-agent coordination rules, domain ownership, parallel/sequential execution, integration checkpoints, conflict resolution. Referenced from [`CLAUDE.md`](../CLAUDE.md). Every subagent reads this on dispatch.

## 1. Contract-first workflow

All cross-package boundaries are defined as typed contracts **before** implementation.

- **Python contracts** live in `packages/brain_core/src/brain_core/<domain>/types.py` — `Protocol`s, dataclasses, pydantic models.
- **HTTP API contract** is the FastAPI-generated OpenAPI at `packages/brain_api/openapi.yaml`, consumed by the frontend via a generated TypeScript client.
- **MCP tool schemas** live alongside the tool definitions in `packages/brain_mcp/src/brain_mcp/tools/<tool>.py`.
- **Vault schema** (frontmatter fields, filename rules, wikilink conventions) lives in `docs/BRAIN.md.template` and is validated by `brain_core.vault.schema`.
- **LLM provider contract** is `brain_core.llm.provider.LLMProvider` — every concrete provider must satisfy it.

Before any agent implements a feature that crosses a package boundary, the contract is written, committed, and tested first. Implementation PRs cannot change contracts without a spec update.

## 2. Domain ownership

Each file in the repo is owned by exactly **one** subagent. Cross-ownership edits require explicit coordination through the main loop.

| Agent | Owns |
|---|---|
| **brain-core-engineer** | `packages/brain_core/**`; `packages/brain_api/**` (HTTP routes/plumbing — the business logic lives in brain_core) |
| **brain-mcp-engineer** | `packages/brain_mcp/**`; `packages/brain_core/src/brain_core/integrations/claude_desktop/**` |
| **brain-frontend-engineer** | `apps/brain_web/src/**`; `apps/brain_web/public/**` |
| **brain-ui-designer** | `docs/design/**`; `apps/brain_web/tailwind.config.ts` (first creation only); shadcn theme files |
| **brain-prompt-engineer** | `packages/brain_core/src/brain_core/prompts/**`; `docs/BRAIN.md.template`; prompt cassettes in `packages/brain_core/tests/prompts/` |
| **brain-test-engineer** | `packages/*/tests/**` (review authority); `apps/brain_web/e2e/**`; `docs/testing/**`; `.github/workflows/**` |
| **brain-installer-engineer** | `packages/brain_cli/**`; `scripts/install.sh`; `scripts/install.ps1`; launcher shortcut assets |

**Shared / coordinated paths** (no single owner — any edit goes through the main loop):
- Root `pyproject.toml`, root `package.json` — adding a dep requires announcement and justification.
- `CLAUDE.md`, `.claude/` — main loop only; subagents never edit these.
- `docs/superpowers/specs/` — spec changes go through the brainstorming skill, not subagents.
- `tasks/todo.md`, `tasks/plans/`, `tasks/lessons.md` — main loop only.

## 3. Parallel vs sequential execution

**Hard sequential**: Plan 06 (UI Design) → Plan 07 (Frontend). No frontend code exists before mockups are approved.

**Soft sequential (recommended order)**:
1. Plan 01 (Foundation) before everything else — it defines the core contracts.
2. Plans 02 (Ingestion), 03 (Chat), 04 (MCP), 05 (API) may parallelize after Foundation, but each completes its own tests before a downstream plan builds on its contracts.
3. Plan 06 (UI Design) runs in parallel with 02–05.
4. Plan 08 (Install) after Foundation and ideally after at least one demoable feature exists (e.g., 02 or 03).
5. Plan 09 (Ship) last.

**Within a plan**: executed via `superpowers:subagent-driven-development` — fresh subagent per task, two-stage review between tasks. Parallel subagent dispatch only for genuinely independent tasks (e.g., two unrelated source handlers in Plan 02).

## 4. Integration checkpoints

**At the end of every plan:**
1. All tests green on Mac **and** Windows CI.
2. Demo artifact captured: screenshot, recording, or test-run receipt.
3. User review gate: spec alignment confirmed, next plan authored or refined.
4. `tasks/lessons.md` updated with any corrections from this plan's execution.
5. `tasks/todo.md` status updated.

**Between plans that touch a shared contract:**
1. The contract-owning agent updates the contract file and its tests **first** and commits.
2. Downstream agents pull and adapt.
3. No parallel edits to the same contract file.

## 5. Conflict resolution

**When two agents need to edit the same file:**
1. Main loop adjudicates — not the agents themselves.
2. Split the file if responsibilities are genuinely separable.
3. If not separable, serialize the edits: agent A goes first, agent B rebases.
4. Document the conflict in `tasks/lessons.md` so the next plan's file structure avoids it.

**When a subagent reports a failure or blocker:**
1. **STOP and re-plan** per `CLAUDE.md`. Do not retry blindly.
2. Identify the **root cause**, not the symptom.
3. If the spec is wrong → update the spec via the brainstorming skill.
4. If the plan is wrong → update the plan file.
5. If the implementation is wrong → write a regression test, then fix.

## 6. Review protocol

Per the user's `CLAUDE.md` workflow directives:
- Main loop uses `AskUserQuestion` with ≤4 labeled options (NUMBER.LETTER format) for any significant decision.
- Recommended option is always listed first.
- Pause for user feedback at the end of every section, plan, and major decision.
- `superpowers:code-reviewer` runs after any major plan step.
- Manual QA checklist (`docs/testing/manual-qa.md`) runs before any release tag.

## 7. What subagents NEVER do

- Edit files outside their ownership without the main loop's permission.
- Mark a task complete without verification (tests, screenshots, demonstrable proof).
- Bypass `scope_guard`, `VaultWriter`, or the `LLMProvider` abstraction.
- Ship code without cross-platform CI green on **both** Mac and Windows.
- Introduce telemetry, analytics, or any "phone home" behavior.
- Write to the vault from anywhere other than `VaultWriter`.
- Author their own plans; plans come from the main loop via the writing-plans skill.
- Skip cross-platform checks "just this once."
