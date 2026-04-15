# brain — Lessons Learned

> Running log of corrections, patterns, and rules. Updated after any user correction, any plan step that went sideways, and any subagent that needed re-dispatch. Review at the start of every session and before authoring each new plan.

## How to use

- Each entry is a short rule with context: **what went wrong**, **why**, **what to do instead**.
- Rules are scoped: project-wide, per-agent, or per-sub-plan.
- Obsolete lessons are struck through with `~~` rather than deleted, so the history is preserved.
- New entries include the date (YYYY-MM-DD) they were added.

## Project-wide

### Deferred architectural questions

- **2026-04-14 — iCloud + uv's `editable=false` workaround creates ghost `* 2.py` / `* 3.py` duplicate files in `.venv/lib/python3.12/site-packages/brain_core/`.** After many `uv sync --reinstall-package brain_core` cycles, Finder's iCloud sync fought with uv's wheel unpacking and produced Finder-style duplicate filenames (`writer 2.py`, `types 3.py`, etc.) inside the installed wheel. These dragged `pytest --cov` reported coverage from 94% down to 78% by adding ~330 lines of "0% covered" phantom code. They are NOT in `src/` and do not affect runtime behavior. **Fix:** `find .venv -name "* [0-9].py" -delete`. **Rule:** if coverage suddenly drops with no source changes, suspect ghost files first. Long-term fix is Plan 01's follow-up to flip `editable = true` once uv's hidden `.pth` bug is resolved. Raised by Task 24 sweep.

- **2026-04-14 — `ClassifyOutput.domain` is a hardcoded `Literal["research","work","personal"]`.** Custom user domains will fail pydantic validation, which the pipeline catches as a generic FAILED with an opaque message. Deliberate for now because the three-domain model is baked into CLAUDE.md (`personal` as a privacy rail), but revisit when user-configurable domains land. **Decision: defer** — tracked for a future config-driven domains task. Raised by Task 17 code quality review.

- **2026-04-14 — `failures.record_failure` silently overwrites on slug collision.** `<slug>.error.json` is keyed only by slug, so a retry destroys the prior failure record. For a single-user tool this is low-stakes, but a `"{slug}.{timestamp}.error.json"` naming convention would preserve retry history. **Decision: defer** — touches the Task 12 `failures.py` module, small follow-up. Raised by Task 17 code quality review.

- **2026-04-14 — Plan 02 handler-hardening sweep COMPLETE.** The 10-item deferred backlog accumulated during Plan 02 Tasks 3–10 was consolidated into three commits after all 8 handlers landed:
  - **Batch 1** (`f36f223`) — targeted behavior fixes: `pdf.py` context-manager via `with fitz.open(...)`, `url.py` raise `HandlerError` on empty trafilatura body, `email.py` tightened `can_handle` (require `@` in From) + removed dead `else` branch, `transcript_vtt.py` `\n\n` separator + dropped `str(spec)`, `transcript_docx.py` dropped `str(spec)`.
  - **Batch 2** (`cd8aad0`) — error-wrapping sweep: raw library exceptions wrapped in `HandlerError` with plain-English "next action" messages across text/url/pdf/transcript_text/transcript_vtt/transcript_docx/tweet. Exception classes used: narrow where available (`UnicodeDecodeError`, `httpx.HTTPStatusError`/`RequestError`, `fitz.FileDataError`, `webvtt.errors.MalformedFileError`/`MalformedCaptionError`, `ValueError` for `json.JSONDecodeError`), bare `Exception` only for `transcript_docx` (python-docx raises heterogeneous types from `zipfile.BadZipFile` to `KeyError`). `email.py` intentionally skipped — stdlib `email.message_from_string` is deliberately forgiving and never raises. All `raise ... from exc` chains preserved.
  - **Batch 3** (`f9553b9`) — test strengthening: new parametrized `test_handler_extract_guards.py` exercises every handler's `extract` bad-input guard (13 cases across 8 handlers), `TranscriptTextHandler` stem-guard tests, `TweetHandler` archive-path assertion.

  Final state: **112 passed, 1 skipped** (up from 88), mypy strict + ruff clean. **Items still deferred:** `can_handle` async→sync Protocol change (out of sweep scope — consult user before touching Protocol); URL `timeout` / PDF `min_chars` config injection (deferred to Task 17 orchestrator); plan-authoring retrospective notes (Task 5 fixture sizing, Task 10 title spec bug); dispatcher ordering contract (enforced in Task 11 test); Plan 01 UndoLog parser and VaultWriter rollback (unrelated to ingest).

