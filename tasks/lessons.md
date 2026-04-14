# brain — Lessons Learned

> Running log of corrections, patterns, and rules. Updated after any user correction, any plan step that went sideways, and any subagent that needed re-dispatch. Review at the start of every session and before authoring each new plan.

## How to use

- Each entry is a short rule with context: **what went wrong**, **why**, **what to do instead**.
- Rules are scoped: project-wide, per-agent, or per-sub-plan.
- Obsolete lessons are struck through with `~~` rather than deleted, so the history is preserved.
- New entries include the date (YYYY-MM-DD) they were added.

## Project-wide

### Deferred architectural questions

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
