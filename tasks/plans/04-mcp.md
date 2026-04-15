# Plan 04 — MCP Server + Claude Desktop Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DRAFT — pending section-by-section review. Task-level steps are intentionally unfilled below the outline until the architecture / scope / decisions sections are approved.**

**Goal:** Ship a working `brain_mcp` stdio server that exposes the Plan 01/02/03 vault/ingest/pending-patch primitives as MCP tools + resources, auto-installs into Claude Desktop, and passes a `brain mcp selftest` round-trip. After this plan, a user can open Claude Desktop and ask "what's in my brain?" — Claude Desktop becomes the chat surface per spec §6.

**Architecture:**
Plan 04 adds one new workspace package (`brain_mcp`) and one new `brain_core` module (`brain_core.integrations.claude_desktop`). The MCP server is a thin wrapper around existing `brain_core` primitives:
- Read tools wrap `BM25VaultIndex`, `vault.frontmatter.parse_frontmatter`, `vault.paths.scope_guard`, and a new `list_recent` helper
- Ingest tools wrap `ingest.pipeline.IngestPipeline` and `ingest.bulk.BulkImporter`
- Write/patch tools wrap `chat.pending.PendingPatchStore`, `vault.writer.VaultWriter`, and `vault.undo.UndoLog.revert`
- Maintenance tools wrap `cost.ledger.CostLedger` and `config.loader/schema/secrets`
- `brain_lint` lands as a stub returning "not yet implemented" since no `brain_core.lint` module exists (deferred to Plan 09)

Every tool has a JSON schema, scope-guards its inputs, and returns typed output. The `brain_cli` package gains a new `brain mcp install|uninstall|selftest` sub-app that calls `brain_core.integrations.claude_desktop` to merge/backup/verify Claude Desktop's config JSON. FakeLLMProvider is injected into the ingest/classify paths the same way Plan 02/03 did for tests; real API keys are needed only for live smoke.

**Tech stack (new deps):**
- `mcp>=1.0` — official Python MCP SDK (stdio transport, tool registration, resource registration)
- (existing) pydantic, typer, rich, pytest, mypy, ruff

**Demo gate:** `uv run python scripts/demo-plan-04.py` runs end-to-end against a temp vault + `FakeLLMProvider`:
1. Spawn the `brain_mcp` server in-process via the MCP SDK's test transport
2. Call `tools/list` → assert all 17 tools + 3 resources registered with valid JSON schemas
3. Call `brain_list_domains` → returns `["research", "work"]`
4. Call `brain_search` with `{"query": "karpathy", "domains": ["research"]}` → returns scoped hits
5. Call `brain_read_note` → returns frontmatter + body
6. Call `brain_ingest` with `{"source": "https://example.com/article", "autonomous": false}` (mocked) → returns a `PatchSet` without writing to the vault
7. Call `brain_list_pending_patches` → returns the staged patch from step 6
8. Call `brain_apply_patch` → writes via `VaultWriter`, patch moves to applied/
9. Call `brain_undo_last` → reverts the apply
10. Call `brain_propose_note` → stages a new-note patch
11. Call `brain_reject_patch` → moves to rejected/
12. Call `brain_cost_report` → returns a total > 0 after the ingest call
13. Attempt `brain_read_note` with `personal/notes/secret.md` from a `["research"]`-scoped call → refuses with ScopeError
14. Call `brain mcp selftest` from the CLI → spawns a REAL subprocess, sends `tools/list`, verifies the 17 tools come back, exits 0

Prints `PLAN 04 DEMO OK` on exit 0.

**Owning subagents:**
- `brain-mcp-engineer` — `brain_mcp` package, tool registration, `brain_core.integrations.claude_desktop`, `brain mcp` CLI
- `brain-core-engineer` — any new primitives needed in `brain_core` (cost report, list_recent, lint stub)
- `brain-test-engineer` — cross-platform sweep + demo script

**Pre-flight** (main loop, before Task 1):
- Confirm `plan-03-chat` tag exists and `origin/main` is at the close commit
- Confirm `ANTHROPIC_API_KEY` status (optional — demo is FakeLLM, only needed for Plan 04 Task 21 cassettes)
- Decide on D1–D12 below

---

