# Plan 07 — Pre-flight Commitments

> **What this is:** a consolidated list of every backend and spec change that Plan 07 (frontend implementation) depends on. Drawn from `design-delta.md`, `design-delta-v2.md`, and the v3 design review. Plan 07 authoring starts from this doc — the decisions in §7 need your sign-off before I write the task groups.
>
> **Date:** 2026-04-21
> **Read with:** `design-brief.md`, `design-delta.md`, `design-delta-v2.md`.

---

## Table of contents

1. [Required brain_core extensions](#1-required-brain_core-extensions)
2. [Required brain_api extensions](#2-required-brain_api-extensions)
3. [New tools](#3-new-tools)
4. [Additive config schema changes](#4-additive-config-schema-changes)
5. [Frontend-only concerns](#5-frontend-only-concerns)
6. [Spec updates](#6-spec-updates)
7. [Open decisions (need your sign-off)](#7-open-decisions)
8. [Dependency ordering for Plan 07](#8-dependency-ordering-for-plan-07)
9. [What NOT to include in Plan 07](#9-what-not-to-include-in-plan-07)

---

## 1. Required brain_core extensions

These are strictly additive changes to `brain_core`. Each preserves existing Plan 01–05 behavior.

### 1.1 Per-category autonomy gate

**Problem:** Design's Autonomous-mode tab has 4 toggles (ingest / entities / concepts / index_rewrites). `brain_apply_patch` currently stages all patches uniformly; there's no way to express "auto-apply ingest patches but require review for index rewrites."

**Extension:**
- Add field `PatchSet.category: Literal["ingest", "entities", "concepts", "index_rewrites", "draft", "other"] = "other"` — tool authors populate it. `brain_ingest` → `"ingest"`; `brain_propose_note` targeting `<domain>/entities/*.md` → `"entities"`; targeting `<domain>/concepts/*.md` → `"concepts"`; targeting `<domain>/index.md` → `"index_rewrites"`; Draft-mode assistant edits → `"draft"`; everything else → `"other"`.
- New function `brain_core.autonomy.should_auto_apply(patchset, config) -> bool`. Reads `config.autonomous.<category>`. Default False.
- `brain_ingest` today has an `autonomous=true` kwarg — keep as an explicit override, but also consult `config.autonomous.ingest` when `autonomous=None`.
- Plan 07 wires `brain_apply_patch` to skip the pending-store-put step when `should_auto_apply()` returns True.

### 1.2 Per-mode chat models

**Problem:** `ChatSessionConfig` has one `model` field. Design's ProvidersPanel + fork dialog both assume per-mode model selection (Ask/Brainstorm/Draft can be different models).

**Extension:**
- Add fields: `ChatSessionConfig.ask_model: str | None`, `.brainstorm_model: str | None`, `.draft_model: str | None`. All default `None` → fall back to the existing `model` field (keeps Plan 03 defaults working).
- `ChatSession.turn(...)` selects model based on `self.mode` → `config.<mode>_model or config.model`.

### 1.3 Cost ledger tagging by mode + stage

**Problem:** `CostLedger.record(...)` accepts `operation: str` + `domain: str`. Design's BudgetWall breakdown wants `Ask / Brainstorm / Draft / Ingest` categories — which don't match current `operation` values.

**Extension:**
- Add optional `mode: str | None` + `stage: str | None` fields to `CostEntry`. `mode` ∈ {"ask", "brainstorm", "draft"} for chat; `None` for ingest. `stage` ∈ {"classify", "summarize", "integrate"} for ingest; `None` for chat.
- `CostLedger.summary(*, today, month)` gains a `by_mode: dict[str, float]` field on `CostSummary`.
- Backfill: call sites in `ChatSession.turn` pass `mode=self.mode`; call sites in `IngestPipeline._summarize/_integrate/classify` pass `stage=`.

### 1.4 Draft-mode inline edits

**Problem:** Design's DocPanel renders inline pending edits via `⟦+…⟧` / `⟦-…⟧` sentinel tokens — a prototype notation. Real backend needs a typed emission model for "the assistant proposed 3 inline edits to the open doc."

**Extension (choose in §7):**
- **Option A (typed-edit WS event):** add a new WS server event `{type: "doc_edit_proposed", edits: [{op: "insert"|"delete"|"replace", anchor: {kind, value}, text}]}`. Frontend maps these to inline highlighted spans in DocPanel.
- **Option B (extend patch_proposed):** existing `patch_proposed` event gains a `kind: "doc_edit"` variant with an `edits` payload. Fewer new event types; tighter coupling to the patch system.

Either way: `ChatSession.turn` in Draft mode emits these events when the assistant message contains structured edits. The `SessionRunner` bridge in `brain_api` maps the `ChatEvent` to the WS event.

### 1.5 `ChatSession.fork_from(source_thread_id, turn_index, *, carry="full")`

**Problem:** Design's ForkDialog creates a new thread from turn N of an existing thread. No current API.

**Extension:**
- New classmethod `ChatSession.fork_from(source_thread_id: str, turn_index: int, *, vault_root, allowed_domains, mode: ChatMode | None = None, carry: Literal["full", "none"] = "full", **kwargs) -> ChatSession`.
- Loads the source thread, copies turns `0..turn_index` as initial context (`initial_turns` kwarg from Plan 05 Task 21a), generates a new `thread_id`, writes a new thread file.
- "summary" carry option deferred — see §7.

---

## 2. Required brain_api extensions

### 2.1 Real token tracking in `cost_update` WS event

**Problem:** Design's context-%-meter derives from `tokensUsed`, currently a frontend-only estimate (`+4200` per turn). The `cost_update` WS event carries `tokens_in + tokens_out` per turn — frontend needs to accumulate them into `cumulative_tokens` and surface.

**Extension:**
- `CostUpdateEvent` already has `tokens_in` and `tokens_out`. Add `cumulative_tokens_in: int` alongside the existing `cumulative_usd`. Frontend uses `cumulative_tokens_in / 200_000` as the context-fill ratio.
- Alternative: add `context_pct_used: float` directly on `turn_end` — but that couples brain_api to a model-specific context window size. Tokens are cleaner.

### 2.2 Draft-mode WS edit event (companion to §1.4)

Whichever §1.4 option lands, `brain_api.chat.session_runner.SessionRunner._convert_chat_event` must map the new brain_core event kind to a new WS server-event Pydantic model.

### 2.3 Ephemeral budget override

**Problem:** Design's BudgetWall "Raise cap by $5 for today" implies an override that resets at midnight. Current `brain_config_set` only supports permanent `budget.daily_usd` changes.

**Extension:**
- Add config keys `budget.override_until: datetime | None` and `budget.override_delta_usd: float`.
- `CostLedger.is_over_budget(config, today)` returns False if `now < override_until`.
- A new tool `brain_budget_override(amount_usd, duration_hours)` sets both fields.
- The override clears automatically on reads after expiry (no scheduled task needed).

---

## 3. New tools

Small additions to `brain_core.tools`. Each follows the Task 5/6 pattern from Plan 05: module at `brain_core/tools/<name>.py` with `NAME`, `DESCRIPTION`, `INPUT_SCHEMA`, `handle()`; auto-registered via `sys.modules[__name__]`; 7-line shim at `brain_mcp/tools/<name>.py`.

### 3.1 `brain_recent_ingests`

**Purpose:** power Inbox's "Recent" / "In progress" / "Needs attention" tabs.

**Shape:** `{limit?: int=20}` → `{ingests: [{source, domain, source_type, status, patch_id?, classified_at, cost_usd, error?}]}`.

Reads from `state.sqlite` — Plan 02 already stores ingest records for idempotency checks. Extend the table schema slightly (migration) to include `status` and `error`.

### 3.2 `brain_create_domain`

**Purpose:** Settings → Domains → Add.

**Shape:** `{slug: str, name: str, accent_color?: str}` → creates `<vault>/<slug>/{index.md, log.md}`, adds to `config.domain_order`. Refuses if slug already exists or fails the kebab-regex.

### 3.3 `brain_rename_domain`

**Purpose:** Settings → Domains → Rename (v3 added the dialog).

**Shape:** `{from: str, to: str, rewrite_frontmatter: bool=true}` → atomic operation:
1. Rename folder `<vault>/<from>/` → `<vault>/<to>/`
2. Rewrite every `domain: <from>` frontmatter entry (if `rewrite_frontmatter`)
3. Rewrite every `[[wikilink]]` in every note whose link target pointed into `<from>/`
4. Update `config.domain_order` entry in place
5. Log as a single `UndoLog` entry (so `brain_undo_last` can revert the rename)

**Not a PatchSet** — it's an atomic tool that bypasses the normal patch machinery, similar to how `brain_undo_last` works. See §7.

### 3.4 `brain_budget_override`

See §2.3 — paired with the config schema changes.

### 3.5 `brain_wikilink_status` *(optional — §9)*

Frontend already ships broken-wikilink rendering via a client-side set. Real backend support would let the frontend detect broken links dynamically. Shape: `{slugs: list[str]}` → `{exists: dict[str, bool]}`.

---

## 4. Additive config schema changes

All additive — no existing Plan 04 `_SETTABLE_KEYS` entries change.

| Key | Type | Default | Purpose |
|---|---|---|---|
| `autonomous.ingest` | bool | false | Plan 07 §1.1 gate |
| `autonomous.entities` | bool | false | Plan 07 §1.1 gate |
| `autonomous.concepts` | bool | false | Plan 07 §1.1 gate |
| `autonomous.index_rewrites` | bool | false | Plan 07 §1.1 gate (design flags `danger`) |
| `autonomous.draft` | bool | false | Plan 07 §1.1 — Draft-mode inline edits apply without staging |
| `ask_model` | str \| null | null | §1.2 per-mode model |
| `brainstorm_model` | str \| null | null | §1.2 per-mode model |
| `draft_model` | str \| null | null | §1.2 per-mode model |
| `domain_order` | list[str] | ["research", "work", "personal"] | UI-visible ordering |
| `budget.override_until` | datetime \| null | null | §2.3 ephemeral cap raise |
| `budget.override_delta_usd` | float | 0.0 | §2.3 ephemeral cap raise |

Extend `brain_mcp.tools.config_set._SETTABLE_KEYS` (and the Plan 07 `brain_api` equivalent) to include every key above.

Also: add `BulkPlan.items[].duplicate: bool` — set by `BulkImporter.plan()` via `_already_ingested` check. Frontend uses for the `dup` warn-chip.

---

## 5. Frontend-only concerns

Not backend work — but Plan 07 task authoring must remember these.

- **V1 fix:** File-to-wiki "person" note type uses subdir `entities/` not `people/`. Single-line frontend fix.
- **Bulk approve-all / reject-all:** frontend loops over individual `brain_apply_patch` / `brain_reject_patch` calls. Show progress + allow cancel mid-loop. Document in Plan 07 as a deliberate non-feature (no batch endpoint).
- **Drop-to-attach:** dragging a file onto the chat triggers `brain_ingest` and pins the resulting patch_id to the next `turn_start` message as `attached_sources`. Add a field to the `TurnStartMessage` Pydantic model (one-line WS spec addition).
- **Per-category autonomy settings Inbox vs Pending toggle:** two switches backed by the same `autonomous.ingest` config key. Must not diverge.
- **Thread grouping by date:** pure frontend (derive from `thread.updated`).
- **Broken-wikilink styling:** frontend-only until §3.5 lands.
- **Tweaks panel strip:** already done in v3. Plan 07 must not resurrect it.

---

## 6. Spec updates

`docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` is the source of truth. Three small updates land during Plan 07 authoring:

1. **§4 Vault schema — add `scratch/` subdir.** For Draft-mode blank scratch docs per V2. Document the convention: "scratch notes are user drafts-in-progress; they're vault-writable but not expected to be cross-linked. Promote to `synthesis/` when done."
2. **§7 MCP tools list — add `brain_recent_ingests`, `brain_create_domain`, `brain_rename_domain`, `brain_budget_override`, (optionally) `brain_wikilink_status`.** Total count bumps from 18 → 22 (+1 optional).
3. **§6 Chat and brainstorm loop — document Draft-mode inline edits emission.** Whichever Option A/B from §1.4 is picked.

Per the Plan 07 workflow: spec updates land in the SAME commit as the corresponding code change, not separately.

---

## 7. Decisions pinned (2026-04-21)

Five forks locked in before Plan 07 authoring. Chosen options marked ✅.

### D1. Draft-mode inline edit emission — event shape ✅ D1a

**Choice:** new `doc_edit_proposed` WS event (Option A from §1.4).

Cleaner separation; Draft mode becomes visually distinct from the normal patch flow. Plan 07 adds a 12th server-emitted WS event. Bumps `SCHEMA_VERSION` to `"2"` (breaking change — frontend pins).

*(Not chosen: D1b overload `patch_proposed` with `kind="doc_edit"` — rejected as too tightly coupled.)*

### D2. Rename-domain execution ✅ D2a

**Choice:** atomic `brain_rename_domain` tool with a single UndoLog entry (§3.3 as written).

Bypasses PatchSet machinery for an inherently cross-vault op. Reversible via `brain_undo_last`. Documented as an architectural exception alongside the existing `brain_undo_last` pattern.

*(Not chosen: D2b giant PatchSet — rejected because thousand-file patches break the Pending UI.)*

### D3. ForkDialog "carry context" option ✅ D3a

**Choice:** ship all three — summary / full / none.

"Summary" adds a Haiku-cheap ~400-token recap step to `ChatSession.fork_from`. Adds one LLM call + latency on fork, but provides the best continuity/cost tradeoff for long threads. Plan 07 wires a `brain_core.chat.fork.summarize_turns(turns, llm) -> str` helper.

*(Not chosen: D3b full/none only — rejected; user wants all three options even with the LLM-call cost.)*

### D4. Ephemeral budget override mechanism ✅ D4a

**Choice:** `budget.override_until: datetime | null` + `budget.override_delta_usd: float` config keys paired with a new `brain_budget_override(amount_usd, duration_hours=24)` tool.

Override auto-clears on reads after expiry — no scheduled task. `CostLedger.is_over_budget(config, today)` consults the override window. Reversible by doing nothing.

*(Not chosen: D4b permanent cap raise — rejected as cap-drift UX failure.)*

### D5. Context-fill metric ✅ D5a

**Choice:** add `cumulative_tokens_in: int` to `CostUpdateEvent`.

Frontend divides by its own model→max-context table (Sonnet 200k, Haiku 200k, Opus 200k). Displayed as "≈N%". No backend-side model awareness needed.

*(Not chosen: D5b `context_pct_used` — rejected; couples brain_api to model-specific constants. D5c drop meter — rejected; long-session signal is genuinely useful.)*

---

## 8. Dependency ordering for Plan 07

Sketch of what must land first so later tasks have stable ground:

**Phase A — brain_core extensions (Plan 07 Group 1):**
- PatchSet.category + autonomy gate (§1.1)
- ChatSession per-mode model + initial_turns carry-over already in place (§1.2, §1.5)
- CostLedger mode/stage tagging + by_mode summary field (§1.3)
- Draft-mode inline edit emission (§1.4, decision D1)
- Additive config schema (§4)
- New tools — recent_ingests, create_domain, rename_domain, budget_override (§3)
- Spec updates (§6)

**Phase B — brain_api extensions (Plan 07 Group 2):**
- Real cumulative tokens in CostUpdateEvent (§2.1, decision D5)
- Draft-mode WS event mapping (§2.2)
- Budget override tool wiring (§2.3)

**Phase C — Next.js frontend (Plan 07 Group 3+):**
- Framework setup (Next.js 15 + Tailwind + shadcn/ui)
- Token read from `.brain/run/api-secret.txt` (server-side only)
- All screens per the v3 design
- WS client wiring (typed events via SCHEMA_VERSION="1")
- Frontend-only concerns from §5

**Hard gate between B and C:** all 22 tools + WS event types must be stable and OpenAPI-documented before any screen is implemented. Plan 07's screens reference the API 1:1.

**Playwright e2e + manual QA + cross-platform sweep + demo + close (Plan 07 Group N):** standard shape, mirroring Plan 04/05.

---

## 9. What NOT to include in Plan 07

Explicit non-goals to keep scope tight:

- **OS keychain integration.** Current plain-text-in-mode-0600 is defensible for a single-user local tool. `keyring` library + Windows Credential Manager is polish. Defer to Plan 09.
- **`brain_wikilink_status` / live broken-link detection.** Frontend's client-side set is fine until the vault graph hits ~1000 notes. Defer.
- **Vector DB / embeddings.** Spec §6 is explicit: no vector DB. Don't let design or future requests sneak one in.
- **Multi-user / permissions.** Single-user only — design-brief §users.
- **Cloud sync UI.** Obsidian Sync, Dropbox, iCloud are the user's problem; the app just writes to a local folder.
- **Analytics / telemetry.** Zero telemetry per CLAUDE.md principle #10. Crash reporting too — log locally, user grep.
- **Mobile / tablet responsive design.** 1024 px minimum, desktop-first.
- **A-B testing infrastructure, feature flags, progressive rollout.** Single-user means single-target.

---

## Ready for Plan 07 authoring

All decisions pinned (§7). Plan 07 can now be drafted. The task outline follows Phase A/B/C ordering from §8.

**Summary of commitments:**
- **D1a** — new `doc_edit_proposed` WS event; `SCHEMA_VERSION` bumps to `"2"`
- **D2a** — atomic `brain_rename_domain` tool
- **D3a** — all three fork carry-context modes (summary requires Haiku-cheap summarizer helper)
- **D4a** — ephemeral budget override via `override_until` + `override_delta_usd` + `brain_budget_override` tool
- **D5a** — `cumulative_tokens_in` on `CostUpdateEvent`

**Tool surface grows:** 18 → **22 tools** (new: `brain_recent_ingests`, `brain_create_domain`, `brain_rename_domain`, `brain_budget_override`). Plus `brain_wikilink_status` optional (§3.5).

**Config schema grows:** 12 new `_SETTABLE_KEYS` entries (§4).

**WS schema bumps to v2** — frontend pins `SCHEMA_VERSION = "2"` and rejects v1 servers (handshake frame).