- **2026-04-13 — UndoLog parser uses `END_PREV` sentinel, ignores written `PREV_LEN` byte-count (Task 14 nit).** If a `prev_text` line happened to be exactly `END_PREV`, the parser would terminate early. Currently safe because none of our content will contain that literal, but the parser should be hardened to slice by the `PREV_LEN` byte count instead of scanning for a sentinel. **Decision: defer** — low-priority robustness fix, no failure case under the current vault content policy. Revisit if user notes are imported that contain arbitrary text blobs.

- **2026-04-13 — VaultWriter rollback hardening (Task 13 nits).** The paranoid review of `VaultWriter` flagged three non-blocking robustness issues that are legitimate but not urgent: (1) individual rollback steps aren't wrapped in try/except, so a mid-rollback failure aborts remaining reverts; (2) undo records are only persisted after all mutations succeed, so a process crash between `_atomic_write` calls and `_write_undo_record` leaves no on-disk undo; (3) `Receipt.applied_files` is not cleared on rollback (moot today because the exception re-raises, but defensive hygiene). **Decision: defer** — all three require careful design (partial-undo semantics, crash-recovery ordering) that benefits from real-world stress testing first. Revisit after Plan 02 exercises `VaultWriter` at ingest volume. The `log_entry` newline-sanitization nit (finding #1) WAS fixed inline during Task 13 with a regression test.

- **2026-04-14 — `SourceHandler.can_handle` declared `async` but is required to be network-free / side-effect-free — the `async` is vacuous.** Every call site has to `await` a pure string/path check. More importantly, future handlers copying the pattern may wrongly assume `can_handle` is a safe place for lightweight I/O. **Decision: defer** — changing the Protocol affects Task 1 (`base.py`) and would propagate to 7 handlers. Revisit as part of the dispatcher (Task 11) work or as a standalone cleanup once all handlers land. Raised by Task 4 code quality review.

- **2026-04-14 — URL handler silently returns empty `body_text` when trafilatura extracts nothing.** `trafilatura.extract(...) or ""` hides the difference between "extracted zero-length" and "extraction failed" (JS-rendered pages, login walls, pure nav chrome). Downstream the LLM summarize step gets garbage input with no clear signal. **Decision: defer** — should be folded into the cross-cutting `HandlerError`-wrapping sweep so all handlers get consistent "no readable content" semantics. Raised by Task 4 code quality review.

- **2026-04-14 — Plan 02 Task 5 fixture spec was internally inconsistent.** Plan's suggested fixture content (`'Plan 02 PDF fixture\nParagraph one.\nParagraph two.'`, ~49 chars) is below `PDFHandler`'s default `min_chars=200`, so the happy-path test would spuriously raise `ScannedPDFError`. Implementer (correctly) expanded the fixture to ~295 chars preserving the required assertion substrings. **Rule for plan authoring:** when a handler has a configurable threshold AND the happy-path test uses a fixture under the threshold, explicitly size the fixture to clear it. Revisit during plan-authoring retrospective.

- **2026-04-14 — Plan 02 Task 10 spec bug: title template didn't match test assertion.** Plan's `f"Tweet by {display}"` with fixture `display="Andrej Karpathy"` produces `"Tweet by Andrej Karpathy"` — the test assertion `"karpathy" in es.title` is case-sensitive and matches "Karpathy" with capital K, NOT the lowercase "karpathy". Implementer fixed inline by adding `@screen_name` into the title (e.g. `"Tweet by Andrej Karpathy (@karpathy)"`). **Rule for plan authoring:** run the test's string assertions against the test's fixture values by hand when writing plans — case-sensitive substring checks are a frequent spec bug source.

