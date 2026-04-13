# brain — Lessons Learned

> Running log of corrections, patterns, and rules. Updated after any user correction, any plan step that went sideways, and any subagent that needed re-dispatch. Review at the start of every session and before authoring each new plan.

## How to use

- Each entry is a short rule with context: **what went wrong**, **why**, **what to do instead**.
- Rules are scoped: project-wide, per-agent, or per-sub-plan.
- Obsolete lessons are struck through with `~~` rather than deleted, so the history is preserved.
- New entries include the date (YYYY-MM-DD) they were added.

## Project-wide

### Deferred architectural questions

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

- **2026-04-13 — pydantic `Literal` validation tests require `# type: ignore[arg-type]`.** When writing a runtime-rejection test like `Config(active_domain="marketing")` for a `Literal` field, mypy strict will (correctly) fail the test file before it ever runs because the string isn't in the Literal set. The standard idiom is `Config(active_domain="marketing")  # type: ignore[arg-type]` with a comment explaining it's a deliberate runtime-validation probe. **Rule:** any test that deliberately passes a statically-invalid value to exercise runtime validation must carry a `# type: ignore[<code>]` and a brief justification comment. Hit during Task 4.
