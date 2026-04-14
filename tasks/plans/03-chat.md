# Plan 03 — Chat (Ask / Brainstorm / Draft) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DRAFT — pending section-by-section review. Task-level steps are intentionally unfilled below the outline until the architecture / scope / decisions sections are approved.**

**Goal:** Ship a working terminal `brain chat` experience with Ask / Brainstorm / Draft modes, streaming tokens, scope-guarded read tools, staged `propose_note` writes, idempotent chat-thread persistence to the vault, and a demo that runs end-to-end against `FakeLLMProvider` (no API key required). All logic lives in `brain_core.chat`; `brain_cli` is introduced in this plan as the first thin wrapper that imports it.

**Architecture:**
Plan 03 adds two packages on top of Plan 01+02:

1. **`brain_core.chat`** — a pure-Python module that owns the conversation loop, mode policy, tool dispatch, context compilation, streaming event shape, thread persistence, and auto-titling. Zero web/MCP/CLI deps. All vault writes go through `VaultWriter`. All LLM calls go through `LLMProvider`. All reads go through `scope_guard`.
2. **`brain_cli`** — a new workspace package: a Typer CLI whose only job (for Plan 03) is `brain chat`, which instantiates `brain_core.chat.ChatSession` and renders streaming events to the terminal. This establishes the wrapper pattern for Plans 04/05 (MCP, API) to copy.

Retrieval is a tool call, not a background index: `search_vault` is BM25 over a lazily-built in-memory index cached in `state.sqlite` (keyed by vault content hash). No vector DB. Context compilation per turn loads `BRAIN.md` + in-scope `index.md` files + explicitly-read notes + user message; oldest-turn trimming kicks in at the configured hard cap.

**Tech stack (new deps):**
- `rank-bm25` — pure-Python BM25 implementation for `search_vault`
- `typer` + `rich` — CLI framework and terminal rendering (streaming deltas, tool-call panels, cost meter)
- `prompt-toolkit` — multi-line input, history, Ctrl-C handling for the REPL
- (existing) `pydantic`, `httpx` via `LLMProvider`, `pytest`, `mypy --strict`, `ruff`

