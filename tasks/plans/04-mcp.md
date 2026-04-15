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

**Checkpoint after Task 3:** main-loop reviews package skeleton, rate limiter contract, and `ToolContext` shape before tool rollout. If the ToolContext gets fields wrong, every Group-2/3/4/5 tool will need to be touched — cheaper to catch here.

---

### Task 1 — `brain_mcp` workspace package skeleton

**Owning subagent:** brain-mcp-engineer

**Files:**
- Modify: root `pyproject.toml` — add `brain_mcp` dep + `[tool.uv.sources]` entry
- Create: `packages/brain_mcp/pyproject.toml`
- Create: `packages/brain_mcp/src/brain_mcp/__init__.py`
- Create: `packages/brain_mcp/src/brain_mcp/__main__.py`
- Create: `packages/brain_mcp/src/brain_mcp/server.py` (skeleton only — no tools yet)
- Create: `packages/brain_mcp/src/brain_mcp/py.typed` (empty PEP 561 marker)
- Create: `packages/brain_mcp/src/brain_mcp/tools/__init__.py` (empty, populated in Tasks 3+)
- Create: `packages/brain_mcp/src/brain_mcp/resources/__init__.py` (empty, populated in Task 10)
- Create: `packages/brain_mcp/tests/conftest.py` — in-memory MCP client fixture
- Create: `packages/brain_mcp/tests/test_server_smoke.py` — initialize + tools/list smoke test

**Context for the implementer:**

This is a NEW workspace package. Lessons from Plan 03 Task 19 (`brain_cli` skeleton):
- `[project.scripts]` MUST live in `packages/brain_mcp/pyproject.toml`, NOT the root — root has `[tool.uv] package = false` which silently drops scripts.
- `py.typed` marker needed from day one (Plan 03 Task 20 lesson).
- Root `pyproject.toml` needs both the `brain_mcp` dep in `[project].dependencies` AND the `brain_mcp = { workspace = true, editable = false }` entry in `[tool.uv.sources]`.
- Workspace is glob-discovered (`members = ["packages/*"]`), so `brain_mcp` is auto-picked up.

New runtime dep: `mcp>=1.0`. This is the official Python MCP SDK. Ships type stubs (PEP 561) so no mypy override needed.

For the `__main__.py` entry point, the plan is `python -m brain_mcp` spawns the stdio server. In Plan 04 Task 1 we just land the skeleton; actual stdio wiring lands in Task 21 when the CLI `brain mcp install` gets invoked. For now the `__main__` is a stub that prints a version string and exits.

**Server skeleton (Task 1):** `server.py` creates an empty `mcp.server.lowlevel.Server("brain")` instance and a `create_server() -> Server` factory. No tools registered yet. The `list_tools` and `call_tool` handlers return empty list / raise `ValueError("unknown tool")` respectively. Tasks 3+ will populate them.

### Step 1 — Create `packages/brain_mcp/pyproject.toml`

```toml
[project]
name = "brain_mcp"
version = "0.0.1"
description = "brain MCP server — exposes brain_core primitives over the Model Context Protocol"
requires-python = ">=3.12"
dependencies = [
    "brain_core",
    "mcp>=1.0",
]

[project.scripts]
brain-mcp = "brain_mcp.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/brain_mcp"]

[tool.uv.sources]
brain_core = { workspace = true }
```

### Step 2 — Update root `pyproject.toml`

Add to `[project].dependencies`:
```toml
dependencies = [
    "brain_core",
    "brain_cli",
    "brain_mcp",
]
```

Add to `[tool.uv.sources]`:
```toml
brain_mcp = { workspace = true, editable = false }
```

### Step 3 — Create `packages/brain_mcp/src/brain_mcp/__init__.py`

```python
"""brain_mcp — Model Context Protocol server wrapping brain_core primitives."""

__version__ = "0.0.1"
```

### Step 4 — Create `packages/brain_mcp/src/brain_mcp/__main__.py`