## Scope — in and out

**In scope for Plan 04:**
- `brain_mcp` new workspace package: stdio server, tool registry, resource registry, in-memory test transport
- **17 tools** per spec §7:
  - Read (6): `brain_list_domains`, `brain_get_index`, `brain_read_note`, `brain_search`, `brain_recent`, `brain_get_brain_md`
  - Ingest (3): `brain_ingest`, `brain_classify`, `brain_bulk_import`
  - Writes (5): `brain_propose_note`, `brain_list_pending_patches`, `brain_apply_patch`, `brain_reject_patch`, `brain_undo_last`
  - Maintenance (3): `brain_cost_report`, `brain_config_get`, `brain_config_set` (D4 defers `brain_lint` to a stub)
- **3 resources**: `brain://BRAIN.md`, `brain://<domain>/index.md`, `brain://config/public`
- Security per spec §7: path scope-guard, `personal` domain explicit-only, secrets never returned, patch size/count caps (delegated to existing `VaultWriter`), per-session rate limits on patches/min + tokens/min
- `brain_core.integrations.claude_desktop` module: OS-aware config path detection (Mac + Windows + Linux stub), timestamped backup, safe JSON merge, verification, clean uninstall
- `brain_cli.commands.mcp` sub-app: `brain mcp install|uninstall|selftest|status`
- VCR contract tests for the MCP tool surface (deferred cassettes — same D7a pattern as Plan 02/03)
- Cross-platform sweep
- Demo script exercising every tool end-to-end

**Explicitly out of scope** (deferred):
- **`brain_lint` real implementation** — no `brain_core.lint` module exists. Plan 04 ships a stub returning `"lint not yet implemented (Plan 09)"`. The tool is registered so MCP tooling discovers it; real linting rules land in Plan 09.
- **Web UI settings "Integrations" page** (spec §7) — that's Plan 07 (frontend)
- **Setup wizard "Connect to Claude Desktop" step** — Plan 08 (installer)
- **Cursor / Zed MCP client snippets** — can be generated later from the Claude Desktop config primitive; not a Plan 04 blocker
- **Real Anthropic API cassettes for `brain_ingest`** — Plan 02 already has VCR cassettes for summarize/integrate/classify; Plan 04's ingest tool just routes through them. New MCP-specific cassettes deferred per D9 (same pattern as Plan 02/03's deferred cassettes).
- **Rate limiter persistence across restarts** — per-session in-memory only in Plan 04. Persistent state is a Plan 09 concern if ever.
- **`brain_undo_last` fancy UX** — just calls `UndoLog.revert(last_undo_id)`. No cascading undo, no "undo the undo", no time window. Plan 07 can add richer UX.

---

## Decisions needed (block Task 1)

Twelve forks. Recommendations marked **(rec)**.

### D1 — MCP SDK version and transport

- **(rec) D1a — Use official `mcp>=1.0` Python SDK, stdio transport only.** Per spec §7. In-memory transport for tests (MCP SDK provides `mcp.shared.memory.create_connected_server_and_client_session` or equivalent — check SDK docs). Real clients connect via stdio.
- **D1b — Use `mcp-sdk-python` or any alternative.** The spec is explicit about the official SDK; no reason to deviate.

**Recommendation: D1a.** No genuine fork.

### D2 — Test transport — in-memory vs subprocess

- **(rec) D2a — Unit tests use the MCP SDK's in-memory test transport** (ClientSession ↔ ServerSession directly wired without stdio). Fast, deterministic, no subprocess overhead. Every per-tool test follows this pattern. The subprocess path (real stdio) is exercised ONLY by `brain mcp selftest` and the demo script's final gate.
- **D2b — All tests go through real subprocess stdio.** More realistic but slower (~50ms per test), harder to debug (child process crashes produce opaque errors), and the SDK's serialization is the same on both paths so coverage is equivalent.
- **D2c — Mix**: unit tests in-memory, integration tests subprocess. This is what we'll end up with anyway (D2a is strictly the unit layer).

**Recommendation: D2a** for per-tool unit tests + D2c-style integration in the `brain mcp selftest` CLI command and demo script. Cleanest layering.

### D3 — `brain_mcp` package structure