**Demo gate:** `uv run python scripts/demo-plan-03.py` drives a scripted transcript against a seeded temp vault (reusing the Plan 02 demo's five notes) using `FakeLLMProvider` with pre-queued chat responses. The script exercises:

1. **Ask mode** — one turn: "What did the Karpathy tweet say?" → fake LLM emits `search_vault` tool call → real BM25 returns the tweet note → fake LLM streams a cited answer. Asserts: citations refer to real note paths, no `propose_note` tool was offered, cost ledger has rows for the turn.
2. **Brainstorm mode** — two turns: fake LLM proposes a `propose_note` patch → patch is staged (not applied) → assert the patch exists in the pending queue and the vault is unchanged.
3. **Draft mode** — one turn with an "open doc" path: fake LLM emits `edit_open_doc` → patch is staged against the open doc → assert the open doc is unchanged until the patch is applied.
4. **Thread persistence** — after each mode, the chat thread file exists at `chats/<domain>/<slug>.md` with correct frontmatter (mode, scope, model, turns, cost_usd), alternating `## User` / `## Assistant` blocks, and tool-call fenced blocks.
5. **Auto-title** — after turn 2, a cheap LLM call produces a 3–6 word title; assert the file was renamed via `VaultWriter` and the rename is recorded in the undo log.
6. **Idempotency** — re-running the demo against the same temp vault does not duplicate thread files and does not re-charge the cost ledger for already-persisted turns.
7. **Scope guard** — a simulated `read_note` for a `personal/` path in a `research`-scoped session raises `ScopeViolationError` before the LLM sees the content.

Prints `PLAN 03 DEMO OK` on exit 0.

**Owning subagents:**
- `brain-core-engineer` — `brain_core.chat` module (session, tools, retrieval, persistence), `brain_cli` package skeleton
- `brain-prompt-engineer` — Ask / Brainstorm / Draft system prompts, mode policy, auto-title prompt, VCR contract tests
- `brain-test-engineer` — cross-platform test sweep, CLI integration tests, demo script

**Pre-flight** (main loop, before Task 1):
- Confirm `plan-02-ingestion` tag exists.
- Confirm `tasks/lessons.md` is up to date from Plan 02.
- Confirm no uncommitted changes on `main`.
- Decide on the open questions in §"Decisions needed" below.

---

## Scope — in and out

**In scope for Plan 03:**
- `brain_core.chat` module: `ChatSession`, mode policy, tool registry, context compiler, thread persistence, auto-title.
- Six tools: `search_vault`, `read_note`, `list_index`, `list_chats`, `propose_note`, `edit_open_doc`.
- BM25 retrieval with content-hash-keyed cache in `state.sqlite`.
- Mode system prompts in `brain_core/prompts/chat_ask.md`, `chat_brainstorm.md`, `chat_draft.md` + auto-title prompt.
- Pending-patch queue abstraction (`brain_core.chat.pending.PendingPatchStore`) — JSON-on-disk, feeds both `propose_note` and `edit_open_doc`. This is the shared queue that Plans 04/05/07 will render.
- `brain_cli` package: `brain chat [--mode ...] [--domain ...] [--open <path>]`, Rich-rendered streaming, tool-call panels, per-turn cost deltas, Ctrl-C graceful abort, `/mode`, `/scope`, `/file` slash commands.
- Cross-platform: Windows terminal rendering (Rich auto-handles), file locking for `state.sqlite` under both platforms, no POSIX-only code.
- Demo script + 12-point per-task self-review checklist (same discipline as Plan 02).

**Explicitly out of scope** (deferred to later plans):
- Web UI / WebSocket streaming events (Plan 05 API + 06 design + 07 frontend).
- MCP tool surface (Plan 04).
- Patch **approval / rejection / apply** UI — Plan 03 only *stages* patches. A minimal `brain patches list/apply/reject` CLI is provided for demo verification; the approval UX lives in Plan 07.
- File-to-wiki action (spec §6) — needs approval UX, deferred to Plan 07.
- Hybrid BM25 + frontmatter/tag filter: Plan 03 ships BM25 over body + title + tags, with simple domain/tag equality filters. Advanced frontmatter predicates deferred.
- Chat history recall UI — `list_chats` works and is tested, but per-thread branching / forking (spec §8 mockups) is UI-era.
- Multi-model routing (spec §14 "Haiku for classify, Sonnet for chat") — Plan 03 uses a single configured model; routing is a knob for Plan 09.

---

## Decisions needed (block Task 1)

These are genuine forks where I want your input before fleshing task steps. Recommended options are marked **(rec)**.

### D1 — Retrieval index scope and rebuild policy

Options for where/when the BM25 index is built:

- **(rec) D1a — Per-session lazy rebuild, cached in `state.sqlite` keyed by (domain, vault_content_hash).** First `search_vault` call in a new session builds an index for the in-scope domains; subsequent calls reuse. Stale detection: hash each note's `(path, mtime_ns, size)` into a rolling vault hash; if it changes, invalidate. Simple, correct, no background process.
- **D1b — Eager index at `ChatSession.__enter__`.** Pay the build cost up front; avoids first-search latency. Worse UX for large vaults at session start; wasted work if the user never searches.
- **D1c — Persistent incremental index updated during ingest.** Most efficient long-term, but couples Plan 03 to Plan 02's pipeline (new write path). Bigger surface area, more tests, larger plan.

**Tradeoff:** D1a gets us real behavior on small vaults with a clean rebuild story; D1c is the "right" long-term answer but drags a pipeline integration into a chat plan.

### D2 — `state.sqlite` introduction

`state.sqlite` doesn't exist yet. Plan 03 is the first consumer. Options:

- **(rec) D2a — Introduce `brain_core.state.StateDB` in Plan 03 with two tables: `chat_threads` (metadata cache) and `bm25_cache` (serialized index blob + vault hash). Schema versioning via a `schema_version` PRAGMA table; migrations are additive-only for now.** Keeps state cache concerns co-located with chat, where they're first needed.
- **D2b — Punt `state.sqlite` to Plan 05 (API) and keep chat metadata in a JSON sidecar at `chats/.state.json`.** Avoids a new module, but the JSON-vs-SQLite split will bite when the API plan lands.
- **D2c — Land a standalone `brain_core.state` module with **just** the `StateDB` primitive (connect, migrate, exec) in Plan 03, but only the two tables chat needs. Future plans add tables in-place.** Cleaner boundary than D2a.

**Recommendation: D2c** — same outcome as D2a but with a cleaner module boundary the later plans can extend without refactoring.

### D3 — Pending patch queue format

- **(rec) D3a — One JSON file per patch at `.brain/pending/<ulid>.json`, with frontmatter-lite headers (created_at, source_thread, mode, tool, target_path, reason) and the validated `PatchSet` as the body.** Trivially listable, trivially approveable, human-debuggable, no DB. `.brain/` already exists from Plan 01.
- **D3b — Single append-only JSONL log at `.brain/pending.jsonl` with a "tombstone" on reject/apply.** More compact, but iterating requires a scan, and deletion semantics are fiddly.
- **D3c — SQLite table in `state.sqlite`.** Couples to D2 and makes patches harder to inspect by hand.

**Recommendation: D3a** — file-per-patch matches the vault's "Markdown is source of truth" ethos and is dead simple.

### D4 — Chat thread persistence timing

The spec says threads are written to `chats/<domain>/<slug>.md` as the source of truth. Options for **when**:

- **(rec) D4a — Write the thread file after every completed turn, atomically via `VaultWriter`.** Crash-safe, matches vault-as-source-of-truth. Cost: one `VaultWriter.apply()` per turn.
- **D4b — In-memory until session close, then one flush.** Faster, but a crash loses the transcript and the `state.sqlite` metadata drifts from the Markdown.
- **D4c — Debounced every N turns or T seconds.** Complexity not worth it for a local tool.

**Recommendation: D4a.** Aligns with principle #6 ("vault is source of truth"). The cost is trivial (one temp+rename per turn).

### D5 — `edit_open_doc` semantics for the CLI

"Open doc" is a UI concept. For the terminal:

- **(rec) D5a — `--open <path>` flag pins a vault-relative path as the "open doc" for the session. `edit_open_doc` stages a patch against that path; the CLI never writes it directly. Draft mode without `--open` is still allowed but `edit_open_doc` is not in the tool registry.** Maps cleanly to UI mental model without building UI.
- **D5b — Prompt interactively for the open doc on entering Draft mode.** More flow, same outcome.
- **D5c — Disallow Draft mode from the CLI entirely; it's a UI feature.** Simpler plan, but leaves a hole in the demo gate and means Draft's tool policy isn't exercised until Plan 07.

**Recommendation: D5a.**

### D6 — Mode switching mid-thread

Spec §6 says "switching mid-thread is logged as a system message." Confirming:

- **(rec) D6a — A `/mode <name>` slash command switches mode in place, appends a `## System` block to the thread (`mode changed: ask → brainstorm`), and updates frontmatter.** Spec-compliant; the `## System` block is a 3rd section type beyond User/Assistant.
- **D6b — Mode switches force a new thread.** Simpler, but loses shared context.

**Recommendation: D6a.**

### D7 — Fake vs real LLM for contract tests

- **(rec) D7a — `FakeLLMProvider` covers all unit + integration tests (including streaming, tool calls, turn loop). VCR cassettes for the three mode prompts + auto-title prompt are recorded in a Task 20-equivalent, gated on `ANTHROPIC_API_KEY` presence. Cassettes are not a merge gate** (same as Plan 02 Tasks 21–22).
- **D7b — Require real cassettes as a merge gate.** Blocks progress on key availability.

**Recommendation: D7a.**

---

## File structure produced by this plan

```
packages/brain_core/
├── pyproject.toml                    # new deps: rank-bm25
├── src/brain_core/
│   ├── chat/
│   │   ├── __init__.py
│   │   ├── types.py                  # ChatMode, ChatTurn, ChatEvent, ChatSessionConfig
│   │   ├── session.py                # ChatSession — the loop
│   │   ├── modes.py                  # mode policy (tool allowlist, temperature, prompt file)
│   │   ├── context.py                # per-turn context compiler
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # ChatTool Protocol + registry
│   │   │   ├── search_vault.py
│   │   │   ├── read_note.py
│   │   │   ├── list_index.py
│   │   │   ├── list_chats.py
│   │   │   ├── propose_note.py
│   │   │   └── edit_open_doc.py
│   │   ├── retrieval.py              # BM25 index build + search + cache
│   │   ├── persistence.py            # chat-thread Markdown writer/reader (via VaultWriter)
│   │   ├── autotitle.py              # turn-2 auto-title LLM call + rename
│   │   └── pending.py                # PendingPatchStore (.brain/pending/<ulid>.json)
│   ├── state/                        # NEW module (D2c)
│   │   ├── __init__.py
│   │   ├── db.py                     # StateDB connect/migrate/exec
│   │   └── migrations/
│   │       └── 0001_chat_and_bm25.sql
│   └── prompts/
│       ├── chat_ask.md               # NEW
│       ├── chat_brainstorm.md        # NEW
│       ├── chat_draft.md             # NEW
│       └── chat_autotitle.md         # NEW
packages/brain_cli/                   # NEW workspace package
├── pyproject.toml
├── src/brain_cli/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py                        # typer.Typer() root
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── chat.py                   # `brain chat` — the only Plan 03 command
│   │   └── patches.py                # `brain patches list|apply|reject` — minimal demo verification
│   └── rendering/
│       ├── __init__.py
│       └── stream.py                 # Rich renderer for ChatEvent stream
└── tests/
    ├── test_cli_smoke.py
    ├── test_chat_command.py          # uses FakeLLMProvider, asserts rendered output
    └── test_patches_command.py
packages/brain_core/tests/
├── chat/
│   ├── __init__.py
│   ├── conftest.py                   # seeded temp-vault fixture (reuses Plan 02 demo vault)
│   ├── test_types.py
│   ├── test_modes.py
│   ├── test_context.py
│   ├── test_retrieval.py
│   ├── test_tool_search_vault.py
│   ├── test_tool_read_note.py
│   ├── test_tool_list_index.py
│   ├── test_tool_list_chats.py
│   ├── test_tool_propose_note.py
│   ├── test_tool_edit_open_doc.py
│   ├── test_persistence.py
│   ├── test_autotitle.py
│   ├── test_pending.py
│   ├── test_session_ask.py           # full turn, Ask mode, no write tools offered
│   ├── test_session_brainstorm.py    # propose_note path
│   ├── test_session_draft.py         # edit_open_doc path
│   ├── test_session_scope_guard.py   # personal leak attempt raises
│   ├── test_session_mode_switch.py   # /mode + ## System block
│   ├── test_session_context_cap.py   # oldest-turn trimming
│   └── test_session_idempotency.py
├── state/
│   ├── __init__.py
│   ├── test_db.py
│   └── test_migrations.py
└── prompts/
    └── cassettes/                    # chat_* cassettes (deferred, optional)
scripts/
└── demo-plan-03.py
```

---

## Per-task self-review checklist (runs in every TDD task)

Same 12-point discipline as Plan 02. Repeated here for convenience.

1. `export PATH="$HOME/.local/bin:$PATH"`
2. New submodule? → `uv sync --reinstall-package brain_core` (and `brain_cli` on Task 17)
3. `uv run pytest packages/brain_core packages/brain_cli -q` — all green, no regressions
4. `cd packages/brain_core && uv run mypy src tests && cd ../..` — strict clean
5. `cd packages/brain_cli && uv run mypy src tests && cd ../..` — strict clean (once brain_cli exists)
6. `uv run ruff check .`
7. `uv run ruff format --check .`
8. `find .venv -name "* [0-9].py"` — empty (iCloud ghost-file trap from Plan 02 lesson)
9. If the task added an LLM-touching code path: grep for direct Anthropic SDK imports outside `providers/anthropic.py`
10. If the task added a vault-write path: grep for any `Path.write_*` / `open(..., "w")` outside `VaultWriter`
11. If the task touched `scope_guard`: verify all read tools still route through it
12. `git status` clean after commit

---

## Task outline (details intentionally unfilled pending section review)

Numbering reserves room for batch sweeps (handler-hardening-style), per Plan 02 lesson "when reviewers raise the same class of concern on 2+ consecutive tasks, prefer batching to a sweep."

**Note:** Tasks 15–25 were renumbered (was 15–23) after Group 4 review surfaced the `LLMProvider` tool_use gap. New Task 15 lands the protocol extension; downstream tasks shift by one.

### Foundation — state DB + pending queue + types
- [ ] **Task 1 — Plan 03 deps + `brain_core.chat.types`** (ChatMode, ChatTurn, ChatEvent, ChatSessionConfig pydantic models). Adds `rank-bm25` to `brain_core` deps.
- [ ] **Task 2 — `brain_core.state.StateDB`** (D2c): connect, migrate, exec primitive + first migration (`chat_threads`, `bm25_cache`).
- [ ] **Task 3 — `brain_core.chat.pending.PendingPatchStore`** (D3a): file-per-patch store + list/get/put/reject/apply-marker.

### Retrieval + tools (each tool is one task)
- [ ] **Task 4 — `brain_core.chat.retrieval`**: BM25 builder, vault-hash staleness detection, state.sqlite cache round-trip.
- [ ] **Task 5 — `ChatTool` Protocol + registry** in `tools/base.py`.
- [ ] **Task 6 — `search_vault` tool** (uses Task 4 retrieval, scope-guarded, returns hits with paths + snippets).
- [ ] **Task 7 — `read_note` tool** (scope-guarded, returns full note + frontmatter).
- [ ] **Task 8 — `list_index` tool** (domain `index.md`).
- [ ] **Task 9 — `list_chats` tool** (uses state.sqlite metadata cache).
- [ ] **Task 10 — `propose_note` tool** (stages a `PatchSet` via `PendingPatchStore`, never writes).
- [ ] **Task 11 — `edit_open_doc` tool** (D5a — requires session `open_doc_path`; stages an exact-string replacement patch).

### Context compilation + persistence
- [ ] **Task 12 — `brain_core.chat.context`**: per-turn context compiler (BRAIN.md + index.md + read notes + user msg), hard cap with oldest-turn trimming.
- [ ] **Task 13 — `brain_core.chat.persistence`**: write/read chat thread Markdown file via `VaultWriter` (D4a), including `## System` blocks.
- [ ] **Task 14 — `VaultWriter.rename_file` + `chat.autotitle`**: new vault-writer op + turn-2 auto-title LLM call.

### LLM extension + session loop
- [ ] **Task 15 — `LLMProvider` tool_use extension** (NEW): additive change to `LLMRequest` / `LLMResponse` / `LLMMessage` / `LLMStreamChunk` to carry tool defs and tool_use blocks. `FakeLLMProvider` gains `queue_tool_use(...)` scripting. `AnthropicProvider` passes `tools=` through to the SDK and maps `tool_use` / `tool_result` blocks both directions. All existing Plan 02 callers (summarize/integrate/classify) remain unchanged — their providers return plain-string `content` when no tools are in the request.
- [ ] **Task 16 — `brain_core.chat.modes`**: mode policy table (tool allowlist + temperature + prompt file), Ask / Brainstorm / Draft system prompt files, and a `ChatTool → ToolDef` converter so the session can hand tool schemas to `LLMProvider`.
- [ ] **Task 17 — `brain_core.chat.session.ChatSession` — event loop** (was 16A): context build → LLM stream → tool dispatch → emit `ChatEvent`s. Pure async loop, no persistence. Tested against `FakeLLMProvider` orchestrating tool calls.
- [ ] **Task 18 — `ChatSession` persistence + autotitle wiring** (was 16B): after each turn, call `ThreadPersistence.write`; after turn 2, call `AutoTitler` + `VaultWriter.rename_file` + update `state.sqlite` thread_id.

### CLI wrapper
- [ ] **Task 19 — `brain_cli` package skeleton** (pyproject, Typer root, `brain --help`).
- [ ] **Task 20 — `brain_cli.commands.chat` + `patches`**: Rich streaming renderer, slash commands (`/mode`, `/scope`, `/file`), prompt-toolkit input, Ctrl-C abort. Plus minimal `brain patches list/apply/reject` for demo verification.

### Contract + cross-platform + demo
- [ ] **Task 21 — Prompt contract test infrastructure**: VCR cassette dir + `skipif ANTHROPIC_API_KEY` template, four cassettes deferred per D7a, unit-level prompt-rendering tests (no network).
- [ ] **Task 22 — Cross-platform sweep**: Windows path handling in `PendingPatchStore` + `rename_file`, `state.sqlite` file locking, Rich rendering off a non-TTY, Ctrl-C signal handling on Windows.
- [ ] **Task 23 — `scripts/demo-plan-03.py`** (7-point demo gate above) + README update.
- [ ] **Task 24 — Handler-style hardening sweep** (reserved slot per Plan 02 lesson — fold cross-cutting review findings from Tasks 4–20 here).
- [ ] **Task 25 — Coverage + lint sweep, tag `plan-03-chat`.**

---

## Module-boundary checkpoints (where main-loop review pauses)

Per your preference to use subagent-driven-development with module-boundary checkpoints, main-loop pauses for review at these points rather than after every task:

1. **After Task 3** — foundation (types / state / pending) is frozen. Main-loop reviews that `StateDB` and `PendingPatchStore` shapes won't need refactoring later.
2. **After Task 11** — tool surface is complete. Main-loop reviews every tool's scope-guard path and LLM schema.
3. **After Task 14** — context + persistence + `rename_file` + auto-title. Main-loop verifies `VaultWriter` is the only writer and chat threads round-trip.
4. **After Task 15** — `LLMProvider` tool_use extension is the highest-risk protocol change in the plan. Review is independent of the chat session work so a regression surfaces early.
5. **After Task 18** — session loop works end-to-end against FakeLLMProvider. This is the first "the chat actually runs" checkpoint.
6. **After Task 20** — CLI wrapper. First "user can type at a terminal" checkpoint.
7. **After Task 25** — plan close, tag, demo artifact.

Between checkpoints, subagents run autonomously with the 12-point self-review checklist. At each checkpoint, main-loop performs spec-compliance review then code-quality review (both stages, per Plan 02 lesson).

---

## Detailed per-task steps

> Filled in group-by-group after outline approval. Foundation (Tasks 1–3) below.
> Remaining groups (Retrieval/tools, Context/persistence, Session, CLI, Contract/demo) intentionally unfilled — the main loop will append them after reviewing Foundation.

---

### Group 1 — Foundation (Tasks 1–3)

**Checkpoint after Task 3:** main-loop reviews `ChatMode` / `ChatTurn` / `ChatEvent` shapes, `StateDB` migration strategy, and `PendingPatchStore` on-disk layout. If these shapes need to change, it's far cheaper to change them before Tasks 4–23 reference them.

---

### Task 1 — Plan 03 deps, `brain_core.chat` package skeleton, `chat.types`

**Owning subagent:** brain-core-engineer

**Files:**
- Modify: `packages/brain_core/pyproject.toml` (add `rank-bm25>=0.2.2`)
- Create: `packages/brain_core/src/brain_core/chat/__init__.py`
- Create: `packages/brain_core/src/brain_core/chat/types.py`
- Create: `packages/brain_core/tests/chat/__init__.py`
- Create: `packages/brain_core/tests/chat/test_types.py`

**Context for the implementer:**
`brain_core.chat` is a brand-new package on top of Plan 02. It must have zero web / MCP / CLI imports. This task lands ONLY the pydantic type surface — no logic. Every downstream task imports from `chat.types`, so getting these shapes right now avoids churn later. `ChatMode` must be a `StrEnum` (Plan 01 lesson: UP042 ruff rule).

- [ ] **Step 1: Add `rank-bm25` dep**

Edit `packages/brain_core/pyproject.toml`, add to `[project].dependencies`:
```toml
"rank-bm25>=0.2.2",
```
Then from repo root:
```bash
uv sync --reinstall-package brain_core
```
Expected: resolves cleanly, `rank-bm25` appears in lockfile.

- [ ] **Step 2: Create package skeleton**

`packages/brain_core/src/brain_core/chat/__init__.py`:
```python
"""brain_core.chat — Ask / Brainstorm / Draft chat loop.

Pure logic. No web, MCP, or CLI dependencies.
"""
```

`packages/brain_core/tests/chat/__init__.py`: empty file.

- [ ] **Step 3: Write the failing test for `ChatMode`, `ChatTurn`, `ChatEvent`, `ChatSessionConfig`**

`packages/brain_core/tests/chat/test_types.py`:
```python
"""Tests for brain_core.chat.types — the typed surface every downstream module imports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from brain_core.chat.types import (
    ChatEvent,
    ChatEventKind,
    ChatMode,
    ChatSessionConfig,
    ChatTurn,
    TurnRole,
)


class TestChatMode:
    def test_members_are_ask_brainstorm_draft(self) -> None:
        assert set(ChatMode) == {ChatMode.ASK, ChatMode.BRAINSTORM, ChatMode.DRAFT}

    def test_values_are_lowercase_strings(self) -> None:
        assert ChatMode.ASK.value == "ask"
        assert ChatMode.BRAINSTORM.value == "brainstorm"
        assert ChatMode.DRAFT.value == "draft"

    def test_str_enum_equality(self) -> None:
        assert ChatMode.ASK == "ask"


class TestChatTurn:
    def test_user_turn_round_trip(self) -> None:
        turn = ChatTurn(
            role=TurnRole.USER,
            content="hello",
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            tool_calls=[],
            cost_usd=0.0,
        )
        assert turn.role == TurnRole.USER
        assert turn.content == "hello"
        assert turn.cost_usd == 0.0

    def test_assistant_turn_accepts_tool_calls(self) -> None:
        turn = ChatTurn(
            role=TurnRole.ASSISTANT,
            content="looking that up",
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            tool_calls=[
                {"name": "search_vault", "args": {"query": "karpathy"}, "result_preview": "1 hit"},
            ],
            cost_usd=0.0012,
        )
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0]["name"] == "search_vault"

    def test_system_turn_for_mode_switch(self) -> None:
        turn = ChatTurn(
            role=TurnRole.SYSTEM,
            content="mode changed: ask -> brainstorm",
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            tool_calls=[],
            cost_usd=0.0,
        )
        assert turn.role == TurnRole.SYSTEM

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatTurn(
                role=TurnRole.ASSISTANT,
                content="x",
                created_at=datetime(2026, 4, 14, tzinfo=UTC),
                tool_calls=[],
                cost_usd=-0.01,
            )


class TestChatEvent:
    def test_delta_event(self) -> None:
        ev = ChatEvent(kind=ChatEventKind.DELTA, data={"text": "hel"})
        assert ev.kind == ChatEventKind.DELTA
        assert ev.data["text"] == "hel"

    def test_tool_call_event(self) -> None:
        ev = ChatEvent(
            kind=ChatEventKind.TOOL_CALL,
            data={"name": "search_vault", "args": {"query": "x"}},
        )
        assert ev.kind == ChatEventKind.TOOL_CALL

    def test_all_kinds_present(self) -> None:
        assert set(ChatEventKind) == {
            ChatEventKind.DELTA,
            ChatEventKind.TOOL_CALL,
            ChatEventKind.TOOL_RESULT,
            ChatEventKind.TURN_END,
            ChatEventKind.COST_UPDATE,
            ChatEventKind.PATCH_PROPOSED,
            ChatEventKind.ERROR,
        }


class TestChatSessionConfig:
    def test_defaults(self) -> None:
        cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
        assert cfg.mode == ChatMode.ASK
        assert cfg.domains == ("research",)
        assert cfg.open_doc_path is None
        assert cfg.context_cap_tokens == 150_000
        assert cfg.model == "claude-sonnet-4-6"

    def test_draft_mode_with_open_doc(self) -> None:
        cfg = ChatSessionConfig(
            mode=ChatMode.DRAFT,
            domains=("work",),
            open_doc_path=Path("work/notes/plan.md"),
        )
        assert cfg.open_doc_path == Path("work/notes/plan.md")

    def test_empty_domains_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatSessionConfig(mode=ChatMode.ASK, domains=())

    def test_personal_in_domains_allowed_explicitly(self) -> None:
        cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("personal",))
        assert "personal" in cfg.domains
```

Run:
```bash
uv run pytest packages/brain_core/tests/chat/test_types.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'brain_core.chat.types'`.

- [ ] **Step 4: Implement `chat.types`**

`packages/brain_core/src/brain_core/chat/types.py`:
```python
"""Typed surface for the chat subsystem. Every other chat.* module imports from here."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatMode(StrEnum):
    ASK = "ask"
    BRAINSTORM = "brainstorm"
    DRAFT = "draft"


class TurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"  # mode switches, scope changes, errors surfaced to the transcript


class ChatEventKind(StrEnum):
    DELTA = "delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TURN_END = "turn_end"
    COST_UPDATE = "cost_update"
    PATCH_PROPOSED = "patch_proposed"
    ERROR = "error"


class ChatTurn(BaseModel):
    role: TurnRole
    content: str
    created_at: datetime
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0.0

    @field_validator("cost_usd")
    @classmethod
    def _non_negative_cost(cls, v: float) -> float:
        if v < 0:
            raise ValueError("cost_usd must be non-negative")
        return v


class ChatEvent(BaseModel):
    """Streamed event from ChatSession. Consumers (CLI, API WS) map 1:1 to their wire format."""

    kind: ChatEventKind
    data: dict[str, Any] = Field(default_factory=dict)


class ChatSessionConfig(BaseModel):
    mode: ChatMode
    domains: tuple[str, ...]
    open_doc_path: Path | None = None
    context_cap_tokens: int = 150_000
    model: str = "claude-sonnet-4-6"

    @field_validator("domains")
    @classmethod
    def _at_least_one_domain(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("at least one domain required")
        return v
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
uv sync --reinstall-package brain_core
uv run pytest packages/brain_core/tests/chat/test_types.py -v
```
Expected: 12 passed.

- [ ] **Step 6: Run the 12-point self-review checklist**

All of: pytest green on `packages/brain_core`, mypy strict clean, ruff + format clean, ghost-file sweep empty, no direct Anthropic SDK imports (none touched), no vault-write paths added, `git status` clean after commit.

- [ ] **Step 7: Commit**

```bash
git add packages/brain_core/pyproject.toml \
        packages/brain_core/src/brain_core/chat/__init__.py \
        packages/brain_core/src/brain_core/chat/types.py \
        packages/brain_core/tests/chat/__init__.py \
        packages/brain_core/tests/chat/test_types.py \
        uv.lock
git commit -m "feat(chat): plan 03 task 1 — chat package skeleton + pydantic types"
```

---

### Task 2 — `brain_core.state.StateDB` + first migration

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/state/__init__.py`
- Create: `packages/brain_core/src/brain_core/state/db.py`
- Create: `packages/brain_core/src/brain_core/state/migrations/__init__.py`
- Create: `packages/brain_core/src/brain_core/state/migrations/0001_chat_and_bm25.sql`
- Create: `packages/brain_core/tests/state/__init__.py`
- Create: `packages/brain_core/tests/state/test_db.py`
- Create: `packages/brain_core/tests/state/test_migrations.py`

**Context for the implementer:**
Per D2c, this is a standalone `brain_core.state` module with just the `StateDB` primitive. Two tables for now: `chat_threads` (metadata cache) and `bm25_cache` (serialized index blob + vault hash). Schema versioning via a `schema_version` table; migrations run at connect time, are additive-only, and are idempotent. Plans 04/05 will add tables via new migration files without touching existing ones. SQLite file lives at `<vault>/.brain/state.sqlite`.

**Cross-platform notes:**
- Use `sqlite3.connect(str(path))` — `pathlib.Path` works on both platforms.
- WAL mode (`PRAGMA journal_mode=WAL`) — supported on Mac and Windows NTFS.
- Pair WAL with `PRAGMA synchronous=NORMAL` — state is a rebuildable cache per CLAUDE.md principle #6, and NORMAL gives ~2× write speed with crash safety for everything except the last committed transaction.
- File locking is sqlite's responsibility; no extra code needed.

**Migration atomicity (IMPORTANT — learned during execution):** Do NOT use `conn.executescript(sql)` for migration application. `executescript` issues an implicit COMMIT on an autocommit connection, which breaks transaction semantics — a partial-failure migration will commit some DDL and never record the `schema_version` row, leaving the DB in a silently inconsistent state. Instead, manually split the SQL file on `;` after stripping `--` line comments, then loop over statements inside an explicit `BEGIN` / `COMMIT` / `ROLLBACK` block. This means migration files MUST NOT contain semicolons inside string literals or trigger bodies (document the limitation in the code, enforce at the first trigger-bearing migration). Also use plain `INSERT` (not `INSERT OR IGNORE`) on `schema_version` — a conflict there is always a bug given the preceding `version <= current` guard.

- [ ] **Step 1: Write the failing test for `StateDB` basics**

`packages/brain_core/tests/state/test_db.py`:
```python
"""Tests for brain_core.state.db — the SQLite primitive."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.state.db import StateDB


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / ".brain" / "state.sqlite"


class TestStateDBBasics:
    def test_connect_creates_parent_dir(self, db_path: Path) -> None:
        assert not db_path.parent.exists()
        db = StateDB.open(db_path)
        try:
            assert db_path.parent.exists()
            assert db_path.exists()
        finally:
            db.close()

    def test_open_is_idempotent(self, db_path: Path) -> None:
        db1 = StateDB.open(db_path)
        db1.close()
        db2 = StateDB.open(db_path)
        try:
            assert db2.schema_version() >= 1
        finally:
            db2.close()

    def test_wal_mode_enabled(self, db_path: Path) -> None:
        db = StateDB.open(db_path)
        try:
            cur = db.exec("PRAGMA journal_mode")
            row = cur.fetchone()
            assert row[0].lower() == "wal"
        finally:
            db.close()

    def test_exec_returns_cursor(self, db_path: Path) -> None:
        db = StateDB.open(db_path)
        try:
            db.exec("INSERT INTO chat_threads(thread_id, path, domain, mode, turns, cost_usd, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("t1", "research/foo.md", "research", "ask", 2, 0.01, "2026-04-14T00:00:00Z"))
            cur = db.exec("SELECT thread_id, mode FROM chat_threads WHERE thread_id = ?", ("t1",))
            row = cur.fetchone()
            assert row == ("t1", "ask")
        finally:
            db.close()

    def test_context_manager(self, db_path: Path) -> None:
        with StateDB.open(db_path) as db:
            assert db.schema_version() >= 1
```

`packages/brain_core/tests/state/test_migrations.py`:
```python
"""Tests for migration discovery and execution."""

from __future__ import annotations

from pathlib import Path

from brain_core.state.db import StateDB


class TestMigrations:
    def test_first_open_records_schema_version_1(self, tmp_path: Path) -> None:
        with StateDB.open(tmp_path / "state.sqlite") as db:
            assert db.schema_version() == 1

    def test_chat_threads_table_exists(self, tmp_path: Path) -> None:
        with StateDB.open(tmp_path / "state.sqlite") as db:
            cur = db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_threads'")
            assert cur.fetchone() is not None

    def test_bm25_cache_table_exists(self, tmp_path: Path) -> None:
        with StateDB.open(tmp_path / "state.sqlite") as db:
            cur = db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='bm25_cache'")
            assert cur.fetchone() is not None

    def test_reopen_does_not_re_run_migrations(self, tmp_path: Path) -> None:
        path = tmp_path / "state.sqlite"
        with StateDB.open(path) as db:
            db.exec("INSERT INTO bm25_cache(domain, vault_hash, index_blob) VALUES (?, ?, ?)",
                    ("research", "deadbeef", b"\\x00\\x01"))
        with StateDB.open(path) as db:
            cur = db.exec("SELECT vault_hash FROM bm25_cache WHERE domain = ?", ("research",))
            row = cur.fetchone()
            assert row[0] == "deadbeef"
```

Run:
```bash
uv run pytest packages/brain_core/tests/state -v
```
Expected: FAIL with `ModuleNotFoundError: brain_core.state`.

- [ ] **Step 2: Create the migration SQL**

`packages/brain_core/src/brain_core/state/migrations/0001_chat_and_bm25.sql`:
```sql
-- brain_core.state migration 0001 — chat thread metadata + BM25 index cache.
-- Owned by Plan 03. Additive-only from here; never ALTER/DROP existing columns.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_threads (
    thread_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    domain TEXT NOT NULL,
    mode TEXT NOT NULL,
    turns INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_domain ON chat_threads(domain);
CREATE INDEX IF NOT EXISTS idx_chat_threads_updated ON chat_threads(updated_at DESC);

CREATE TABLE IF NOT EXISTS bm25_cache (
    domain TEXT PRIMARY KEY,
    vault_hash TEXT NOT NULL,
    index_blob BLOB NOT NULL,
    built_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 3: Implement `StateDB`**

`packages/brain_core/src/brain_core/state/__init__.py`:
```python
"""brain_core.state — shared SQLite primitives. Vault is source of truth; state is cache."""

from brain_core.state.db import StateDB

__all__ = ["StateDB"]
```

`packages/brain_core/src/brain_core/state/migrations/__init__.py`: empty file.

`packages/brain_core/src/brain_core/state/db.py`:
```python
"""StateDB — thin SQLite wrapper with additive migrations.

Cross-platform: uses pathlib for all paths, WAL journal mode, no POSIX-only syscalls.
Migrations apply transactionally: each file runs inside an explicit BEGIN/COMMIT/ROLLBACK.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class StateDB:
    """Thin SQLite wrapper. Use StateDB.open(path) as the entry point."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def open(cls, path: Path) -> Self:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), isolation_level=None)  # autocommit
        conn.execute("PRAGMA journal_mode=WAL")
        # NORMAL pairs with WAL per CLAUDE.md principle #6 (state is a rebuildable cache).
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        db = cls(conn)
        try:
            db._apply_migrations()
        except Exception:
            db.close()  # release the half-built resource before re-raising
            raise
        return db

    def _apply_migrations(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        current = self.schema_version()
        for sql_file in sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
            version = int(sql_file.name[:4])
            if version <= current:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            self._apply_one_migration(version, sql)

    def _apply_one_migration(self, version: int, sql: str) -> None:
        """Apply a single migration file transactionally.

        We avoid sqlite3.executescript — it issues an implicit COMMIT on autocommit
        connections, which breaks rollback semantics. Instead we split on ; after
        stripping line comments, and run each statement inside an explicit transaction.

        LIMITATION: the splitter does not understand semicolons inside string literals
        or trigger bodies. Today's DDL-only migrations satisfy that constraint; the
        first trigger-bearing migration must upgrade the splitter.
        """
        cleaned_lines = [
            line for line in sql.splitlines() if not line.strip().startswith("--")
        ]
        cleaned = "\n".join(cleaned_lines)
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        try:
            self._conn.execute("BEGIN")
            for stmt in statements:
                self._conn.execute(stmt)
            self._conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def schema_version(self) -> int:
        try:
            cur = self._conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        except sqlite3.OperationalError:
            return 0
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def exec(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
```

- [ ] **Step 4: Add a regression test for transactional rollback**

Add to `test_migrations.py`:

```python
def test_failed_migration_rolls_back_cleanly(tmp_path, monkeypatch):
    """A broken 0002 migration must roll back atomically — no partial tables,
    no stale schema_version row, and the DB must be reopenable with a valid
    migrations dir afterward."""
    import brain_core.state.db as db_module
    fake_migrations = tmp_path / "fake_migrations"
    fake_migrations.mkdir()
    # Copy the real 0001 verbatim.
    real_0001 = db_module._MIGRATIONS_DIR / "0001_chat_and_bm25.sql"
    (fake_migrations / "0001_chat_and_bm25.sql").write_text(
        real_0001.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Write a broken 0002 with a valid statement followed by invalid SQL.
    (fake_migrations / "0002_broken.sql").write_text(
        "CREATE TABLE partial_good (x INTEGER);\nBROKEN SYNTAX HERE;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "_MIGRATIONS_DIR", fake_migrations)

    db_path = tmp_path / "state.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        StateDB.open(db_path)

    # Reopen with just the valid migration and verify rollback:
    (fake_migrations / "0002_broken.sql").unlink()
    with StateDB.open(db_path) as db:
        # partial_good from the broken migration must NOT exist.
        cur = db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='partial_good'")
        assert cur.fetchone() is None
        # schema_version has exactly version 1.
        cur = db.exec("SELECT version FROM schema_version")
        assert cur.fetchall() == [(1,)]
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
uv sync --reinstall-package brain_core
uv run pytest packages/brain_core/tests/state -v
```
Expected: **10 passed** (5 in test_db.py + 5 in test_migrations.py).

- [ ] **Step 6: 12-point self-review checklist**

- [ ] **Step 7: Commit**

```bash
git add packages/brain_core/src/brain_core/state/ \
        packages/brain_core/tests/state/
git commit -m "feat(state): plan 03 task 2 — StateDB primitive + chat/bm25 migration"
```

**Note for future plan authors:** the original plan text here specified `conn.executescript(sql)` and `INSERT OR IGNORE` on schema_version. Both are latent correctness bugs for partial-failure migrations and were caught in Task 2's code-quality review during execution (`08e04a0`). The version above reflects the shipped implementation. Future migration-related plans should NOT revert to `executescript`.

---

### Task 3 — `brain_core.chat.pending.PendingPatchStore`

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/pending.py`
- Create: `packages/brain_core/tests/chat/test_pending.py`

**Context for the implementer:**
Per D3a, the pending-patch queue is one JSON file per patch at `<vault>/.brain/pending/<patch_id>.json`. `patch_id` is `{epoch_ms:013d}-{uuid4.hex[:8]}` — sortable lexicographically by creation time, no new dep. Each file contains an envelope (metadata) + a `PatchSet` body. Three terminal states: `pending` (file present in `pending/`), `rejected` (file moved to `pending/rejected/`), `applied` (file moved to `pending/applied/`). This matches `.brain/logs/` / `.brain/run/` directory conventions from Plan 01 — ignored by git via the existing `.brain/` gitignore rule.

`PatchSet` comes from `brain_core.vault.types` (already exists from Plan 02).

**Cross-platform notes:**
- Writes via `_atomic_write_text` helper (temp + rename) — never `open(..., "w")` directly.
- `os.replace()` is atomic on both Mac and Windows, AND works cross-directory on the same filesystem. We exploit that for state transitions: first rewrite the envelope in place (tmp + `os.replace` → src), then rename src → dest across directories.

**State transition atomicity (IMPORTANT — learned during execution):** The naive pattern `write(dest) → unlink(src)` has a crash window where both files exist, and on next `list()` the stale pending/ file reappears — a user's rejected patch pops back into their queue. Instead, `_move()` uses a two-phase atomic sequence:
1. Compute the updated envelope (new status + reason)
2. Write tmp in `src.parent` with the updated JSON
3. `os.replace(tmp, src)` — src now has terminal status atomically
4. `os.replace(src, dest)` — cross-directory atomic rename

A crash between phases 3 and 4 leaves src with `status != PENDING`. `list()` has a safety net filter that excludes any loaded envelope where `env.status != PendingStatus.PENDING`, so the stale file is invisible to consumers. The clean path is atomic; the crash path self-heals at list time.

- [ ] **Step 1: Write the failing test**

`packages/brain_core/tests/chat/test_pending.py`:
```python
"""Tests for brain_core.chat.pending.PendingPatchStore."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from brain_core.chat.pending import PendingEnvelope, PendingPatchStore, PendingStatus
from brain_core.chat.types import ChatMode
from brain_core.vault.types import NewFile, PatchSet


def _sample_patchset(text: str = "body") -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/sample.md"), content=f"# sample\\n\\n{text}")],
        reason="test fixture",
    )