- **2026-04-14 — TweetHandler test omits `archive_path.exists()` assertion that URL handler test has.** Archive-write is production-relevant behavior; the tweet test relies on no regression protection. **Decision: fold into the post-Task 10 test-strengthening sweep** — add archive assertions to all handler tests consistently. Raised by Task 10 review.

- **2026-04-14 — Tweet handler must be dispatched BEFORE URL handler; the ordering contract lives in the dispatcher, not the handlers.** Tweet URLs also match URLHandler's `can_handle`, so if dispatcher iteration order is wrong, tweets silently get trafilatura-scraped. Task 11's `_default_handlers()` list already places Tweet before URL (per plan lines 1368–1378) and the dispatcher test `test_dispatch_tweet_url_picks_tweet_handler_before_url_handler` enforces it. No action here; just document the contract so future handler additions don't break it. Raised by Task 10 review.

- **2026-04-14 — TranscriptVTTHandler joins cues with `"\n"` while TranscriptDOCXHandler joins paragraphs with `"\n\n"`.** Inconsistent across handlers, and the VTT choice collapses intra-cue newlines into inter-cue separators — LLM loses "continuation of same utterance" vs "new speaker turn" distinction. **Decision: fix in the post-Task 10 handler-hardening sweep** — standardize all handlers on `"\n\n"` paragraph separators and re-verify test assertions still pass (should, since they use substring containment). Raised by Tasks 7–9 code quality review.

- **2026-04-14 — Redundant `str(spec)` conversions in transcript_vtt.py and transcript_docx.py.** `webvtt.read`/`webvtt.from_srt` and `docx.Document` all accept `Path` directly at runtime. The `str()` wrap is spec-verbatim but inconsistent with `text.py`'s direct `spec.read_text()` style. Minor cleanup — fold into the same sweep. Raised by Tasks 7–9 code quality review.

- **2026-04-14 — TranscriptTextHandler's `"transcript" in spec.stem.lower()` stem guard is the single load-bearing line that separates it from TextHandler, and it is untested.** Task 11 dispatcher tests will implicitly exercise it (`hello.txt` must route to TextHandler, not TranscriptTextHandler), but a direct can_handle-true and can_handle-false pair is trivial to add. **Decision: defer to the post-Task 10 test-strengthening sweep** — same pass that adds extract-on-bad-input tests across all handlers. Raised by Task 7 code quality review.

- **2026-04-14 — EmailHandler body-extraction has dead `else` branch copied from plan spec.** For non-multipart messages, `msg.get_payload(decode=True)` always returns `bytes` (never a non-bytes value), so the `if isinstance(payload, bytes) / else` inside the non-multipart branch has an unreachable fallback. Test passes because the happy path hits the bytes branch. **Decision: defer cleanup** — spec is verbatim, behavior correct. Revisit as part of post-Task 10 handler-hardening sweep. Raised by Task 6 code quality review.

- **2026-04-14 — EmailHandler `can_handle` heuristic has false-positive risk.** Accepts any string whose first 10 lines contain `from:`, `to:`, `subject:` as headers — a pasted meeting-notes doc or Markdown snippet with those tokens would be misrouted. Cheap fix: also require the `From` value to contain `@`. Not fixed here because deviating from the spec's heuristic could ripple into Task 11 dispatcher tests. **Decision: defer to handler-hardening sweep post-Task 10**, then tighten all `can_handle` heuristics at once. Raised by Task 6 code quality review.

- **2026-04-14 — Handlers that open external resources (fitz, docx) should use context managers when the library supports them.** `PDFHandler` uses explicit `try/finally` per the plan spec. `with fitz.open(spec) as doc:` is cleaner and eliminates the split open/close. Not a bug (no leak: if `fitz.open` raises, nothing was opened), but worth unifying as part of the same cross-cutting sweep that wraps handler errors in `HandlerError`. **Decision: defer** with the HandlerError sweep at end of Task 10 / before Task 11. Raised by Task 5 code quality review.

