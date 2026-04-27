# Plan 11 — Persistent Config + Per-Domain Overrides + Privacy Rail Generalization

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close out the three load-bearing forwards from Plan 10 in one coherent plan:

1. **B (foundation) — Disk-level Config persistence.** Today there is *no* `save_config()` in `brain_core/config/`; `loader.py` is read-only. Every mutation tool (`brain_config_set`, `brain_create_domain`, `brain_rename_domain`, `brain_delete_domain`, `brain_budget_override`) carries an explicit "in-memory only — issue #27" comment. After a restart the on-disk folder set is rediscovered (so domains survive in degraded form), but every other Config field reverts to defaults. Plan 11 ships an atomic, locked, backup-on-write `save_config()` and threads it through all five mutation tools.
2. **A (UX last-mile) — Default scope on first frontend mount = `Config.active_domain`.** Plan 10 Task 7 explicitly descoped this; the lessons-rule "don't bolt schema/state plumbing onto the end of a parent task" said treat it as a separate task. Plan 11 lifts `active_domain` onto the `brain_list_domains` response and adds a `scopeInitialized` flag to `app-store` so a first-load hydrates from the user's preferred domain instead of a hardcoded default.
3. **C (generalization) — `Config.privacy_railed: list[str]` + `Config.domain_overrides: dict[str, DomainOverride]`.** Plan 10 D5 hardcoded `personal` as the privacy-railed slug by name. Plan 11 generalizes the rail to a list (still requiring `personal` as a member — see D11) and adds optional per-domain LLM/autonomy overrides resolved through a single seam.

**Architecture:** The new persistence layer mirrors the `VaultWriter` pattern — a separate `brain_core/config/writer.py` owns all disk writes via atomic temp+rename + `filelock` + a single rolling `.bak` backup. The loader gains a fallback chain (`config.json` → `.bak` → defaults). Every mutation tool that today carries a "#27 in-memory only" comment becomes truthful in one task: after a successful in-memory mutation it calls `save_config()`; if that disk write fails, the in-memory mutation is reverted and a structured error surfaces to the caller. The per-domain override resolver lives at `brain_core/llm/__init__.py::resolve_llm_config(config, domain) -> LLMConfig`, and every consumer that today reads `config.llm.<field>` is rewritten to call the resolver. The privacy-rail generalization keeps `personal` required by validator (D11), so Plan 10's structural-by-name guarantee survives — but the rail surface is a `list[str]` so additional slugs can be railed too. Spec §4 and §7 are amended in the same commit as Task 10 to acknowledge the new shape.

**Tech Stack:** Same gates as the prior plans — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright for the frontend. One *existing* dep (`filelock`) gets a new caller; no new third-party deps.