@pytest.fixture
def store(tmp_path: Path) -> PendingPatchStore:
    return PendingPatchStore(tmp_path / ".brain" / "pending")


class TestPutAndList:
    def test_put_creates_pending_file(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="research/2026-04-14-foo.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/notes/sample.md"),
            reason="new note from chat",
        )
        assert env.status == PendingStatus.PENDING
        assert (store.root / f"{env.patch_id}.json").exists()

    def test_list_returns_pending_sorted_by_id(self, store: PendingPatchStore) -> None:
        ids = []
        for i in range(3):
            env = store.put(
                patchset=_sample_patchset(f"v{i}"),
                source_thread="t.md",
                mode=ChatMode.BRAINSTORM,
                tool="propose_note",
                target_path=Path(f"research/n{i}.md"),
                reason="x",
            )
            ids.append(env.patch_id)
            time.sleep(0.002)
        listed = [e.patch_id for e in store.list()]
        assert listed == sorted(ids)

    def test_get_round_trip(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset("hello"),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        loaded = store.get(env.patch_id)
        assert loaded is not None
        assert loaded.patchset.new_files[0].content.endswith("hello")
        assert loaded.mode == ChatMode.BRAINSTORM


class TestRejectAndApply:
    def test_reject_moves_to_rejected_dir(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        store.reject(env.patch_id, reason="user rejected")
        assert not (store.root / f"{env.patch_id}.json").exists()
        assert (store.root / "rejected" / f"{env.patch_id}.json").exists()
        assert store.get(env.patch_id) is None

    def test_mark_applied_moves_to_applied_dir(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        store.mark_applied(env.patch_id)
        assert not (store.root / f"{env.patch_id}.json").exists()
        assert (store.root / "applied" / f"{env.patch_id}.json").exists()

    def test_list_ignores_rejected_and_applied(self, store: PendingPatchStore) -> None:
        a = store.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note",
                      Path("r/a.md"), "x")
        time.sleep(0.002)
        b = store.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note",
                      Path("r/b.md"), "x")
        time.sleep(0.002)
        c = store.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note",
                      Path("r/c.md"), "x")
        store.reject(a.patch_id, reason="no")
        store.mark_applied(c.patch_id)
        remaining = [e.patch_id for e in store.list()]
        assert remaining == [b.patch_id]

    def test_reject_unknown_id_raises(self, store: PendingPatchStore) -> None:
        with pytest.raises(KeyError):
            store.reject("nonexistent", reason="x")


class TestCrossPlatform:
    def test_patch_id_is_sortable_lexicographically(self, store: PendingPatchStore) -> None:
        first = store.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note",
                          Path("r/a.md"), "x")
        time.sleep(0.002)
        second = store.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note",
                           Path("r/b.md"), "x")
        assert first.patch_id < second.patch_id

    def test_root_created_lazily(self, tmp_path: Path) -> None:
        root = tmp_path / ".brain" / "pending"
        s = PendingPatchStore(root)
        assert not root.exists()
        s.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note",
              Path("r/a.md"), "x")
        assert root.exists()
```

Run:
```bash
uv run pytest packages/brain_core/tests/chat/test_pending.py -v
```
Expected: FAIL with `ModuleNotFoundError: brain_core.chat.pending`.

- [ ] **Step 2: Implement `PendingPatchStore`**

`packages/brain_core/src/brain_core/chat/pending.py`:
```python
"""PendingPatchStore — file-per-patch staging queue for chat-proposed vault mutations.

Per Plan 03 D3a, each pending patch is one JSON file at .brain/pending/<patch_id>.json.
Rejected patches move to .brain/pending/rejected/. Applied patches move to .brain/pending/applied/.
Patch IDs are sortable lexicographically by creation time.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from brain_core.chat.types import ChatMode
from brain_core.vault.types import PatchSet


class PendingStatus(StrEnum):
    PENDING = "pending"
    REJECTED = "rejected"
    APPLIED = "applied"


class PendingEnvelope(BaseModel):
    patch_id: str
    created_at: datetime
    source_thread: str
    mode: ChatMode
    tool: str
    target_path: Path
    reason: str
    status: PendingStatus = PendingStatus.PENDING
    patchset: PatchSet = Field(...)


def _new_patch_id() -> str:
    ms = int(time.time() * 1000)
    suffix = uuid.uuid4().hex[:8]
    return f"{ms:013d}-{suffix}"


def _atomic_write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8", newline="\\n")
    os.replace(tmp, path)


class PendingPatchStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(
        self,
        patchset: PatchSet,
        source_thread: str,
        mode: ChatMode,
        tool: str,
        target_path: Path,
        reason: str,
    ) -> PendingEnvelope:
        env = PendingEnvelope(
            patch_id=_new_patch_id(),
            created_at=datetime.now(UTC),
            source_thread=source_thread,
            mode=mode,
            tool=tool,
            target_path=target_path,
            reason=reason,
            patchset=patchset,
        )
        _atomic_write_text(
            self.root / f"{env.patch_id}.json",
            env.model_dump_json(indent=2),
        )
        return env

    def list(self) -> list[PendingEnvelope]:
        if not self.root.exists():
            return []
        out: list[PendingEnvelope] = []
        for f in sorted(self.root.glob("*.json")):
            if f.parent != self.root:
                continue
            env = PendingEnvelope.model_validate_json(f.read_text(encoding="utf-8"))
            # Safety net for the _move() crash window: if a file is in pending/ but its
            # on-disk status is already terminal (REJECTED/APPLIED), skip it. Clean path
            # never produces such files; crash path self-heals here.
            if env.status != PendingStatus.PENDING:
                continue
            out.append(env)
        return out

    def get(self, patch_id: str) -> PendingEnvelope | None:
        f = self.root / f"{patch_id}.json"
        if not f.exists():
            return None
        return PendingEnvelope.model_validate_json(f.read_text(encoding="utf-8"))

    def reject(self, patch_id: str, reason: str) -> None:
        self._move(patch_id, PendingStatus.REJECTED, reason=reason)

    def mark_applied(self, patch_id: str) -> None:
        self._move(patch_id, PendingStatus.APPLIED, reason=None)

    def _move(self, patch_id: str, new_status: PendingStatus, reason: str | None) -> None:
        src = self.root / f"{patch_id}.json"
        if not src.exists():
            raise KeyError(patch_id)
        env = PendingEnvelope.model_validate_json(src.read_text(encoding="utf-8"))
        env = env.model_copy(
            update={"status": new_status, "reason": reason if reason is not None else env.reason}
        )
        # Phase 1: rewrite src in place with the terminal status.
        # We write the tmp directly (not via _atomic_write_text) because the subsequent
        # os.replace(tmp, src) IS the atomic commit — wrapping it in another atomic
        # helper would double-rename.
        tmp = src.with_suffix(src.suffix + ".tmp")
        tmp.write_text(env.model_dump_json(indent=2), encoding="utf-8", newline="\n")
        os.replace(tmp, src)
        # Phase 2: atomic cross-directory rename to the terminal status dir.
        dest_dir = self.root / new_status.value
        dest_dir.mkdir(parents=True, exist_ok=True)
        os.replace(src, dest_dir / f"{patch_id}.json")
```

- [ ] **Step 3: Add two regression tests for the atomicity fix**

Add `test_reject_actually_moves_via_os_replace` to `TestRejectAndApply`:

```python
def test_reject_actually_moves_via_os_replace(self, store: PendingPatchStore) -> None:
    env = store.put(
        patchset=_sample_patchset(),
        source_thread="t.md",
        mode=ChatMode.BRAINSTORM,
        tool="propose_note",
        target_path=Path("research/n.md"),
        reason="x",
    )
    src = store.root / f"{env.patch_id}.json"
    dest = store.root / "rejected" / f"{env.patch_id}.json"
    store.reject(env.patch_id, reason="user rejected")
    assert not src.exists()
    assert dest.exists()
    loaded = PendingEnvelope.model_validate_json(dest.read_text(encoding="utf-8"))
    assert loaded.status == PendingStatus.REJECTED
    assert loaded.reason == "user rejected"
```

Add a new `TestCrashRecovery` class:

```python
class TestCrashRecovery:
    def test_list_skips_stale_pending_with_terminal_status(
        self, store: PendingPatchStore
    ) -> None:
        """Simulate a crash between phase 1 (rewrite src with new status) and
        phase 2 (os.replace src -> dest). The stale pending file must NOT
        resurrect into list() output."""
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        src = store.root / f"{env.patch_id}.json"
        # Manually reproduce the mid-crash state: src present but status=REJECTED.
        stale = env.model_copy(update={"status": PendingStatus.REJECTED})
        src.write_text(stale.model_dump_json(indent=2), encoding="utf-8")

        listed = [e.patch_id for e in store.list()]
        assert env.patch_id not in listed
```

Also bump all four `time.sleep(0.002)` occurrences in the existing tests to `time.sleep(0.01)` — 2ms is below historical Windows timer granularity and could be flaky on CI runners.

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest packages/brain_core/tests/chat/test_pending.py -v
```
Expected: **11 passed** (9 original + 2 new regression tests).

- [ ] **Step 5: 12-point self-review checklist**

Extra verification for Task 3:
- Grep for any `open(..., "w")` or `write_text` outside `_atomic_write_text` / the `_move` phase-1 tmp write in `pending.py` — should find only those two sites.
- `PendingPatchStore` writes to `.brain/pending/`, not the vault proper — confirm no `VaultWriter` bypass concern (this is scratch/state, not vault content).

- [ ] **Step 6: Commit**

```bash
git add packages/brain_core/src/brain_core/chat/pending.py \
        packages/brain_core/tests/chat/test_pending.py
git commit -m "feat(chat): plan 03 task 3 — PendingPatchStore (.brain/pending/<id>.json)"
```

**Note for future plan authors:** the original plan text here specified `_atomic_write_text(dest, ...)` followed by `src.unlink()` in `_move()`, and did NOT filter `list()` by status. Both were latent crash-recovery bugs caught in Task 3's code-quality review during execution (`62b0c1d`). The version above reflects the shipped implementation. Future staging-queue work should NOT revert to write-dest-then-unlink-src.

---

**Checkpoint — pause here for main-loop review.**

At this point: 3 tasks landed, ~31 tests added, zero vault writes introduced. The shapes that downstream tasks depend on (`ChatMode`, `ChatTurn`, `ChatEvent`, `ChatSessionConfig`, `StateDB`, `PendingEnvelope`) are now fixed. Main loop performs spec-compliance review + code-quality review before dispatching Task 4 (`retrieval`).

---

### Group 2 — Retrieval + tools (Tasks 4–11)

**Checkpoint after Task 11:** main-loop reviews the tool surface as a whole — every tool's scope-guard path, LLM schema, and error taxonomy. Tools are dispatched by the session loop in Task 16, so catching shape issues now prevents session-loop churn.

---

### Task 4 — `brain_core.chat.retrieval` — BM25 index + `state.sqlite` cache

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/retrieval.py`
- Create: `packages/brain_core/tests/chat/test_retrieval.py`

**Context for the implementer:**
`BM25VaultIndex` builds a per-domain BM25 index over `(title, tags, body)` of every `.md` note in the domain, excluding `chats/` (chat threads are their own corpus via `list_chats`). The index is cached in `state.sqlite` `bm25_cache`, keyed by domain. Cache is invalidated when the **vault hash** for that domain changes — sha256 of the sorted list of `(rel_path, mtime_ns, size)` tuples. This is cheap to compute and catches every file-level change without a full re-read.

Tokenization is simple: lowercase, `\w+` split, drop stopwords (basic English set, <50 words, defined in-module). Good enough for a local KB; upgrade later if needed.

Retrieval stores the `rank_bm25.BM25Okapi` instance + the `doc_refs` list (paths, titles, snippets) as a pickled blob. Pickle is safe here because it's our own data written to our own cache; load failures re-trigger a rebuild.

- [ ] **Step 1: Write the failing test** — `packages/brain_core/tests/chat/test_retrieval.py` (6 tests): `build_then_search_returns_relevant_hit`, `search_excludes_chats_directory`, `search_returns_snippet`, `second_build_uses_cache` (asserts `was_cache_hit("research") is True`), `cache_invalidated_on_file_change` (writes a new note, rebuilds, asserts cache miss + new hit), `search_without_build_raises`. Fixture creates a vault with `research/notes/karpathy.md`, `research/notes/rag.md`, `research/index.md`, and a `research/chats/old-thread.md` that must be excluded.

- [ ] **Step 2: Implement `retrieval.py`** — `BM25VaultIndex(vault_root, db)` with `build(domains)`, `search(query, domains, top_k)`, `was_cache_hit(domain)`. Internal helpers: `_compute_vault_hash(domain)` hashes sorted `(rel_path, mtime_ns, size)` excluding `chats/`. `_load_cache`/`_save_cache` pickle `(BM25Okapi, doc_refs)` into the `bm25_cache` table. `_read_domain_docs` iterates `rglob("*.md")`, parses frontmatter via `brain_core.vault.frontmatter.parse`, builds a `f"{title}\n{tags}\n{body}"` blob per doc, tokenizes. `search` returns `SearchHit(path, score, title, snippet)` sorted by score desc, limited to `top_k`. Raises `RuntimeError("not built")` if search is called before build.

- [ ] **Step 3: Run tests — expect PASS**

```bash
uv sync --reinstall-package brain_core
uv run pytest packages/brain_core/tests/chat/test_retrieval.py -v
```
Expected: 6 passed.

- [ ] **Step 4: 12-point self-review checklist**

Extras: confirm `retrieval.py` does NOT import `scope_guard` — retrieval reads its own domain's files, scope enforcement is the *tool* layer's job (Task 6). Confirm chat threads are excluded (`if "chats" in rel.parts`).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(chat): plan 03 task 4 — BM25VaultIndex with state.sqlite cache"
```

---

### Task 5 — `ChatTool` Protocol + `ToolRegistry`

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/__init__.py` (empty)
- Create: `packages/brain_core/src/brain_core/chat/tools/base.py`
- Create: `packages/brain_core/tests/chat/test_tools_base.py`

**Context:**
The Protocol defines what every tool looks like; the registry is where session assembles the tool set based on mode policy (Task 15). Every tool is a class that takes an `args` dict (already validated against its JSON schema by the caller) and a `ToolContext`, returning a `ToolResult`.

- [ ] **Step 1: Write the failing test** — 6 tests for `ChatTool` Protocol and `ToolRegistry`:

```python
"""Tests for ChatTool Protocol + ToolRegistry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from brain_core.chat.tools.base import (
    ChatTool,
    ToolContext,
    ToolRegistry,
    ToolResult,
)


class _EchoTool:
    name = "echo"
    description = "echo back the args"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(text=args["text"])


def test_echo_tool_satisfies_protocol() -> None:
    tool: ChatTool = _EchoTool()
    assert tool.name == "echo"


def test_run_returns_tool_result(tmp_path: Path) -> None:
    tool = _EchoTool()
    ctx = ToolContext(
        vault_root=tmp_path, allowed_domains=("research",),
        open_doc_path=None, retrieval=None, pending_store=None, state_db=None,
        source_thread="t.md", mode_name="ask",
    )
    result = tool.run({"text": "hi"}, ctx)
    assert result.text == "hi"
    assert result.data is None
    assert result.proposed_patch is None


def test_register_and_get() -> None:
    reg = ToolRegistry()
    reg.register(_EchoTool())
    assert reg.get("echo").name == "echo"


def test_get_unknown_raises() -> None:
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")


def test_filter_by_allowlist() -> None:
    reg = ToolRegistry()
    reg.register(_EchoTool())
    filtered = reg.subset(allowlist=("echo",))
    assert [t.name for t in filtered.all()] == ["echo"]
    assert reg.subset(allowlist=()).all() == []


def test_double_register_raises() -> None:
    reg = ToolRegistry()
    reg.register(_EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_EchoTool())
```

- [ ] **Step 2: Implement**

`base.py`: `ToolContext` dataclass with fields `vault_root: Path`, `allowed_domains: tuple[str, ...]`, `open_doc_path: Path | None`, `retrieval: Any`, `pending_store: PendingPatchStore | None`, `state_db: StateDB | None`, `source_thread: str`, `mode_name: str`. `ToolResult` dataclass with `text: str`, `data: dict[str, Any] | None = None`, `proposed_patch: PendingEnvelope | None = None`. `ChatTool` is a `@runtime_checkable` `Protocol` with `name: str`, `description: str`, `input_schema: dict[str, Any]`, `def run(self, args, ctx) -> ToolResult`. `ToolRegistry` has `register(tool)` (raises `ValueError` on duplicate name), `get(name)` (raises `KeyError`), `all()`, `subset(allowlist: tuple[str, ...]) -> ToolRegistry`. `retrieval` is typed `Any` to avoid an import cycle with `retrieval.py`.

- [ ] **Step 3–5: Run, self-review, commit**

```bash
uv run pytest packages/brain_core/tests/chat/test_tools_base.py -v
```
Expected: 6 passed.

```bash
git commit -m "feat(chat): plan 03 task 5 — ChatTool Protocol + ToolRegistry"
```

---

### Task 6 — `search_vault` tool

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/search_vault.py`
- Create: `packages/brain_core/tests/chat/test_tool_search_vault.py`

**Context:**
Wraps `BM25VaultIndex.search` behind the tool interface. Every returned hit's path is verified via `scope_guard(vault_root / hit.path, vault_root=vault_root, allowed_domains=ctx.allowed_domains)` — belt-and-braces against a retrieval bug leaking cross-domain paths. `top_k` defaults to 5, cap at 20. Accepts an optional `domains` arg that MUST be a subset of `ctx.allowed_domains`; providing an out-of-scope domain raises `ScopeError`.

- [ ] **Step 1: Write the failing test** — 5 tests: `returns_in_scope_hits`, `respects_top_k`, `top_k_capped_at_20` (asserts `result.data["top_k_used"] == 20` when caller passes 500), `out_of_scope_domain_raises` (ScopeError when `domains=["personal"]` against `allowed=("research",)`), `empty_query_returns_empty`. Fixture creates a vault with `research/notes/llm.md` and `personal/notes/secret.md`; `ctx.allowed_domains=("research",)`; BM25 index built on `("research",)`.

- [ ] **Step 2: Implement**

