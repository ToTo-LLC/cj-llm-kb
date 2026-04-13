# brain

LLM-maintained personal knowledge base following Andrej Karpathy's "LLM Wiki" pattern. A Python + TypeScript monorepo that turns a folder of Markdown files into a second brain you can chat, brainstorm, and draft with.

## Start here

**Read the full spec first:** `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`. It is the source of truth for every decision on this project. Any change to architecture, vault schema, prompts, or safety rails requires a spec update first.

## At a glance

- **Purpose**: ingest research, work, and personal source material; maintain an Obsidian-compatible Markdown wiki; chat/brainstorm/draft against it.
- **Stack**: Python 3.12 + `uv` workspace for `brain_core` / `brain_cli` / `brain_mcp` / `brain_api`; Next.js 15 + TypeScript + Tailwind + shadcn/ui for `brain_web`.
- **Entry points**: `brain start` (web app at http://localhost:4317), Claude Desktop via MCP, `brain` CLI.
- **Vault location**: `~/Documents/brain/` — **not** inside this repo. Vault is content (sacred, survives the code). Repo is code.
- **Cross-platform**: Mac 13+ and Windows 11 are first class. Linux falls out for free but is not a day-one target.

## Architecture in one paragraph

A pure Python `brain_core` package owns all logic (vault I/O, ingestion pipeline, LLM provider abstraction, chat loop, lint, cost tracking, config) and has **zero** web or MCP dependencies. Three thin wrappers import it: `brain_cli` (Typer-based CLI + setup wizard launcher), `brain_mcp` (MCP server for Claude Desktop), `brain_api` (FastAPI REST + WebSocket for the web app). The Next.js frontend `brain_web` talks only to `brain_api`. All four wrappers share one vault on disk. See the spec for details.

## Non-negotiable principles

1. **The vault is sacred.** Every vault mutation goes through `VaultWriter`. Writes are atomic (temp + rename). Every applied change is recorded in the undo log. Uninstall never deletes the vault without typed confirmation.

2. **Scope guard everywhere.** Every vault read and write passes through `brain_core.vault.scope_guard(path, allowed_domains)`. There must be no code path that bypasses it. `personal` content never appears in default or wildcard queries.

3. **LLM writes are always staged, never direct.** The LLM produces typed patch sets (`new_files`, `edits`, `index_entries`, `log_entry`). Patches validate before apply. The autonomous-mode user setting only changes whether the approval queue auto-approves — the tool surface and validation are identical.

4. **`LLMProvider` is an abstraction.** Every LLM-touching module imports `brain_core.llm.LLMProvider`, never a concrete SDK directly. Anthropic is the day-one implementation; swapping or adding providers is a config change, not a refactor.

5. **Cost is a first-class citizen.** Every LLM call writes to `costs.sqlite` with operation, model, tokens, cost, and domain. Budget caps are hard kill switches, not soft warnings.

6. **Vault is the source of truth; SQLite is a cache.** `state.sqlite`, `costs.sqlite`, and any future search indexes must be rebuildable from vault content alone. `brain doctor --rebuild-cache` must work end-to-end.

7. **Tests alongside code.** Every `brain_core` module has unit tests. Every pipeline has an integration test. Every prompt has a VCR-recorded contract test. No merges without green CI on Mac *and* Windows.

8. **Cross-platform from day one.** No POSIX-only code. Paths via `pathlib`. Line endings LF on disk. Filenames sanitized against Windows reserved names (`CON`, `PRN`, etc.). Long paths use `\\?\` prefix on Windows. No `shell=True`. No hardcoded forward slashes.

9. **Non-technical usability is a requirement.** Error messages in plain English with a next action. Every destructive action requires typed confirmation. Setup happens in the browser, not the terminal. Drag-and-drop, paste, and file picker everywhere content can enter.

10. **Privacy-first.** Zero telemetry. Zero analytics. The only outbound non-LLM call is an opt-out version check. Secrets never logged. LLM prompt/response bodies are not logged unless `log_llm_payloads` is explicitly enabled.

## Subagents available in this project

Use the Task tool with the matching `subagent_type`. Delegate focused work to the right specialist over doing everything in the main loop.

- **brain-core-engineer** — `brain_core` Python library (vault, ingest, llm, chat, lint, cost, config). Test-driven, typed, no web/MCP deps.
- **brain-mcp-engineer** — `brain_mcp` MCP server + Claude Desktop auto-install / detection / self-test.
- **brain-frontend-engineer** — `brain_web` Next.js app. **Only writes code after mockups are approved.**
- **brain-ui-designer** — design system, wireframes, high-fidelity mockups, accessibility, microcopy. **Runs before any frontend code.**
- **brain-prompt-engineer** — summarize / integrate / classify / lint / chat-mode prompts. Owns the `BRAIN.md` template. Writes VCR contract tests.
- **brain-test-engineer** — three-layer test strategy (unit / integration / LLM contract) + Playwright e2e + manual QA checklist.
- **brain-installer-engineer** — `install.sh` / `install.ps1`, `brain doctor`, packaging, cross-platform setup QA.

## Workflow rules

- Every non-trivial change: brainstorm → spec update → plan → implement with the right subagent → tests → review.
- Changes to vault schema, prompts, or safety rails: spec update **first**, implementation second.
- Run `brain doctor` before committing anything that touches config, install, or cross-platform code paths.
- Never commit `.brain/secrets.env` or anything under `.brain/logs/` or `.brain/run/`.

## What NOT to do

- Do not write to the vault outside `VaultWriter`.
- Do not add a code path that bypasses `scope_guard`.
- Do not import the Anthropic SDK outside `brain_core/llm/providers/anthropic.py`.
- Do not log LLM prompt or response bodies by default.
- Do not add telemetry, analytics, crash reporting, or "phone home" features.
- Do not bundle the vault into the repo.
- Do not use POSIX-only APIs, `shell=True` subprocess calls, or hardcoded path separators.
- Do not invoke a frontend implementation task before mockups exist and are approved.
- Do not mark a task complete with failing tests, partial work, or skipped cross-platform runs.

### Workflow Orchestration

## 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

# 1.1 Plan Mode Directives
Review this plan thoroughly before making any code changes. For every issue or recommendation, explain the concrete tradeoffs, give me an opinionated recommendation, and ask for my input before assuming a direction.
My Engineering Preferences
Use these to guide your recommendations:

Be consistent — don't repeat yourself aggressively.
Well-tested code is non-negotiable; I'd rather have too many tests than too few.
I write code that's "engineered enough" — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity).
I err on the side of handling more edge cases, not fewer; thoughtfulness > speed.
Bias toward explicit over clever.


1. Architecture Review
Evaluate:

Overall system design and component boundaries.
Dependency graph and coupling concerns.
Data flow patterns and potential bottlenecks.
Scaling characteristics and single points of failure.
Security architecture (auth, data access, API boundaries).

2. Code Quality Review
Evaluate:

Code organization and module structure.
DRY violations — be aggressive here.
Error handling patterns and missing edge cases (call these out explicitly).
Technical debt hotspots.
Areas that are over-engineered or under-engineered relative to my preferences.

3. Test Review
Evaluate:

Test coverage gaps (unit, integration, e2e).
Test quality and assertion strength.
Missing edge case coverage — be thorough.
Untested failure modes and error paths.

4. Performance Review
Evaluate:

N+1 queries and database access patterns.
Memory-usage concerns.
Caching opportunities.
Slow or high-complexity code paths.


For Each Issue You Find
For every specific issue (bug, smell, design concern, or risk):

Describe the problem concretely, with file and line references.
Present 2–3 options, including "do nothing" where appropriate.
For each option, specify: implementation effort, risk, impact on other code, and maintenance burden.
Give me your recommended option and why, mapped to my preferences above.
Then explicitly ask whether I agree or want to choose a different direction before proceeding.

Workflow and Interaction

Do not assume my priorities on timeline or scale.
After each section, pause and ask for my feedback before moving on.


BEFORE YOU START
Ask if I want one of two options:

BIG CHANGE: Work through this interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 4 top issues in each section.
SMALL CHANGE: Work through interactively ONE option per section.

FOR EACH STAGE OF REVIEW: Output the explanation and pros/cons of each stage's questions and your opinionated recommendation and why, then use the AskUserQuestion tool to present at most 4 options to the user. When using AskUserQuestion, make sure each option clearly labels the issue NUMBER and option LETTER so the user doesn't get confused. Make the recommended option always the 1st option.

## 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

## 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

## 4. Verification Before Done
- Never mark a task complete without proving it works
- **ALWAYS validate fixes via the UI in the browser before declaring done** — reading code is not sufficient
- After making backend changes, restart the backend server before testing
- After making frontend changes, do a hard refresh (Cmd+Shift+R) to ensure HMR/cache issues don't give false results
- For each fix, take a screenshot showing the fix working and describe what you verified
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

## 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

## 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

# Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

# Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

## Planning and Development Approach

### Always Create Detailed Plans First

When creating new features and functionality, **always create a detailed plan** before writing any code. The goal is to maximize the likelihood of producing bug-free code on the first implementation.

A good plan includes:
1. **Requirements Analysis** - What exactly needs to be built
2. **Architecture Decisions** - How it fits into the existing system
3. **File Changes** - Specific files to create/modify
4. **Data Flow** - How data moves through the system
5. **Edge Cases** - Potential error conditions and how to handle them
6. **Dependencies** - What needs to exist before implementation
7. **Testing Strategy** - How to verify the implementation works

### Agent Orchestration

**Always refer to the orchestration guide:**
```
/.claude/ORCHESTRATION_GUIDE.md
```

This guide details:
- Contract-first development workflow
- Domain isolation (which agent owns which files)
- Parallel vs sequential execution rules
- Integration checkpoints
- Conflict resolution protocols