```python
"""Entry point: `python -m brain_mcp` runs the stdio MCP server.

Task 1 lands a stub that prints the version and exits. Task 21 wires the
real stdio transport via `mcp.server.stdio.stdio_server`.
"""

from __future__ import annotations

import sys

from brain_mcp import __version__


def main() -> int:
    print(f"brain_mcp {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Step 5 — Create `packages/brain_mcp/src/brain_mcp/py.typed`

Empty file. PEP 561 marker.

### Step 6 — Create `packages/brain_mcp/src/brain_mcp/server.py` (skeleton)

```python
"""brain MCP server factory.

Task 1 lands the skeleton — empty tool list, rejecting call_tool handler.
Tasks 3+ populate via brain_mcp.tools.* modules registered at factory time.
"""

from __future__ import annotations

from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server


def create_server() -> Server:
    """Build a fresh `mcp.server.lowlevel.Server` instance with handlers registered.

    Does NOT start the stdio transport. Callers (brain_mcp.__main__, test
    harnesses) are responsible for running the server against their chosen
    transport.
    """
    server: Server = Server("brain")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return []

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        raise ValueError(f"unknown tool: {name}")

    return server
```

### Step 7 — Create `packages/brain_mcp/src/brain_mcp/tools/__init__.py` and `resources/__init__.py`

Both empty files. Populated in later tasks.

### Step 8 — Create `packages/brain_mcp/tests/conftest.py`

```python
"""Shared fixtures for brain_mcp tests.

The `mcp_session` fixture spins up an in-memory MCP server + client pair using
`mcp.shared.memory.create_client_server_memory_streams`. Each test gets a
fresh ClientSession already initialized against a fresh server from
`create_server()`. No stdio, no subprocess, no network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from brain_mcp.server import create_server


@pytest.fixture
async def mcp_session() -> AsyncIterator[ClientSession]:
    server = create_server()
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                lambda: server.run(
                    server_streams[0],
                    server_streams[1],
                    server.create_initialization_options(),
                )
            )
            async with ClientSession(client_streams[0], client_streams[1]) as session:
                await session.initialize()
                yield session
            tg.cancel_scope.cancel()
```

**Note:** the exact signature of `create_client_server_memory_streams()` and whether the server streams need to be unpacked `(read, write)` vs passed as a tuple to `server.run()` depends on the real SDK shape. Verify against the installed `mcp` package before finalizing — adjust the fixture to match. The `anyio.create_task_group().cancel_scope.cancel()` pattern is the SDK's documented clean-shutdown path.

### Step 9 — Create `packages/brain_mcp/tests/test_server_smoke.py`

```python
"""Smoke tests for the brain MCP server — empty-tool baseline."""

from __future__ import annotations

from mcp.client.session import ClientSession


async def test_initialize_succeeds(mcp_session: ClientSession) -> None:
    """Session initialization via the in-memory fixture should complete cleanly."""
    # If the fixture yielded, initialize() already succeeded.
    result = await mcp_session.list_tools()
    # Task 1 baseline: zero tools registered.
    assert result.tools == []


async def test_unknown_tool_raises(mcp_session: ClientSession) -> None:
    """Calling a non-existent tool raises a protocol error."""
    import pytest

    with pytest.raises(Exception):  # noqa: BLE001 — MCP raises its own error type
        await mcp_session.call_tool("nonexistent", {})
```

### Step 10 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_mcp -v
```
Expect: **2 passed** (initialize smoke + unknown-tool smoke).

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_mcp && uv run mypy src tests
```
Expect: `Success: no issues found in N source files`.

Full suite + 12-point self-review, then:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && git add packages/brain_mcp/ pyproject.toml uv.lock && git commit -m "feat(mcp): plan 04 task 1 — brain_mcp workspace package skeleton"
```

---

### Task 2 — `brain_mcp.rate_limit.RateLimiter`

**Owning subagent:** brain-mcp-engineer

**Files:**
- Create: `packages/brain_mcp/src/brain_mcp/rate_limit.py`
- Create: `packages/brain_mcp/tests/test_rate_limit.py`

**Context for the implementer:**

Per D7a, rate limiting is an in-memory token bucket on the server instance. Two independent buckets: `patches_per_minute` (default 20), `tokens_per_minute` (default 100_000). Each bucket has a capacity and a refill rate. `RateLimiter.check("patches", cost=1)` returns True if `cost` tokens are available (and deducts them); False if not.

No dependencies beyond stdlib. State lives on the `RateLimiter` instance (not persisted).

Token bucket math:
- `capacity` tokens maximum
- `refill_rate` tokens per second (e.g., 20/60 = 0.333/s for patches)
- On each `check(bucket, cost)`:
  - `now = time.monotonic()`
  - `elapsed = now - self._last_refill[bucket]`
  - `self._tokens[bucket] = min(capacity, self._tokens[bucket] + elapsed * refill_rate)`
  - `self._last_refill[bucket] = now`
  - if `self._tokens[bucket] >= cost`: `self._tokens[bucket] -= cost`; return True
  - else: return False

### Step 1 — Write the failing tests

`packages/brain_mcp/tests/test_rate_limit.py`:
```python
"""Tests for brain_mcp.rate_limit.RateLimiter."""

from __future__ import annotations

import time

import pytest

from brain_mcp.rate_limit import RateLimiter, RateLimitConfig


def test_fresh_limiter_allows_up_to_capacity() -> None:
    cfg = RateLimitConfig(patches_per_minute=5, tokens_per_minute=100)
    limiter = RateLimiter(cfg)
    # First 5 patches should all be allowed.
    for _ in range(5):
        assert limiter.check("patches", cost=1) is True
    # 6th should be refused.
    assert limiter.check("patches", cost=1) is False


def test_tokens_bucket_independent_of_patches() -> None:
    cfg = RateLimitConfig(patches_per_minute=1, tokens_per_minute=100)
    limiter = RateLimiter(cfg)
    assert limiter.check("patches", cost=1) is True
    # Patches bucket now exhausted, but tokens bucket is fresh.
    assert limiter.check("tokens", cost=50) is True
    assert limiter.check("tokens", cost=50) is True
    assert limiter.check("tokens", cost=1) is False


def test_unknown_bucket_raises() -> None:
    limiter = RateLimiter(RateLimitConfig())
    with pytest.raises(KeyError, match="unknown"):
        limiter.check("nonexistent", cost=1)


def test_bucket_refills_over_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock time.monotonic to advance 30s and confirm the bucket has refilled."""
    fake_time = 1000.0

    def _now() -> float:
        return fake_time

    monkeypatch.setattr("brain_mcp.rate_limit.time.monotonic", _now)
    cfg = RateLimitConfig(patches_per_minute=60)  # 1/s refill
    limiter = RateLimiter(cfg)
    # Drain the bucket.
    for _ in range(60):
        assert limiter.check("patches", cost=1) is True
    assert limiter.check("patches", cost=1) is False
    # Advance 30 seconds — should refill 30 tokens.
    fake_time += 30.0
    for _ in range(30):
        assert limiter.check("patches", cost=1) is True
    assert limiter.check("patches", cost=1) is False


