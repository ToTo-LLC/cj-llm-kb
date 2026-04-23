# Contributing to brain

Contributions welcome. brain is built via a plan-driven subagent workflow — read this first so your change matches the shape of the project. The short version: specs precede code, every change has tests, and the vault is sacred.

If you're here because of a specific bug or a small fix, jump straight to [PR guidelines](#pr-guidelines). If you want to add a feature, start with [Workflow](#workflow--plan-driven).

---

## Dev setup

### Prerequisites

- **Python 3.12+** — the `brain_core`, `brain_cli`, `brain_mcp`, and `brain_api` packages target 3.12.
- **uv 0.4+** — Python workspace + package manager. Install from <https://docs.astral.sh/uv/>.
- **Node 20 + pnpm 9** — build-time only for `apps/brain_web`. End users never need Node; contributors do, to rebuild the UI bundle.

### Clone + install

```bash
git clone https://github.com/ToTo-LLC/cj-llm-kb && cd cj-llm-kb
uv sync --all-packages
pnpm -F brain_web install
```

`uv sync --all-packages` installs every workspace package in editable mode and resolves dev dependencies. `pnpm -F brain_web install` is only needed if you plan to touch the Next.js app.

### Smoke test

```bash
uv run pytest packages/ -q
pnpm -F brain_web test --run
```

Both suites should finish green. If the Python suite fails before you've touched anything, open an issue — that's a regression. If the frontend suite fails, first check that `pnpm -F brain_web install` completed and your Node version is 20.

### Run the app locally

```bash
uv run brain start
```

Opens the browser at `http://localhost:4317/`. The first run walks the 6-step setup wizard. The vault defaults to `~/Documents/brain/` — don't point it inside this repo.

### Run `brain doctor`

```bash
uv run brain doctor
```

Diagnostic. Run this before committing any change that touches config, install scripts, or cross-platform code paths. It surfaces broken vault layouts, stale caches, missing binaries, and permissions problems with plain-English remediation steps.

---

## Workflow — plan-driven