**Demo gate:** `uv run python scripts/demo-plan-11.py` boots a temp vault with no `config.json` on disk, then walks: (1) first `brain_config_set autonomous_mode=true` writes `config.json`; restart-then-reload sees `autonomous_mode == true`. (2) `brain_create_domain hobby` persists; restart-then-reload sees `domains` includes `hobby` (proves persistence beyond folder rediscovery). (3) Set `domain_overrides.hobby.classify_model = "claude-haiku-4-5-20251001"`; invoke ingest into `hobby` and assert the cost-ledger row shows the override model, not the global. (4) Set `Config.privacy_railed = ["personal", "journal"]` and assert `journal` queries require explicit opt-in identical to `personal`. (5) Attempt to set `Config.privacy_railed = ["journal"]` (removing `personal`); assert validator refusal. (6) Attempt to mutate `Config.domain_overrides` with a key not in `Config.domains`; assert validator refusal. (7) Corrupt `config.json` to invalid JSON; restart and assert fall-back to `config.json.bak` with a structured warning logged. (8) Open the frontend with `scopeInitialized=false` in storage; assert the topbar scope picker hydrates to `[active_domain]` from the `brain_list_domains` response, then flips the flag. Prints `PLAN 11 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents:** `brain-core-engineer` (writer, loader fallback, schema, resolver, mutation-tool wiring), `brain-prompt-engineer` (no prompt changes — privacy-rail wording is tool-level, not LLM-level), `brain-frontend-engineer` (Settings → Domains override editor, privacy-rail editor, app-store scopeInitialized flag, useDomains active_domain consumer), `brain-test-engineer` (cross-package coverage sweep + Playwright e2e), `brain-installer-engineer` (no scope — install paths unchanged).

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 10 closed clean: `git tag --list | grep plan-10-configurable-domains` exists.
- Confirm no uncommitted changes on `main`.
- Confirm `tasks/lessons.md` contains the Plan 10 closure section (used by Task 1's reference to the pydantic v2 cross-field validator pattern and Task 4's reference to the "permission rail seeding" rule).
- Note that issue #27 (config persistence) in `docs/v0.1.0-known-issues.md` is the load-bearing context for Group I; Plan 11 closes it. Issue #21 stays closed (Plan 10 finished it).
- Note the recurring uv `UF_HIDDEN .pth` workaround documented in `tasks/lessons.md` Plan 10 — implementers should add `chflags nohidden .venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` before any pytest run that hits a package whose source they've modified. Do NOT re-diagnose if you see "No module named brain_core" — this is the cause every time.

---

## What Plan 11 explicitly does NOT do

These are tempting adjacent expansions that would balloon scope. Each is filed for a later plan or backlog:

- **Per-domain budget caps** — `BudgetConfig.daily_usd` / `monthly_usd` stay global. Per-domain caps need a separate ledger schema change (the cost ledger currently sums per-domain but doesn't gate per-domain).
- **Per-domain rate limits** — `LLMConfig` has no rate-limit field today; rate limits live in the provider client. Plan 11 doesn't restructure that.
- **Per-domain retention policies** — auto-archive after N days, etc. Already deferred in Plan 10 NOT-DOING list.
- **Sub-domains / nesting** — `research/papers/`, `research/talks/` as first-class scope nodes. Already deferred in Plan 10.
- **A full "Repair config" UI screen** — spec §10 ("Config / state errors → startup validator surfaces a Repair config screen") is a deeper iteration. Plan 11 lands the auto-fallback chain (D7) only; Repair UI is a future iteration.
- **Migration tool for old `config.json` files** — pydantic defaults handle missing fields automatically; no migration tool needed. If a user's `config.json` lacks `domains`, `domain_overrides`, or `privacy_railed`, the loader fills defaults on read and `save_config()` round-trips with the new fields on next mutation.
- **Hot-reload of config changes across processes** — Plan 11 persists changes; downstream processes that have cached `Config` see the change on next restart. Cross-process invalidation (e.g., `brain_api` notifying `brain_mcp` of a domain rename) is a future iteration. Document the restart requirement in user-guide.
- **Disk-persistence for `BudgetConfig.override_until` / `override_delta_usd`** — these are intentionally ephemeral (Plan 07 Task 4 design). Plan 11 *does* round-trip them via `save_config()` so a restart preserves an active override for the rest of its window, but does not extend the override semantics.
- **Per-call `temperature` overrides on the chat loop** — `temperature` is overrideable per-domain in `domain_overrides` but not per-chat-turn. That's a chat-mode feature, not a config-persistence feature.

If any of these come up during implementation, file a TODO and keep moving.

---

## Decisions (locked 2026-04-27)

User signed off on all 16 recommendations on 2026-04-27. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope. The "Decision" column is the locked decision; the "Why" column is the rationale that survives in the source comments / docstrings.

### Group I — Persistence (B)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | **`save_config()` lives in a new module** `brain_core/config/writer.py` mirroring the `VaultWriter` pattern. | ✅ | Separation of read (loader) and write (writer) seams. Matches the `VaultWriter` precedent + CLAUDE.md principle #1 ("the vault is sacred — every mutation through one writer"). |
| D2 | **Atomic-write semantics:** temp file in same dir → `os.replace()` → `fsync` the parent dir on POSIX. | ✅ | `os.replace()` is atomic on Mac and Windows (NTFS); same recipe `VaultWriter` uses today. No `shell=True`, no POSIX-only path. |
| D3 | **Concurrent-write safety:** `filelock` on `<vault>/.brain/config.json.lock`. | ✅ | brain_api + brain_mcp can both run simultaneously; spec §10 endorses `filelock`. Less invasive than reworking the brain_api ↔ brain_mcp call graph. |
| D4 | **Persisted-field whitelist:** explicit `_PERSISTED_FIELDS` set on `Config`. **Persist:** `domains`, `active_domain`, `autonomous_mode`, `web_port`, `log_llm_payloads`, `llm` (sub-config), `budget` (sub-config — *including* `override_until` / `override_delta_usd` per the NOT-DOING note above), `autonomous` (sub-config), `handlers` (sub-config), `domain_overrides` (new D12), `privacy_railed` (new D10). **Don't persist:** `vault_path` (chicken-and-egg — we need it to find `config.json`). | ✅ | Explicit > implicit. Prevents accidentally round-tripping env-only fields. |
| D5 | **Failure UX on disk-write fail:** revert in-memory mutation + raise structured error. Caller surfaces in UI. | ✅ | Inverse of "vault is source of truth, caches are derived" — disk `config.json` is the source of truth, in-memory `Config` is the cache. Cache must not diverge. |
| D6 | **Backup-on-write:** single rolling `<vault>/.brain/config.json.bak` written before each `save_config()`. | ✅ | Cheap, recoverable. Doesn't bloat snapshot infra. Prevents a crashed write from bricking startup. |
| D7 | **Loader fallback on corrupt `config.json`:** auto-fall-back to `config.json.bak` with logged warning; if `.bak` is also corrupt, fall back to defaults + structured warning. | ✅ | Spec §10 mentions a future "Repair config" UI screen — that's a deeper iteration. Auto-fallback is the pragmatic v0.2 behavior. |

### Group II — Default scope (A)

| # | Decision | Locked | Why |
|---|---|---|---|
| D8 | **`active_domain` plumbing path:** add `active_domain: str` field to `brain_list_domains` response. | ✅ | Frontend already calls `listDomains()` on every mount; one round trip. Avoids a new tool. |
| D9 | **`scopeInitialized` flag location:** boolean on app-store, persisted to `localStorage` keyed by vault path. | ✅ | Matches existing app-store persistence patterns. Prevents the "active_domain default keeps re-applying after user explicitly changed scope" footgun. |

### Group III — Per-domain overrides + privacy rail (C)

| # | Decision | Locked | Why |
|---|---|---|---|
| D10 | **`Config.privacy_railed` shape:** `list[str]` defaulting to `["personal"]`. | ✅ | Same shape as `Config.domains`; symmetric slug-validation; flat set, no per-domain dict overhead. **Requires spec §4 + §7 amendment** (D16). |
| D11 | **`personal` semantics under generalization:** `personal` REQUIRED in `privacy_railed` by validator (alongside Plan 10 D5 requirement that it's in `Config.domains`). User can ADD other slugs but cannot REMOVE `personal`. | ✅ | Generalizes the rail without weakening Plan 10's structural-by-name safety property. |
| D12 | **`Config.domain_overrides` shape:** `dict[str, DomainOverride]` where `DomainOverride` is a pydantic model with all-optional fields: `classify_model`, `default_model`, `temperature`, `max_output_tokens`, `autonomous_mode`. **NOTE on field set:** the user-locked decision named `classify_model / summarize_model / chat_model`; the real `LLMConfig` schema only has `default_model + classify_model + temperature + max_output_tokens` — `default_model` is the umbrella for non-classify operations. The override field set follows the real schema; the locked intent ("override LLM behavior per-domain, including the autonomy bool") is preserved. | ✅ | Covers the two adjacent expansions Plan 10 NOT-DOING list explicitly named. Defers per-domain budget caps + rate limits. |
| D13 | **Resolver seam for overrides:** new `resolve_llm_config(config, domain) -> LLMConfig` in `brain_core/llm/__init__.py`. Every consumer that today reads `config.llm.<field>` calls `resolve_llm_config(config, domain).<field>` instead. Autonomy override is a sibling resolver: `resolve_autonomous_mode(config, domain) -> bool`. | ✅ | Single seam, easy to test. Prevents per-call branching scattered across classifier/chat/ingest. |
| D14 | **Settings UI surface:** extend `panel-domains.tsx` with an expand/collapse override editor per domain row showing `DomainOverride` fields. The privacy-rail toggle is a per-row checkbox on the same panel (`personal` checkbox is disabled per D11). | ✅ | The per-domain admin surface already lives there. Putting overrides under LLM providers would force users to toggle between two panels per domain. |
| D15 | **`BRAIN.md` auto-update on privacy-rail change:** NO. (Plan 10 D10 stays.) Document the new field in user-guide instead, surface a one-line tip in the settings panel. | ✅ | The user's `BRAIN.md` is hand-edited and out of scope for automatic rewriting. |

### Group IV — Spec alignment

| # | Decision | Locked | Why |
|---|---|---|---|
| D16 | **Spec amendment scope:** amend §4 ("Domain separation") and §7 ("MCP server surface") wording in the same commit as the plan file: replace `personal` references with `<privacy-railed slug>` semantics. Limit amendment to wording — no architecture change. | ✅ | CLAUDE.md "Workflow rules" require spec update FIRST when changing safety rails. The spec change is in scope and lands as Task 10. |

The implementer routes any unrecognized rule edge case (D5 alternative semantics, D11 strictness, D12 field-set, D13 alternative seam location, D16 amendment beyond §4/§7) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/
│   ├── config/
│   │   ├── schema.py                    # MODIFY: + DomainOverride model, + Config.domain_overrides, + Config.privacy_railed, + _PERSISTED_FIELDS
│   │   ├── loader.py                    # MODIFY: fallback chain (config.json → .bak → defaults)
│   │   └── writer.py                    # NEW: save_config() with atomic + filelock + backup
│   ├── llm/
│   │   └── __init__.py                  # MODIFY: + resolve_llm_config(), + resolve_autonomous_mode()
│   ├── ingest/
│   │   ├── classifier.py                # MODIFY: read via resolve_llm_config() instead of config.llm.classify_model
│   │   └── pipeline.py                  # MODIFY: same for default_model / temperature / autonomy gate
│   ├── chat/
│   │   └── session.py                   # MODIFY: same for default_model / temperature
│   └── tools/
│       ├── config_set.py                # MODIFY: call save_config() after in-memory mutation; revert on disk fail
│       ├── create_domain.py             # MODIFY: same
│       ├── rename_domain.py             # MODIFY: same
│       ├── delete_domain.py             # MODIFY: same
│       ├── budget_override.py           # MODIFY: same
│       └── list_domains.py              # MODIFY: response grows active_domain field
└── tests/
    ├── config/
    │   ├── test_schema_overrides.py     # NEW: DomainOverride model + Config.domain_overrides validation
    │   ├── test_schema_privacy_rail.py  # NEW: privacy_railed list[str] validation, personal-required
    │   ├── test_writer.py               # NEW: atomic write, filelock contention, backup, _PERSISTED_FIELDS filter
    │   └── test_loader_fallback.py      # NEW: corrupt config.json → .bak; corrupt both → defaults
    ├── llm/
    │   └── test_resolver.py             # NEW: per-domain override resolution; autonomy resolver
    ├── tools/
    │   ├── test_config_set_persists.py  # NEW: round-trip via save_config; disk-fail reverts in-memory
    │   ├── test_create_domain_persists.py
    │   ├── test_rename_domain_persists.py
    │   ├── test_delete_domain_persists.py
    │   ├── test_budget_override_persists.py
    │   └── test_list_domains_active.py  # NEW: response includes active_domain
    └── integration/
        └── test_config_persistence_e2e.py  # NEW: tool mutation → restart-equivalent reload → state preserved

apps/brain_web/
├── src/components/settings/
│   ├── panel-domains.tsx                # MODIFY: per-row override editor (collapse/expand) + privacy-rail toggle
│   └── domain-override-form.tsx         # NEW: extracted DomainOverride form
├── src/lib/api/tools.ts                 # MODIFY: typed helper for active_domain on listDomains response; configSet typed for new fields
├── src/lib/state/app-store.ts           # MODIFY: + scopeInitialized flag, + localStorage persistence
├── src/lib/hooks/useDomains.ts          # MODIFY: hook surfaces active_domain
├── src/components/shell/topbar.tsx      # MODIFY: first-mount hydrates scope from active_domain
└── tests/
    ├── unit/
    │   ├── settings-domain-overrides.test.tsx  # NEW: override form validation, save/reset
    │   ├── settings-privacy-rail.test.tsx      # NEW: rail toggle, personal disabled
    │   └── app-store-scope-init.test.ts        # NEW: scopeInitialized flag, localStorage persistence
    └── e2e/
        └── persistence.spec.ts          # NEW: Playwright walk — set autonomy → restart-equivalent reload → still on

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md       # MODIFY: §4 + §7 wording per D16

docs/user-guide/
└── domain-overrides.md                  # NEW: short doc on per-domain overrides + privacy-rail editing

scripts/
└── demo-plan-11.py                      # NEW: 8-gate demo per the demo gate above

tasks/
├── plans/11-persistent-config.md        # this file
├── lessons.md                           # MODIFY: + Plan 11 closure section
└── todo.md                              # MODIFY: row 11 → ✅ Complete on closure
```

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 10. Every implementer task MUST end with this checklist before reporting DONE.

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core` (or whichever package)
3. **uv `UF_HIDDEN` workaround:** `chflags nohidden /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` — clears the recurring "No module named brain_core" symptom (lessons.md Plan 10).
4. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions
5. `cd packages/<pkg> && uv run mypy src tests && cd -` — strict clean
6. `uv run ruff check . && uv run ruff format --check .` — clean
7. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
8. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check in the spec is invariant-based, not total-based.
9. **Browser-in-the-loop verification** for any task that touches a UI surface (Tasks 7 + 8 + 9): start brain, take screenshots of the relevant flows pre and post change, attach to per-task review.
10. `git status` — clean after commit

Any failure in 4–9 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — Schema: `Config.privacy_railed` + `Config.domain_overrides` + `_PERSISTED_FIELDS`

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py`
- Create: `packages/brain_core/tests/config/test_schema_privacy_rail.py`
- Create: `packages/brain_core/tests/config/test_schema_overrides.py`

