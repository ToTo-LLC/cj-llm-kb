# Plan 10 — Configurable Domains

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the vault's domain set user-configurable. Today the three top-level domains are baked into a Python `Literal["research","work","personal"]` on `ClassifyOutput.domain`, into `ALLOWED_DOMAINS` in `vault/paths.py`, into the classify prompt's literal text, and into the Settings UI. Plan 10 lifts that to a runtime list driven by `Config.domains` so the user can run brain with `{research, work, hobby, finance}` (or any other slug set) without code edits — while preserving the safety properties of v0.1.0 (the `personal` domain stays privacy-railed; deleting a domain leaves data behind, never silently drops it; renaming a domain rewrites wikilinks).

**Architecture:** All four backend packages already route every domain decision through one of three choke points — the typed `Config.domains`/`Config.active_domain` fields, `vault.paths.scope_guard()`, and the classify prompt's domain enum. Plan 10 widens those choke points without touching the `VaultWriter` / `IngestPipeline` / `ChatSession` invariants. The classify prompt becomes a templated multi-domain enum (rendered per-call from the live config), `scope_guard` reads `Config.domains` instead of a module-level constant, and the Settings UI grows real Add/Rename/Delete affordances backed by the existing `brain_create_domain` / `brain_rename_domain` / `brain_delete_domain` MCP tools. The `personal` slug remains hardcoded as the privacy-railed name (renaming it is rejected) so the "never in default queries" guarantee is structural, not configuration-driven.

**Tech Stack:** Same gates as the prior plans — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright for the frontend. No new third-party deps.

**Demo gate:** `uv run python scripts/demo-plan-10.py` boots a temp vault with the default `{research, work, personal}` domain set, then walks: (1) add a `hobby` domain via `brain_create_domain` and assert the classify prompt now accepts `hobby` in its enum, (2) ingest a fixture targeting `hobby`, assert the source note + index entry land under `hobby/`, (3) rename `work` → `consulting` via `brain_rename_domain` and assert wikilinks across the vault are rewritten, (4) attempt to rename `personal` and assert refusal, (5) delete `consulting` via `brain_delete_domain` (typed-confirm equivalent) and assert the trash folder holds the data + the undo log can restore it, (6) restart the in-process classifier with `{research, hobby, personal}` and assert ingest still routes correctly. Prints `PLAN 10 DEMO OK` on exit 0.

**Owning subagents:** `brain-core-engineer` (config schema, scope_guard, classifier, prompt renderer), `brain-prompt-engineer` (classify prompt template + contract test), `brain-frontend-engineer` (Settings ManageDomains panel, ChatScreen scope picker, BrowseScreen file tree), `brain-test-engineer` (cross-package coverage sweep + Playwright e2e).

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm v0.1.0 ship sweep clean: `git tag --list | grep v0.1.0` exists.
- Confirm no uncommitted changes on `main`.
- Confirm `tasks/lessons.md` is up to date from the v0.1.x cleanup pass.
- Note that issues #21 (configurable domains) and #29 (`ChatMode.MCP`-style mid-iteration scope changes) in `docs/v0.1.0-known-issues.md` are the load-bearing context for this plan; #21 is closed by Plan 10, #29 is unrelated and stays open.

---

## What Plan 10 explicitly does NOT do

These are tempting adjacent expansions that would balloon scope. Each is filed for a later plan or backlog:

- **Per-domain LLM model overrides** — e.g. "ingest into `personal` always uses Haiku." `LLMConfig.classify_model` is global today; per-domain pinning is a v0.3 idea, not Plan 10.
- **Per-domain autonomy defaults** — `AutonomousConfig` is global; Plan 10 leaves it that way. A future plan can make `autonomous.<category>` a `dict[domain, bool]`.
- **Domain-level retention policies** — auto-archive after N days, etc. Out of scope.
- **Sub-domains / nesting** — `research/papers/`, `research/talks/` as first-class scope nodes. Today these are folder organization within a flat domain; Plan 10 keeps that. A future plan could promote sub-folders to addressable scope.
- **Importing an existing folder hierarchy as a domain** — `brain_create_domain` mkdirs an empty domain. Importing requires the bulk-import flow which is its own iteration.
- **Migrating the `personal` privacy rail to a per-domain flag** — the `personal` slug stays privacy-railed by name. Generalizing this to `Config.privacy_railed: list[str]` is filed as a Plan 11 idea.

If any of these come up during implementation, file a TODO and keep moving.

---