- **(rec) D3a — One file per tool under `brain_mcp/tools/*.py` mirroring `brain_cli/commands/`**. Each tool module exports a `register(server)` function that the MCP server calls at startup. Tests live in `brain_mcp/tests/test_tool_<name>.py`.
- **D3b — One big `tools.py` with all 17 tools.** Faster to grep, but ~800 LoC in a single file is where Plan 03 explicitly avoided landing.
- **D3c — Tools as pydantic-validated handlers registered via decorators.** Elegant but introduces a custom decorator framework that the MCP SDK already provides.

**Recommendation: D3a.** Matches `brain_cli.commands.*` convention and Plan 03's `chat.tools.*` convention. One file per tool, ~60-100 LoC each.

### D4 — `brain_lint` — stub or build it?

- **(rec) D4a — Stub.** `brain_lint` tool is registered but returns `{"status": "not_implemented", "message": "Plan 09 will land the real lint engine"}`. Downstream clients see the tool but get a graceful "not yet" response. Cost: ~10 LoC + one test.
- **D4b — Build a minimal lint in Plan 04.** Scope-heavy — need to design lint rules (broken wikilinks, missing frontmatter, orphan notes, dead index entries). That's its own plan.
- **D4c — Drop the tool entirely.** Client tooling that advertises a fixed 17-tool surface would break on later addition. Lose discoverability.

**Recommendation: D4a.** Keep the surface stable, defer the engine.

### D5 — `brain_core.cost` report API

`CostLedger` has `total_for_day`, `total_by_domain`, `total_for_month` but no single "report" function. `brain_cost_report` needs to return:
```json
{"today_usd": 0.12, "month_usd": 3.45, "by_domain": {"research": 0.08, "work": 0.04}}
```

- **(rec) D5a — Add a thin `CostLedger.summary(today, month)` method to `brain_core.cost.ledger`** that returns a typed `CostSummary(today_usd, month_usd, by_domain)`. Plan 04 modifies the ledger additively; existing methods unchanged. The MCP tool calls `.summary(today=date.today(), month=(year, month))` and dumps the result.
- **D5b — `brain_mcp_cost_report` composes the calls in-place**, no new ledger method. Keeps `brain_core.cost` untouched but duplicates the date computation if any other caller wants the same shape.
- **D5c — Hold for Plan 04 and defer to Plan 07 frontend.** The MCP tool returns just `today_usd` for now.

**Recommendation: D5a.** Additive change, one method, matches the additive `rename_file` pattern from Plan 03.

### D6 — `brain_recent` — where does "recent" come from?

Spec says `brain_recent` returns recently modified notes. Options:

- **(rec) D6a — Walk `vault_root/<domain>/` with `rglob("*.md")`**, sort by `mtime_ns`, return the top N. Simple, stateless, cross-platform.
- **D6b — Maintain a recency index in `state.sqlite`** updated by `VaultWriter.apply`. Faster but requires a new migration + hook. Overkill for Plan 04.
- **D6c — Parse `<domain>/log.md`** (already maintained by `VaultWriter` per Plan 01). Good semantics (only tracks real vault changes, not filesystem-level touches) but slower.

**Recommendation: D6a.** Filesystem walk is fast on Plan 03-scale vaults (<1000 notes) and doesn't introduce new state.

### D7 — Rate limiting shape

Spec §7 says "per-session rate limit on patches/min and tokens/min". Options:

- **(rec) D7a — Token bucket in-memory on the `brain_mcp` server instance.** Two buckets: `patches_per_minute` (default 20), `tokens_per_minute` (default 100_000). Each tool call checks the relevant bucket before proceeding; over-limit returns an MCP error with a retry-after hint. State lives in `server._rate_limits`; lost on server restart (acceptable per spec intent).
- **D7b — Persistent rate limits in `state.sqlite`**. Overkill for per-session bounds.
- **D7c — Delegate to Plan 02's `BudgetEnforcer`**. That's dollar-based, not rate-based; different axis.

**Recommendation: D7a.** Plain dict + `time.monotonic()` math, no deps.

### D8 — `brain_ingest` tool — sync or async?

The MCP SDK's tool handlers are async. `IngestPipeline.run()` is async too (Plan 02). Good fit.