```python
"""search_vault tool — BM25 retrieval over the session's allowed domains."""

from __future__ import annotations

from typing import Any

from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.tools.base import ChatTool, ToolContext, ToolResult
from brain_core.vault.paths import ScopeError, scope_guard

_MAX_TOP_K = 20
_DEFAULT_TOP_K = 5


class SearchVaultTool:
    name = "search_vault"
    description = "BM25 search over notes in the active scope. Returns paths + snippets."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": _MAX_TOP_K},
            "domains": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        top_k = min(int(args.get("top_k", _DEFAULT_TOP_K)), _MAX_TOP_K)
        requested = tuple(args.get("domains") or ctx.allowed_domains)
        for d in requested:
            if d not in ctx.allowed_domains:
                raise ScopeError(f"domain {d!r} not in allowed {ctx.allowed_domains}")
        if not query:
            return ToolResult(text="(empty query)", data={"hits": [], "top_k_used": top_k})

        idx: BM25VaultIndex = ctx.retrieval
        hits = idx.search(query, domains=requested, top_k=top_k)

        # Belt-and-braces scope verification on every path before returning it.
        verified: list[dict[str, Any]] = []
        for h in hits:
            scope_guard(
                ctx.vault_root / h.path,
                vault_root=ctx.vault_root,
                allowed_domains=ctx.allowed_domains,
            )
            verified.append(
                {
                    "path": h.path.as_posix(),
                    "title": h.title,
                    "snippet": h.snippet,
                    "score": round(h.score, 4),
                }
            )
        lines = [f"- {h['path']} — {h['title']}" for h in verified] or ["(no hits)"]
        return ToolResult(
            text="\n".join(lines),
            data={"hits": verified, "top_k_used": top_k},
        )
```

- [ ] **Step 3–5: Run, self-review, commit**

Expected: 5 passed.

```bash
git commit -m "feat(chat): plan 03 task 6 — search_vault tool (scope-guarded BM25)"
```

---

### Task 7 — `read_note` tool

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/read_note.py`
- Create: `packages/brain_core/tests/chat/test_tool_read_note.py`

**Context:** Takes a vault-relative `path`, scope-guards it, reads the file, parses frontmatter, returns `{frontmatter, body, path}`. Raises `ScopeError` on out-of-scope path, `FileNotFoundError` on missing, `ValueError("vault-relative")` on absolute path.

- [ ] **Step 1: Write the failing test** — 4 tests:

```python
def test_reads_in_scope_note(ctx):
    result = ReadNoteTool().run({"path": "research/notes/karpathy.md"}, ctx)
    assert "Wiki pattern" in result.text
    assert result.data["frontmatter"]["title"] == "Karpathy"
    assert result.data["path"] == "research/notes/karpathy.md"


def test_out_of_scope_raises(ctx):
    with pytest.raises(ScopeError):
        ReadNoteTool().run({"path": "personal/notes/secret.md"}, ctx)


def test_missing_file_raises_friendly(ctx):
    with pytest.raises(FileNotFoundError, match="not found"):
        ReadNoteTool().run({"path": "research/notes/missing.md"}, ctx)


def test_absolute_path_rejected(ctx, vault):
    with pytest.raises(ValueError, match="vault-relative"):
        ReadNoteTool().run({"path": str(vault / "research" / "notes" / "karpathy.md")}, ctx)
```

Fixture: vault with `research/notes/karpathy.md` and `personal/notes/secret.md`; `ctx.allowed_domains=("research",)`.

- [ ] **Step 2: Implement**

```python
"""read_note tool — scope-guarded note reader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_core.chat.tools.base import ChatTool, ToolContext, ToolResult
from brain_core.vault.frontmatter import parse as parse_frontmatter
from brain_core.vault.paths import scope_guard


class ReadNoteTool:
    name = "read_note"
    description = "Read a note by vault-relative path. Returns frontmatter + body."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        raw = str(args["path"])
        p = Path(raw)
        if p.is_absolute():
            raise ValueError("path must be vault-relative, not absolute")
        full = scope_guard(
            ctx.vault_root / p,
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        if not full.exists():
            raise FileNotFoundError(f"note {raw!r} not found in vault")
        text = full.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        return ToolResult(
            text=body,
            data={"frontmatter": fm, "body": body, "path": p.as_posix()},
        )
```

- [ ] **Step 3–5: Run, self-review, commit**

Expected: 4 passed.

```bash
git commit -m "feat(chat): plan 03 task 7 — read_note tool (scope-guarded)"
```

---

### Task 8 — `list_index` tool

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/list_index.py`
- Create: `packages/brain_core/tests/chat/test_tool_list_index.py`

**Context:** Returns contents of `<domain>/index.md`. If no `domain` arg, defaults to `ctx.allowed_domains[0]`. Scope-guarded. Missing index returns `text="(no index yet)"`.

- [ ] **Step 1: Write the failing test** — 4 tests: `default_domain` (omit arg → uses `allowed_domains[0]`), `explicit_domain`, `out_of_scope_raises` (ScopeError on `domain="personal"`), `missing_index_returns_empty` (empty vault dir → `text == "(no index yet)"`).

- [ ] **Step 2: Implement**

```python
"""list_index tool — read a domain's index.md."""

from __future__ import annotations

from typing import Any

from brain_core.chat.tools.base import ChatTool, ToolContext, ToolResult
from brain_core.vault.frontmatter import parse as parse_frontmatter
from brain_core.vault.paths import ScopeError, scope_guard