- **2026-04-14 — Handler tests don't exercise `extract`'s own guard (non-Path / missing file).** `TextHandler` and `PDFHandler` both have `if not isinstance(spec, Path) or not spec.exists(): raise HandlerError(...)` but only `can_handle` is tested against that case. The `extract` guard is dead-tested code. **Decision: defer to a cross-cutting test-strengthening pass** once all handlers land, so all get the same parametrized "extract-on-bad-input raises HandlerError" test at once. Raised by Task 5 code quality review.

- **2026-04-14 — URL handler fetch params (`timeout=30.0`) are hardcoded magic numbers.** Should come from `brain_core.config` once handler-layer config injection is designed. **Decision: defer** — config plumbing for handlers isn't in Plan 02. Revisit when the pipeline orchestrator (Task 17) starts passing config through. Raised by Task 4 code quality review.

- **2026-04-14 — Task 4 implementer duplicated `respx>=0.21` into `packages/brain_core/pyproject.toml` `[project].dependencies` when it was already in the root `[dependency-groups].dev`.** Root cause: the implementer hit an import error during TDD, assumed the dep was missing, added it at the first place that worked, and didn't check the root. **Rule for dispatching future handler tasks:** when a task needs a test-only library, include in the prompt "before adding any dep, check root `pyproject.toml` `[dependency-groups].dev` — dev/test deps live there, not in package `pyproject.toml` files." Fixed in commit `1e3c244`.

- **2026-04-13 — Cross-cutting: wrap handler read errors in `HandlerError` with plain-English messages (Task 3 nit).** `TextHandler.extract` calls `spec.read_text(encoding="utf-8")` which raises a raw `UnicodeDecodeError` on non-UTF-8 input; project principle is "plain English with a next action." Same concern will apply to every handler that touches bytes (pdf, email, transcripts, docx). **Decision: defer to a cross-cutting sweep** after 2–3 more handlers land — batch the `try/except → HandlerError` wrapping so the pattern is consistent across all handlers rather than bespoke per file. Revisit at the end of Task 10 (tweet handler) or before Task 11 (dispatcher).

- **2026-04-13 — Code quality reviewer misread registration pattern (Task 3).** Reviewer flagged `TextHandler` never calling `register()` as "blocking." Not a bug: Task 11's dispatcher instantiates handlers explicitly via `_default_handlers()` — the `HANDLERS` list / `register()` in `base.py` is unused by the plan. **Rule for future reviewer prompts:** include the dispatcher's intended wiring (or a pointer to it) in the review context so reviewers don't chase phantom registration gaps. Also: consider whether `base.py`'s dead `register()`/`HANDLERS` should be removed in a cleanup pass once the dispatcher lands — deferred, low priority.

- **2026-04-13 — Does `anthropic` belong as a direct dep of `brain_core`, or should the LLM layer be split into a separate `brain_llm` package?** Current layering (per Plan 01): the Anthropic SDK is a `brain_core` dep but is only imported from `brain_core/llm/providers/anthropic.py` (enforced via CLAUDE.md rule). This keeps the `LLMProvider` abstraction clean but means `brain_core` has a production SDK dep. A future split would isolate providers into `brain_llm` so `brain_core` stays provider-free. **Decision: defer.** Revisit if a second provider is added (OpenAI, local) and the layering starts to creak. Raised by Task 2 code quality review.

## Per agent

### brain-core-engineer
_none_

### brain-mcp-engineer
_none_

### brain-frontend-engineer
_none_

### brain-ui-designer
_none_

### brain-prompt-engineer
_none_

### brain-test-engineer
_none_

### brain-installer-engineer
_none_

## Per sub-plan

### Plan 01 — Foundation