- **(rec) D8a — Tool handler is `async def`, awaits `pipeline.run(source=..., llm=..., ...)`, returns the resulting `PatchSet` as JSON.** When `autonomous=False` (default), the patch is staged via `PendingPatchStore` and the tool returns `{"patch_id": ..., "status": "pending"}`. When `autonomous=True`, the patch is applied via `VaultWriter.apply` in the same call and the tool returns `{"status": "applied", "undo_id": ...}`.
- **D8b — Split into `brain_ingest_dry_run` + `brain_ingest_apply`** — two tools for two flows. Discoverability cost (the LLM sees two tools with overlapping semantics).

**Recommendation: D8a.** The `autonomous` flag is in the spec; follow it.

### D9 — VCR contract tests for MCP tools

- **(rec) D9a — Same pattern as Plan 02/03 — land the infrastructure + skipped test skeletons in Task 21. Real cassettes recorded only when an `ANTHROPIC_API_KEY` is available. Not a merge gate.** Reuse the existing `conftest.py` from `brain_core/tests/prompts/`.
- **D9b — No VCR for MCP.** The ingest tool is the only MCP surface that hits the real API, and Plan 02 already has cassettes for summarize/integrate/classify. MCP-level cassettes would duplicate.
- **D9c — Require cassettes as a merge gate.** Blocks on API key availability.

**Recommendation: D9a.** Follows Plan 02/03 convention.

### D10 — Claude Desktop config path resolution

Spec says OS-aware detection. Known paths:
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%/Claude/claude_desktop_config.json` (i.e. `C:\Users\<u>\AppData\Roaming\Claude\...`)
- **Linux:** `~/.config/Claude/claude_desktop_config.json` (Claude Desktop is Mac/Windows only officially, but the path is standard XDG)

- **(rec) D10a — Plain `platform.system()` switch** with a `detect_config_path() -> Path` helper that returns the right path or raises `UnsupportedPlatformError` on unknown platforms. Environment override via `BRAIN_CLAUDE_DESKTOP_CONFIG_PATH` for tests.
- **D10b — Use `platformdirs.user_config_dir("Claude")`.** New dep; subtly different paths on some platforms; not how Claude Desktop actually stores its config.

**Recommendation: D10a.** Hardcode the paths the actual app uses; override via env var for tests.

### D11 — `mcpServers` config merge semantics

The Claude Desktop config file has a top-level `mcpServers` key. Install must merge, not overwrite.

- **(rec) D11a — Read JSON, deep-update `mcpServers.brain` with our entry (`command`, `args`, `env`), write back with `timestamped backup first`. If `brain` already exists, overwrite that sub-key only (idempotent install). Preserve all other keys in the config.**
- **D11b — Ship a regenerate-only flow.** User runs `brain mcp install` which prints the JSON snippet to copy-paste. Safer (no file writes) but breaks the "auto-install" spec requirement.

**Recommendation: D11a.** Backup + merge is standard. Idempotent install.

### D12 — `brain mcp selftest` — what does it verify?

- **(rec) D12a — Three checks:** (1) Claude Desktop config file exists at the detected path and has a `mcpServers.brain` entry, (2) spawning the `brain_mcp` server as a subprocess and sending `tools/list` returns the 17-tool list within 5 seconds, (3) the registered command path in the config actually resolves to a valid executable. Prints pass/fail per check.
- **D12b — Just check the config file.** Cheap but doesn't catch broken executables.
- **D12c — Full round-trip through Claude Desktop.** Can't — Claude Desktop is GUI-only.

**Recommendation: D12a.** Three checks, ~30 LoC of orchestration.

---

## File structure produced by this plan

```
packages/brain_mcp/                          # NEW workspace package
├── pyproject.toml
├── src/brain_mcp/
│   ├── __init__.py
│   ├── __main__.py                          # python -m brain_mcp → stdio server
│   ├── server.py                            # MCPServer class + startup
│   ├── rate_limit.py                        # token-bucket rate limiter
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                          # shared tool context + helpers
│   │   ├── list_domains.py
│   │   ├── get_index.py
│   │   ├── read_note.py
│   │   ├── search.py
│   │   ├── recent.py
│   │   ├── get_brain_md.py
│   │   ├── ingest.py
│   │   ├── classify.py
│   │   ├── bulk_import.py
│   │   ├── propose_note.py
│   │   ├── list_pending_patches.py
│   │   ├── apply_patch.py
│   │   ├── reject_patch.py
│   │   ├── undo_last.py
│   │   ├── lint.py                          # D4a stub
│   │   ├── cost_report.py
│   │   ├── config_get.py
│   │   └── config_set.py
│   └── resources/
│       ├── __init__.py
│       ├── brain_md.py                      # brain://BRAIN.md
│       ├── domain_index.py                  # brain://<domain>/index.md
│       └── config_public.py                 # brain://config/public
└── tests/
    ├── conftest.py                          # in-memory MCP client fixture
    ├── test_server_smoke.py                 # tools/list assertion
    ├── test_rate_limit.py
    ├── test_tool_list_domains.py
    ├── test_tool_get_index.py
    ├── test_tool_read_note.py
    ├── test_tool_search.py
    ├── test_tool_recent.py
    ├── test_tool_get_brain_md.py
    ├── test_tool_ingest.py
    ├── test_tool_classify.py
    ├── test_tool_bulk_import.py
    ├── test_tool_propose_note.py
    ├── test_tool_list_pending_patches.py
    ├── test_tool_apply_patch.py
    ├── test_tool_reject_patch.py
    ├── test_tool_undo_last.py
    ├── test_tool_lint.py
    ├── test_tool_cost_report.py
    ├── test_tool_config_get_set.py
    ├── test_resource_brain_md.py
    ├── test_resource_domain_index.py
    └── test_resource_config_public.py