## Decisions (locked 2026-04-27)

User signed off on all ten recommendations on 2026-04-27. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope. The "Decision" column is the locked decision; the "Why" column is the rationale that survives in the source comments / docstrings.

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | **Default domain set:** `{research, work, personal}` (unchanged from v0.1). | ✅ | Zero-cost compatibility with the v0.1 setup wizard. Existing users see no change. |
| D2 | **Slug validation rules:** lowercase regex `[a-z][a-z0-9_-]{1,30}`; no leading digit; no `_`/`-` at start/end; no path-separator chars. | ✅ | Filesystem-safe across Mac/Win/Linux. Disallows `con`/`prn`/etc. on Windows. Extends the existing `_is_valid_slug` in `vault/paths.py`. |
| D3 | **Delete behavior:** move the folder to `<vault>/.brain/trash/<slug>.<ts>/` and emit an undo entry. **Never `rm -rf`.** | ✅ | Matches v0.1's `brain_delete_domain` semantics (already shipped in Plan 07 Task 25A). |
| D4 | **Rename behavior:** rewrite every `[[slug]]` reference whose resolved target is under the renamed folder. | ✅ | Matches v0.1's `brain_rename_domain` (already shipped). Plan 10 surfaces it from the UI. |
| D5 | **Privacy rail:** `personal` is privacy-railed by SLUG (hardcoded), not by a per-domain flag. | ✅ | Generalizing now widens the safety surface and contradicts the spec's "personal never in default queries" wording. Per-domain flag is filed as a Plan 11 idea. |
| D6 | **Classify prompt enum scope:** only the call's `allowed_domains`, not every configured domain. | ✅ | Smaller enums classify more reliably; out-of-scope domains aren't valid targets anyway. |
| D7 | **Editing `Config.domains` to remove a slug that still has notes:** the slug stays usable for read paths but is hidden from the UI and from `allowed_domains` defaults. The folder is NOT deleted. The user must run Delete via the UI to actually remove data. | ✅ | "Edit a config field" should never destroy data. |
| D8 | **Classify prompt render time:** per call (fresh from `Config`), not cached at module load. | ✅ | The user can add/remove domains while the server is running; the next ingest must see the new set without a restart. Cost is one string format per classify call. |
| D9 | **Add Domain UI tool call:** `brain_create_domain` (already shipped — Plan 07 Task 4). Plan 10 adds the form + accent-swatch picker on top. | ✅ | Reuse over rebuild. |
| D10 | **`BRAIN.md` auto-update on domain change:** NO. The user's BRAIN.md is hand-edited and out of scope for automatic rewriting. | ✅ | Spec principle — BRAIN.md is the user's voice, not the LLM's. |

The implementer routes any unrecognized rule edge case (D7 alternative semantics, D5 flag-vs-slug, D10 auto-rewrite) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/
│   ├── config/
│   │   └── schema.py             # MODIFY: Domain Literal → list[str]; add ``domains`` field
│   ├── prompts/
│   │   ├── classify.md           # MODIFY: domain enum becomes a {{domains}} template var
│   │   ├── loader.py             # already supports template vars; verify
│   │   └── schemas.py            # MODIFY: ClassifyOutput.domain Literal → str + post-validator
│   ├── ingest/
│   │   └── classifier.py         # MODIFY: accept allowed_domains, render template per-call
│   ├── vault/
│   │   └── paths.py              # MODIFY: scope_guard reads from passed-in domain set, not module const
│   └── tools/
│       ├── classify.py           # MODIFY: pass ctx.allowed_domains to classifier
│       ├── ingest.py             # MODIFY: pass ctx.allowed_domains through
│       └── bulk_import.py        # MODIFY: same
└── tests/
    ├── config/
    │   └── test_schema_domains.py     # NEW: domains list validation, slug rules, personal-required
    ├── prompts/
    │   └── test_classify_template.py  # NEW: enum rendered correctly for varying domain sets
    ├── ingest/
    │   └── test_classifier_domains.py # NEW: classify routes to user-added domain
    └── vault/
        └── test_paths_dynamic.py      # NEW: scope_guard with non-default domain sets

apps/brain_web/
├── src/components/settings/
│   ├── panel-domains.tsx              # MODIFY: real Add/Rename/Delete affordances
│   └── domain-form.tsx                # NEW: extracted Add Domain form (slug + name + accent)
├── src/components/shell/
│   └── topbar.tsx                     # MODIFY: scope picker reads live domain list
├── src/components/setup/steps/
│   └── starting-theme.tsx             # MODIFY: theme picker driven by Config.domains
└── tests/
    ├── unit/settings-domains.test.tsx # MODIFY: cover Add/Rename/Delete flows
    └── e2e/domains.spec.ts            # NEW: Playwright walk through full lifecycle