- **2026-04-13 — Root `pyproject.toml` needs `dependencies = ["brain_core"]` to actually install workspace members into the venv.** `[tool.uv.sources] brain_core = { workspace = true }` only tells uv *where* to resolve `brain_core` from; the root project still has to depend on it. Task 1 of Plan 01 omitted this; Task 2's implementer fixed it by adding the dependency. **Rule for future scaffolding tasks:** when adding a new workspace member, update the root `pyproject.toml` dependencies in the same commit. **How to apply:** before marking a workspace-member-introducing task complete, verify `uv run python -c "import <new_pkg>"` works.

- **2026-04-13 — macOS + uv 0.11.6 + Python 3.12.4 editable install bug**: uv writes the editable `.pth` file (`_brain_core.pth`) with the macOS `UF_HIDDEN` flag set, and Python's `site.py` explicitly skips hidden `.pth` files ("Skipping hidden .pth file"). Result: editable install silently fails to expose the package on `sys.path`. **Workaround in use**: set `editable = false` in `[tool.uv.sources]` so uv installs a built wheel instead. **Downside**: source edits to `brain_core` require `uv sync` to propagate — this will bite during rapid iteration. **How to apply:** if `import brain_core` ever fails after `uv sync`, check `.venv/lib/python3.12/site-packages/` for a hidden `_brain_core.pth` first. **Follow-up TODO:** monitor uv releases for a fix and flip `editable` back to `true` when available; or evaluate switching to a hatchling editable redirector.

- **2026-04-13 — Non-editable install requires explicit reinstall when adding new submodules.** Corollary of the editable=false workaround above. When a new subpackage (e.g. `brain_core.config`) is added under `packages/brain_core/src/brain_core/`, the installed wheel does not see it until you run `uv sync --reinstall-package brain_core`. The symptom is `ModuleNotFoundError` from the fresh test file even though the source is correct. **Rule for every TDD task that adds a new submodule:** run `uv sync --reinstall-package brain_core` after creating the source file and before running the tests for the first time. Hit during Task 4 execution.

- **2026-04-13 — Use `enum.StrEnum` for string-valued enums, not `class X(str, Enum)`.** ruff UP042 flags the legacy `(str, Enum)` pattern in Python 3.12. `StrEnum` is semantically equivalent for our use (.value still returns the string, comparisons work) and was added in 3.11. **Rule:** for any enum where every member's value is a string, use `from enum import StrEnum` and `class X(StrEnum):`. Hit during Plan 02 Task 1.

- **2026-04-13 — Run ruff in every task, not just at sweep time.** Plan 01 Tasks 1–20 never invoked `ruff check` or `ruff format`, so Task 21's sweep found 49 lint errors + 9 format diffs accumulated across 18 files. All were mechanical (UP017 `timezone.utc`→`datetime.UTC`, UP037 unquoted annotations, I001 import order, C408 `dict()`→`{}`, RUF003 unicode math symbols, UP040 `TypeAlias`→`type`). **Rule for every future TDD task:** include `uv run ruff check . && uv run ruff format --check .` in the self-review checklist alongside pytest and mypy. Catching lint drift per-task prevents big-bang fix commits at sweep time.