packages/brain_core/src/brain_core/
├── integrations/                            # NEW module
│   ├── __init__.py
│   └── claude_desktop.py                    # config detect + backup + merge + verify + uninstall
└── cost/
    └── ledger.py                            # MODIFIED: add CostLedger.summary()

packages/brain_cli/src/brain_cli/commands/
└── mcp.py                                   # NEW: brain mcp install|uninstall|selftest|status

scripts/
└── demo-plan-04.py                          # 14-gate demo script

pyproject.toml                               # MODIFIED: add brain_mcp to workspace deps
```

---

## Per-task self-review checklist

Same 12-point discipline as Plan 02/03. Repeated here for convenience.

1. `export PATH="$HOME/.local/bin:$PATH"`
2. New submodule? → `uv sync --reinstall-package brain_mcp` (or `brain_core` / `brain_cli` as appropriate)
3. `uv run pytest packages/brain_core packages/brain_cli packages/brain_mcp -q` — full suite green
4. `cd packages/brain_mcp && uv run mypy src tests && cd ../..` — strict clean **(run from the package dir — Tasks 8/14/16/20 of Plan 03 all tripped running mypy from the repo root)**
5. Same from `packages/brain_core` and `packages/brain_cli`
6. `uv run ruff check . && uv run ruff format --check .` — clean
7. `find .venv -name "* [0-9].py"` — empty
8. No direct Anthropic SDK imports outside `brain_core/llm/providers/anthropic.py`
9. No vault-write paths added outside `VaultWriter`
10. No `scope_guard` bypasses
11. `git status` clean after commit
12. Commit message matches the task's convention

---

## Task outline (details intentionally unfilled pending section review)

**25 tasks in 8 groups, 7 checkpoints.** Mirrors Plan 03's shape.

### Group 1 — Foundation
- [ ] **Task 1 — `brain_mcp` workspace package skeleton** (pyproject, empty Typer-less `__main__`, `server.py` skeleton, in-memory test transport fixture)
- [ ] **Task 2 — `RateLimiter` + tests** (token bucket, patches/min, tokens/min)
- [ ] **Task 3 — `brain_mcp.tools.base`** (shared `ToolContext`, JSON schema helpers, scope-guard wrapper)

### Group 2 — Read tools (6 tasks)
- [ ] **Task 4 — `brain_list_domains`**
- [ ] **Task 5 — `brain_get_index`**
- [ ] **Task 6 — `brain_read_note`**
- [ ] **Task 7 — `brain_search`** (wraps `BM25VaultIndex`; shares the Plan 03 cache)
- [ ] **Task 8 — `brain_recent`** (D6a filesystem walk)
- [ ] **Task 9 — `brain_get_brain_md`**

### Group 3 — Resources
- [ ] **Task 10 — 3 MCP resources** (`brain://BRAIN.md`, `brain://<domain>/index.md`, `brain://config/public`) in one task, ~30 LoC + 3 tests