def test_cost_greater_than_capacity_refused() -> None:
    cfg = RateLimitConfig(tokens_per_minute=100)
    limiter = RateLimiter(cfg)
    assert limiter.check("tokens", cost=101) is False
    # Partial spend should still work.
    assert limiter.check("tokens", cost=50) is True


def test_defaults_match_spec() -> None:
    cfg = RateLimitConfig()
    assert cfg.patches_per_minute == 20
    assert cfg.tokens_per_minute == 100_000
```

Run: `cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_mcp/tests/test_rate_limit.py -v`
Expected: FAIL with `ModuleNotFoundError: brain_mcp.rate_limit`.

### Step 2 — Implement `rate_limit.py`

```python
"""Token-bucket rate limiter for brain_mcp.

Per spec §7: per-session rate limit on patches/min and tokens/min. This is an
in-memory bucket on the server instance — state is lost on restart, which is
acceptable for a per-session bound.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitConfig:
    patches_per_minute: int = 20
    tokens_per_minute: int = 100_000


class RateLimiter:
    """Two-bucket token-bucket limiter. `check(bucket, cost)` returns True if
    the cost was consumed, False if refused."""

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        now = time.monotonic()
        # (capacity, refill_rate_per_second, current_tokens, last_refill_time)
        self._buckets: dict[str, list[float]] = {
            "patches": [
                float(config.patches_per_minute),
                config.patches_per_minute / 60.0,
                float(config.patches_per_minute),
                now,
            ],
            "tokens": [
                float(config.tokens_per_minute),
                config.tokens_per_minute / 60.0,
                float(config.tokens_per_minute),
                now,
            ],
        }

    def check(self, bucket: str, *, cost: int) -> bool:
        if bucket not in self._buckets:
            raise KeyError(f"unknown rate-limit bucket: {bucket!r}")
        b = self._buckets[bucket]
        capacity, refill_rate, current, last = b
        now = time.monotonic()
        elapsed = now - last
        refilled = min(capacity, current + elapsed * refill_rate)
        if refilled >= cost:
            b[2] = refilled - cost
            b[3] = now
            return True
        b[2] = refilled
        b[3] = now
        return False
```

### Step 3 — Run tests + self-review + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_mcp && uv run pytest packages/brain_mcp/tests/test_rate_limit.py -v
```
Expected: **6 passed**.

Full suite + mypy + ruff + ghost check, then:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && git add packages/brain_mcp/src/brain_mcp/rate_limit.py packages/brain_mcp/tests/test_rate_limit.py && git commit -m "feat(mcp): plan 04 task 2 — RateLimiter token bucket (patches + tokens per minute)"
```

---

### Task 3 — `brain_mcp.tools.base` — `ToolContext` + JSON schema helpers

**Owning subagent:** brain-mcp-engineer

**Files:**
- Create: `packages/brain_mcp/src/brain_mcp/tools/base.py`
- Create: `packages/brain_mcp/tests/test_tools_base.py`

**Context for the implementer:**

`ToolContext` is the frozen record passed to every MCP tool handler. It holds everything a tool might need: vault root, allowed domains (from the request, NOT global — different calls have different scopes), retrieval index, pending store, state DB, vault writer, LLM provider, cost ledger, rate limiter, undo log. Every MCP tool handler receives one.

`ToolContext.retrieval`, `.llm`, and other heavy types are typed `Any` to avoid import cycles — the concrete tools narrow at use site, just like Plan 03 Tasks 5/17 did.

Also lands two helpers:
- `scope_guard_path(rel_path: str, ctx: ToolContext) -> Path` — converts an MCP tool's `path` argument to a vault-absolute path, scope-guarded. Raises `ScopeError` on out-of-scope. Centralizes the scope check so every tool has the same behavior.
- `text_result(text: str, *, data: dict[str, Any] | None = None) -> list[types.TextContent]` — wraps a tool's output into the MCP SDK's `TextContent` list shape. If `data` is provided, serializes it as JSON in a second TextContent.

### Step 1 — Write the failing tests

`packages/brain_mcp/tests/test_tools_base.py`:
```python
"""Tests for brain_mcp.tools.base — ToolContext + helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain_mcp.tools.base import (
    ToolContext,
    scope_guard_path,
    text_result,
)
from brain_core.vault.paths import ScopeError