brain changes follow the `tasks/plans/NN-name.md` pattern driven by the [`superpowers:subagent-driven-development`](https://github.com/anthropics/superpowers) skill. For any non-trivial change (anything 3+ steps, anything touching vault schema / safety rails / prompts), the shape is:

1. **Brainstorm.** Scope the problem. Write it down.
2. **Spec update.** Edit `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` first. The spec is the source of truth for every decision.
3. **Plan.** Add or extend a plan file under `tasks/plans/`. Checkbox tasks, owning subagent, hard gates.
4. **Implement with a subagent.** Delegate focused work to the right specialist (see [`CLAUDE.md`](CLAUDE.md) for the roster: `brain-core-engineer`, `brain-mcp-engineer`, `brain-frontend-engineer`, `brain-ui-designer`, `brain-prompt-engineer`, `brain-test-engineer`, `brain-installer-engineer`).
5. **Tests.** Unit, integration, and — for any prompt change — a VCR contract test. Green on Mac and Windows.
6. **Review.** Update the plan's Review section, capture anything learned in `tasks/lessons.md`.

Small bugfixes can skip the spec + plan steps and go straight to PR, as long as they come with a regression test. "New feature" always starts with a spec update.

The two files every contributor should skim before editing:

- [`tasks/todo.md`](tasks/todo.md) — the active plan's open items.
- [`tasks/lessons.md`](tasks/lessons.md) — patterns worth not re-learning.

---

## Testing

Three tiers of Python tests plus a web tier:

- **Unit tests** alongside code (`packages/brain_core/tests/`, `packages/brain_cli/tests/`, `packages/brain_mcp/tests/`, `packages/brain_api/tests/`). Pure `brain_core`, no network, no live LLM — uses `FakeLLMProvider`. Target coverage: **>85%** on `brain_core`.
- **Integration tests** across packages and pipelines. Still `FakeLLMProvider`, but real filesystem, real SQLite, real FastAPI test client, real MCP server over stdio. Golden-vault fixture; mutations asserted against committed golden files.
- **LLM contract tests** — real API calls recorded via VCR-style cassettes and committed. Replay by default; `RUN_LIVE_LLM_TESTS=1` re-records before a release. Assertions on schema validity, token budget, scope compliance, and wikilink validity.
- **Frontend tests** — Vitest + React Testing Library for components; Playwright end-to-end for setup wizard, drag-drop ingest, patch approval, chat turn, and bulk-import dry-run. Every Playwright test runs axe-core. **Zero WCAG 2.2 AA violations is a hard gate.**

Run them:

```bash
uv run pytest packages/ -q           # unit + integration, fast path
uv run pytest -m llm_contract        # contract tests (replay cassettes)
pnpm -F brain_web test --run         # Vitest component tests
pnpm -F brain_web e2e                # Playwright (requires brain_api running)
```

**No merges without green CI on Mac and Windows.** A green Mac run alone does not unblock a merge — the GitHub Actions matrix runs both, and both must pass.

### Writing tests

- **Regression tests on every bugfix.** No fix merges without a test that failed before the fix and passes after.
- **Synthetic data only.** No real personal content in fixtures or cassettes.
- **Fix flakiness, don't retry it.** Root-cause every flake. Only add retries where the failure is genuinely non-deterministic and documented.
- **Fast feedback.** Unit tests finish in under 30s. Integration under 3 min. The full matrix under 15 min.

---

## Coding rules

Condensed from [`CLAUDE.md`](CLAUDE.md) — read that for the full reasoning behind each one. These are non-negotiable:

1. **The vault is sacred.** Every vault mutation goes through `VaultWriter`. Writes are atomic (temp + rename). Every applied change is recorded in the undo log. Uninstall never deletes the vault without typed confirmation.

2. **Scope-guard every vault read and write.** All vault access passes through `brain_core.vault.scope_guard(path, allowed_domains)`. There must be no code path that bypasses it. `personal` content never appears in default or wildcard queries.

3. **LLM writes are always staged, never direct.** The LLM produces typed patch sets (`new_files`, `edits`, `index_entries`, `log_entry`). Patches validate before apply. The autonomous-mode setting only changes whether the approval queue auto-approves — the tool surface and validation are identical.

4. **`LLMProvider` is an abstraction.** Every LLM-touching module imports `brain_core.llm.LLMProvider`, never a concrete SDK directly. Anthropic is the day-one implementation. **Do not import the Anthropic SDK outside `packages/brain_core/src/brain_core/llm/providers/anthropic.py`.**

5. **Cost is a first-class citizen.** Every LLM call writes to `costs.sqlite` with operation, model, tokens, cost, and domain. Budget caps are hard kill switches, not soft warnings.

6. **Vault is the source of truth; SQLite is a cache.** `state.sqlite`, `costs.sqlite`, and any future search indexes must be rebuildable from vault content alone. `brain doctor --rebuild-cache` must work end-to-end.

7. **Tests alongside code.** Every `brain_core` module has unit tests. Every pipeline has an integration test. Every prompt has a VCR-recorded contract test.

8. **Cross-platform from day one.** No POSIX-only code. Paths via `pathlib`. Line endings LF on disk. Filenames sanitized against Windows reserved names (`CON`, `PRN`, etc.). Long paths use `\\?\` prefix on Windows. No `shell=True`. No hardcoded forward slashes.

9. **Non-technical usability is a requirement.** Error messages in plain English with a next action. Every destructive action requires typed confirmation. Drag-and-drop, paste, and file picker everywhere content can enter.

10. **Privacy-first.** Zero telemetry. Zero analytics. The only outbound non-LLM call is an opt-out version check. Secrets never logged. LLM prompt/response bodies are not logged unless `log_llm_payloads` is explicitly enabled.

### What not to do

- Do not write to the vault outside `VaultWriter`.
- Do not add a code path that bypasses `scope_guard`.
- Do not import the Anthropic SDK outside `brain_core/llm/providers/anthropic.py`.
- Do not log LLM prompt or response bodies by default.
- Do not add telemetry, analytics, crash reporting, or "phone home" features.
- Do not bundle the vault into the repo.
- Do not use POSIX-only APIs, `shell=True` subprocess calls, or hardcoded path separators.
- Do not invoke a frontend implementation task before mockups exist and are approved.

---

## PR guidelines

A PR is mergeable when:

- **Tests are green on Mac and Windows.** GitHub Actions matrix. Both rows green.
- **A regression test accompanies every bugfix.** The test fails on `main` and passes on the PR.
- **Coverage on `brain_core` stays above 85%.** Don't weaken assertions to make flakiness go away.
- **Lessons are updated if behavior changed.** Add a row to `tasks/lessons.md` capturing the pattern worth not re-learning.
- **No plan drift.** If the PR touches a file an open plan task claims to own, either the plan gets updated or the PR gets rescoped.
- **No secrets committed.** `.brain/secrets.env`, `.brain/logs/`, `.brain/run/` are all gitignored — keep it that way.

Keep PRs focused. One plan task per PR is ideal. If a PR balloons past ~500 lines of diff, split it.

**Commit message style.** Follow the convention in `git log`: `scope(area): short imperative summary`. Examples from recent history:

```
feat(mcp): plan 04 task 5 — brain_get_index tool
refactor(mcp): plan 04 task 4 — cache tool context + ToolModule Protocol
docs(plan): plan 04 — track tasks 2-4 deferrals for task 25 sweep
```

---

## Issues and security reports

- **Bugs** — open a GitHub issue at <https://github.com/ToTo-LLC/cj-llm-kb/issues>. Include `brain doctor` output, OS + version, and repro steps.
- **Feature requests** — same issue tracker, tag `enhancement`. A spec sketch goes a long way.
- **Security-sensitive reports** — do not open a public issue. Email **chris@tomorrowtoday.com** with details and I'll coordinate a fix.

---

Thanks for reading. The short version of everything above: spec first, tests always, vault is sacred, no telemetry. If in doubt, re-read [`CLAUDE.md`](CLAUDE.md) and the [design spec](docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md).