class ListIndexTool:
    name = "list_index"
    description = "Read <domain>/index.md. Defaults to first allowed domain."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"domain": {"type": "string"}},
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        domain = str(args.get("domain") or ctx.allowed_domains[0])
        if domain not in ctx.allowed_domains:
            raise ScopeError(f"domain {domain!r} not in allowed {ctx.allowed_domains}")
        index_path = scope_guard(
            ctx.vault_root / domain / "index.md",
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        if not index_path.exists():
            return ToolResult(text="(no index yet)", data={"domain": domain, "body": ""})
        raw = index_path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        return ToolResult(text=body, data={"domain": domain, "frontmatter": fm, "body": body})
```

- [ ] **Step 3–5: Run, self-review, commit**

Expected: 4 passed.

```bash
git commit -m "feat(chat): plan 03 task 8 — list_index tool"
```

---

### Task 9 — `list_chats` tool

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/list_chats.py`
- Create: `packages/brain_core/tests/chat/test_tool_list_chats.py`

**Context:** Queries `state.sqlite` `chat_threads` table. Filters: `domain` (must be in allowed), optional `query` text (SQL LIKE on `path`). Returns most-recent 20 by `updated_at DESC`. Per-row: `{thread_id, path, domain, mode, turns, cost_usd, updated_at}`. The table is populated by `persistence.py` in Task 13 — for THIS task, tests insert rows directly via `db.exec(...)` to exercise the query.

- [ ] **Step 1: Write the failing test** — 4 tests. Fixture inserts 3 threads: t1 (research, older), t2 (research, newer, path contains "rag"), t3 (personal). Tests: `lists_in_scope_only` (t3 excluded), `ordered_by_updated_desc` (t2 first), `query_filter` (`query="rag"` → only t2), `personal_domain_rejected` (ScopeError).

- [ ] **Step 2: Implement**

```python
"""list_chats tool — query state.sqlite for chat thread metadata."""

from __future__ import annotations

from typing import Any

from brain_core.chat.tools.base import ChatTool, ToolContext, ToolResult
from brain_core.vault.paths import ScopeError

_LIMIT = 20


class ListChatsTool:
    name = "list_chats"
    description = "List recent chat threads in scope, optionally filtered by substring."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "query": {"type": "string"},
        },
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if ctx.state_db is None:
            raise RuntimeError("list_chats requires state_db in ToolContext")
        domain = args.get("domain")
        if domain and domain not in ctx.allowed_domains:
            raise ScopeError(f"domain {domain!r} not in allowed {ctx.allowed_domains}")
        domains = (domain,) if domain else ctx.allowed_domains
        placeholders = ",".join("?" for _ in domains)
        sql = (
            f"SELECT thread_id, path, domain, mode, turns, cost_usd, updated_at "
            f"FROM chat_threads WHERE domain IN ({placeholders})"
        )
        params: tuple[Any, ...] = tuple(domains)
        if args.get("query"):
            sql += " AND path LIKE ?"
            params = params + (f"%{args['query']}%",)
        sql += f" ORDER BY updated_at DESC LIMIT {_LIMIT}"
        cur = ctx.state_db.exec(sql, params)
        rows = [
            {"thread_id": r[0], "path": r[1], "domain": r[2], "mode": r[3],
             "turns": r[4], "cost_usd": r[5], "updated_at": r[6]}
            for r in cur.fetchall()
        ]
        text = "\n".join(f"- {r['path']} ({r['turns']} turns)" for r in rows) or "(no chats yet)"
        return ToolResult(text=text, data={"threads": rows})
```

- [ ] **Step 3–5: Run, self-review, commit**

Expected: 4 passed.

```bash
git commit -m "feat(chat): plan 03 task 9 — list_chats tool"
```

---

### Task 10 — `propose_note` tool

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/propose_note.py`
- Create: `packages/brain_core/tests/chat/test_tool_propose_note.py`

**Context:**
Brainstorm/Draft modes only. Takes `{path, content, reason}`. Validates path is vault-relative and in scope. Constructs `PatchSet(new_files=[NewFile(...)])`. Stages via `PendingPatchStore.put`. Returns `ToolResult` with `proposed_patch` set. Never writes to the vault.

- [ ] **Step 1: Write the failing test** — 4 tests: `stages_a_pending_patch` (asserts vault unchanged AND `len(pending_store.list()) == 1`), `out_of_scope_path_rejected` (ScopeError), `absolute_path_rejected` (ValueError("vault-relative")), `requires_pending_store` (RuntimeError when `ctx.pending_store is None`).

- [ ] **Step 2: Implement**

```python
"""propose_note tool — stage a new-note patch; never writes to the vault."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brain_core.chat.tools.base import ChatTool, ToolContext, ToolResult
from brain_core.chat.types import ChatMode
from brain_core.vault.paths import scope_guard
from brain_core.vault.types import NewFile, PatchSet


class ProposeNoteTool:
    name = "propose_note"
    description = "Stage a new note for approval. Does NOT write to the vault."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["path", "content", "reason"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if ctx.pending_store is None:
            raise RuntimeError("propose_note requires pending_store in ToolContext")
        raw_path = str(args["path"])
        p = Path(raw_path)
        if p.is_absolute():
            raise ValueError("path must be vault-relative, not absolute")
        scope_guard(
            ctx.vault_root / p,
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        patchset = PatchSet(
            new_files=[NewFile(path=p, content=str(args["content"]))],
            reason=str(args["reason"]),
        )
        envelope = ctx.pending_store.put(
            patchset=patchset,
            source_thread=ctx.source_thread,
            mode=ChatMode(ctx.mode_name),
            tool="propose_note",
            target_path=p,
            reason=str(args["reason"]),
        )
        return ToolResult(
            text=f"Staged new note at {p.as_posix()} (patch {envelope.patch_id}).",
            data={"patch_id": envelope.patch_id, "target_path": p.as_posix()},
            proposed_patch=envelope,
        )
```

- [ ] **Step 3–5: Run, self-review, commit**

Expected: 4 passed. Self-review extras: grep for `VaultWriter`, `write_text`, `open(` in `propose_note.py` — all must be absent.

```bash
git commit -m "feat(chat): plan 03 task 10 — propose_note tool (staged only)"
```

---

### Task 11 — `edit_open_doc` tool

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/tools/edit_open_doc.py`
- Create: `packages/brain_core/tests/chat/test_tool_edit_open_doc.py`

**Context:**
Draft mode only (enforcement of "only in registry when `open_doc_path` is set" is the registry's job in Task 15; this tool guards against `ctx.open_doc_path is None`). Takes `{old, new, reason}` — exact-string replace against the open doc. (Range-based editing is brittle over a plain-text protocol; string replace is what the LLM can reliably emit.) Validates `old` appears **exactly once** in the current doc before staging. Constructs `PatchSet(edits=[Edit(...)])`. Stages via `PendingPatchStore`.

- [ ] **Step 1: Write the failing test** — 3 tests: `stages_an_edit` (asserts doc unchanged + 1 pending patch), `requires_open_doc` (RuntimeError when `ctx.open_doc_path is None`), `old_must_match_exactly_once` — tests both missing (`ValueError("not found")`) and ambiguous (overwrite doc to `"one\ntwo\none\n"`, assert `ValueError("not unique")`).

- [ ] **Step 2: Implement**

```python
"""edit_open_doc tool — stage an exact-string replacement against the session's open doc."""

from __future__ import annotations

from typing import Any

from brain_core.chat.tools.base import ChatTool, ToolContext, ToolResult
from brain_core.chat.types import ChatMode
from brain_core.vault.paths import scope_guard
from brain_core.vault.types import Edit, PatchSet


class EditOpenDocTool:
    name = "edit_open_doc"
    description = "Stage an exact-string replacement against the session's open doc."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "old": {"type": "string"},
            "new": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["old", "new", "reason"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if ctx.open_doc_path is None:
            raise RuntimeError("edit_open_doc requires open_doc_path in ToolContext")
        if ctx.pending_store is None:
            raise RuntimeError("edit_open_doc requires pending_store in ToolContext")
        full = scope_guard(
            ctx.vault_root / ctx.open_doc_path,
            vault_root=ctx.vault_root,
            allowed_domains=ctx.allowed_domains,
        )
        if not full.exists():
            raise FileNotFoundError(f"open doc {ctx.open_doc_path} not found")
        body = full.read_text(encoding="utf-8")
        old = str(args["old"])
        occurrences = body.count(old)
        if occurrences == 0:
            raise ValueError(f"old text not found in {ctx.open_doc_path}")
        if occurrences > 1:
            raise ValueError(f"old text not unique in {ctx.open_doc_path} ({occurrences} matches)")
        patchset = PatchSet(
            edits=[Edit(path=ctx.open_doc_path, old=old, new=str(args["new"]))],
            reason=str(args["reason"]),
        )
        envelope = ctx.pending_store.put(
            patchset=patchset,
            source_thread=ctx.source_thread,
            mode=ChatMode(ctx.mode_name),
            tool="edit_open_doc",
            target_path=ctx.open_doc_path,
            reason=str(args["reason"]),
        )
        return ToolResult(
            text=f"Staged edit to {ctx.open_doc_path.as_posix()} (patch {envelope.patch_id}).",
            data={"patch_id": envelope.patch_id},
            proposed_patch=envelope,
        )
```

- [ ] **Step 3–5: Run, self-review, commit**

Expected: 3 passed.

```bash
git commit -m "feat(chat): plan 03 task 11 — edit_open_doc tool (staged string-replace)"
```

---

**Checkpoint — pause for main-loop review.**

11 tasks landed. Every tool dispatched by Task 16's session loop exists with scope-guard coverage. Main-loop spec + code-quality review checks:

- Every tool's `run()` touching a path passes through `scope_guard`.
- No tool writes the vault — `propose_note` and `edit_open_doc` only stage.
- Tool input schemas shaped correctly for the LLM tool_use API.
- `ToolRegistry.subset(allowlist=...)` ready for Task 15 mode policy wiring.
- Retrieval cache invalidation behaves correctly (most-likely-to-break piece).

---

### Group 3 — Context + persistence (Tasks 12–14)

**Checkpoint after Task 14:** main-loop verifies (a) `VaultWriter` is the ONLY vault-write path (including the new `rename_file` op landed in Task 14), (b) chat threads round-trip losslessly through Markdown, (c) the context cap behaves correctly under oldest-turn trimming, (d) `state.sqlite chat_threads` stays consistent with on-disk thread files.

---

### Task 12 — `brain_core.chat.context` — per-turn context compiler

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/context.py`
- Create: `packages/brain_core/tests/chat/test_context.py`

**Context for the implementer:**
Before every LLM call the session builds the prompt context from four layers: (1) `BRAIN.md` at vault root + mode-specific system prompt, (2) `<domain>/index.md` for every in-scope domain, (3) any notes the model explicitly `read_note`'d in prior turns (kept in `read_notes` dict keyed by path), (4) the turn history + new user message. If the total estimated tokens exceed `config.context_cap_tokens`, trim oldest turns **before** the last user message until under the cap. Never trim BRAIN.md, index.md, or read_notes — the spec's hard cap is an overflow backstop, not a search-summary mechanism.

**Token estimation** is a simple `len(text) // 4` heuristic — close enough for a local tool. No `tiktoken` dep. The actual provider will truncate on the wire if our estimate is wrong; that's acceptable.

`BRAIN.md` may not exist in a fresh vault. Missing → empty string, not an error. (A setup wizard step in Plan 08 will seed it.)

- [ ] **Step 1: Write the failing test**

`packages/brain_core/tests/chat/test_context.py` — 7 tests:

```python
"""Tests for brain_core.chat.context.ContextCompiler."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from brain_core.chat.context import ContextCompiler, CompiledContext
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "index.md").write_text("# research index\n- [[karpathy]]\n", encoding="utf-8")
    (tmp_path / "BRAIN.md").write_text("# BRAIN\n\nYou are brain.\n", encoding="utf-8")
    return tmp_path


def _turn(role: TurnRole, content: str) -> ChatTurn:
    return ChatTurn(role=role, content=content, created_at=datetime(2026, 4, 14, tzinfo=UTC))


def test_compiles_brain_md_and_index(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="You are ASK mode.")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    ctx = compiler.compile(cfg, turns=[], read_notes={}, user_message="hello")
    assert "You are brain." in ctx.system
    assert "You are ASK mode." in ctx.system
    assert "# research index" in ctx.system


def test_missing_brain_md_is_empty(tmp_path: Path) -> None:
    (tmp_path / "research").mkdir()
    compiler = ContextCompiler(vault_root=tmp_path, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    ctx = compiler.compile(cfg, turns=[], read_notes={}, user_message="hi")
    assert "BRAIN" not in ctx.system or ctx.system.count("BRAIN") == 0
    assert "ASK" in ctx.system


def test_read_notes_included_as_system_blocks(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    ctx = compiler.compile(
        cfg,
        turns=[],
        read_notes={Path("research/notes/karpathy.md"): "# Karpathy\n\nLLM wiki pattern."},
        user_message="q",
    )
    assert "research/notes/karpathy.md" in ctx.system
    assert "LLM wiki pattern" in ctx.system


def test_turns_and_user_message_in_messages(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    turns = [
        _turn(TurnRole.USER, "first question"),
        _turn(TurnRole.ASSISTANT, "first answer"),
    ]
    ctx = compiler.compile(cfg, turns=turns, read_notes={}, user_message="second question")
    assert ctx.messages[0] == {"role": "user", "content": "first question"}
    assert ctx.messages[1] == {"role": "assistant", "content": "first answer"}
    assert ctx.messages[-1] == {"role": "user", "content": "second question"}


def test_system_turn_becomes_assistant_note(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    turns = [_turn(TurnRole.SYSTEM, "mode changed: ask -> brainstorm")]
    ctx = compiler.compile(cfg, turns=turns, read_notes={}, user_message="q")
    assert any("mode changed" in m["content"] for m in ctx.messages)


def test_context_cap_trims_oldest_turns(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",), context_cap_tokens=50)
    # Each big turn is ~80 tokens under len//4 estimation.
    big = "word " * 320  # ~1600 chars => ~400 tokens
    turns = [
        _turn(TurnRole.USER, "ancient turn 1"),
        _turn(TurnRole.ASSISTANT, big),
        _turn(TurnRole.USER, "recent turn"),
    ]
    ctx = compiler.compile(cfg, turns=turns, read_notes={}, user_message="now")
    # Oldest turns trimmed; "now" and at least the most recent turn survive.
    contents = [m["content"] for m in ctx.messages]
    assert "now" in contents
    assert "ancient turn 1" not in contents


def test_cap_never_trims_user_message_or_system(vault: Path) -> None:
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",), context_cap_tokens=5)
    ctx = compiler.compile(cfg, turns=[], read_notes={}, user_message="MUST SURVIVE")
    assert any("MUST SURVIVE" in m["content"] for m in ctx.messages)
    assert "You are ASK mode." in ctx.system
```

Run: `uv run pytest packages/brain_core/tests/chat/test_context.py -v` → FAIL (no module).

- [ ] **Step 2: Implement `context.py`**

```python
"""ContextCompiler — build the prompt context for a single chat turn.

Layers (in order):
    1. BRAIN.md (if present) + mode-specific system prompt
    2. <domain>/index.md for every in-scope domain
    3. Explicitly-read notes from prior turns
    4. Turn history + new user message (with oldest-turn trimming if over cap)

Token estimation is len(text)//4 — close enough for a local tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain_core.chat.types import ChatSessionConfig, ChatTurn, TurnRole


def _est_tokens(text: str) -> int:
    return len(text) // 4


@dataclass(frozen=True)
class CompiledContext:
    system: str
    messages: list[dict[str, Any]]
    estimated_tokens: int


class ContextCompiler:
    def __init__(self, vault_root: Path, mode_prompt: str) -> None:
        self.vault_root = vault_root
        self.mode_prompt = mode_prompt

    def compile(
        self,
        config: ChatSessionConfig,
        turns: list[ChatTurn],
        read_notes: dict[Path, str],
        user_message: str,
    ) -> CompiledContext:
        system_parts: list[str] = []

        brain_md = self.vault_root / "BRAIN.md"
        if brain_md.exists():
            system_parts.append(brain_md.read_text(encoding="utf-8"))

        system_parts.append(self.mode_prompt)

        for domain in config.domains:
            idx = self.vault_root / domain / "index.md"
            if idx.exists():
                system_parts.append(f"# index: {domain}\n\n{idx.read_text(encoding='utf-8')}")

        for path, body in read_notes.items():
            system_parts.append(f"# note: {path.as_posix()}\n\n{body}")

        system = "\n\n".join(system_parts)

        messages: list[dict[str, Any]] = [
            self._turn_to_message(t) for t in turns
        ]
        messages.append({"role": "user", "content": user_message})

        # Apply hard cap: trim oldest turns (leaving the new user message and any trailing assistant/tool messages).
        cap = config.context_cap_tokens
        total = _est_tokens(system) + sum(_est_tokens(m["content"]) for m in messages)
        while total > cap and len(messages) > 1:
            dropped = messages.pop(0)
            total -= _est_tokens(dropped["content"])

        return CompiledContext(system=system, messages=messages, estimated_tokens=total)

    def _turn_to_message(self, turn: ChatTurn) -> dict[str, Any]:
        if turn.role == TurnRole.SYSTEM:
            # System turns (mode switches, scope changes) surface as assistant narration
            # so the LLM sees them in context without needing a third Anthropic role.
            return {"role": "assistant", "content": f"[system] {turn.content}"}
        return {"role": turn.role.value, "content": turn.content}
```

- [ ] **Step 3: Run tests — expect PASS** (7 passed).
- [ ] **Step 4: 12-point self-review.**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(chat): plan 03 task 12 — ContextCompiler (BRAIN.md + index + notes + turns)"
```

---

### Task 13 — `brain_core.chat.persistence` — thread Markdown writer/reader

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/persistence.py`
- Create: `packages/brain_core/tests/chat/test_persistence.py`

**Context for the implementer:**
Per D4a, the chat thread is written as a Markdown file in the vault via `VaultWriter.apply()` after every completed turn. The file lives at `<domain>/chats/<thread_id>.md` where `<thread_id>` starts as `<yyyy-mm-dd>-draft-<short>` and becomes `<yyyy-mm-dd>-<auto-title-slug>` after Task 14's rename. Frontmatter carries `mode`, `scope` (comma-separated domains), `model`, `created`, `updated`, `turns`, `cost_usd`, `filed_to` (optional, for future file-to-wiki action).

Body format: one `## User` / `## Assistant` / `## System` section per turn. Tool calls are rendered as fenced blocks **inside** the Assistant section:

```markdown
## Assistant

I'll search for that.

```tool:search_vault
{"query": "karpathy"}
```
```tool-result:search_vault
- research/notes/karpathy.md — Karpathy
```

Here's what I found...
```

**Update semantics:** every turn flush is a full-file rewrite via `PatchSet(new_files=[NewFile(path, content)])` for the first write, then `PatchSet(edits=[Edit(path, old_body, new_body)])` for subsequent writes. `VaultWriter` already handles atomic temp-and-rename, so crash safety is inherited. Simpler than incremental append because Markdown doesn't have a good append-with-frontmatter-update primitive.

**`state.sqlite` sync:** after every successful `apply()`, upsert the `chat_threads` row via `INSERT OR REPLACE`.

- [ ] **Step 1: Write the failing test** — 7 tests:

```python
"""Tests for brain_core.chat.persistence — thread Markdown writer/reader."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


@pytest.fixture
def env(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    (vault / "research" / "chats").mkdir()
    writer = VaultWriter(vault_root=vault, undo_root=tmp_path / ".brain" / "undo")
    db = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    persistence = ThreadPersistence(vault_root=vault, writer=writer, db=db)
    yield vault, writer, db, persistence
    db.close()


def _turn(role: TurnRole, content: str, *, cost: float = 0.0) -> ChatTurn:
    return ChatTurn(role=role, content=content, created_at=datetime(2026, 4, 14, tzinfo=UTC), cost_usd=cost)


def test_first_write_creates_file_via_vault_writer(env) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    thread_id = "2026-04-14-draft-abc123"
    persistence.write(thread_id=thread_id, config=cfg, turns=[_turn(TurnRole.USER, "hi")])
    path = vault / "research" / "chats" / f"{thread_id}.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "mode: ask" in content
    assert "## User" in content
    assert "hi" in content


def test_second_write_updates_same_file(env) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[_turn(TurnRole.USER, "first")])
    persistence.write(
        thread_id=tid, config=cfg,
        turns=[_turn(TurnRole.USER, "first"), _turn(TurnRole.ASSISTANT, "second")],
    )
    content = (vault / "research" / "chats" / f"{tid}.md").read_text(encoding="utf-8")
    assert content.count("## User") == 1
    assert content.count("## Assistant") == 1
    assert "first" in content and "second" in content


def test_state_db_row_upserted(env) -> None:
    vault, _, db, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.BRAINSTORM, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[
        _turn(TurnRole.USER, "q"), _turn(TurnRole.ASSISTANT, "a", cost=0.02),
    ])
    row = db.exec("SELECT mode, turns, cost_usd FROM chat_threads WHERE thread_id = ?", (tid,)).fetchone()
    assert row == ("brainstorm", 2, 0.02)


def test_tool_calls_rendered_as_fenced_blocks(env) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    turn = ChatTurn(
        role=TurnRole.ASSISTANT,
        content="I found it.",
        created_at=datetime(2026, 4, 14, tzinfo=UTC),
        tool_calls=[{"name": "search_vault", "args": {"query": "x"}, "result_preview": "- r/a.md"}],
        cost_usd=0.01,
    )
    persistence.write(thread_id=tid, config=cfg, turns=[turn])
    content = (vault / "research" / "chats" / f"{tid}.md").read_text(encoding="utf-8")
    assert "```tool:search_vault" in content
    assert "```tool-result:search_vault" in content


def test_system_turn_rendered(env) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[
        _turn(TurnRole.SYSTEM, "mode changed: ask -> brainstorm"),
    ])
    content = (vault / "research" / "chats" / f"{tid}.md").read_text(encoding="utf-8")
    assert "## System" in content
    assert "mode changed" in content


def test_read_round_trip(env) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    tid = "2026-04-14-draft-abc123"
    turns_in = [_turn(TurnRole.USER, "hi"), _turn(TurnRole.ASSISTANT, "hello")]
    persistence.write(thread_id=tid, config=cfg, turns=turns_in)
    loaded = persistence.read(vault / "research" / "chats" / f"{tid}.md")
    assert [t.role for t in loaded.turns] == [TurnRole.USER, TurnRole.ASSISTANT]
    assert loaded.turns[0].content.strip() == "hi"
    assert loaded.turns[1].content.strip() == "hello"
    assert loaded.config.mode == ChatMode.ASK


def test_path_uses_first_domain(env) -> None:
    vault, _, _, persistence = env
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research", "work"))
    tid = "2026-04-14-draft-abc123"
    persistence.write(thread_id=tid, config=cfg, turns=[_turn(TurnRole.USER, "x")])
    # Cross-scope chats land in the first domain's chats/ dir.
    assert (vault / "research" / "chats" / f"{tid}.md").exists()
    assert not (vault / "work" / "chats" / f"{tid}.md").exists()
```

- [ ] **Step 2: Implement `persistence.py`**

Key shape:

```python
"""Chat-thread Markdown writer/reader. All writes flow through VaultWriter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from brain_core.chat.types import ChatMode, ChatSessionConfig, ChatTurn, TurnRole
from brain_core.state.db import StateDB
from brain_core.vault.frontmatter import parse as parse_frontmatter
from brain_core.vault.types import Edit, NewFile, PatchSet
from brain_core.vault.writer import VaultWriter


@dataclass(frozen=True)
class LoadedThread:
    config: ChatSessionConfig
    turns: list[ChatTurn]


class ThreadPersistence:
    def __init__(self, vault_root: Path, writer: VaultWriter, db: StateDB) -> None:
        self.vault_root = vault_root
        self.writer = writer
        self.db = db

    def thread_path(self, thread_id: str, config: ChatSessionConfig) -> Path:
        # First domain wins for path placement; scope stays recorded in frontmatter.
        return Path(config.domains[0]) / "chats" / f"{thread_id}.md"

    def write(
        self,
        thread_id: str,
        config: ChatSessionConfig,
        turns: list[ChatTurn],
    ) -> Path:
        rel = self.thread_path(thread_id, config)
        full = self.vault_root / rel
        body = self._render(thread_id=thread_id, config=config, turns=turns)
        if full.exists():
            patch = PatchSet(
                edits=[Edit(path=rel, old=full.read_text(encoding="utf-8"), new=body)],
                reason=f"chat turn {len(turns)}",
            )
        else:
            patch = PatchSet(
                new_files=[NewFile(path=rel, content=body)],
                reason=f"chat thread {thread_id} created",
            )
        self.writer.apply(patch, allowed_domains=config.domains)
        cost = sum(t.cost_usd for t in turns)
        self.db.exec(
            "INSERT OR REPLACE INTO chat_threads"
            "(thread_id, path, domain, mode, turns, cost_usd, updated_at) VALUES (?,?,?,?,?,?,?)",
            (thread_id, rel.as_posix(), config.domains[0], config.mode.value,
             len(turns), cost, datetime.now(UTC).isoformat()),
        )
        return full

    def read(self, path: Path) -> LoadedThread:
        raw = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        domains = tuple(d.strip() for d in str(fm.get("scope", "")).split(",") if d.strip())
        config = ChatSessionConfig(
            mode=ChatMode(fm["mode"]),
            domains=domains or (path.parent.parent.name,),
            model=fm.get("model", "claude-sonnet-4-6"),
        )
        turns: list[ChatTurn] = []
        for role_name, section in _split_sections(body):
            turns.append(ChatTurn(
                role=TurnRole(role_name.lower()),
                content=section,
                created_at=datetime.fromisoformat(fm.get("updated", datetime.now(UTC).isoformat())),
            ))
        return LoadedThread(config=config, turns=turns)

    def _render(self, *, thread_id: str, config: ChatSessionConfig, turns: list[ChatTurn]) -> str:
        now = datetime.now(UTC).isoformat()
        cost = sum(t.cost_usd for t in turns)
        fm = (
            "---\n"
            f"mode: {config.mode.value}\n"
            f"scope: {','.join(config.domains)}\n"
            f"model: {config.model}\n"
            f"created: {turns[0].created_at.isoformat() if turns else now}\n"
            f"updated: {now}\n"
            f"turns: {len(turns)}\n"
            f"cost_usd: {cost}\n"
            "---\n\n"
            f"# {thread_id}\n\n"
        )
        sections: list[str] = []
        for t in turns:
            header = {"user": "## User", "assistant": "## Assistant", "system": "## System"}[t.role.value]
            body = t.content.strip()
            if t.tool_calls:
                for call in t.tool_calls:
                    name = call.get("name", "unknown")
                    body += (
                        f"\n\n```tool:{name}\n{json.dumps(call.get('args', {}), indent=2)}\n```"
                        f"\n\n```tool-result:{name}\n{call.get('result_preview', '')}\n```"
                    )
            sections.append(f"{header}\n\n{body}")
        return fm + "\n\n".join(sections) + "\n"


_SECTION_RE = re.compile(r"^## (User|Assistant|System)\s*$", re.MULTILINE)


def _split_sections(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    matches = list(_SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((m.group(1), body[start:end].strip()))
    return out
```

- [ ] **Step 3: Run tests** (7 passed).
- [ ] **Step 4: Self-review** — extras: grep for `open(` / `write_text` / `.write(` in `persistence.py`. Only allowed call is `VaultWriter.apply(...)`. `self.db.exec(...)` is fine — `state.sqlite` is not vault content.
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(chat): plan 03 task 13 — ThreadPersistence via VaultWriter + state.sqlite sync"
```

---

### Task 14 — Auto-title: `VaultWriter.rename_file` + `chat.autotitle`

**Owning subagent:** brain-core-engineer + brain-prompt-engineer (autotitle prompt)

**Files:**
- Modify: `packages/brain_core/src/brain_core/vault/writer.py` (add `rename_file` op with undo-log support)
- Modify: `packages/brain_core/tests/vault/test_writer.py` (new tests for `rename_file`)
- Create: `packages/brain_core/src/brain_core/chat/autotitle.py`
- Create: `packages/brain_core/src/brain_core/prompts/chat_autotitle.md`
- Create: `packages/brain_core/tests/chat/test_autotitle.py`

**Context for the implementer — IMPORTANT scope note:**
Spec §6 says "after turn 2, a cheap LLM call produces a 3–6 word title and **renames the file**." `VaultWriter.apply(PatchSet)` currently has no rename operation — `PatchSet` only models `new_files`, `edits`, `index_entries`, `log_entry`. Rather than work around it with delete+create-at-new-path (which `PatchSet` doesn't model either), this task lands a **first-class `VaultWriter.rename_file(src, dst, *, allowed_domains) -> Receipt`** operation with full undo-log support. This is a principled capability addition that later plans (file-to-wiki in Plan 07, note-move operations) will reuse.

This deviates from "Plan 03 never touches Plan 01 code." It's a deliberate exception documented here because the spec demands it. Task 14 is the ONLY task in Plan 03 that modifies `brain_core.vault`.

**Rename semantics:**
- Source and destination must both be inside the vault, both in the same allowed domain (no cross-domain moves — that would bypass scope intent).
- Atomic: `os.replace(src, dst)` on both platforms.
- Undo-log: one record with `op=rename`, `src`, `dst`. Rollback reverses with `os.replace(dst, src)`.
- Destination must not exist (no implicit overwrite).
- Parent of `dst` is created if missing.

**Autotitle prompt:** cheap Haiku-tier call with the turn-2 conversation as input. Must return a single line, 3–6 words, slug-safe (lowercase, ASCII, hyphens). Output schema: `AutoTitleOutput(title: str, slug: str)` with `slug` derived from `title`. VCR cassette deferred per D7a.

**Chat integration:** `AutoTitler.run(session)` is called by `ChatSession` after turn 2. Returns the new thread_id. Session computes the old + new rel paths, calls `vault_writer.rename_file`, updates `state.sqlite chat_threads` row's `path` column, returns new thread_id.

- [ ] **Step 1: Write failing tests for `VaultWriter.rename_file`**

Tests in `test_writer.py` (4 new):
- `rename_file_moves_file_atomically`
- `rename_file_rolls_back_on_failure` (force dst parent to be read-only on mac — or mock `os.replace` to raise)
- `rename_file_rejects_cross_domain` (src=research/, dst=work/ → ScopeError)
- `rename_file_refuses_overwrite` (dst exists → FileExistsError)

- [ ] **Step 2: Implement `rename_file`** on `VaultWriter`:

```python
def rename_file(
    self,
    src: Path,
    dst: Path,
    *,
    allowed_domains: tuple[str, ...],
) -> Receipt:
    src_abs = scope_guard(self.vault_root / src, vault_root=self.vault_root, allowed_domains=allowed_domains)
    dst_abs = scope_guard(self.vault_root / dst, vault_root=self.vault_root, allowed_domains=allowed_domains)
    src_rel = src_abs.relative_to(self.vault_root)
    dst_rel = dst_abs.relative_to(self.vault_root)
    if src_rel.parts[0] != dst_rel.parts[0]:
        raise ScopeError(f"rename across domains not allowed: {src_rel.parts[0]} -> {dst_rel.parts[0]}")
    if not src_abs.exists():
        raise FileNotFoundError(f"source {src} does not exist")
    if dst_abs.exists():
        raise FileExistsError(f"destination {dst} already exists")
    dst_abs.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src_abs, dst_abs)
    undo_id = self._new_undo_id()
    self._write_undo_record(undo_id, [("rename", str(src_rel), str(dst_rel))])
    return Receipt(undo_id=undo_id, applied_files=[dst_rel])
```

(Signature of `_write_undo_record` may need a small extension to accept the op-typed tuple shape. Prefer adding an overload rather than breaking the existing one — belt-and-braces for Plan 02's undo writers.)

- [ ] **Step 3: Run `test_writer.py`** — 4 new green.

- [ ] **Step 4: Write the autotitle prompt**

`packages/brain_core/src/brain_core/prompts/chat_autotitle.md`:
```markdown
You are titling a chat thread. Given the first two turns of a conversation (a user question and the assistant's reply), produce a short, descriptive title.

Constraints:
- 3 to 6 words
- No punctuation except hyphens
- Lowercase ASCII
- Must capture the topic, not the user's exact phrasing

Respond with JSON matching this schema:
{
  "title": "short human-readable title",
  "slug": "same title as kebab-case-slug"
}

Turns:
{{turns}}
```

- [ ] **Step 5: Write failing tests for `autotitle.py`** — 3 tests using `FakeLLMProvider`:

```python
def test_run_returns_validated_title(fake_llm):
    fake_llm.queue_response('{"title": "karpathy llm wiki", "slug": "karpathy-llm-wiki"}')
    autotitler = AutoTitler(llm=fake_llm, prompt_loader=real_prompt_loader)
    result = autotitler.run([user_turn, assistant_turn])
    assert result.title == "karpathy llm wiki"
    assert result.slug == "karpathy-llm-wiki"


def test_invalid_json_raises_autotitle_error(fake_llm):
    fake_llm.queue_response("not json at all")
    with pytest.raises(AutoTitleError):
        AutoTitler(llm=fake_llm, prompt_loader=real_prompt_loader).run([user_turn, assistant_turn])


def test_slug_mismatch_raises(fake_llm):
    fake_llm.queue_response('{"title": "foo bar", "slug": "completely-different"}')
    with pytest.raises(AutoTitleError, match="slug"):
        AutoTitler(llm=fake_llm, prompt_loader=real_prompt_loader).run([user_turn, assistant_turn])
```

- [ ] **Step 6: Implement `autotitle.py`**

```python
"""Auto-title: after turn 2, ask a cheap LLM to summarize the thread in 3-6 words."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from brain_core.chat.types import ChatTurn
from brain_core.llm.provider import LLMProvider
from brain_core.prompts.loader import PromptLoader


class AutoTitleError(ValueError):
    pass


@dataclass(frozen=True)
class AutoTitleResult:
    title: str
    slug: str


_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AutoTitler:
    def __init__(self, llm: LLMProvider, prompt_loader: PromptLoader, model: str = "claude-haiku-4-5") -> None:
        self.llm = llm
        self.prompt_loader = prompt_loader
        self.model = model

    def run(self, turns: list[ChatTurn]) -> AutoTitleResult:
        prompt = self.prompt_loader.load("chat_autotitle").render(
            turns="\n\n".join(f"{t.role.value}: {t.content}" for t in turns[:2])
        )
        raw = self.llm.complete(prompt, model=self.model, max_tokens=64)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AutoTitleError(f"autotitle returned non-JSON: {raw[:100]}") from exc
        title = str(data.get("title", "")).strip()
        slug = str(data.get("slug", "")).strip()
        if not title or not slug:
            raise AutoTitleError(f"autotitle missing fields: {data}")
        if not _SLUG_RE.match(slug):
            raise AutoTitleError(f"autotitle slug not kebab-case: {slug!r}")
        expected_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if slug != expected_slug:
            raise AutoTitleError(f"autotitle slug {slug!r} does not match title {title!r}")
        return AutoTitleResult(title=title, slug=slug)
```

(Verify the actual signature of `LLMProvider.complete` / `PromptLoader.load` against Plan 02 code before shipping — adjust accordingly if the real API differs.)

- [ ] **Step 7: Run all Task 14 tests**

```bash
uv run pytest packages/brain_core/tests/vault/test_writer.py packages/brain_core/tests/chat/test_autotitle.py -v
```
Expected: 4 new writer tests + 3 autotitle tests = 7 new green.

- [ ] **Step 8: 12-point self-review**

Extras:
- Every existing `VaultWriter` test still passes (`rename_file` is additive).
- Undo-log format backward compatible (old records still parse).
- `autotitle.py` has zero direct Anthropic imports.

- [ ] **Step 9: Commit**

Two commits — one for the writer op, one for autotitle:

```bash
git add packages/brain_core/src/brain_core/vault/writer.py \
        packages/brain_core/tests/vault/test_writer.py
git commit -m "feat(vault): add VaultWriter.rename_file with undo support (plan 03 task 14a)"

git add packages/brain_core/src/brain_core/chat/autotitle.py \
        packages/brain_core/src/brain_core/prompts/chat_autotitle.md \
        packages/brain_core/tests/chat/test_autotitle.py
git commit -m "feat(chat): plan 03 task 14b — AutoTitler with chat_autotitle prompt"
```

---

**Checkpoint — pause for main-loop review.**

14 tasks landed. Persistence, rename, context, auto-title all working in isolation. The next group (15–16) wires them together into `ChatSession`.

---

### Group 4 — LLM extension + session loop (Tasks 15–18)

**Checkpoint after Task 15** (new): main-loop reviews the `LLMProvider` protocol extension in isolation. This is the highest-risk change in Plan 03 — it touches Plan 01/02 code additively. Every Plan 02 test must still pass unchanged.

**Checkpoint after Task 18**: first end-to-end "the chat actually runs against FakeLLMProvider" milestone.

---

### Task 15 — `LLMProvider` tool_use extension

**Owning subagent:** brain-core-engineer (implementation) + brain-test-engineer (regression sweep)

**Files:**
- Modify: `packages/brain_core/src/brain_core/llm/types.py` (additive — `ToolDef`, `ToolUse`, `ToolResultBlock`, `TextBlock`, `ContentBlock` union; `LLMRequest.tools`, `LLMResponse.tool_uses`, `LLMMessage.content` union; `LLMStreamChunk` tool events)
- Modify: `packages/brain_core/src/brain_core/llm/fake.py` (add `queue_tool_use(tool_uses=..., text="")` scripting)
- Modify: `packages/brain_core/src/brain_core/llm/providers/anthropic.py` (pass `tools=` through, map `tool_use`/`tool_result` both directions)
- Create: `packages/brain_core/tests/llm/test_tool_use_types.py`
- Create: `packages/brain_core/tests/llm/test_fake_tool_use.py`
- Modify: `packages/brain_core/tests/llm/test_anthropic.py` (if a unit-level test exists; add a mocked-SDK case for tool_use) — if the provider is only cassette-tested, land that cassette change in Task 21 instead

**Context for the implementer — read this before writing any code:**

This task **additively** extends `LLMProvider`. Rule: **every existing Plan 02 call site must keep working without modification.** Concretely:

1. `LLMRequest.tools` defaults to `[]`. When `tools=[]`, providers MUST behave exactly as today. Regression test: run the full `brain_core` test suite with zero changes to any summarize/integrate/classify call site and confirm no failures.
2. `LLMResponse.content` stays typed as `str`. When the provider responds with plain text (today's case), `content` is the same string it always was. Plan 02 callers read `response.content` as a string and that still works.
3. A new `LLMResponse.tool_uses: list[ToolUse] = []` field carries tool-use blocks when `tools` was non-empty. Plan 02 callers never look at it.
4. `LLMMessage.content` becomes a `str | list[ContentBlock]` union. Plan 02 call sites that pass `content="..."` (string) keep working. Plan 03 call sites pass a `list[ContentBlock]` when sending tool_result blocks back. Pydantic v2 handles the discriminated union natively.
5. `LLMStreamChunk` gains optional tool_use fields: `tool_use_start: ToolUseStart | None`, `tool_use_input_delta: str | None`, `tool_use_stop_id: str | None`. Text-only streams leave them `None`.

**New types** (in `llm/types.py`, additive — do NOT modify existing types except to add the `tools`, `tool_uses`, and content-union fields):

```python
class ToolDef(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolUse(BaseModel):
    id: str
    name: str
    input: dict[str, Any]


class TextBlock(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    kind: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    kind: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="kind"),
]
```

Then modify existing types:

```python
class LLMMessage(BaseModel):
    role: Role
    content: str | list[ContentBlock]  # union — str for plain text, list for tool-use turns


class LLMRequest(BaseModel):
    model: str
    messages: list[LLMMessage]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    stop_sequences: list[str] = Field(default_factory=list)
    tools: list[ToolDef] = Field(default_factory=list)  # NEW


class LLMResponse(BaseModel):
    model: str
    content: str  # still a string; see stop_reason=="tool_use" for tool calls
    usage: TokenUsage
    stop_reason: str | None = None
    tool_uses: list[ToolUse] = Field(default_factory=list)  # NEW


class ToolUseStart(BaseModel):
    id: str
    name: str


class LLMStreamChunk(BaseModel):
    delta: str = ""
    usage: TokenUsage | None = None
    done: bool = False
    tool_use_start: ToolUseStart | None = None   # NEW
    tool_use_input_delta: str | None = None      # NEW
    tool_use_stop_id: str | None = None          # NEW
```

**Stop-reason convention:** when the model emits tool_use blocks, `LLMResponse.stop_reason == "tool_use"`. `ChatSession` in Task 17 uses that to decide whether to loop (dispatch tools, feed results back) or terminate the turn.

**FakeLLMProvider extension:** add `queue_tool_use(tool_uses: list[ToolUse], text: str = "", *, stop_reason: str = "tool_use")` alongside the existing `queue_response(text)`. Also add `queue_stream_tool_use(...)` for streaming tests.

**AnthropicProvider wiring:** pass `tools=[t.model_dump() for t in request.tools]` through to `anthropic.messages.create`. When iterating the response, collect `content_block` entries of type `"tool_use"` into `tool_uses`. When iterating a stream, emit `tool_use_start` on `content_block_start` with type `tool_use`, `tool_use_input_delta` on `input_json_delta`, `tool_use_stop_id` on matching `content_block_stop`.

- [ ] **Step 1: Write the failing tests** — in `test_tool_use_types.py`:

```python
"""Additive tool_use support on LLM types."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from brain_core.llm.types import (
    ContentBlock,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TextBlock,
    TokenUsage,
    ToolDef,
    ToolResultBlock,
    ToolUse,
    ToolUseBlock,
    ToolUseStart,
)


def test_request_defaults_tools_empty() -> None:
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="hi")])
    assert req.tools == []


def test_request_accepts_tool_defs() -> None:
    td = ToolDef(name="search_vault", description="x",
                 input_schema={"type": "object", "properties": {"q": {"type": "string"}}})
    req = LLMRequest(model="m", messages=[LLMMessage(role="user", content="hi")], tools=[td])
    assert req.tools[0].name == "search_vault"


def test_response_defaults_tool_uses_empty() -> None:
    resp = LLMResponse(model="m", content="hi", usage=TokenUsage(input_tokens=1, output_tokens=1))
    assert resp.tool_uses == []
    assert resp.content == "hi"  # existing Plan 02 shape unchanged


def test_response_with_tool_uses() -> None:
    resp = LLMResponse(
        model="m", content="", usage=TokenUsage(input_tokens=5, output_tokens=3),
        stop_reason="tool_use",
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "x"})],
    )
    assert resp.stop_reason == "tool_use"
    assert resp.tool_uses[0].input == {"query": "x"}


def test_message_accepts_string_content_plan02_shape() -> None:
    m = LLMMessage(role="user", content="plain text")
    assert m.content == "plain text"


def test_message_accepts_content_block_list() -> None:
    blocks: list[ContentBlock] = [
        TextBlock(text="hello"),
        ToolResultBlock(tool_use_id="tu_1", content="- a.md\n- b.md"),
    ]
    m = LLMMessage(role="user", content=blocks)
    assert isinstance(m.content, list)
    assert m.content[0].kind == "text"
    assert m.content[1].kind == "tool_result"


def test_content_block_discriminator_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        LLMMessage.model_validate({"role": "user", "content": [{"kind": "nope", "x": 1}]})


def test_stream_chunk_tool_use_events() -> None:
    chunk = LLMStreamChunk(tool_use_start=ToolUseStart(id="tu_1", name="search_vault"))
    assert chunk.tool_use_start is not None
    assert chunk.tool_use_start.name == "search_vault"

    chunk2 = LLMStreamChunk(tool_use_input_delta='{"query": "x"}')
    assert chunk2.tool_use_input_delta == '{"query": "x"}'

    chunk3 = LLMStreamChunk(tool_use_stop_id="tu_1", done=False)
    assert chunk3.tool_use_stop_id == "tu_1"
```

Then in `test_fake_tool_use.py`:

```python
"""FakeLLMProvider tool_use scripting."""

import pytest

from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import (
    ContentBlock,
    LLMMessage,
    LLMRequest,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUse,
)


@pytest.mark.asyncio
async def test_queue_tool_use_non_streaming() -> None:
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "x"})],
        text="",
    )
    req = LLMRequest(
        model="m",
        messages=[LLMMessage(role="user", content="hi")],
        tools=[ToolDef(name="search_vault", description="x", input_schema={})],
    )
    resp = await fake.complete(req)
    assert resp.stop_reason == "tool_use"
    assert resp.tool_uses[0].name == "search_vault"
    assert resp.tool_uses[0].input == {"query": "x"}


@pytest.mark.asyncio
async def test_queue_response_still_works_for_plan02_callers() -> None:
    fake = FakeLLMProvider()
    fake.queue_response("plain summary")
    req = LLMRequest(model="m", messages=[LLMMessage(role="user", content="hi")])
    resp = await fake.complete(req)
    assert resp.content == "plain summary"
    assert resp.tool_uses == []


@pytest.mark.asyncio
async def test_tool_result_round_trip_shape() -> None:
    fake = FakeLLMProvider()
    fake.queue_response("acknowledged")
    blocks: list[ContentBlock] = [ToolResultBlock(tool_use_id="tu_1", content="a.md, b.md")]
    req = LLMRequest(
        model="m",
        messages=[
            LLMMessage(role="user", content="first"),
            LLMMessage(role="assistant", content=[TextBlock(text="calling tool")]),
            LLMMessage(role="user", content=blocks),
        ],
    )
    resp = await fake.complete(req)
    assert resp.content == "acknowledged"
```

- [ ] **Step 2: Update `types.py`** with the additive changes shown above. Regenerate every discriminated-union test above passes.

- [ ] **Step 3: Update `FakeLLMProvider`** — `queue_tool_use` appends a scripted response that `complete()` returns as `LLMResponse(content="", tool_uses=[...], stop_reason="tool_use")`. Streaming variant (`queue_stream_tool_use`) is deferred unless Task 17 needs it — make it a simple loop that emits `tool_use_start`, several `tool_use_input_delta` slices of the JSON-encoded input, then `tool_use_stop_id`, then `done=True`.

- [ ] **Step 4: Update `AnthropicProvider`** — pass `tools=` through, map response blocks to `tool_uses`. For the stream path, translate SDK events to our `LLMStreamChunk` fields. Keep the existing non-tool path identical. If the provider file has inline unit tests, extend them; otherwise rely on Task 21's VCR cassettes.

- [ ] **Step 5: Run the entire `brain_core` test suite — regression gate**

```bash
uv run pytest packages/brain_core -q
```

Expected: **every existing test still green.** Plus the ~10 new tests from Task 15. This is the hard regression gate — the whole point of "additive change" is Plan 02 is untouched. If any summarize/integrate/classify test fails, STOP and investigate.

- [ ] **Step 6: 12-point self-review**

Extras:
- grep for any call site that reads `response.content` expecting a string — confirm they still get a string (non-tool case).
- grep for any `LLMMessage(content=...)` call — confirm existing string-passing sites are untouched.
- mypy strict must pass on the discriminated-union types (Pydantic v2 + `Annotated[..., Field(discriminator="kind")]`).

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(llm): plan 03 task 15 — additive tool_use extension to LLMProvider"
```

---

### Task 16 — `brain_core.chat.modes` + mode prompts + `ChatTool → ToolDef` converter

**Owning subagent:** brain-prompt-engineer (prompts) + brain-core-engineer (modes module)

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/modes.py`
- Create: `packages/brain_core/src/brain_core/prompts/chat_ask.md`
- Create: `packages/brain_core/src/brain_core/prompts/chat_brainstorm.md`
- Create: `packages/brain_core/src/brain_core/prompts/chat_draft.md`
- Create: `packages/brain_core/tests/chat/test_modes.py`

**Context:**
A pure-data mode policy table + three prompt files + a helper to turn a `ChatTool` into an `LLMProvider` `ToolDef`. No runtime logic beyond table lookup and schema mapping.

**Mode policy table** (per spec §6):

| Mode | Tool allowlist | Temperature | Prompt file |
|---|---|---|---|
| ASK | search_vault, read_note, list_index, list_chats | 0.2 | chat_ask.md |
| BRAINSTORM | search_vault, read_note, list_index, list_chats, propose_note | 0.8 | chat_brainstorm.md |
| DRAFT | search_vault, read_note, list_index, list_chats, propose_note, edit_open_doc | 0.4 | chat_draft.md |

The Draft allowlist includes `edit_open_doc`; the session loop in Task 17 is responsible for removing `edit_open_doc` from the effective registry when `open_doc_path is None` (spec D5a).

**Prompt files** — brief, opinionated. Key requirements per spec:
- **Ask**: "Answer from wiki with citations. Refuse to speculate beyond sources." Must cite `[[note-slug]]` for every claim. If the search returns no results, say so rather than guessing.
- **Brainstorm**: "Push back, propose alternatives, ask Socratic questions, speculate when clearly marked as such." Staged patches via `propose_note` preferred over long assistant messages when the user is clearly trying to capture something.
- **Draft**: "Collaborate on the open document. The wiki is background context; the open doc is the focus."

Each prompt file is a plain Markdown system prompt with no template variables (the session compiler prepends BRAIN.md, indices, and read-notes around it).

- [ ] **Step 1: Write the failing test** — 6 tests:

```python
"""Tests for brain_core.chat.modes."""

from __future__ import annotations

from brain_core.chat.modes import MODES, ModePolicy, tool_to_tooldef
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.chat.types import ChatMode
from brain_core.llm.types import ToolDef


def test_all_modes_present() -> None:
    assert set(MODES.keys()) == {ChatMode.ASK, ChatMode.BRAINSTORM, ChatMode.DRAFT}


def test_ask_policy() -> None:
    p = MODES[ChatMode.ASK]
    assert p.temperature == 0.2
    assert "propose_note" not in p.tool_allowlist
    assert "edit_open_doc" not in p.tool_allowlist
    assert "search_vault" in p.tool_allowlist
    assert p.prompt_file == "chat_ask.md"


def test_brainstorm_adds_propose_note() -> None:
    p = MODES[ChatMode.BRAINSTORM]
    assert p.temperature == 0.8
    assert "propose_note" in p.tool_allowlist
    assert "edit_open_doc" not in p.tool_allowlist


def test_draft_adds_edit_open_doc() -> None:
    p = MODES[ChatMode.DRAFT]
    assert p.temperature == 0.4
    assert "propose_note" in p.tool_allowlist
    assert "edit_open_doc" in p.tool_allowlist


def test_tool_to_tooldef() -> None:
    tool = SearchVaultTool()
    td = tool_to_tooldef(tool)
    assert isinstance(td, ToolDef)
    assert td.name == "search_vault"
    assert td.description == tool.description
    assert td.input_schema == tool.input_schema


def test_prompts_exist() -> None:
    from brain_core.prompts.loader import PromptLoader
    loader = PromptLoader()
    for fname in ("chat_ask", "chat_brainstorm", "chat_draft"):
        tmpl = loader.load(fname)
        assert len(tmpl.raw) > 100  # not empty stub
```

- [ ] **Step 2: Implement `modes.py`**

```python
"""Chat mode policy — pure data table + ChatTool → ToolDef converter."""

from __future__ import annotations

from dataclasses import dataclass

from brain_core.chat.tools.base import ChatTool
from brain_core.chat.types import ChatMode
from brain_core.llm.types import ToolDef


@dataclass(frozen=True)
class ModePolicy:
    mode: ChatMode
    tool_allowlist: tuple[str, ...]
    temperature: float
    prompt_file: str


_READ_TOOLS = ("search_vault", "read_note", "list_index", "list_chats")

MODES: dict[ChatMode, ModePolicy] = {
    ChatMode.ASK: ModePolicy(
        mode=ChatMode.ASK,
        tool_allowlist=_READ_TOOLS,
        temperature=0.2,
        prompt_file="chat_ask.md",
    ),
    ChatMode.BRAINSTORM: ModePolicy(
        mode=ChatMode.BRAINSTORM,
        tool_allowlist=(*_READ_TOOLS, "propose_note"),
        temperature=0.8,
        prompt_file="chat_brainstorm.md",
    ),
    ChatMode.DRAFT: ModePolicy(
        mode=ChatMode.DRAFT,
        tool_allowlist=(*_READ_TOOLS, "propose_note", "edit_open_doc"),
        temperature=0.4,
        prompt_file="chat_draft.md",
    ),
}


def tool_to_tooldef(tool: ChatTool) -> ToolDef:
    return ToolDef(
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
    )
```

- [ ] **Step 3: Write the three prompt files** (each ≥ 100 chars, per spec §6 mode descriptions; see the context block above). Keep them direct and opinionated.

- [ ] **Step 4: Run tests + 12-point self-review** (6 tests pass).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(chat): plan 03 task 16 — mode policy + Ask/Brainstorm/Draft prompts"
```

---

### Task 17 — `ChatSession` event loop (was 16A)

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/session.py`
- Create: `packages/brain_core/tests/chat/test_session_loop.py`

**Context for the implementer:**
This task lands the **pure event loop only** — no persistence, no autotitle. That wiring is Task 18. This split is per the Plan 02 Task 17A/17B lesson: the event loop is complex enough that persistence failures would muddy loop debugging.

**Shape:** `ChatSession` is an async class with a single public method `turn(user_message: str) -> AsyncIterator[ChatEvent]`. Internally:

1. Compile the context (ContextCompiler.compile).
2. Build the `LLMRequest` with tools from the mode-filtered registry, temperature from mode policy.
3. Stream the response. Emit `ChatEvent(DELTA, {"text": ...})` for each text delta. Buffer tool_use blocks as they stream.
4. When the stream ends with `stop_reason == "tool_use"`:
   - For each tool_use: emit `TOOL_CALL` event, dispatch via `ToolRegistry.get(name).run(args, ctx)`, catch exceptions, emit `TOOL_RESULT` event, append a `ToolResultBlock` to the next message in `messages`.
   - Loop back to step 3 with the updated messages list. Cap at 10 tool-call rounds per turn (safety rail).
   - If a tool emitted a `proposed_patch`, emit `PATCH_PROPOSED` with the envelope.
5. When the stream ends with any other `stop_reason`: emit `TURN_END` with final assistant text + total tokens/cost for the turn, return.
6. On any exception: emit `ERROR` event with a plain-English message and re-raise.

**What this task does NOT do:**
- Persist the turn to disk (Task 18).
- Call autotitle after turn 2 (Task 18).
- Update `state.sqlite` chat_threads (Task 18).
- Have a CLI in front of it (Task 20).

**Open-doc handling:** at session construction, if `config.open_doc_path is None`, the session filters `edit_open_doc` OUT of its effective tool registry (belt-and-braces beyond the mode allowlist).

**Cost accounting:** each `LLMResponse.usage` is translated to a cost via `brain_core.cost` (existing from Plan 01). Emit `COST_UPDATE` event after each LLM round with running session cost.

- [ ] **Step 1: Write the failing test — ~8 tests** covering: single-turn no-tool (FakeLLM queues plain response, expect DELTA + TURN_END), single-tool-call (queue tool_use → expect TOOL_CALL + TOOL_RESULT + second stream → TURN_END), tool error (tool raises → TOOL_RESULT with `is_error`), propose_note emits PATCH_PROPOSED, 10-round safety cap (queue 11 tool_uses → expect TURN_END with error flag), ERROR event on unexpected exception, `edit_open_doc` filtered out when `open_doc_path` is None, mode-allowlist filtering applied (Ask mode has no propose_note even if registered).

Key test fixture:

```python
@pytest.fixture
def session_env(tmp_path, fake_llm):
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    (vault / "research" / "index.md").write_text("# research\n- [[foo]]\n", encoding="utf-8")
    (vault / "research" / "notes").mkdir()
    (vault / "research" / "notes" / "foo.md").write_text("---\ntitle: Foo\n---\nfoo body", encoding="utf-8")
    db = StateDB.open(tmp_path / "state.sqlite")
    registry = ToolRegistry()
    registry.register(SearchVaultTool())
    registry.register(ReadNoteTool())
    registry.register(ListIndexTool())
    registry.register(ListChatsTool())
    registry.register(ProposeNoteTool())
    registry.register(EditOpenDocTool())
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(("research",))
    pending = PendingPatchStore(tmp_path / ".brain" / "pending")
    compiler = ContextCompiler(vault_root=vault, mode_prompt="ASK")
    cfg = ChatSessionConfig(mode=ChatMode.ASK, domains=("research",))
    session = ChatSession(
        config=cfg,
        llm=fake_llm,
        compiler=compiler,
        registry=registry,
        retrieval=retrieval,
        pending_store=pending,
        state_db=db,
        vault_root=vault,
        thread_id="2026-04-14-draft-test0001",
    )
    yield session, fake_llm
    db.close()
```

Example test:

```python
@pytest.mark.asyncio
async def test_single_turn_no_tool(session_env):
    session, fake_llm = session_env
    fake_llm.queue_stream_text("Hello there.")
    events = [e async for e in session.turn("hi")]
    kinds = [e.kind for e in events]
    assert ChatEventKind.DELTA in kinds
    assert kinds[-1] == ChatEventKind.TURN_END
```

- [ ] **Step 2: Implement `session.py`**

Signature:

```python
class ChatSession:
    MAX_TOOL_ROUNDS = 10

    def __init__(
        self,
        config: ChatSessionConfig,
        llm: LLMProvider,
        compiler: ContextCompiler,
        registry: ToolRegistry,
        retrieval: BM25VaultIndex,
        pending_store: PendingPatchStore,
        state_db: StateDB,
        vault_root: Path,
        thread_id: str,
    ) -> None: ...

    async def turn(self, user_message: str) -> AsyncIterator[ChatEvent]: ...
```

Effective registry = registry filtered by mode allowlist AND (if `config.open_doc_path is None`) minus `edit_open_doc`. **Extract this filter into a private method `_build_effective_registry(self) -> ToolRegistry`** so Task 18's `switch_mode` / `set_open_doc` helpers can re-invoke it after config mutation. Store the result as `self._effective_registry` and use it in the turn loop. ToolContext is built once per turn (since it's constant across tool-call rounds within a turn). The `ChatTurn` list is kept in `self._turns` on the instance — Task 18 will read it for persistence.

- [ ] **Step 3–5: Run tests + self-review + commit** (~8 passed).

```bash
git commit -m "feat(chat): plan 03 task 17 — ChatSession async event loop (no persistence yet)"
```

---

### Task 18 — `ChatSession` persistence + autotitle wiring (was 16B)

**Owning subagent:** brain-core-engineer

**Files:**
- Modify: `packages/brain_core/src/brain_core/chat/session.py` (add `persistence` + `autotitler` constructor params, write after each turn, rename after turn 2)
- Create: `packages/brain_core/tests/chat/test_session_persistence.py`

**Context for the implementer:**
Add `persistence: ThreadPersistence` and `autotitler: AutoTitler | None` to `ChatSession.__init__`. After each `turn()` completes (in the same async method, just before yielding TURN_END), call `persistence.write(thread_id, config, self._turns)`. After turn 2 (detected when `len(self._turns) == 4` — user-assistant-user-assistant), call `autotitler.run(self._turns)`, compute the new thread_id (`<yyyy-mm-dd>-<slug>-<short>`), call `vault_writer.rename_file(old_rel, new_rel, allowed_domains=config.domains)`, update `self.thread_id`, and update `state.sqlite` by deleting the old row + inserting the new (since `thread_id` is the primary key). `autotitler is None` disables the autotitle step — used by tests that don't want to exercise it.

**Tricky bit — path update ordering:** `persistence.write()` uses `self.thread_id` to compute the path. After autotitle, the new `thread_id` must propagate BEFORE the next turn's write so that turn 3 writes to the new path. Handle by: (1) write turn 2 under old name, (2) autotitle, (3) rename file on disk, (4) update `self.thread_id`, (5) state.sqlite DELETE old + INSERT new. If rename or state update fails, roll back `self.thread_id` to the old value and re-raise.

- [ ] **Step 1: Write failing tests** — 5 tests:

```python
@pytest.mark.asyncio
async def test_turn_persists_thread_markdown(persistent_session):
    session, fake_llm, vault = persistent_session
    fake_llm.queue_stream_text("hello")
    async for _ in session.turn("hi"):
        pass
    assert (vault / "research" / "chats" / f"{session.thread_id}.md").exists()


@pytest.mark.asyncio
async def test_turn_2_triggers_autotitle_and_rename(persistent_session):
    session, fake_llm, vault = persistent_session
    fake_llm.queue_stream_text("answer 1")
    async for _ in session.turn("q1"):
        pass
    old_thread_id = session.thread_id

    fake_llm.queue_stream_text("answer 2")
    fake_llm.queue_response('{"title": "llm wiki basics", "slug": "llm-wiki-basics"}')
    async for _ in session.turn("q2"):
        pass

    assert session.thread_id != old_thread_id
    assert "llm-wiki-basics" in session.thread_id
    assert not (vault / "research" / "chats" / f"{old_thread_id}.md").exists()
    assert (vault / "research" / "chats" / f"{session.thread_id}.md").exists()


@pytest.mark.asyncio
async def test_state_db_row_updated_on_rename(persistent_session):
    session, fake_llm, vault = persistent_session
    fake_llm.queue_stream_text("a1")
    async for _ in session.turn("q1"):
        pass
    fake_llm.queue_stream_text("a2")
    fake_llm.queue_response('{"title": "foo bar baz", "slug": "foo-bar-baz"}')
    async for _ in session.turn("q2"):
        pass
    rows = session.state_db.exec("SELECT thread_id FROM chat_threads").fetchall()
    ids = [r[0] for r in rows]
    assert session.thread_id in ids
    assert not any("draft" in i for i in ids)


@pytest.mark.asyncio
async def test_autotitle_none_skips_rename(no_autotitle_session):
    session, fake_llm = no_autotitle_session
    original = session.thread_id
    fake_llm.queue_stream_text("a1")
    async for _ in session.turn("q1"):
        pass
    fake_llm.queue_stream_text("a2")
    async for _ in session.turn("q2"):
        pass
    assert session.thread_id == original


@pytest.mark.asyncio
async def test_autotitle_failure_rolls_back_thread_id(persistent_session):
    session, fake_llm, _ = persistent_session
    fake_llm.queue_stream_text("a1")
    async for _ in session.turn("q1"):
        pass
    original = session.thread_id
    fake_llm.queue_stream_text("a2")
    fake_llm.queue_response("not json")  # AutoTitler will raise
    # Session swallows the autotitle error — turn still completes.
    async for _ in session.turn("q2"):
        pass
    assert session.thread_id == original  # thread_id unchanged on autotitle failure
```

- [ ] **Step 2: Extend `ChatSession`** — add `persistence`, `autotitler`, `vault_writer` params; call `persistence.write` at end of each `turn()`; add post-turn-2 autotitle block wrapped in try/except that emits a `ChatEvent(ERROR, ...)` on failure but does not re-raise (auto-title is non-essential). Rename ordering per the "tricky bit" above.

  **Also add public runtime-mutation helpers the CLI will call from slash commands:**

  ```python
  def switch_mode(self, new_mode: ChatMode) -> None:
      """Switch mode mid-thread. Appends a TurnRole.SYSTEM turn to the transcript
      and updates effective tool registry + temperature.

      Spec §6 D6a: mode switches are logged as system messages.
      """
      if new_mode == self.config.mode:
          return
      old = self.config.mode
      self.config = self.config.model_copy(update={"mode": new_mode})
      self._effective_registry = self._build_effective_registry()
      self._turns.append(ChatTurn(
          role=TurnRole.SYSTEM,
          content=f"mode changed: {old.value} -> {new_mode.value}",
          created_at=datetime.now(UTC),
      ))

  def switch_scope(self, new_domains: tuple[str, ...]) -> None:
      """Replace the active scope. Appends a SYSTEM turn for the transcript."""
      if new_domains == self.config.domains:
          return
      old = self.config.domains
      self.config = self.config.model_copy(update={"domains": new_domains})
      # Rebuild retrieval for the new scope; BM25 cache hit on already-built domains.
      self.retrieval.build(new_domains)
      self._turns.append(ChatTurn(
          role=TurnRole.SYSTEM,
          content=f"scope changed: {','.join(old)} -> {','.join(new_domains)}",
          created_at=datetime.now(UTC),
      ))

  def set_open_doc(self, path: Path | None) -> None:
      """Pin/unpin the open doc. Refreshes effective registry (edit_open_doc on/off)."""
      self.config = self.config.model_copy(update={"open_doc_path": path})
      self._effective_registry = self._build_effective_registry()
  ```

  These three helpers each need a unit test (add to `test_session_persistence.py`):
  - `switch_mode` appends a SYSTEM turn and filters the effective registry to match the new mode's allowlist.
  - `switch_scope` rebuilds retrieval and appends a SYSTEM turn.
  - `set_open_doc(None)` removes `edit_open_doc` from the effective registry; `set_open_doc(path)` adds it back when mode is DRAFT.

  The `_build_effective_registry()` helper is extracted from Task 17's `__init__` so it can be re-called here without duplicating the filter logic.

- [ ] **Step 3–5: Run tests + self-review + commit** (5 passed).

```bash
git commit -m "feat(chat): plan 03 task 18 — ChatSession persistence + autotitle wiring"
```

---

**Checkpoint — pause for main-loop review.**

18 tasks landed. `ChatSession` runs end-to-end against `FakeLLMProvider`: accepts a user message, streams deltas, dispatches tool calls, stages patches, persists the thread, auto-titles after turn 2. Next group (Tasks 19–20) puts a user-facing CLI in front of it.

---

### Group 5 — CLI wrapper (Tasks 19–20)

**Checkpoint after Task 20**: first "user can type at a terminal" milestone. Main-loop does a hands-on CLI smoke test (drive a real terminal session against `FakeLLMProvider`) plus code-quality review of the streaming renderer and slash-command parser.

---

### Task 19 — `brain_cli` package skeleton

**Owning subagent:** brain-core-engineer (wrappers follow brain_core owner since they're trivial)

**Files:**
- Create: `packages/brain_cli/pyproject.toml`
- Create: `packages/brain_cli/src/brain_cli/__init__.py`
- Create: `packages/brain_cli/src/brain_cli/__main__.py`
- Create: `packages/brain_cli/src/brain_cli/app.py`
- Create: `packages/brain_cli/src/brain_cli/commands/__init__.py` (empty)
- Create: `packages/brain_cli/tests/__init__.py` (empty)
- Create: `packages/brain_cli/tests/test_cli_smoke.py`
- Modify: root `pyproject.toml` — add `brain_cli` workspace member + root `[project].dependencies += ["brain_cli"]`
- Modify: root `pyproject.toml` `[project.scripts]` — add `brain = "brain_cli.app:app"` entry point

**Context for the implementer:**
This task lands the workspace package wiring only. The CLI has exactly ONE command: `brain --version` (for the smoke test). Tasks 20 lands the real `chat` and `patches` subcommands. Per Plan 01 lesson: adding a workspace member requires (a) workspace source entry, (b) root `[project].dependencies += "brain_cli"`, (c) re-running `uv sync` to install. Also set `editable = false` via `[tool.uv.sources]` to match `brain_core` (Plan 01 editable bug).

- [ ] **Step 1: Write the failing smoke test**

`packages/brain_cli/tests/test_cli_smoke.py`:
```python
"""Smoke test — CLI entry point wires Typer root."""

from __future__ import annotations

from typer.testing import CliRunner

from brain_cli.app import app


def test_version_flag() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "brain" in result.stdout.lower()


def test_help_lists_future_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "brain" in result.stdout.lower()
```

Run: `uv run pytest packages/brain_cli -v` → FAIL (no module).

- [ ] **Step 2: Create `packages/brain_cli/pyproject.toml`**

```toml
[project]
name = "brain_cli"
version = "0.0.1"
requires-python = ">=3.12"
dependencies = [
    "brain_core",
    "typer>=0.13",
    "rich>=13.9",
    "prompt-toolkit>=3.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/brain_cli"]

[tool.uv.sources]
brain_core = { workspace = true }
```

- [ ] **Step 3: Update root `pyproject.toml`**

Add `brain_cli` to workspace members, add `brain_cli` to root `[project].dependencies`, add `[project.scripts]` entry:

```toml
[tool.uv.workspace]
members = ["packages/brain_core", "packages/brain_cli"]

[tool.uv.sources]
brain_core = { workspace = true, editable = false }
brain_cli  = { workspace = true, editable = false }

[project.scripts]
brain = "brain_cli.app:app"
```

(Preserve any existing keys — additive only.)

- [ ] **Step 4: Implement the Typer root**

`packages/brain_cli/src/brain_cli/__init__.py`:
```python
"""brain_cli — Typer CLI wrapper around brain_core."""

__version__ = "0.0.1"
```

`packages/brain_cli/src/brain_cli/app.py`:
```python
"""Typer root. Subcommands land in commands/ (Task 20)."""

from __future__ import annotations

import typer

from brain_cli import __version__

app = typer.Typer(
    name="brain",
    help="brain — local LLM-maintained personal knowledge base",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"brain {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """brain CLI root."""
```

`packages/brain_cli/src/brain_cli/__main__.py`:
```python
from brain_cli.app import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Install + run tests**

```bash
uv sync --reinstall-package brain_cli
uv run pytest packages/brain_cli -v
brain --version    # sanity check from a shell
```

Expected: 2 passed; shell `brain --version` prints `brain 0.0.1`.

- [ ] **Step 6: 12-point self-review** — mypy strict on `brain_cli`, ruff clean.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(cli): plan 03 task 19 — brain_cli workspace package skeleton"
```

---

### Task 20 — `brain_cli.commands.chat` + `brain_cli.commands.patches`

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_cli/src/brain_cli/commands/chat.py`
- Create: `packages/brain_cli/src/brain_cli/commands/patches.py`
- Create: `packages/brain_cli/src/brain_cli/rendering/__init__.py` (empty)
- Create: `packages/brain_cli/src/brain_cli/rendering/stream.py`
- Create: `packages/brain_cli/src/brain_cli/session_factory.py`
- Create: `packages/brain_cli/tests/test_chat_command.py`
- Create: `packages/brain_cli/tests/test_patches_command.py`
- Modify: `packages/brain_cli/src/brain_cli/app.py` — register subcommands

**Context for the implementer:**

**`session_factory.py`** is where `ChatSession` is constructed from CLI options. It takes `(mode, domains, open_doc, model, vault_root, llm_provider=None)` and returns a ready-to-run `ChatSession`. If `llm_provider is None`, it builds an `AnthropicProvider` from env/config; if provided, it uses that — this is how tests inject `FakeLLMProvider`. This indirection is the testability hook.

**`rendering/stream.py`** is the Rich renderer — one class `StreamRenderer` with `async render(events: AsyncIterator[ChatEvent])` that translates events to terminal output:
- `DELTA` → `console.print(text, end="")` with no newline
- `TOOL_CALL` → dimmed panel `╭─ search_vault(query="x") ─╮`
- `TOOL_RESULT` → dimmed panel with truncated result body
- `PATCH_PROPOSED` → yellow panel `📝 patch staged: <target_path> [<patch_id>]` (user has explicitly approved the emoji for this renderer)
- `COST_UPDATE` → status bar update (Rich's `Live` display)
- `TURN_END` → newline + dimmed `cost +$0.0031 · total $0.0092`
- `ERROR` → red panel

**Slash commands** parsed in the input loop, not by Typer:
- `/mode ask|brainstorm|draft` — constructs a new mode policy, appends a `TurnRole.SYSTEM` turn via session's public helper, switches `session.config.mode`
- `/scope d1,d2` — updates `session.config.domains` (with warning if `personal` is included, per CLAUDE.md principle #9)
- `/file <path>` — sets `session.config.open_doc_path`; warns if not currently in Draft mode
- `/quit` or Ctrl-D — exits cleanly

**`brain patches`** subcommands:
- `brain patches list` — prints staged patches from `PendingPatchStore` (table: id, created_at, mode, tool, target_path, reason)
- `brain patches apply <id>` — loads envelope, calls `VaultWriter.apply(envelope.patchset, allowed_domains=(domain_from_target,))`, then `pending_store.mark_applied(id)`. Requires typed confirmation (`"yes"`) per CLAUDE.md principle #9. **Skippable with `--yes` flag** for the demo.
- `brain patches reject <id> --reason "..."` — calls `pending_store.reject(id, reason)`.

- [ ] **Step 1: Write failing tests**

`test_chat_command.py` drives the CLI via Typer's `CliRunner` with a `FakeLLMProvider` injected via `monkeypatch` on `session_factory.build_session`:

```python
@pytest.mark.asyncio
async def test_chat_single_turn_streams_to_stdout(tmp_path, monkeypatch):
    # seed vault, fake LLM, inject via session_factory
    # runner.invoke(app, ["chat", "--mode", "ask", "--domain", "research", "--vault", str(vault)])
    # pass user input via stdin: "hi\n/quit\n"
    # assert fake response text appears in result.stdout
    ...


def test_chat_slash_mode_switches_and_appends_system_turn(...): ...
def test_chat_slash_file_requires_draft_mode_warning(...): ...
def test_chat_ctrl_d_exits_cleanly(...): ...
```

`test_patches_command.py`:
```python
def test_patches_list_shows_pending_only(tmp_path): ...
def test_patches_apply_writes_via_vault_writer(tmp_path): ...
def test_patches_apply_without_yes_requires_confirmation(tmp_path): ...
def test_patches_reject_moves_to_rejected_dir(tmp_path): ...
```

- [ ] **Step 2: Implement `session_factory.py`**

```python
"""Build a ChatSession from CLI options. Test-injection point for FakeLLMProvider."""

from __future__ import annotations

from pathlib import Path

from brain_core.chat.context import ContextCompiler
from brain_core.chat.persistence import ThreadPersistence
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.session import ChatSession
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.tools.base import ToolRegistry
from brain_core.chat.tools.search_vault import SearchVaultTool
# ... imports for all 6 tools ...
from brain_core.chat.types import ChatMode, ChatSessionConfig
from brain_core.chat.modes import MODES
from brain_core.chat.autotitle import AutoTitler
from brain_core.llm.provider import LLMProvider
from brain_core.llm.providers.anthropic import AnthropicProvider
from brain_core.prompts.loader import PromptLoader
from brain_core.state.db import StateDB
from brain_core.vault.writer import VaultWriter


def build_session(
    *,
    mode: ChatMode,
    domains: tuple[str, ...],
    open_doc: Path | None,
    model: str,
    vault_root: Path,
    llm: LLMProvider | None = None,
) -> ChatSession:
    state_db = StateDB.open(vault_root / ".brain" / "state.sqlite")
    writer = VaultWriter(vault_root=vault_root, undo_root=vault_root / ".brain" / "undo")
    pending = PendingPatchStore(vault_root / ".brain" / "pending")
    retrieval = BM25VaultIndex(vault_root=vault_root, db=state_db)
    retrieval.build(domains)

    loader = PromptLoader()
    mode_prompt = loader.load(MODES[mode].prompt_file).raw
    compiler = ContextCompiler(vault_root=vault_root, mode_prompt=mode_prompt)
    persistence = ThreadPersistence(vault_root=vault_root, writer=writer, db=state_db)

    registry = ToolRegistry()
    for tool_cls in _all_tool_classes():
        registry.register(tool_cls())
    effective = registry.subset(allowlist=MODES[mode].tool_allowlist)

    llm = llm or AnthropicProvider()
    config = ChatSessionConfig(mode=mode, domains=domains, open_doc_path=open_doc, model=model)

    thread_id = _new_draft_thread_id()
    autotitler = AutoTitler(llm=llm, prompt_loader=loader)

    return ChatSession(
        config=config, llm=llm, compiler=compiler, registry=effective,
        retrieval=retrieval, pending_store=pending, state_db=state_db,
        vault_root=vault_root, thread_id=thread_id,
        persistence=persistence, autotitler=autotitler, vault_writer=writer,
    )
```

- [ ] **Step 3: Implement `rendering/stream.py`** — `StreamRenderer` class with per-event-kind handlers. Use `rich.console.Console` with `force_terminal=False` detection (Task 22 cross-platform sweep verifies). Render `TOOL_CALL` as a dimmed panel; `DELTA` appends to a running assistant-turn string with no panel. Track cumulative cost for the status bar.

- [ ] **Step 4: Implement `commands/chat.py`**

```python
@app.command()
def chat(
    mode: ChatMode = typer.Option(ChatMode.ASK, "--mode", "-m"),
    domain: list[str] = typer.Option(["research"], "--domain", "-d"),
    open_doc: Path | None = typer.Option(None, "--open"),
    model: str = typer.Option("claude-sonnet-4-6", "--model"),
    vault: Path = typer.Option(Path.home() / "Documents" / "brain", "--vault"),
) -> None:
    """Start an interactive chat session."""
    session = build_session(
        mode=mode, domains=tuple(domain), open_doc=open_doc, model=model, vault_root=vault,
    )
    asyncio.run(_run_chat_loop(session))
```

`_run_chat_loop` uses `prompt_toolkit.PromptSession` for input, handles `/mode`, `/scope`, `/file`, `/quit`, and on each real user message calls `session.turn(msg)` and pipes through `StreamRenderer`. Ctrl-C raises `KeyboardInterrupt` → print "Aborted." → break cleanly.

- [ ] **Step 5: Implement `commands/patches.py`**

```python
@patches_app.command("list")
def list_patches(vault: Path = typer.Option(...)): ...

@patches_app.command("apply")
def apply_patch(patch_id: str, yes: bool = typer.Option(False, "--yes"),
                vault: Path = typer.Option(...)): ...

@patches_app.command("reject")
def reject_patch(patch_id: str, reason: str = typer.Option(..., "--reason"),
                 vault: Path = typer.Option(...)): ...
```

`apply` without `--yes` prompts `Type "yes" to apply:` and bails if the input isn't exactly `"yes"` (typed confirmation per CLAUDE.md principle #9). `apply` calls `VaultWriter.apply(env.patchset, allowed_domains=(env.target_path.parts[0],))` and then `pending_store.mark_applied(patch_id)`.

- [ ] **Step 6: Register subcommands in `app.py`**

```python
from brain_cli.commands.chat import chat
from brain_cli.commands.patches import patches_app

app.command()(chat)
app.add_typer(patches_app, name="patches")
```

- [ ] **Step 7: Run tests + 12-point self-review**

Extras:
- `brain chat --help` prints the command signature correctly from a shell.
- `brain patches apply <id>` without `--yes` prompts for typed confirmation.
- `StreamRenderer` handles `force_terminal=False` without crashing (Task 22 verifies more thoroughly).

- [ ] **Step 8: Manual smoke test**

```bash
brain chat --mode ask --domain research --vault /tmp/test-vault
```
Type a message, see streaming output (will fail at Anthropic call without a key — that's fine; the CLI should exit cleanly with a friendly error).

- [ ] **Step 9: Commit**

```bash
git commit -m "feat(cli): plan 03 task 20 — brain chat + brain patches commands"
```

---

**Checkpoint — pause for main-loop review.**

20 tasks landed. A user can run `brain chat` and interact with the system. Remaining tasks are contract tests, cross-platform sweep, demo script, hardening sweep, and plan close.

---

### Group 6 — Contract + cross-platform + demo + close (Tasks 21–25)

**Checkpoint after Task 25**: plan close. Tag, demo artifact, lessons update, main-loop marks Plan 03 ✅ in `tasks/todo.md`.

---

### Task 21 — Prompt contract test infrastructure

**Owning subagent:** brain-prompt-engineer

**Files:**
- Create: `packages/brain_core/tests/prompts/test_chat_prompts_rendering.py` (no-network unit tests — rendering only)
- Modify: `packages/brain_core/tests/prompts/conftest.py` (reuse Plan 02 VCR fixture if present; add `chat_*` cassette dir)
- Create: `packages/brain_core/tests/prompts/cassettes/chat_ask.yaml` (empty placeholder + `.gitkeep`)
- Create: `packages/brain_core/tests/prompts/cassettes/chat_brainstorm.yaml` (placeholder)
- Create: `packages/brain_core/tests/prompts/cassettes/chat_draft.yaml` (placeholder)
- Create: `packages/brain_core/tests/prompts/cassettes/chat_autotitle.yaml` (placeholder)
- Create: `packages/brain_core/tests/prompts/test_chat_prompts_contract.py` (all gated on `ANTHROPIC_API_KEY`; skipped by default per D7a)
- Modify: `docs/testing/prompts-vcr.md` (extend Plan 02 doc with a chat-mode recording recipe)

**Context:**
Per D7a, real-API cassettes are deferred and are not a merge gate. This task lands the **infrastructure** to record them later plus no-network **rendering** tests that exercise each `chat_*.md` prompt file's template substitution.

- [ ] **Step 1: Write no-network rendering tests** — 4 tests, one per chat prompt file. Assert each loads, renders with the expected variable names from Task 16/14, and contains the spec §6 keywords (Ask: "cite", "refuse to speculate"; Brainstorm: "alternatives", "Socratic"; Draft: "open document"; autotitle: "3 to 6 words", "kebab-case").

- [ ] **Step 2: Write contract test skeletons** — each wrapped in `@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"))` and `@pytest.mark.vcr(cassette_library_dir=..., record_mode="none")`. Each test runs one real LLM call and asserts the response parses against its expected schema (auto-title returns valid JSON with matching slug; mode prompts return plain text or tool_use blocks as appropriate). These stay skipped in CI unless a key is present.

- [ ] **Step 3: Extend `docs/testing/prompts-vcr.md`** — document the 4 new cassette files, the recording command, and the redaction list (reuse Plan 02's `authorization`, `x-api-key`, `anthropic-api-key` — no new secrets).

- [ ] **Step 4: Run rendering tests** (4 passed, contract tests skipped). 12-point self-review.

- [ ] **Step 5: Commit**

```bash
git commit -m "test(prompts): plan 03 task 21 — chat prompt rendering tests + deferred cassettes"
```

---

### Task 22 — Cross-platform sweep

**Owning subagent:** brain-test-engineer

**Files:**
- Modify: any files flagged during the sweep (likely `pending.py`, `session_factory.py`, `rendering/stream.py`, `retrieval.py`)
- Create: `packages/brain_core/tests/chat/test_crossplatform.py`
- Create: `packages/brain_cli/tests/test_crossplatform.py`

**Context for the implementer:**
This is a non-mechanical sweep. Walk every module added in Tasks 1–20 and verify:

1. **Paths**: no hardcoded `/`. All path joins via `pathlib.Path`. Filenames don't use Windows reserved names (`CON`, `PRN`, `NUL`, `AUX`, etc.) — the only dynamic filename source is the autotitle slug in Task 14 plus the `patch_id` in Task 3; slugs are ASCII-lowercase-hyphen (already constrained) and `patch_id` is `ms-hex` (safe).
2. **File locking**: `state.sqlite` WAL mode is enabled (verified in Task 2). The `PendingPatchStore.put` temp+rename is atomic on both platforms. Run the `test_pending.py` suite under a simulated concurrent-write scenario (two processes both calling `put`) to confirm no overwrites — do this as a unit test that spawns two threads (simpler than real processes).
3. **`os.replace` semantics**: atomic on both. Verify `VaultWriter.rename_file` from Task 14 works when `dst` is on a different subdirectory of the same drive (it is; vault is one drive).
4. **Rich rendering off a non-TTY**: `force_terminal=None` auto-detects; confirm `StreamRenderer` doesn't crash when stdout is piped. Test via `CliRunner` which captures stdout.
5. **Ctrl-C handling**: prompt-toolkit on Windows uses `windows_events`; confirm `KeyboardInterrupt` propagates cleanly and the chat loop exits with "Aborted." not a traceback.
6. **Long paths on Windows**: if the vault root is >260 chars, Python 3.12 + long-path-aware Windows handles it; don't add `\\?\` prefix explicitly — rely on the OS setting. Note this as a Plan 08 installer concern (installer must enable long-path support).
7. **Line endings**: all Markdown writes use `newline="\n"` (already in `_atomic_write_text`). Verify `ThreadPersistence._render` doesn't embed `\r\n` anywhere.
8. **`TypedDict` / `StrEnum` / `match` statement ruff compatibility** — already a Plan 01 lesson; re-confirm no drift.
9. **iCloud ghost-file check** — run `find .venv -name "* [0-9].py"` per Plan 02 lesson. Empty.
10. **CI run on both platforms** — Plan 03's CI must be green on Mac AND Windows before this task marks DONE.

Any fix found during this sweep is landed in the same commit as its test.

- [ ] **Step 1: Walk every module, file a finding list** (no code changes yet). Expected: 0–3 findings. Zero is acceptable if Tasks 1–20 were disciplined.
- [ ] **Step 2: Write tests that would have caught each finding** before writing the fix. TDD even for cross-platform fixes.
- [ ] **Step 3: Land fixes + tests together.**
- [ ] **Step 4: Run the full `brain_core + brain_cli` test suite on both platforms.** On Mac locally; Windows via the CI branch push.
- [ ] **Step 5: Commit (one commit per finding)**.

```bash
git commit -m "fix(chat): plan 03 task 22 — cross-platform sweep (<N findings>)"
```

---

### Task 23 — `scripts/demo-plan-03.py`

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `scripts/demo-plan-03.py`
- Modify: `README.md` (add a "Plan 03 demo" section pointing to the script, per Plan 02 convention)

**Context:**
The demo script is the plan's proof artifact. It drives the entire chat subsystem against `FakeLLMProvider`, with pre-queued responses that exercise every demo-gate assertion (see plan header §"Demo gate" for the 7 points). No real network. No API key.

Script structure:

```python
#!/usr/bin/env python3
"""Plan 03 demo — end-to-end chat against FakeLLMProvider.

Asserts the 7-point demo gate from tasks/plans/03-chat.md and prints
PLAN 03 DEMO OK on success.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from brain_cli.session_factory import build_session
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode, ChatEventKind
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import ToolUse
from brain_core.vault.paths import ScopeError
from brain_core.vault.writer import VaultWriter


def _seed_vault(vault: Path) -> None:
    """Reuse the Plan 02 demo's 5 notes — the chat's retrievable corpus."""
    ...  # copy research/notes/*.md from scripts/fixtures/plan-02/ into vault/research/


async def _assert_ask_mode(vault: Path, fake: FakeLLMProvider) -> None:
    # Queue: LLM → tool_use(search_vault) → tool_result (real BM25) → LLM → text
    fake.queue_tool_use(tool_uses=[ToolUse(id="tu_1", name="search_vault",
                                            input={"query": "karpathy"})])
    fake.queue_stream_text("Karpathy's LLM wiki pattern [[karpathy]].")
    session = build_session(mode=ChatMode.ASK, domains=("research",), open_doc=None,
                            model="claude-sonnet-4-6", vault_root=vault, llm=fake)
    events = []
    async for ev in session.turn("What did Karpathy say?"):
        events.append(ev)
    # Assertions...
    assert any(e.kind == ChatEventKind.TOOL_CALL and e.data["name"] == "search_vault" for e in events)
    assert any(e.kind == ChatEventKind.DELTA for e in events)
    # No PATCH_PROPOSED in Ask mode — propose_note not in allowlist


async def _assert_brainstorm_mode(vault: Path, fake: FakeLLMProvider) -> None:
    fake.queue_tool_use(tool_uses=[ToolUse(id="tu_2", name="propose_note",
                                            input={"path": "research/notes/new.md",
                                                   "content": "# new\n\nbody",
                                                   "reason": "brainstorm idea"})])
    fake.queue_stream_text("Staged.")
    session = build_session(mode=ChatMode.BRAINSTORM, ...)
    events = [e async for e in session.turn("Let's think about this.")]
    assert any(e.kind == ChatEventKind.PATCH_PROPOSED for e in events)
    # Vault must be unchanged
    assert not (vault / "research" / "notes" / "new.md").exists()
    # Pending queue has one entry
    assert len(PendingPatchStore(vault / ".brain" / "pending").list()) == 1


async def _assert_draft_mode(vault: Path, fake: FakeLLMProvider) -> None:
    # Create an open doc first, then queue edit_open_doc
    ...


def _assert_thread_persistence(vault: Path, thread_id: str) -> None:
    path = vault / "research" / "chats" / f"{thread_id}.md"
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "## User" in body and "## Assistant" in body


async def _assert_autotitle(vault: Path, fake: FakeLLMProvider) -> None:
    # 2-turn session, second turn queues an autotitle JSON response
    ...


async def _assert_idempotency(vault: Path) -> None:
    # Re-run the same 4-turn script against the existing vault;
    # assert no duplicate thread files and cost ledger unchanged.
    ...


def _assert_scope_guard(vault: Path, fake: FakeLLMProvider) -> None:
    # Simulated read_note of personal/ path in research-scoped session
    try:
        session = build_session(mode=ChatMode.ASK, domains=("research",), ...)
        # Directly invoke ReadNoteTool.run with ctx.allowed_domains=("research",)
        # and path="personal/notes/secret.md" — expect ScopeError.
        ...
        raise AssertionError("expected ScopeError")
    except ScopeError:
        pass


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        vault.mkdir()
        _seed_vault(vault)

        fake = FakeLLMProvider()
        await _assert_ask_mode(vault, fake)
        await _assert_brainstorm_mode(vault, fake)
        await _assert_draft_mode(vault, fake)
        _assert_thread_persistence(vault, ...)
        await _assert_autotitle(vault, fake)
        await _assert_idempotency(vault)
        _assert_scope_guard(vault, fake)

        print("PLAN 03 DEMO OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 1: Write the script** — follow the skeleton above, fill in every helper, every assertion, every queued response. Assertion messages must be specific enough that a failure pinpoints which demo gate point failed.

- [ ] **Step 2: Run it**

```bash
uv run python scripts/demo-plan-03.py
```

Expected: prints `PLAN 03 DEMO OK`, exit 0.

- [ ] **Step 3: Run it a second time** — same temp vault, verify idempotency path passes too.

- [ ] **Step 4: Capture the demo receipt** — paste the full stdout into `tasks/lessons.md` under the Plan 03 section for the close artifact (per Plan 02 lesson: "Every plan has an explicit demo gate. No plan is marked ✅ without a proof artifact").

- [ ] **Step 5: Update README** — add a "Plan 03 demo" heading under the existing Plan 02 one, pointing at the script.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(chat): plan 03 task 23 — end-to-end demo script (all 7 gates)"
```

---

### Task 24 — Hardening sweep (reserved slot)

**Owning subagent:** brain-core-engineer + brain-test-engineer

**Files:** whatever the review found

**Context:**
Per Plan 02 lesson "when reviewers raise the same class of concern on 2+ consecutive tasks, prefer batching to a sweep," this task is the batch destination for all deferred nits accumulated during Tasks 4–20. Examples of what may land here (unknowable in advance):

- Error-message consistency across tools (all `ScopeError` / `ValueError` / `FileNotFoundError` messages should have plain-English "next action" text per CLAUDE.md principle #9)
- Any repeated "`ctx.xxx is None`" guard that could be a single `@requires(...)` decorator
- BM25 retrieval threshold tuning if demo runs showed unreliable hits
- Test-parametrization cleanup if reviewers flagged duplication across tool tests
- Any `async` / `sync` mismatches that mypy strict flagged but tests didn't exercise

If the review surfaces nothing, this task becomes a formal "no-op close" commit — file the review receipt in `tasks/lessons.md` and move on.

**Known deferrals accumulated during execution** (main loop will append to this list as more surface):

- **Task 4 stopword set is 57 words**, slightly over the "<50" soft target. Trim or update the spec comment.
- **Task 9 `list_chats` `LIKE` escaping.** `query` param is parameterized (no SQL injection) but `%` and `_` in the user's query act as wildcards. Local-KB concern, not security. Fix by escaping `\%` and `\_`, then appending `ESCAPE '\\'` to the LIKE clause. Alternative: document the wildcard behavior and leave as-is.
- **Task 11 `edit_open_doc` empty-`old` string** falls through to "not unique" error because `body.count("")` returns `len(body)+1`. Add explicit guard: `if not old: raise ValueError("old text must be non-empty")` before the count.
- **Task 7 `read_note` + Task 8 `list_index` `FrontmatterError` fallback path** has no direct regression test (the lenient `fm={}, body=raw` branch). Add one parametrized test covering both tools.
- **Task 10/11 staging-tool consistency**: `text` messages are the only place the patch_id surfaces to the LLM. Consider a shared helper if a third staging tool lands.
- **Task 13 section regex** (`^## (User|Assistant|System)\s*$`) would match a literal `## User` line inside a fenced code block in assistant content. Add an adversarial-content regression test.
- **Task 14a cross-domain check** raises plain `PermissionError` instead of `ScopeError` (which is a subclass). Normalize to `ScopeError` for consistency with the rest of `VaultWriter`.
- **Task 14a negative-path tests missing** for src-outside-vault, dst-outside-vault, src-not-existing. `scope_guard` is covered elsewhere but explicit tests would lock the `rename_file` contract.
- **Plan-author meta-lesson (Tasks 14, 8)**: (1) plan text referenced imagined APIs (`PromptLoader` class, `FakeLLMProvider.queue_response`) instead of real Plan 02 signatures (`load_prompt` function, `.queue`). Verify real signatures before writing future tasks. (2) Tasks 8 and 14 both triggered false "mypy pre-existing errors" from implementers running mypy from the wrong cwd. Add explicit `cd packages/brain_core` to the per-task self-review checklist in Task 25.

- [ ] **Step 1: Collect all deferred items from Tasks 4–20 review logs** into a findings list (append to the known list above).
- [ ] **Step 2: Batch-fix each with test coverage** — same TDD discipline.
- [ ] **Step 3: Run full test suite + 12-point self-review.**
- [ ] **Step 4: Commit** (one commit per batch, matching Plan 02 batch-1/2/3 convention if >5 findings).

```bash
git commit -m "refactor(chat): plan 03 task 24 — hardening sweep (<N findings>)"
```

---

### Task 25 — Coverage + lint sweep + tag `plan-03-chat`

**Owning subagent:** brain-test-engineer

**Files:**
- Modify: `tasks/todo.md` — mark Plan 03 ✅ with date + tag + demoable artifact summary
- Modify: `tasks/lessons.md` — add the "Plan 03 — Chat" section with completion entry, handoff items to Plan 04, and any lessons learned during execution
- Modify: `tasks/plans/03-chat.md` — mark every task checkbox checked; add a "Review" section at the bottom with final stats

**Context:**
Plan close. This task does NOT add new features. It verifies the full plan is green, captures the demo artifact, updates tracking files, and tags the release point.

- [ ] **Step 1: Run the full test suite across both packages**

```bash
uv run pytest packages/brain_core packages/brain_cli -q --cov=brain_core --cov=brain_cli --cov-report=term-missing
```

Coverage targets: `brain_core.chat` ≥ 90%, `brain_core.state` ≥ 90%, `brain_cli` ≥ 85% (CLI has inherent harder-to-cover paths for Rich + prompt-toolkit). Total `brain_core` must not regress from Plan 02's 94%.

If coverage has dropped: investigate (first suspect: iCloud ghost files per Plan 02 lesson). If real gap: add tests before tagging.

- [ ] **Step 2: mypy strict + ruff + format** across both packages. Zero findings.

- [ ] **Step 3: Run the demo script one more time** — capture receipt.

- [ ] **Step 4: Update `tasks/todo.md`** — mark Plan 03 ✅ (2026-04-xx, tag `plan-03-chat`), demoable deliverable `brain chat` Ask/Brainstorm/Draft working in terminal with N tests across brain_core + brain_cli.

- [ ] **Step 5: Update `tasks/lessons.md`** — new "Plan 03 — Chat" section mirroring Plan 02's shape. Include:
  - Plan 03 complete summary (test counts, coverage, demo receipt, commit count)
  - Subagent-driven development retrospective — what the 7 checkpoints caught
  - Handoff items to Plan 04 (MCP): `state.sqlite` ready to extend with tool-call audit table; `PendingPatchStore` reusable by MCP `brain_propose_note`; retrieval cache reusable
  - Any lessons surfaced during Task 15 (LLM ext) — most likely source of new rules
  - Any cross-platform surprises from Task 22

- [ ] **Step 6: Tag the release point**

```bash
git tag plan-03-chat
git push origin main --tags
```

- [ ] **Step 7: Final commit**

```bash
git add tasks/todo.md tasks/lessons.md tasks/plans/03-chat.md
git commit -m "docs: close plan 03 (chat) — tag plan-03-chat"
```

---

**Plan 03 complete.** Next step (outside this plan): main-loop authors Plan 04 (MCP + Claude Desktop) using Plan 03's lessons as input.

---

## Review

*To be filled in by the implementer at Task 25. Template:*

- **Task count:** 25 (planned) / ? (actual)
- **Commits since `plan-02-ingestion`:** ?
- **Test counts:** brain_core (?) + brain_cli (?) = ? total
- **Coverage:** brain_core ?% · brain_cli ?%
- **Demo receipt:** (paste output of `scripts/demo-plan-03.py`)
- **Lessons captured:** (link to new entries in `tasks/lessons.md`)
- **Handoff to Plan 04:** (state.sqlite / pending queue / retrieval cache notes)