def test_tool_context_frozen(tmp_path: Path) -> None:
    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    # Frozen dataclass: attribute assignment fails at runtime.
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError or AttributeError
        ctx.allowed_domains = ("personal",)  # type: ignore[misc]


def test_scope_guard_path_happy(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "foo.md").write_text("x", encoding="utf-8")
    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    resolved = scope_guard_path("research/notes/foo.md", ctx)
    assert resolved == (tmp_path / "research" / "notes" / "foo.md").resolve()


def test_scope_guard_path_rejects_out_of_scope(tmp_path: Path) -> None:
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    with pytest.raises(ScopeError):
        scope_guard_path("personal/notes/secret.md", ctx)


def test_scope_guard_path_rejects_absolute(tmp_path: Path) -> None:
    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    with pytest.raises(ValueError, match="vault-relative"):
        scope_guard_path(str(tmp_path / "research" / "foo.md"), ctx)


def test_text_result_plain() -> None:
    out = text_result("hello world")
    assert len(out) == 1
    assert out[0].type == "text"
    assert out[0].text == "hello world"


def test_text_result_with_data() -> None:
    out = text_result("summary", data={"key": "value", "count": 3})
    assert len(out) == 2
    assert out[0].text == "summary"
    assert out[1].type == "text"
    # Second content is JSON-encoded.
    import json
    parsed = json.loads(out[1].text)
    assert parsed == {"key": "value", "count": 3}