**Goal:** Land the new pydantic shapes. Everything else in the plan depends on these fields existing.

**What to do:**
1. Add `class DomainOverride(BaseModel)` with all-optional fields: `classify_model: str | None`, `default_model: str | None`, `temperature: float | None` (with same `ge=0.0, le=1.5` as `LLMConfig.temperature`), `max_output_tokens: int | None` (with `gt=0`), `autonomous_mode: bool | None`. `model_config = ConfigDict(extra="forbid")`.
2. Add `Config.domain_overrides: dict[str, DomainOverride] = Field(default_factory=dict)`. Add a `model_validator(mode="after")` that asserts every key in `domain_overrides` is a member of `self.domains` (cross-field check, same pattern as Plan 10's `_check_active_domain_in_domains`).
3. Add `Config.privacy_railed: list[str] = Field(default_factory=lambda: [PRIVACY_RAILED_SLUG])`. Add a `field_validator("privacy_railed")` that runs the D2 slug rules + D11 requirement (`PRIVACY_RAILED_SLUG` must be present). Add a `model_validator(mode="after")` that asserts every entry is also in `self.domains` (you cannot rail a slug that doesn't exist as a domain).
4. Add `_PERSISTED_FIELDS: frozenset[str]` at module scope listing the fields from D4. Reference it from a class-method `Config.persisted_dict(self) -> dict[str, Any]` that returns `self.model_dump(include=_PERSISTED_FIELDS)`.

**Spec for the new test files:**

`test_schema_privacy_rail.py`:
- Default `Config().privacy_railed == ["personal"]`.
- `Config(privacy_railed=["personal", "journal"], domains=[..., "journal"])` validates.
- `Config(privacy_railed=["journal"])` raises (missing `personal`).
- `Config(privacy_railed=["personal", "1bad"])` raises (slug rule).
- `Config(privacy_railed=["personal", "ghost"], domains=["research", "work", "personal"])` raises (`ghost` not in domains).
- `Config(privacy_railed=["personal", "personal"])` raises (duplicate).

`test_schema_overrides.py`:
- Default `Config().domain_overrides == {}`.
- `DomainOverride()` (all-default) validates with all-`None` fields.
- `DomainOverride(temperature=2.0)` raises (above ceiling).
- `DomainOverride(temperature=-0.1)` raises (below floor).
- `DomainOverride(max_output_tokens=0)` raises (must be > 0).
- `DomainOverride(extra_field="x")` raises (`extra="forbid"`).
- `Config(domain_overrides={"hobby": DomainOverride(classify_model="haiku")}, domains=["research", "work", "personal", "hobby"])` validates.
- `Config(domain_overrides={"ghost": DomainOverride()}, domains=["research", "work", "personal"])` raises (`ghost` not in domains).
- `Config().persisted_dict()` returns a dict with exactly the D4 keys, no `vault_path`.

**Per-task review:** existing Plan 10 schema tests (`test_schema_domains.py`) still pass — adding fields shouldn't regress them. Run `test_settable_keys_all_resolve_to_a_real_schema_field` (Plan 04 schema-vs-allowlist regression test) and decide whether `domain_overrides` and `privacy_railed` should join `_SETTABLE_KEYS` (recommendation: NO for now — these are structured fields surfaced via dedicated tools, not the generic `brain_config_set`. Document the exception in `_KNOWN_NOT_ON_CONFIG`).

---

## Task 2 — Writer: `save_config()` with atomic + filelock + backup

**Files:**
- Create: `packages/brain_core/src/brain_core/config/writer.py`
- Create: `packages/brain_core/tests/config/test_writer.py`

**Goal:** Land the atomic, locked, backup-on-write `save_config()`. This is the foundational seam for D1 + D2 + D3 + D6.

**What to do:**
1. New `save_config(config: Config, vault_root: Path) -> Path` returns the path of the written `config.json`.
2. Resolve `<vault_root>/.brain/config.json`. Ensure `<vault_root>/.brain/` exists (mkdir parents=True, exist_ok=True).
3. Acquire `filelock.FileLock("<vault_root>/.brain/config.json.lock", timeout=5.0)`. Surface lock-acquisition timeout as a structured `ConfigPersistenceError` (new exception class in this module) with message "another brain process is writing config.json; try again".
4. If `config.json` exists, copy it to `config.json.bak` (D6). Use `shutil.copy2` to preserve mtime; this is fine on both Mac and Windows.
5. Serialize via `config.persisted_dict()` (Task 1) → `json.dumps(..., indent=2, sort_keys=True, default=_json_default)` where `_json_default` handles `Path` → `str` and `datetime` → ISO-8601 (matches existing patterns in `chat/persistence.py`).
6. Write to `<vault_root>/.brain/config.json.tmp` (UTF-8, LF line endings explicitly: `newline="\n"`), then `os.replace(tmp, target)` (atomic on Mac and Windows).
7. On POSIX (`os.name == "posix"`), `fsync` the parent dir: open the dir as a fd, call `os.fsync(fd)`, close. Skip on Windows (no equivalent that's both atomic and portable; `os.replace` already gives the durability guarantee on NTFS).
8. Return the target path.

**Spec for `test_writer.py`:**
- `save_config(Config(), tmp_path)` writes `<tmp_path>/.brain/config.json` containing valid JSON; round-tripping via `json.loads` produces a dict whose keys are exactly `_PERSISTED_FIELDS`.
- `save_config(...)` twice in a row leaves `config.json.bak` containing the *previous* contents.
- Mid-write crash simulation: monkeypatch `os.replace` to raise; assert no `config.json` exists (the tmp file may exist; clean it up in the writer's `try/except` with `tmp.unlink(missing_ok=True)`).
- Lock contention: `with filelock.FileLock(...).acquire():` in one thread; another thread's `save_config()` raises `ConfigPersistenceError` with the timeout message. Use a 0.5s timeout in the test to keep it fast.
- `vault_path` is NOT in the persisted JSON (D4 sanity check).
- Pretty-printed output: round-tripping a `Config` whose `domains == ["research", "work", "personal", "hobby"]` produces a JSON file whose `domains` array has stable ordering on disk (sort_keys preserves dict ordering deterministically).

**Per-task review:** verify the writer file imports nothing from `brain_core.tools.*` or `brain_core.vault.*` — it sits at the `config/` layer, peer to `loader.py`. Cross-platform check: run the tests on Mac (CI default) and confirm the `os.fsync` parent-dir branch is exercised; the test for the `os.name == "posix"` skip path can be a single `monkeypatch.setattr(os, "name", "nt")` round-trip to assert no `fsync` call is made.

---

## Task 3 — Loader fallback chain (`config.json` → `.bak` → defaults)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/loader.py`
- Create: `packages/brain_core/tests/config/test_loader_fallback.py`

**Goal:** Make the loader survive a corrupt `config.json` per D7. Today `load_config` raises ValueError on JSON parse failure — that would brick startup if the writer ever crashes mid-write.

**What to do:**
1. Refactor `load_config()`'s file-read branch into a helper `_try_read_config_file(path: Path) -> dict[str, Any] | None`: returns parsed dict on success, `None` (with a `structlog.warning(...)` line) on parse error or file-missing.
2. New behavior: try `config.json` → on `None`, try `config.json.bak` → on `None`, use empty dict (defaults).
3. Each fallback step logs a structured warning: `event="config_load_fallback"`, `attempted=path`, `reason="parse_error"` or `"missing"`.
4. The `config_file` parameter to `load_config` keeps its existing semantics (caller passes the *primary* path). The loader looks for `<config_file.parent>/<config_file.stem>.bak` automatically.

**Spec for `test_loader_fallback.py`:**
- Clean read: write valid `config.json`, no `.bak`; loader returns parsed Config; no warning logged.
- Corrupt main + valid bak: write garbage to `config.json`, valid JSON to `config.json.bak`; loader returns Config from bak; warning logged with `attempted=config.json`.
- Corrupt main + corrupt bak: both garbage; loader returns default `Config()`; two warnings logged.
- Missing main + valid bak: only `.bak` exists; loader returns Config from bak (this matches a hypothetical "user manually deleted config.json" case).
- Loader signature unchanged — env layer + cli_overrides still applied on top of whichever layer succeeded.

**Per-task review:** ensure the existing Plan 04 / Plan 10 loader tests still pass. The fallback chain is additive — clean reads behave identically.

---

## Task 4 — Wire `save_config()` into all five mutation tools

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py`
- Modify: `packages/brain_core/src/brain_core/tools/create_domain.py`
- Modify: `packages/brain_core/src/brain_core/tools/rename_domain.py`
- Modify: `packages/brain_core/src/brain_core/tools/delete_domain.py`
- Modify: `packages/brain_core/src/brain_core/tools/budget_override.py`
- Create: `packages/brain_core/tests/tools/test_config_set_persists.py`
- Create: `packages/brain_core/tests/tools/test_create_domain_persists.py`
- Create: `packages/brain_core/tests/tools/test_rename_domain_persists.py`
- Create: `packages/brain_core/tests/tools/test_delete_domain_persists.py`
- Create: `packages/brain_core/tests/tools/test_budget_override_persists.py`

**Goal:** Every "#27 in-memory only" comment in the codebase becomes truthful. After a successful in-memory mutation, each tool calls `save_config(ctx.config, ctx.vault_root)`. If save fails, the in-memory mutation is reverted and a structured error surfaces (D5).

**What to do (per tool):**
1. Wrap the existing in-memory mutation in: snapshot the current `Config` (via `ctx.config.model_copy(deep=True)`) → mutate in-place → call `save_config(ctx.config, ctx.vault_root)` inside `try`.
2. On `ConfigPersistenceError` (or any exception from `save_config`): assign the snapshot back over `ctx.config`'s mutable fields (pydantic v2 `__pydantic_fields_set__`-aware copy) and re-raise as the tool's existing error type with a wrapping message.
3. Update each tool's docstring: remove the "in-memory only — issue #27" sentence; replace with "persisted to `<vault>/.brain/config.json` via `save_config()`".

**Spec for each `test_*_persists.py`:**
- Success path: invoke tool, assert in-memory mutation present, assert `<vault>/.brain/config.json` written, assert reload-via-load_config sees the mutation.
- Disk-fail path: monkeypatch `save_config` to raise `ConfigPersistenceError`; invoke tool; assert in-memory state matches pre-mutation snapshot AND assert tool surfaced the error.
- Concurrent-call path (one test per file is enough — no need to stress every tool): two threads invoking the tool serialize via the filelock and both ultimately succeed (no data loss).
- `budget_override` only: assert that `override_until` and `override_delta_usd` round-trip (per the NOT-DOING note that they intentionally persist).

**Per-task review:** lessons.md "Test-fixture seeding has to track new permission rails" applies here — running each tool's existing test file FIRST and verifying no fixture is missing the mutation-snapshot expectation. Also verify that `set_api_key.py` does NOT get this treatment: secrets live in `secrets.env`, not `config.json` (Plan 09 #20 closure).

---

## Task 5 — Resolver: `resolve_llm_config()` + `resolve_autonomous_mode()` + consumer rewrite

**Files:**
- Modify: `packages/brain_core/src/brain_core/llm/__init__.py`
- Create: `packages/brain_core/tests/llm/test_resolver.py`
- Modify (consumer): `packages/brain_core/src/brain_core/ingest/classifier.py`
- Modify (consumer): `packages/brain_core/src/brain_core/ingest/pipeline.py`
- Modify (consumer): `packages/brain_core/src/brain_core/chat/session.py`
- Modify (consumer): `packages/brain_core/src/brain_core/tools/classify.py`
- Modify (consumer): `packages/brain_core/src/brain_core/tools/ingest.py`
- Modify (consumer): `packages/brain_core/src/brain_core/tools/bulk_import.py`
- Modify (consumer): any other consumer that today reads `config.llm.*` or `config.autonomous_mode` in a domain-aware context (audit via grep)

**Goal:** Per D13, single seam for per-domain override resolution. Every consumer that today reads `config.llm.<field>` or `config.autonomous_mode` in a domain-aware context goes through the resolver.

**What to do:**
1. Add `def resolve_llm_config(config: Config, domain: str | None) -> LLMConfig` to `brain_core/llm/__init__.py`. Behavior: if `domain` is `None` or has no entry in `config.domain_overrides`, return `config.llm` unchanged. Otherwise, build a new `LLMConfig` by merging: for each field in `LLMConfig`, take the override value if set, else the global `config.llm.<field>`.
2. Add `def resolve_autonomous_mode(config: Config, domain: str | None) -> bool`. Same merge pattern: override if set on `config.domain_overrides[domain].autonomous_mode`, else `config.autonomous_mode`. Note: `Config.autonomous` (the per-category flags model) is NOT covered by this resolver — the per-domain override is a single coarse boolean intended to mirror the existing global `autonomous_mode`. Per-domain category flags are a future iteration (filed in NOT-DOING).
3. Audit consumers via grep `grep -rn "config\.llm\." packages/brain_core/src/` and `grep -rn "config\.autonomous_mode" packages/brain_core/src/`. For each match in an ingest / chat / classify path: replace with the resolver call passing the active domain. For matches in non-domain-aware paths (e.g. `ping_llm`, `cost_report` formatting): leave unchanged, document the exception as a one-line comment.

**Spec for `test_resolver.py`:**
- `resolve_llm_config(config, None)` returns `config.llm` (identity check on field values, not necessarily the same object).
- `resolve_llm_config(config, "research")` with no override returns equivalent of `config.llm`.
- `resolve_llm_config(config, "hobby")` with `config.domain_overrides["hobby"] = DomainOverride(classify_model="haiku-X")` returns an `LLMConfig` whose `classify_model == "haiku-X"` and other fields match `config.llm`.
- Partial override: only `temperature` set → resolver returns `LLMConfig` with `temperature` from override and `default_model / classify_model / max_output_tokens` from global.
- `resolve_autonomous_mode(config, "hobby")` with `autonomous_mode=True` global and `domain_overrides["hobby"].autonomous_mode=False` returns `False`.
- `resolve_autonomous_mode(config, "hobby")` with `autonomous_mode=False` global and `domain_overrides["hobby"].autonomous_mode=True` returns `True`.
- Override for a domain not in `Config.domains` → cannot happen (Task 1 validator catches it), but defensively: resolver doesn't crash if `domain` is some arbitrary string (returns the global).

**Per-task review:** every consumer rewrite has its existing tests run; existing tests should pass unchanged (the override field is empty by default → resolver returns the global). Add one new parameterized test in each consumer's test file that asserts the resolver IS being called (e.g. monkeypatch `resolve_llm_config` to return a sentinel and verify the consumer used it).

---

## Task 6 — `brain_list_domains` exposes `active_domain` (A)

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/list_domains.py`
- Modify: `packages/brain_core/tests/tools/test_list_domains.py`
- Create: `packages/brain_core/tests/tools/test_list_domains_active.py`

**Goal:** Per D8, the response shape grows `active_domain: str` field so the frontend can hydrate scope on first load without a second round trip.

**What to do:**
1. Add `active_domain: str` to the `ListDomainsResult` response model. Source: `ctx.config.active_domain`.
2. Update the JSON schema in the tool registration so MCP and API consumers see the new field.
3. mypy strict on the new field; ensure the response constructor in the tool body sets it.

**Spec for `test_list_domains_active.py`:**
- Default Config → response `active_domain == "research"`.
- Config with `active_domain="work"` → response reflects it.
- Config where `active_domain` was changed via `brain_config_set` → next `brain_list_domains` call reflects it (read-after-write within a session).

**Per-task review:** existing tests for `list_domains` still pass; the new field is additive. Frontend Task 9 will consume this field — flag for the frontend implementer that the response shape changed.

---

## Task 7 — Settings → Domains panel: per-domain override editor + privacy-rail toggle

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx`
- Create: `apps/brain_web/src/components/settings/domain-override-form.tsx`
- Modify: `apps/brain_web/src/lib/api/tools.ts` (typed helpers for `domain_overrides` / `privacy_railed` mutation paths)
- Create: `apps/brain_web/tests/unit/settings-domain-overrides.test.tsx`
- Create: `apps/brain_web/tests/unit/settings-privacy-rail.test.tsx`

**Goal:** Per D14, surface per-domain overrides + privacy-rail toggle on the existing domains panel.

**What to do:**
1. Each domain row gets an expand/collapse caret. Expanded state shows `<DomainOverrideForm>` with optional fields: `classify_model`, `default_model`, `temperature`, `max_output_tokens`, `autonomous_mode`. "Reset to global" per-field button clears the override.
2. Each domain row gets a "Privacy-railed" checkbox. Checked = slug is in `Config.privacy_railed`. Unchecking removes it (except for `personal` — checkbox is `disabled` with a tooltip "personal is required and cannot be un-railed" per D11).
3. Both surfaces persist via the appropriate path:
   - Override edits: a new tool call (recommendation: `brain_set_domain_override(slug, override)` — or extend `brain_config_set` to accept the dotted key `domain_overrides.<slug>.<field>`; pick one and pin it. **Recommendation: extend `brain_config_set` for consistency with the existing settings flow** — this means the `_SETTABLE_KEYS` allowlist on `brain_config_set` grows to include `domain_overrides.<slug>.classify_model` etc. as wildcard-pattern entries. This is the same pattern as `handlers.<name>.<field>` already in `_SETTABLE_KEYS`).
   - Privacy-rail toggle: same — `brain_config_set` with key `privacy_railed`.
4. After every successful mutation: refresh `useDomains()` cache (per Plan 10 lessons "Frontend cache invalidation needs to fan out").
5. Toast on success/failure via `system-store`.

**Spec for the new test files:**

`settings-domain-overrides.test.tsx`:
- Renders the form for a domain with no overrides; all fields show placeholder = "uses global".
- Setting `classify_model = "claude-haiku-4-5-20251001"` and clicking Save → calls `brain_config_set` with `domain_overrides.<slug>.classify_model` and the value.
- "Reset to global" clicks send `null` for that field (which Task 4's `config_set` interprets as "remove this override field").
- Form validation surfaces D2 slug rules client-side (consistent with Plan 10 panel-domains validation).

`settings-privacy-rail.test.tsx`:
- `personal` row's Privacy-railed checkbox is `disabled` AND `checked`.
- Other rows: checking adds the slug to `Config.privacy_railed` via `brain_config_set`; unchecking removes it.
- Last-domain delete edge case: if the user deletes a railed domain, the panel auto-removes it from the rail before the delete (or the backend rejects with a clear error and the panel shows it; pin the cleaner option in implementation review).

**Per-task review:** Browser-in-the-loop verification per CLAUDE.md "Verification Before Done" rule. Reviewer takes screenshots of: the panel with one expanded override editor, the panel with `personal` checkbox disabled-and-checked, and a post-save toast. **Merge ordering:** Task 9 (spec amendment) MUST be merged before this task's PR — the privacy-rail UI describes user-facing behavior the spec needs to acknowledge. Implementer can develop in either order but the merge sequence is locked.

---

## Task 8 — `useDomains()` + topbar consume `active_domain` on first mount

**Files:**
- Modify: `apps/brain_web/src/lib/hooks/useDomains.ts`
- Modify: `apps/brain_web/src/lib/state/app-store.ts`
- Modify: `apps/brain_web/src/components/shell/topbar.tsx`
- Create: `apps/brain_web/tests/unit/app-store-scope-init.test.ts`
- Modify: `apps/brain_web/tests/unit/topbar.test.tsx`

**Goal:** Per A + D8 + D9, on first frontend mount with `scopeInitialized=false`, hydrate `app-store.scope = [active_domain]` from the `brain_list_domains` response, then flip the flag.

**What to do:**
1. `useDomains()` hook: in addition to the existing `Domain[]` it returns, expose `activeDomain: string` from the response.
2. `app-store`: add `scopeInitialized: boolean` (default `false`), persist to `localStorage` keyed by vault path (read the existing pattern from `useVaultName`). Add an action `markScopeInitialized()`.
3. Topbar (or a higher-level shell component — pick the cleanest mount point): on first mount where `scopeInitialized === false` AND the hook has resolved, set `scope = [activeDomain]` then call `markScopeInitialized()`. Subsequent mounts read scope from app-store as today.
4. If `activeDomain` is not in the live domain list (rare race — user changed `active_domain` then deleted that domain in another window), fall back to the first non-railed domain in the list. Log a warning to the console.

**Spec for `app-store-scope-init.test.ts`:**
- Fresh app-store: `scopeInitialized === false`, `scope === []`.
- After calling `markScopeInitialized()`: flag flips, persisted to localStorage.
- Reload app-store from a localStorage that has `scopeInitialized=true`: flag survives the reload, scope is whatever was persisted.
- Vault path change clears the scopeInitialized flag (so a different vault re-runs first-load hydration).

**Per-task review:** Browser-in-the-loop verification — fresh-localStorage walk: open brain in incognito, confirm topbar scope picker shows the active_domain selected (not all-three or empty); change active_domain via Settings, reload incognito, confirm new active_domain is now the first-load default. Lessons.md "default scope follow-up was descoped explicitly" rule satisfied — this is now its own task with the schema/state plumbing it needs.

---

## Task 9 — Spec amendment + user-guide doc updates (D16)

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§4 + §7 wording per D16)
- Create: `docs/user-guide/domain-overrides.md`

**Goal:** Bring the spec in line with `Config.privacy_railed: list[str]`. CLAUDE.md "Workflow rules" require spec update FIRST when changing safety rails — so this task (despite landing late in plan order) is a HARD prerequisite for Task 7's privacy-rail UI to ship.

**What to do:**
1. Spec §4 ("Domain separation — Hybrid scoped model"): replace the sentence "Cross-scope is always opt-in; default queries stay in one domain." with: "Cross-scope is always opt-in; default queries stay in one domain. Any domain in `Config.privacy_railed` (defaulting to `[\"personal\"]`) is excluded from default and wildcard queries — explicit inclusion in the `domains` argument is required for read access. The list is user-editable via Settings → Domains; `personal` is structurally required and cannot be removed."
2. Spec §7 ("MCP server surface — Security"): replace `personal domain reads require explicit inclusion in the domains argument — never in wildcards` with `Privacy-railed domain reads (any slug in Config.privacy_railed) require explicit inclusion in the domains argument — never in wildcards`.
3. New `docs/user-guide/domain-overrides.md`: ~150 words covering (a) what `Config.privacy_railed` does, (b) what `Config.domain_overrides` does, (c) where to edit them in Settings, (d) the restart-required note (per the NOT-DOING "hot-reload" item).

**Per-task review:** verify no other section of the spec references `personal` in a way that contradicts the new generalization. Run `grep -n "personal" docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` and inspect each match; update or leave as-is (e.g., the §1 Overview's "personal (life admin, decisions, references)" is fine — it's describing the default domain, not the rail).

---

## Task 10 — Demo + e2e + lessons closure

**Files:**
- Create: `scripts/demo-plan-11.py`
- Create: `apps/brain_web/tests/e2e/persistence.spec.ts`
- Modify: `tasks/lessons.md`
- Modify: `tasks/todo.md`

**Goal:** Land the 8-gate demo from the plan header. Add a Playwright walk that mutates settings, restart-equivalent reload, and asserts persistence. Capture lessons.

**Demo script gates** (re-stated):
1. Vault boots with no `config.json`; `brain_config_set autonomous_mode=true` writes `config.json`; reload Config via `load_config()` → `autonomous_mode == True`.
2. `brain_create_domain hobby` persists; reload sees `domains` includes `hobby`.
3. Set `domain_overrides.hobby.classify_model = "claude-haiku-4-5-20251001"`; ingest a fixture into `hobby`; assert the cost-ledger row records the override model (use `cost_report` tool to inspect).
4. Set `Config.privacy_railed = ["personal", "journal"]`; assert `journal` is excluded from a wildcard `brain_search` call exactly like `personal` is.
5. Attempt `Config.privacy_railed = ["journal"]` (removing `personal`); assert validator refusal.
6. Attempt `Config.domain_overrides = {"ghost": DomainOverride()}` with `ghost` not in `domains`; assert validator refusal.
7. Corrupt `config.json` with `path.write_text("{not json")`; reload via `load_config()` and assert it returned a valid Config sourced from `.bak` + a structlog warning was emitted (capture via `structlog.testing.capture_logs`).
8. Frontend gate: spawn Playwright, clear `localStorage`, open brain at `http://localhost:4317`, assert the topbar scope chip shows the active_domain (e.g., "research"), assert localStorage now has `scopeInitialized=true`.

Print `PLAN 11 DEMO OK` on exit 0; non-zero exit on any gate failure. Use the same fixture-vault pattern as `scripts/demo-plan-10.py`.

**Lessons capture:** every spec bug surfaced by an implementer (rule 1–7 of `docs/style/plan-authoring.md`) goes into `tasks/lessons.md` under "Plan 11" with the date, description, and rule number. Plan 11 closure entry mirrors the Plan 10 format: closure summary, then one paragraph per lesson worth carrying forward.

**Demo script execution prefix** for the implementer: same `chflags nohidden` workaround as the per-task checklist; this script imports brain_core and will trip the bug otherwise.

---

## Review (pending)

To be filled in on closure following the Plan 10 format:
- **Tag:** `plan-11-persistent-config` (cut on green demo).
- **Closes:** `docs/v0.1.0-known-issues.md` item #27 (config persistence).
- **Bumps:** tool count change TBD by Task 7's pinning (extend `brain_config_set` allowlist [no tool count change] vs new `brain_set_domain_override` tool [+1]).
- **Verification:** all 8 demo gates green (`scripts/demo-plan-11.py` → `PLAN 11 DEMO OK`); pytest count + vitest count + Playwright count to be filled in.
- **Backlog forward:** TBD per implementer-surfaced backlog items; candidate Plan 12 themes documented above in NOT-DOING (per-domain budget caps; per-domain rate limits; Repair-config UI; cross-process config invalidation).
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 11" feed Plan 12's authoring.

---

**End of Plan 11.**