### Group 4 — Ingest tools (3 tasks)
- [ ] **Task 11 — `brain_ingest`** (D8a — async, respects `autonomous` flag, returns staged or applied status)
- [ ] **Task 12 — `brain_classify`**
- [ ] **Task 13 — `brain_bulk_import`** (`dry_run=True` default)

### Group 5 — Write/patch tools (5 tasks)
- [ ] **Task 14 — `brain_propose_note`** (wraps Plan 03's `PendingPatchStore.put` + `PatchSet(new_files=[NewFile(...)])`)
- [ ] **Task 15 — `brain_list_pending_patches`**
- [ ] **Task 16 — `brain_apply_patch`**
- [ ] **Task 17 — `brain_reject_patch`**
- [ ] **Task 18 — `brain_undo_last`** (wraps `UndoLog.revert(last_undo_id)`)

### Group 6 — Maintenance tools + `CostLedger.summary`
- [ ] **Task 19 — `CostLedger.summary` + `brain_cost_report` + `brain_lint` stub + `brain_config_get` + `brain_config_set`** (one task — all four are small and share the maintenance-tool test file)

### Group 7 — Claude Desktop integration + `brain mcp` CLI
- [ ] **Task 20 — `brain_core.integrations.claude_desktop`** (detect, backup, merge, verify, uninstall) + tests against temp config files
- [ ] **Task 21 — `brain_cli.commands.mcp`** (install / uninstall / selftest / status subcommands, wires to the integration module)

### Group 8 — Contract + cross-platform + demo + close
- [ ] **Task 22 — VCR contract test infrastructure** for the 3 tools that route through the real LLM (`brain_ingest`, `brain_classify`, `brain_bulk_import`). Cassettes deferred per D9a.
- [ ] **Task 23 — Cross-platform sweep** (walk `brain_mcp` + `integrations.claude_desktop`, verify pathlib + WAL + os.replace + Windows line endings + Claude Desktop config paths)
- [ ] **Task 24 — `scripts/demo-plan-04.py`** (14-gate demo)
- [ ] **Task 25 — Hardening sweep + coverage + tag `plan-04-mcp`**

*(Hardening sweep + close combined into one task here because Plan 04 is smaller-surface than Plan 03 — the tool handlers are thin wrappers and most of the real work is in brain_core primitives that Plans 01–03 already landed.)*

---

## Module-boundary checkpoints

Seven review pause points, matching Plan 03's rhythm:

1. **After Task 3** — foundation (package, rate limiter, base) frozen before tool rollout
2. **After Task 9** — read tool surface complete (6 tools + 3 resources, Task 10 folded into checkpoint)
3. **After Task 13** — ingest tool surface complete
4. **After Task 18** — write/patch tool surface complete
5. **After Task 19** — maintenance tool surface complete (entire tool surface done — time to gate check)
6. **After Task 21** — Claude Desktop integration live; `brain mcp install` works
7. **After Task 25** — plan close, tag, demo receipt

---

## Detailed per-task steps

*Intentionally unfilled. After the outline, decisions, and file structure are approved, I will fill in per-task bite-sized steps (test-first, exact code, exact commands, expected output) group-by-group following Plan 03's rhythm.*

### Group 1 — Foundation (Tasks 1–3)

*To be filled in after decision + outline review.*

### Group 2 — Read tools (Tasks 4–9)

*To be filled in.*

### Group 3 — Resources (Task 10)

*To be filled in.*

### Group 4 — Ingest tools (Tasks 11–13)

*To be filled in.*

### Group 5 — Write/patch tools (Tasks 14–18)

*To be filled in.*

### Group 6 — Maintenance tools (Task 19)

*To be filled in.*

### Group 7 — Claude Desktop integration (Tasks 20–21)

*To be filled in.*

### Group 8 — Contract + cross-platform + demo + close (Tasks 22–25)

*To be filled in.*