```

Run: `cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_mcp/tests/test_tools_base.py -v`
Expected: FAIL with `ModuleNotFoundError: brain_mcp.tools.base`.

### Step 2 — Implement `tools/base.py`

```python
"""ToolContext + shared helpers for brain_mcp tools.

Every concrete tool in brain_mcp.tools.* receives a ToolContext that carries
the primitives it might need. Heavy types (retrieval, llm, writer) are typed
as Any to avoid import cycles — concrete tools narrow at use site.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mcp.types as types

from brain_core.vault.paths import scope_guard


@dataclass(frozen=True)
class ToolContext:
    vault_root: Path
    allowed_domains: tuple[str, ...]
    retrieval: Any          # BM25VaultIndex
    pending_store: Any      # PendingPatchStore
    state_db: Any           # StateDB
    writer: Any             # VaultWriter
    llm: Any                # LLMProvider
    cost_ledger: Any        # CostLedger
    rate_limiter: Any       # RateLimiter
    undo_log: Any           # UndoLog


def scope_guard_path(rel_path: str, ctx: ToolContext) -> Path:
    """Convert a vault-relative string path to an absolute scope-guarded Path.

    Raises:
        ValueError: if `rel_path` is absolute
        ScopeError: if the resolved path falls outside ctx.allowed_domains
    """
    p = Path(rel_path)
    if p.is_absolute():
        raise ValueError(f"path must be vault-relative, not absolute: {rel_path!r}")
    return scope_guard(
        ctx.vault_root / p,
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
    )


def text_result(text: str, *, data: dict[str, Any] | None = None) -> list[types.TextContent]:
    """Wrap a tool's output into the MCP SDK's TextContent list shape.

    If `data` is provided, appends a second TextContent containing the JSON
    encoding. Clients (Claude Desktop) render both.
    """
    out: list[types.TextContent] = [types.TextContent(type="text", text=text)]
    if data is not None:
        out.append(
            types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))
        )
    return out
```

### Step 3 — Run tests + self-review + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_mcp && uv run pytest packages/brain_mcp -v
```
Expected: **2 smoke + 6 rate_limit + 6 base = 14 passed** in brain_mcp; full suite + 1 skipped.

12-point self-review (mypy from `packages/brain_mcp/`, ruff, ghost check), then:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && git add packages/brain_mcp/src/brain_mcp/tools/base.py packages/brain_mcp/tests/test_tools_base.py && git commit -m "feat(mcp): plan 04 task 3 — ToolContext + scope_guard_path + text_result helpers"
```

---

**Checkpoint 1 — pause for main-loop review.**

3 tasks landed. `brain_mcp` package exists, smoke test passes through the in-memory MCP transport, rate limiter works, every tool in Group 2+ has a `ToolContext` shape to rely on. Main loop reviews:
- Is `ToolContext` carrying the right fields?
- Does the in-memory test fixture actually work with the real MCP SDK 1.0+ API? (Task 1 verified this empirically with the smoke test.)
- Is `scope_guard_path`'s centralization useful, or will concrete tools bypass it anyway?
- Any API drift between the task text and the real `mcp` package version installed?

Before Task 4, the next main-loop dispatch should confirm the rate limiter contract is OK — does every MCP tool check `rate_limiter.check("tokens", cost=...)` before making an LLM call, or is it only checked at the ingest tool layer?

---

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