- **2026-04-13 — Async generator methods in Protocols must use `def`, not `async def`.** Declaring `async def stream(self, ...) -> AsyncIterator[X]:` in a Protocol types it as a coroutine returning an AsyncIterator, which does NOT match an implementation that uses `async def stream(...): yield ...` (that's an async generator). mypy strict correctly rejects the mismatch. **Rule:** for async-generator methods in a `Protocol`, write `def stream(...) -> AsyncIterator[X]: ...` (no `async`), then implementations can be either `async def` + `yield` (generator) or `async def` returning an explicit `AsyncIterator`. Hit during Task 16.

- **2026-04-13 — Adding a 3rd-party Python dep also requires its type stubs for mypy strict.** Adding `pyyaml>=6.0` as a `brain_core` runtime dep was not enough — mypy strict raised `import-untyped` on `import yaml` until `types-PyYAML>=6.0` was added to the root dev group. **Rule:** when a task adds a new non-trivial runtime dep, also check whether the package has a `types-*` stub package and add it to root dev deps in the same commit. Not needed for packages that ship their own `py.typed` marker (most modern libs) or have inline types. Hit during Task 8.

- **2026-04-13 — pydantic `Literal` validation tests require `# type: ignore[arg-type]`.** When writing a runtime-rejection test like `Config(active_domain="marketing")` for a `Literal` field, mypy strict will (correctly) fail the test file before it ever runs because the string isn't in the Literal set. The standard idiom is `Config(active_domain="marketing")  # type: ignore[arg-type]` with a comment explaining it's a deliberate runtime-validation probe. **Rule:** any test that deliberately passes a statically-invalid value to exercise runtime validation must carry a `# type: ignore[<code>]` and a brief justification comment. Hit during Task 4.

- **2026-04-13 — Plan 01 complete.** 64 unit tests + 1 windows-skipped, 92% coverage on brain_core, mypy strict clean, ruff clean. Demo gate green: `uv run python scripts/demo-plan-01.py` prints 6 checks + `PLAN 01 DEMO OK`. Tagged `plan-01-foundation`.

### Plan 02 — Ingestion

- **2026-04-14 — Plan 02 complete.** 191 passed + 1 windows-skipped, **94% coverage** on brain_core (exceeds 85% target), mypy strict clean, ruff + ruff-format clean. Demo gate green: `uv run python scripts/demo-plan-02.py` ingests 5 source types (text, URL-mocked, PDF, VTT transcript, tweet-mocked) end-to-end with 10 LLM calls total, proves idempotency with zero additional LLM calls on re-ingest, prints `PLAN 02 DEMO OK`. Tagged `plan-02-ingestion`. 44 commits since `plan-01-foundation`.

- **2026-04-14 — Subagent-driven development gave ~15 task commits of clean first-pass implementations plus 4 targeted fixes from quality review.** The two-stage review rhythm (spec compliance first, then code quality) caught real issues: `_integrate` feeding JSON instead of markdown to the LLM (`746f44d`), `BulkImporter.apply` ignoring per-item classified_domain (`603dd6a`), prompts package hardening (`06023f6`), URL handler respx dup dep (`1e3c244`), dispatcher error-message match assertion (`76b834d`). None of these were caught by the spec reviewer — all by the code quality reviewer. **Rule:** do NOT skip the code quality review even when spec compliance is green.

- **2026-04-14 — Handler-hardening sweep was the right shape for deferred work.** Tasks 3–10 accumulated ~10 cross-cutting concerns that the user correctly chose to batch into a post-Task-10 sweep (4 batches, 5 commits). Advantages: consistent patterns across all 8 handlers (error wrapping taxonomy, context managers, test coverage), one mental model per concern rather than bespoke per-file, no half-finished handlers. Disadvantage: the deferred-items list grew to 10 lessons and became its own mini-backlog. **Rule for Plan 03:** when reviewers raise the same class of concern on 2+ consecutive tasks, prefer batching to a sweep rather than fixing inline; let the deferral list be the sweep plan.

- **2026-04-14 — Task batching tradeoff: Task 17 (pipeline orchestrator) was split into 17A (pure helpers) + 17B (orchestration) and that was the right call.** Landing helpers with unit tests first meant Batch B's end-to-end test failures (none happened) would point at orchestration, not helpers. Counter-evidence: Task 19 (bulk import) was NOT split and got a 10-test file on first pass — but the review caught a real per-item classification bug that a narrower split would have surfaced sooner. **Rule for Plan 03:** split tasks with ≥200 LoC or multi-stage logic; single-subagent OK for small modules but always include a regression test for the interface contract.

- **2026-04-14 — iCloud + uv `editable=false` workaround produces ghost `* 2.py` / `* 3.py` files in the installed wheel after repeated `uv sync --reinstall-package` cycles.** Phantom files added ~330 lines of "0% covered" code to pytest reports, dragging Task 24's coverage from 94% to 78%. Not a real regression — fix is `find .venv -name "* [0-9].py" -delete`. Long-term fix is Plan 01's deferred TODO to flip `editable = true` once the uv hidden-`.pth` bug is resolved. **Rule:** if coverage suddenly drops with no source changes, grep the venv for ghost files first.

- **2026-04-14 — VCR cassette infrastructure landed, recording deferred.** Task 20 landed `pytest-vcr` marker, `vcr_config` fixture with header redaction (`authorization`, `x-api-key`, `anthropic-api-key`), empty cassettes directory, and docs at `docs/testing/prompts-vcr.md` with the `skipif` test template. Tasks 21 (record) and 22 (contract assertions) deferred indefinitely — they need an `ANTHROPIC_API_KEY` and are not a merge gate per the plan. When a key is available, a future implementer can copy the template from the docs and land both in one sitting.

- **Plan 02 → Plan 03 handoff items:** (1) `ClassifyOutput.domain` is a hardcoded `Literal["research","work","personal"]` — revisit when configurable domains are needed. (2) `failures.record_failure` silently overwrites on slug collision — add timestamp suffix for retry history. (3) `timeout=30.0` in URLHandler is hardcoded — plumb via config once Task 17-equivalent orchestrator design for Plan 03 (chat) decides how. (4) Related-notes retrieval for `_integrate` is stubbed — lands in a later plan. (5) Tasks 21–22 VCR cassettes deferred.

### Plan 03 — Chat

- **2026-04-15 — Plan 03 complete.** 366 passed + 5 skipped, 91% total brain_core coverage, mypy strict clean in both packages, ruff + format clean. Demo gate green: `uv run python scripts/demo-plan-03.py` → `PLAN 03 DEMO OK` (7 gates: Ask mode, Brainstorm propose_note, Draft edit_open_doc, thread persistence, auto-title rename, idempotency, scope guard). Tagged `plan-03-chat`. 42 commits since `plan-02-ingestion`.

- **Coverage note.** `brain_core.chat.*` averages 96% (autotitle 94, context 100, modes 100, pending 99, persistence 99, retrieval 93, session 88, tools 93–100, types 100). `brain_core.state.db` 97%. `brain_cli.commands.chat` 58%, `brain_cli.commands.patches` 55% — below the 85% target because the interactive stdin paths are only exercised by the demo, not the unit tests. Rendering (`stream.py`) is 80%. Total brain_core 91% (down from Plan 02's 94% — the delta is almost entirely the Anthropic provider at 35%, unchanged from Plan 01, plus the chat session loop's streaming branches). Gap documented; no feature-freeze-breaking fixes in Task 25.

- **Subagent-driven development retrospective.** 25 tasks, 6 groups, 7 checkpoints. Main loop dispatched fresh `brain-core-engineer` subagents per task with spec-compliance review + code-quality review in parallel after each. Two-stage review caught consistency issues the spec reviewer missed: Task 10 `is` vs `==` spec bug, Task 14 brace escaping in wrong prompt section, Task 17 `set_open_doc` SYSTEM turn inconsistency, Task 18 `len == 4` fragility, Task 20 missing 📝 emoji. Most tasks landed on first try. Tasks 2, 3, 14, 17, 18, 19, 20 needed follow-up fix commits (all caught by reviewers, not by post-hoc debugging). Checkpoint cadence (after Tasks 3, 11, 14, 15, 18, 20, 25) let main loop pause for user review without stalling per-task progress.

- **Handoff items to Plan 04 (MCP server):**
  - `state.sqlite` ready to extend — add a new migration file in `packages/brain_core/src/brain_core/state/migrations/0002_*.sql` for any MCP-specific tables (tool_call audit log, rate-limit tracking, etc.) without touching `0001_chat_and_bm25.sql`.
  - `PendingPatchStore` is reusable by MCP's `brain_propose_note` tool — same file-per-patch queue format.
  - `BM25VaultIndex` retrieval is reusable by MCP's `brain_search` tool.
  - `LLMProvider.complete(request)` with `request.tools` works end-to-end; MCP's stdio tool surface can wrap it.
  - Chat thread format at `<domain>/chats/<id>.md` is the canonical persisted thread — MCP can read these for cross-session history if needed.
  - `ChatSession` is NOT reusable by MCP (Claude Desktop IS the chat in MCP world per spec §6). MCP exposes READ tools only.

- **2026-04-15 — uv `[project.scripts]` + `package = false` gotcha.** A workspace root with `[tool.uv] package = false` silently ignores `[project.scripts]`. Entry points must live in the packaged workspace member's own `pyproject.toml`. Discovered in Task 19. Relevant for Plan 04+ any time a new workspace member (brain_mcp, brain_api, brain_web) needs a console script.

- **2026-04-15 — PEP 561 `py.typed` marker needed from day one.** `brain_core` was missing `src/brain_core/py.typed`, causing 24 spurious mypy import-untyped errors when running mypy from `packages/brain_cli/`. Fixed in Task 20. Every new workspace member needs a `py.typed` marker file.

- **2026-04-15 — `editable = false` workaround bites source edits.** The Plan 01 workaround for uv's hidden-`.pth` bug means every source edit requires `uv sync --reinstall-package <pkg>` to propagate. Hit this during most of Plan 03's follow-up fix commits. Operational friction, no correctness concern. Still waiting on upstream uv fix.

- **2026-04-15 — Self-review mypy-from-wrong-cwd trap.** Implementers running `uv run mypy src tests` from the repo root (vs `packages/brain_core/`) hit "no mypy config, no issues found in 0 files" or phantom "pre-existing errors in unrelated files" and report false status. Task 8, 14, 16, 20 all tripped on this. **Rule for future plan execution:** self-review checklist must say `cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_core && uv run mypy src tests` explicitly.

- **2026-04-15 — Plan-author API verification.** Plan 03 text referenced imagined APIs (`PromptLoader` class, `FakeLLMProvider.queue_response`) instead of the real Plan 02 shapes (`load_prompt` function, `.queue`). Implementers correctly adapted. **Rule for future plan authoring:** open the real source files and verify signatures before writing task prompts.

- **2026-04-15 — Plan-author spec bug: `is` vs `==` on round-tripped pydantic models.** Plan 03 Task 10 spec asserted `result.proposed_patch is env_obj` but `store.list()` re-reads from disk and reconstructs `PendingEnvelope` — identity equality is structurally impossible. Implementer flagged and relaxed to `==`. **Rule:** for any assertion involving an object that round-trips through serialization, use `==` not `is`.

- **2026-04-15 — Plan-author arithmetic traps: `len(turns) == 4` bypassed by slash commands.** Plan 03 Task 18 spec used `len(_turns) == 4` to detect "end of turn 2", but any SYSTEM turn appended by `switch_mode`/`switch_scope`/`set_open_doc` between turns 1 and 2 bypasses it (count becomes 5 at the moment the check fires, never matches again). Fixed to count USER turns. **Rule:** state-detection checks should count INVARIANT data (USER turns monotonically increase by 1 per real turn), not ALL data.

- **2026-04-15 — Two scope-sensitive deviations were approved.** `VaultWriter.rename_file` (Task 14a) and the `LLMProvider` tool_use extension (Task 15) both touched Plan 01/02 code. Both were additive, both preserved existing behavior, both passed regression with zero Plan 02 test changes. **Rule:** touching existing code is OK when the change is strictly additive, has a clear hard regression gate, and is documented in the plan as an explicit exception.

- **2026-04-15 — Cross-platform surprises from Task 22.** One finding: `_write_rename_undo_record` was missing `newline="\n"`, would have produced CRLF on Windows. Fixed with a regression test that monkeypatches `Path.write_text` to assert the kwarg. Zero other findings. Plan 03 code held up well to the cross-platform audit because every writer routes through `_atomic_write_text` (which already enforces LF) or `os.replace` (atomic on both OS).

- **2026-04-15 — Task 24 hardening sweep.** 22 deferred items grouped into 4 batches (A behavior, B tests, C comments, D defer). 3 commits landed (`3cbb8a6`, `9f1db05`, `197dec9`), +9 new regression tests. Batch D items (5 NICE-TO-HAVEs) deferred to Plan 07 or later without commit — documented in lessons.