scripts/
└── demo-plan-10.py                    # NEW: 6-gate demo per the demo gate above

tasks/
└── plans/10-configurable-domains.md   # this file
```

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 07. Every implementer task MUST end with this checklist before reporting DONE.

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core` (or whichever package)
3. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions
4. `cd packages/<pkg> && uv run mypy src tests && cd -` — strict clean
5. `uv run ruff check . && uv run ruff format --check .` — clean
6. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
7. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check in the spec is invariant-based, not total-based.
8. `git status` — clean after commit

Any failure in 3–7 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — Schema + slug rules (issue #21 foundation)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py`
- Create: `packages/brain_core/tests/config/test_schema_domains.py`

**Goal:** Replace the `Domain = Literal["research","work","personal"]` alias with a runtime-validated `list[str]` field on `Config`. Land the slug-validation rules from D2.

**What to do:**
1. Add `Config.domains: list[str]` defaulting to `["research", "work", "personal"]`.
2. Add a pydantic field validator that runs the D2 slug rules on every entry.
3. Require `"personal"` to be in `Config.domains` (D5 — the privacy rail is hardcoded by slug). Pydantic-level error message: "personal is required and may not be removed; use Settings → Domains to control its visibility."
4. Update `Config.active_domain` to validate that the current value is in `Config.domains` (not the static `ALLOWED_DOMAINS` tuple).
5. Keep the old `Domain = Literal[...]` alias as a deprecation re-export for one minor version so external callers (none expected) get a runtime warning.

**Spec for the new test file:**
- Default `Config().domains == ["research", "work", "personal"]`.
- `Config(domains=["research", "work", "personal", "hobby"])` validates.
- `Config(domains=["research", "work"])` raises (`personal` missing).
- `Config(domains=["research", "1bad"])` raises (slug rule).
- `Config(domains=["research", "Work"])` raises (uppercase).
- `Config(domains=["research", "work", "personal", "research"])` raises (duplicate).

**Per-task review:** schema-vs-allowlist regression test (`test_settable_keys_all_resolve_to_a_real_schema_field`) still passes — `domains` is a list, not a settable field via `brain_config_set`. If we want it to be settable later it joins `_KNOWN_NOT_ON_CONFIG` with a justification.

---

## Task 2 — `vault.paths.scope_guard` reads from the live domain set

**Files:**
- Modify: `packages/brain_core/src/brain_core/vault/paths.py`
- Modify: `packages/brain_core/tests/vault/test_paths.py`
- Create: `packages/brain_core/tests/vault/test_paths_dynamic.py`

**Goal:** `scope_guard` already takes `allowed_domains: tuple[str, ...]` per-call. The module-level `ALLOWED_DOMAINS` constant is used only for type-narrowing in two places. Drop the constant; widen the type to `tuple[str, ...]`.

**What to do:**
1. Delete `ALLOWED_DOMAINS = ("research", "work", "personal")` and update the two call sites to import from `Config` defaults if they need a default tuple.
2. Add a test that creates a vault with `{research, hobby, personal}` and asserts `scope_guard` accepts `hobby/notes/foo.md` and rejects `work/notes/foo.md`.
3. Pin that `personal` remains scope-guarded as before — adding domains doesn't loosen the privacy rail.

**Per-task review:** Plan 02's test_paths.py uses string literals for domain names; verify they still pass with the dropped constant.

---

## Task 3 — Templated classify prompt + per-call rendering

**Files:**
- Modify: `packages/brain_core/src/brain_core/prompts/classify.md`
- Modify: `packages/brain_core/src/brain_core/prompts/schemas.py`
- Modify: `packages/brain_core/src/brain_core/prompts/loader.py` (verify template support)
- Create: `packages/brain_core/tests/prompts/test_classify_template.py`

**Goal:** The classify prompt currently lists `"research" / "work" / "personal"` as the domain enum verbatim. Replace with a `{{domains}}` template variable rendered per-call.

**What to do:**
1. Audit `classify.md` and replace every literal domain reference with the template variable. Pin the JSON-output spec to `"domain": "<one of the listed names>"`.
2. Loosen `ClassifyOutput.domain` from `Literal[...]` to `str`. Add a model_validator that asserts the returned domain is in the list passed via context (the caller is responsible for providing the list).
3. Verify `prompts.loader` already supports `{{var}}` substitution — Plan 02's loader does; this is a sanity check.
4. Test cases: classify call with `domains=["research", "hobby"]` produces a prompt that mentions both names and only those names. Classify call returning a domain outside the set fails validation with a clear error.

---

## Task 4 — `classify()` + ingest pipeline thread the domain set through

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/classifier.py`
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py`
- Modify: `packages/brain_core/src/brain_core/tools/classify.py`
- Modify: `packages/brain_core/src/brain_core/tools/ingest.py`
- Modify: `packages/brain_core/src/brain_core/tools/bulk_import.py`
- Modify: `packages/brain_core/tests/ingest/test_classifier.py`
- Create: `packages/brain_core/tests/ingest/test_classifier_domains.py`

**Goal:** The classifier function and the pipeline both need to accept the active domain set so per-call rendering (D8) actually fires.

**What to do:**
1. Add `allowed_domains: tuple[str, ...]` to `classifier.classify(...)` (it's already on `ClassifyResult` but not on the function signature).
2. The pipeline already plumbs `allowed_domains` through `ingest()`; verify it reaches `classify()` and the prompt renderer.
3. Test cases (in `test_classifier_domains.py`):
   - Classify a "fishing rod" snippet with `domains=["research","work","personal","hobby"]` and a fake LLM that returns `"hobby"`. Assert `ClassifyResult.domain == "hobby"`.
   - Classify with an LLM that returns `"made-up-domain"` — assert `ClassifyResult.needs_user_pick is True` (or the pipeline routes to the QUARANTINED path; pick one and pin it).

---

## Task 5 — Backend domain admin tools surface to the UI contract

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/list_domains.py`
- Modify: `packages/brain_core/src/brain_core/tools/create_domain.py`
- Modify: `packages/brain_core/src/brain_core/tools/rename_domain.py`
- Modify: `packages/brain_core/src/brain_core/tools/delete_domain.py`
- Modify: tests for each

**Goal:** The four domain-admin tools already exist (Plan 07 Task 4 + 25A). Plan 10 verifies they enforce the new `Config.domains` semantics:

1. `brain_list_domains` returns the union of `Config.domains` and the on-disk slug list (so the UI sees both "configured" and "discovered" domains; D7 says they can diverge).
2. `brain_create_domain` rejects slugs that fail the D2 rules. After the create, the slug is appended to `Config.domains` (in-memory; persistence is deferred per existing #27).
3. `brain_rename_domain` rejects renaming `personal` (D5) and rejects renaming TO a slug already in `Config.domains`.
4. `brain_delete_domain` rejects deleting `personal` and the last non-personal domain (so the user can't accidentally end up with only `personal`).

**Per-task review:** Verify each tool's response shape matches what the frontend currently consumes; if any field renames, fix the consumer.

---

## Task 6 — Settings → Domains panel: real Add/Rename/Delete

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx`
- Create: `apps/brain_web/src/components/settings/domain-form.tsx`
- Modify: `apps/brain_web/src/lib/api/tools.ts` (typed helpers — verify `createDomain` / `renameDomain` / `deleteDomain` exist)
- Modify: `apps/brain_web/tests/unit/settings-domains.test.tsx`

**Goal:** The current panel shows a static list with non-functional Rename/Delete buttons (per the v0.1.0 release-note caveat). Plan 10 wires real flows.

**What to do:**
1. Extract the Add Domain form into `domain-form.tsx` so it's reusable from the setup wizard's theme step.
2. Wire the Rename button → `RenameDomainDialog` (already exists in `dialogs/`) → `brain_rename_domain` tool.
3. Wire the Delete button → `TypedConfirmDialog` (typed-confirm with the slug as the word) → `brain_delete_domain` tool.
4. Refresh the list via `brain_list_domains` after every successful mutation.
5. Toast on success/failure via `system-store`.
6. Update unit tests: assert form validation (D2 rules surface client-side too); assert the Rename dialog opens; assert Delete is gated by typed-confirm.

**Per-task review:** This is the one task that requires browser verification per CLAUDE.md. Reviewer takes a screenshot of: the panel with 4 domains, the Rename dialog mid-edit, the typed-confirm at "type `hobby` to delete" stage, and the post-delete state showing 3 domains.

---

## Task 7 — Topbar scope picker + Browse file tree consume live domains

**Files:**
- Modify: `apps/brain_web/src/components/shell/topbar.tsx`
- Modify: `apps/brain_web/src/components/browse/file-tree.tsx`
- Modify: `apps/brain_web/src/lib/state/app-store.ts` (scope state already a `string[]`; verify)
- Modify: associated tests

**Goal:** Both surfaces currently hardcode `STUB_DOMAINS = [{id:"research"...}, ...]`. Replace with a hook that fetches via `listDomains()` once on mount and caches.

**What to do:**
1. Add a small `useDomains()` hook (similar to `useVaultName()` from issue #14) that fetches once per session, caches via module-level singleton, and returns `Domain[]` with `{slug, label, accent}`.
2. Topbar scope picker renders the live list; clicking a slug toggles it in `app-store.scope`.
3. Browse file tree renders one section per live domain.

**Per-task review:** verify nothing in the topbar/tree silently filters to the static three; default scope on first load = the user's `Config.active_domain`.

---

## Task 8 — Setup wizard's theme step uses the live domain set

**Files:**
- Modify: `apps/brain_web/src/components/setup/steps/starting-theme.tsx`
- Modify: tests

**Goal:** The wizard's step 4 currently picks one of `{research, work, personal, blank}`. Plan 10 makes it pick from the user-edited `Config.domains` (the wizard's earlier vault-location step is an opportunity to seed the list). For v0.2 the wizard ships the same default list — the change is structural, not visual: the seeds are driven by `Config.domains`, not hardcoded.

**What to do:**
1. Read `Config.domains` after the vault-location step.
2. Render a card per non-`personal` domain (personal is privacy-railed and never seeded).
3. The "blank" option stays as the don't-seed-anything escape hatch.

---

## Task 9 — Demo + e2e + lessons closure

**Files:**
- Create: `scripts/demo-plan-10.py`
- Create: `apps/brain_web/tests/e2e/domains.spec.ts`
- Modify: `tasks/lessons.md`
- Modify: `tasks/todo.md`

**Goal:** Land the demo gate from the plan header. Add a Playwright walk that creates a domain, ingests into it, renames it, and deletes it.

**Demo script gates** (re-stated):
1. Vault boots with `{research, work, personal}`.
2. Add `hobby` via `brain_create_domain`; `brain_list_domains` returns 4.
3. Ingest a fixture targeting `hobby`; assert source note + index entry under `hobby/`.
4. Rename `work` → `consulting`; assert wikilinks rewritten.
5. Reject `brain_rename_domain` for `personal`.
6. Delete `consulting`; assert trash folder + undo log entry.
7. Restart classifier with `{research, hobby, personal}`; assert ingest still routes correctly.

Print `PLAN 10 DEMO OK` on exit 0; non-zero exit on any gate failure.

**Lessons capture:** every spec bug surfaced by an implementer (rule 1–7 of `docs/style/plan-authoring.md`) goes into `tasks/lessons.md` under "Plan 10" with the date, description, and rule number. Plan 10 closure entry mirrors the format from Plan 02.

---

## Review (closed 2026-04-27)

- **Tag:** `plan-10-configurable-domains` (cut on green demo).
- **Closes:** `docs/v0.1.0-known-issues.md` item #21 (configurable domains).
- **Bumps:** tool count unchanged (36 → 36) — the four domain-admin tools (`brain_create_domain`, `brain_rename_domain`, `brain_delete_domain`, `brain_list_domains`) shipped in Plan 07 Task 4 + 25A; Plan 10 made them `Config.domains` aware and added the new D2 / D5 / D7 rails.
- **Verification:** all 7 demo gates green (`scripts/demo-plan-10.py` → `PLAN 10 DEMO OK`); 1022 brain_core/api/mcp/cli pytest cases + 247 brain_web vitest cases + 1 new Playwright e2e (`tests/e2e/domains.spec.ts`).
- **Backlog forward:**
  - "Default scope on first load = `Config.active_domain`" — descoped from Task 7 (needs `active_domain` exposure on `list_domains` response + `scopeInitialized` flag on app-store). Filed for Plan 11.
  - Disk-level config persistence for `Config.domains` mutations — currently in-memory only via the admin tools; restart relies on the on-disk folder set + `DEFAULT_DOMAINS` fallback. Issue #27.
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 10" feed Plan 11's authoring (per-domain LLM model overrides, `Config.privacy_railed` generalization, etc.).

---

**End of Plan 10.**
