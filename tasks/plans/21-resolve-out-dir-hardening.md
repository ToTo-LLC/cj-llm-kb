# Plan 21 — `resolve_out_dir` hardening against editable-install / iCloud-masked workspaces

**Authored:** 2026-05-12 (post Plan 20 close on 2026-05-12, tag
`plan-20-response-model-pins-and-wrapper-audit` at `9bbba9e`).
**Scope:** Close the Plan 19 T2 surprise #2 / Plan 20 Q1=1.A deferral.
`packages/brain_api/src/brain_api/static_ui.py:96` uses
`Path(__file__).resolve().parents[4]` as the dev-fallback root for
`<repo_root>/apps/brain_web/out/`. Under uv editable install + iCloud
`.pth` masking (auto-memory `feedback_uv_uf_hidden.md` +
`feedback_brain_web_out_dir.md`), `parents[4]` does NOT reach the repo
root; `resolve_out_dir` raises; the silent-degrade in
`app.py:280-286` (`except RuntimeError: pass`) swallows the failure and
the SPA mount is skipped. Symptom: `curl /` returns 404 but `curl
/api/setup-status` returns 200 ("API-only mode") with no signal to the
developer about why. Plan 21 lands a hybrid fix per user Q1=1.D:
(a) replace `.parents[4]` with a content-based walk-up to
`pyproject.toml` (workspace root marker); (b) add a structured
`log.warning` when `mount_static_ui=True` but `resolve_out_dir` raises,
so unintentional degrades surface immediately. Both fixes are
pathlib-only (cross-platform), ~25 LOC + unit tests per user Q2=2.A.
**Shape:** 2 substantive tasks + 1 closure. Mirrors Plan 20's small
shape; per-task ~30-60 LOC PR budget; combined spec + code-quality
review per task.

## At a glance

- **Theme A — `resolve_out_dir` resolver hardening** (T1): replace
  the depth-based `Path(__file__).resolve().parents[4]` index with a
  content-based `_find_repo_root` walk-up looking for
  `pyproject.toml` (workspace root marker). Pure-pathlib so
  Windows-safe. Unit tests via mocked filesystem (Q2=2.A) cover
  walk-up at various depths + fallback when marker missing.
- **Theme B — Silent-degrade observability** (T2): add a structured
  `log.warning` in `app.py` when `mount_static_ui=True` AND
  `resolve_out_dir` raises (the "API-only mode" silent-degrade
  branch). CI / contract tests pass `mount_static_ui=False` so they
  don't trigger the warning — observability fires only when a real
  developer running visual QA hits the failure. Unit test covers the
  warning's structured fields + that it does NOT fire when
  `mount_static_ui=False`.
- **Closure** (T3): demo + lessons + todo.md + tag
  `plan-21-resolve-out-dir-hardening`.

## Why this plan exists (1 paragraph)

Plan 19 T2's supplemental visual verification (commit `1b148a7`)
documented this bug; Plan 20 Q1=1.A explicitly deferred the fix
("Small Plan 20 = #6 + #7; resolve_out_dir defer to Plan 21+"). The
durable workaround — explicit `BRAIN_WEB_OUT_DIR=apps/brain_web/out`
env override — works but requires every visual-QA invocation on this
repo to remember it. The root cause is a brittle depth assumption:
`Path(__file__).resolve().parents[4]` works under normal install
layouts but fails under uv editable install + iCloud `.pth` masking
(the `.pth` file masking causes `__file__.resolve()` to resolve to an
unexpected location whose `parents[4]` is not the repo root). Plan 16
/ Plan 19 T5 lesson "implementers MUST grep before assuming
file/symbol locations" generalizes here to "code MUST verify
content/markers, not assume depth." A content-based walk-up to
`pyproject.toml` is robust regardless of how the resolved `__file__`
arrived at its current location. The paired observability fix (log
warning on silent-degrade) addresses the secondary issue: when the
resolver DOES fail despite the hardening (e.g., a future install
layout breaks even walk-up), the developer sees the warning
immediately instead of debugging a silent 404.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Hardening approach = 1.D Hybrid (walk-up + log warning).** Replace `Path(__file__).resolve().parents[4]` with a `_find_repo_root` helper that walks up from `Path(__file__).resolve().parent` looking for `pyproject.toml`. If found, use that as the workspace root for the `apps/brain_web/out/` fallback. If not found (e.g., walk-up reaches `/`), fall back to the current `.parents[4]` behavior + `resolve_out_dir`'s existing error-message path. Pair with a structured `log.warning` (via `structlog` per the brain_api convention) in `app.py:283-286` when `mount_static_ui=True` but `resolve_out_dir` raises. | locked (user 1.D) | Walk-up replaces a brittle index with content-based lookup, which is robust regardless of editable-install / symlinks / iCloud / future tooling. Observability complements the fix so any future failure mode surfaces immediately instead of silent-404-ing. Both fixes are small, targeted, pathlib-only. |
| D2 | **Test scope = 2.A unit tests only.** Mock filesystem (`tmp_path` + `monkeypatch.setattr(<module>, "__file__", ...)` pattern) for walk-up tests; structlog log-capture fixture (`caplog` if structlog routes through stdlib, OR `structlog.testing.capture_logs()`) for warning tests. No smoke test, no integration test. | locked (user 2.A) | Walk-up logic is pure filesystem traversal — mocked tests are deterministic and fast. The smoke + integration variants (2.B / 2.C) would catch surprises that mocked tests miss, but the walk-up is content-based; if it walks up and finds `pyproject.toml`, the actual content of `pyproject.toml` doesn't matter to the resolver. Mocked tests cover the logic exhaustively. |
| D3 | **T1 bundled with sub-fixes (walk-up helper + use in resolve_out_dir + tests).** Same Plan 19 T4 / Plan 20 T1 bundle precedent: same pattern (introduce helper, swap call site, add tests), ~40-60 LOC total, no live consumers per shape. | locked per Plan 19 D3 / Plan 20 D3 | Bundling keeps per-task review focused. Split would add overhead without proportional value. |
| D4 | **Implementer re-derives walk-up termination at exec time.** Plan-doc cites `pyproject.toml` as the workspace root marker. Implementer MUST verify at exec time that `pyproject.toml` exists at the repo root (it does: `/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/pyproject.toml`) AND that no `pyproject.toml` exists at intermediate `packages/<name>/` levels that would short-circuit the walk-up incorrectly. Plan 16/19 T5 / Plan 20 D4 grep-before-assuming lesson. | locked per Plan 19 T1 / Plan 20 D4 | Plan-doc shape claims are snapshots; implementation must re-derive against current main. If `packages/brain_api/pyproject.toml` exists (which it likely does in a workspace setup), the walk-up needs a different marker (e.g., `.git` directory, or check for a specific marker file like a workspace `[tool.uv.workspace]` section in pyproject.toml). |
| D5 | **Preserved Plan 17/earlier carry-forwards (4 NOT-DOING items)** stay NOT-DOING in Plan 22 candidate tail block at Plan 21 closure. | locked per Plan 20 D5 | All four have explicit not-yet-actionable criteria unchanged since Plan 17/18/19/20 closure (no triggers have fired). Preserve rationale-per-item. |
| D6 | **No findings table.** Plan 21 has no audit task; T1+T2 are fix + tests + closure. | locked at authoring | Plan 21 closes a known bug with a known cause; no enumeration phase is needed. The Plan 19/20 audit-then-size pattern (D6) applies to audit-style plans; Plan 21 is fix-style. |
| D7 | **Demo gate: per-item closure assertion, no gate-count target.** ~6 gates is the natural count for Plan 21's surface. | locked per Plan 20 D7 / Plan 19 D7 | Gate count adapts to closure shape. |
| D8 | **Per-task review: combined spec + code-quality** held across 47 tasks in Plan 16; 18 in Plan 17; 5 in Plan 18; 5 in Plan 19; 4 in Plan 20. | locked per Plan 16 D35 / Plan 17 D2 / Plan 18 D5 / Plan 19 D8 / Plan 20 D8 | No reason to re-litigate at the Plan-15+ polish-pass scale. |
| D9 | **No new dependencies.** Plan 21 ships zero new pip / npm packages. Uses existing structlog from brain_api. | locked per Plan 20 D9 / Plan 19 D9 / Plan 18 D6 | All Plan 21 work is pure-Python resolver helper + structlog log call + unit tests. |
| D10 | **Push at Plan 21 close, after user authorization.** Single `git push` covers all Plan 21 commits. Tag is lightweight per project convention (Plans 17-20 all `commit` type); use explicit `git push origin <tag>` after commits-push since `--follow-tags` skips lightweight tags. | locked per Plan 20 D10 / Plan 19 D10 + Plan 20 closure lesson | Standard cadence. Plan 20 closure observed the lightweight-tag / `--follow-tags` interaction; documented in project_state memory + applied here. |
| D11 | **Sequential subagent dispatch via `superpowers:subagent-driven-development`.** | locked per Plan 20 D11 / Plan 19 D11 | Combined review per task plus sequential dispatch held across five prior polish-scale plans. |

## Tech stack

Same as Plans 16 + 17 + 18 + 19 + 20: Python 3.12, pydantic v2, mypy
--strict, ruff, structlog (already used in brain_api), pytest, vitest,
Playwright. No new tools. No new dependencies. CI runs on macos-14 +
windows-2022 per Plan 14's matrix.

## Demo gate description

`scripts/demo-plan-21.py` asserts, in sequence:

1. **(T1.a)** `packages/brain_api/src/brain_api/static_ui.py` defines
   a `_find_repo_root` helper (function exists; signature accepts a
   starting `Path` and a marker filename; returns `Path | None`).
   Structural regex/AST match.
2. **(T1.b)** `resolve_out_dir`'s body references `_find_repo_root`
   (the `.parents[4]` literal is replaced OR retained only as a final
   fallback after walk-up). Structural regex match.
3. **(T1.c)** Unit tests for `_find_repo_root` exist at
   `packages/brain_api/tests/test_static_ui_find_repo_root.py` (or
   sibling name) with at minimum: (a) walk-up finds marker at root;
   (b) walk-up finds marker at intermediate level (verifies first-hit
   wins); (c) walk-up returns None when marker absent up to `/`;
   (d) handles starting path == file vs == directory.
4. **(T2.a)** `packages/brain_api/src/brain_api/app.py` `except
   RuntimeError` branch in the `mount_static_ui` block emits a
   structured warning (regex match for `log.warning(...)` or
   `logger.warning(...)` inside the except branch).
5. **(T2.b)** Unit tests for the warning behavior exist at
   `packages/brain_api/tests/test_app_silent_degrade_warning.py` (or
   sibling name) with at minimum: (a) warning fires when
   `mount_static_ui=True` + `resolve_out_dir` raises; (b) warning
   does NOT fire when `mount_static_ui=False`; (c) warning carries
   the original RuntimeError's message (or an equivalent diagnostic
   payload).
6. **(T3)** `tasks/todo.md` row 21 marked ✅; `tasks/lessons.md` has
   a Plan 21 closure section; final stdout line is `PLAN 21 DEMO OK`.

## Tasks

### Theme A — `resolve_out_dir` resolver hardening

#### T1 — `_find_repo_root` walk-up helper + use in `resolve_out_dir` + tests

**Files:**
- Modify: `packages/brain_api/src/brain_api/static_ui.py` — add a
  `_find_repo_root(start: Path, *, marker: str = "pyproject.toml") -> Path | None`
  helper near the top of the file (after the module docstring +
  imports). Update `resolve_out_dir` to use the walk-up result as
  the primary dev-fallback root; retain the existing `.parents[4]`
  as a secondary fallback only if walk-up returns `None`.
- Create: `packages/brain_api/tests/test_static_ui_find_repo_root.py`
  — unit tests for the walk-up helper using `tmp_path` fixtures.

**Goal:** Replace the brittle depth-based `Path(__file__).resolve().parents[4]`
fallback with a content-based walk-up to a workspace root marker
(`pyproject.toml`). The walk-up is robust regardless of how the
resolved `__file__` arrived at its current location — uv editable
install, symlinks, iCloud `.pth` masking, future tooling quirks.

**What to do:**
1. **Re-derive the workspace marker at exec time per D4.** Before
   writing the helper, verify:
   - `pyproject.toml` exists at `/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/pyproject.toml` (workspace root).
   - Inspect `packages/<name>/` directories for sub-pyproject.toml
     files (uv workspaces typically have a sub-pyproject per package).
     If sub-pyprojects exist, the walk-up's first-hit termination
     would short-circuit at the package level instead of reaching
     the workspace root. **MITIGATION:** check the found
     `pyproject.toml` for the workspace marker (e.g.,
     `[tool.uv.workspace]` section or `name = "brain"` at the root
     project metadata). If first-hit's content doesn't match the
     workspace marker, continue walking up.
   - Decide at exec time whether to use `pyproject.toml`-by-content
     OR a less ambiguous marker (e.g., `.git` directory, or a
     dedicated `BRAIN_WORKSPACE_ROOT` sentinel file). Plan author's
     opinion: `.git` is the cleanest unambiguous marker for "this
     is the repo root" — every repo has one and only one
     top-level `.git`. Use `marker = ".git"` as the default, with
     `pyproject.toml` as an alternative for non-git-repo contexts
     (e.g., a tarball-extracted source dir). **Implementer adjudicates
     at exec time.**
2. **Write the helper.** Pattern:
   ```python
   def _find_repo_root(start: Path, *, marker: str = ".git") -> Path | None:
       """Walk up from ``start`` looking for ``marker``.

       Returns the first ancestor directory containing ``marker``, or
       ``None`` if walk-up reaches the filesystem root without a hit.
       ``marker`` may be a file name OR a directory name — pathlib's
       ``exists()`` covers both.
       """
       current = start if start.is_dir() else start.parent
       for ancestor in (current, *current.parents):
           if (ancestor / marker).exists():
               return ancestor
       return None
   ```
   Cross-platform: pathlib-only; `Path.parents` is a generator that
   stops at the root; `.exists()` works on Windows + macOS + Linux.
3. **Use in `resolve_out_dir`.** Replace lines 93-97 (the `here =
   Path(__file__).resolve(); repo_root = here.parents[4]; candidates.append(...)`
   block) with:
   ```python
   # Repo dev-fallback: walk up from this file looking for the .git
   # directory (workspace root marker). Robust against editable
   # install / iCloud `.pth` masking / symlinks where the depth
   # assumption (parents[4]) doesn't hold.
   here = Path(__file__).resolve()
   repo_root = _find_repo_root(here)
   if repo_root is not None:
       candidates.append(repo_root / "apps" / "brain_web" / "out")
   # Secondary fallback (preserves prior behavior if walk-up fails
   # entirely — e.g., tarball-extracted source dir with no .git).
   try:
       candidates.append(here.parents[4] / "apps" / "brain_web" / "out")
   except IndexError:
       pass  # parents[4] beyond root; skip silently.
   ```
4. **Unit tests.** Use `tmp_path` to construct a fake workspace
   tree. Cover:
   - **`test_find_repo_root_finds_marker_at_start`** — marker at
     `tmp_path / ".git"`; call with `tmp_path / "subdir" / "file.py"`;
     assert returns `tmp_path`.
   - **`test_find_repo_root_finds_marker_at_intermediate_level`** —
     marker at `tmp_path / ".git"` AND `tmp_path / "subdir" / ".git"`
     (simulating nested git or sub-workspace); call with
     `tmp_path / "subdir" / "deeper" / "file.py"`; assert returns
     `tmp_path / "subdir"` (first-hit wins, correct walk-up
     semantics).
   - **`test_find_repo_root_returns_none_when_marker_absent`** — no
     marker anywhere up the tree; call with
     `tmp_path / "file.py"`; assert returns `None`. (Note: in a real
     filesystem, walking up from `tmp_path` eventually reaches `/`
     which might have a `.git` from the test runner's environment;
     use a custom marker like `BRAIN_TEST_SENTINEL` for this test to
     avoid false positives.)
   - **`test_find_repo_root_accepts_starting_path_as_directory`** —
     pass `tmp_path` (a directory) instead of a file; assert walk-up
     starts from `tmp_path` itself, not its parent.
   - **`test_find_repo_root_accepts_starting_path_as_file`** — pass
     `tmp_path / "fake.py"` (a file); assert walk-up starts from
     `tmp_path`, not deeper.
5. **Verify locally.** Run the new tests via the project recipe per
   `feedback_uv_uf_hidden.md`:
   ```bash
   find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; \
     uv run --package brain_api pytest \
     packages/brain_api/tests/test_static_ui_find_repo_root.py -v
   ```
   Also run the existing brain_api test suite once more to verify
   `resolve_out_dir`'s production callers are unaffected:
   ```bash
   find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; \
     uv run --package brain_api pytest packages/brain_api/tests/ -q
   ```
6. **Append `## T1 outcome`** to `tasks/plans/21-resolve-out-dir-hardening.md`
   with per-step receipts: (a) `_find_repo_root` helper added at
   `static_ui.py:<line>`; (b) `resolve_out_dir` updated to walk-up
   primary + `parents[4]` secondary; (c) test file path + test
   count + pass/fail; (d) brain_api full-suite run output.

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) `_find_repo_root` is pure pathlib (no `os.path`, no `shell=True`);
(b) marker default is `.git` (or implementer's adjudicated choice
documented in the T1 outcome); (c) `resolve_out_dir` retains
secondary `.parents[4]` fallback wrapped in `try: ... except
IndexError: pass` (defensive against walk-up returning a path so deep
that `parents[4]` overshoots); (d) unit tests cover walk-up
termination, intermediate-marker first-hit, missing-marker `None`,
both file + directory starting paths; (e) all brain_api tests still
pass.

### Theme B — Silent-degrade observability

#### T2 — Structured warning on silent-degrade + tests

**Files:**
- Modify: `packages/brain_api/src/brain_api/app.py` — replace the
  bare `except RuntimeError: pass` at lines 283-286 with a structured
  `log.warning` (via structlog per brain_api convention). The
  warning fires only when `mount_static_ui=True` AND
  `resolve_out_dir` raised — the production "API-only mode" intent
  for CI / contract tests / headless deployments uses
  `mount_static_ui=False` so the warning is silent there.
- Create or modify: `packages/brain_api/tests/test_app_silent_degrade_warning.py`
  — unit tests verifying warning fires + payload + non-fire when
  `mount_static_ui=False`.

**Goal:** Make the silent-degrade visible to developers running
visual QA. The current bare `except RuntimeError: pass` is correct
in intent (skip mount for headless) but its silence hides the
iCloud-induced failure during dev workflow. Structured warning gives
the developer immediate signal: "SPA mount skipped — `resolve_out_dir`
raised; SPA at `/` will 404." The warning's structured payload
includes the original error message + a pointer to the
`BRAIN_WEB_OUT_DIR` env-override workaround.

**What to do:**
1. **Read brain_api's structlog usage** at exec time to verify the
   logger setup. Grep `import structlog` or `get_logger` in
   `packages/brain_api/src/brain_api/`. Mirror the existing logger
   shape (e.g., `log = structlog.get_logger(__name__)` at module
   level). If brain_api uses stdlib `logging` instead of structlog,
   mirror that.
2. **Replace the except branch.** Current code at app.py:280-286:
   ```python
   if mount_static_ui:
       try:
           out_dir = resolve_out_dir()
           app.mount("/", SPAStaticFiles(directory=str(out_dir), html=True), name="ui")
       except RuntimeError:
           # API-only mode (CI, contract tests, headless). Intentional no-op.
           pass
   ```
   Replace with:
   ```python
   if mount_static_ui:
       try:
           out_dir = resolve_out_dir()
           app.mount("/", SPAStaticFiles(directory=str(out_dir), html=True), name="ui")
       except RuntimeError as exc:
           # Visual-QA / dev surface degraded to API-only mode. CI uses
           # mount_static_ui=False so this branch only fires for an
           # unintentional resolver failure (e.g., uv editable install
           # + iCloud .pth masking — see auto-memory
           # feedback_brain_web_out_dir.md). Log a structured warning so
           # the developer sees the cause without debugging a silent 404.
           log.warning(
               "spa_mount_skipped",
               error=str(exc),
               hint="set BRAIN_WEB_OUT_DIR=apps/brain_web/out, or run `pnpm --dir apps/brain_web build`",
           )
   ```
   (Field names follow brain_api's existing structlog convention —
   verify at exec time and adjust to match. If stdlib logging is
   used, use `log.warning("SPA mount skipped: %s. Hint: %s", exc, ...)`.)
3. **Unit tests.** Use `caplog` (stdlib logging capture) or
   `structlog.testing.capture_logs()` (structlog capture):
   - **`test_silent_degrade_warning_fires_when_resolve_raises`** —
     `monkeypatch.setattr("brain_api.app.resolve_out_dir", lambda: raise RuntimeError("simulated"))`;
     call `create_app(...)` with `mount_static_ui=True`; assert
     warning was logged with `error="simulated"` and `hint`
     containing `BRAIN_WEB_OUT_DIR`.
   - **`test_silent_degrade_warning_does_not_fire_when_mount_static_ui_false`** —
     same monkeypatch; call `create_app(...)` with
     `mount_static_ui=False`; assert NO warning logged (the early
     return path skips the try-block entirely).
   - **`test_silent_degrade_warning_does_not_fire_on_successful_mount`** —
     no monkeypatch (or monkeypatch returns a valid tmp_path);
     call `create_app(...)` with `mount_static_ui=True`; assert NO
     warning logged.
4. **Verify locally.** Run the new tests + the full brain_api suite:
   ```bash
   find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; \
     uv run --package brain_api pytest \
     packages/brain_api/tests/test_app_silent_degrade_warning.py -v
   ```
   Plus the full suite for regression coverage.
5. **Append `## T2 outcome`** to the plan doc with per-step receipts.

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) the structlog/logging convention used matches brain_api's existing
shape (verified at exec time); (b) warning fires only when
`mount_static_ui=True` + RuntimeError raised; (c) hint message points
at the documented workaround (`BRAIN_WEB_OUT_DIR` env OR `pnpm build`);
(d) test fixtures correctly intercept the resolver via monkeypatch on
the helper's import-time binding in `brain_api.app` (NOT just
`brain_api.static_ui.resolve_out_dir`, per Plan 17 T17 monkeypatch-
binding lesson); (e) all brain_api tests still pass.

### Closure

#### T3 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-21.py` — assert each gate per the demo
  description above (6 gates).
- Modify: `tasks/lessons.md` — append a "Plan 21 closure" section.
- Modify: `tasks/todo.md` — row 21 marked ✅ Complete; tail block
  refreshed as "Plan 22 candidate scope" preserving the 4 NOT-DOING
  carry-forwards per D5 + any new candidates surfaced during Plan 21
  execution.
- Tag: `plan-21-resolve-out-dir-hardening` cut on green demo.

**Goal:** land Plan 21 closure following Plan 20 T4's shape.

**What to do:**
1. **`demo-plan-21.py`.** Per D7, the demo asserts each item is
   CLOSED with per-item structural assertions: regex for the
   `_find_repo_root` helper existence; regex for `resolve_out_dir`
   referencing it; existence of test files + key test function names;
   regex for `log.warning` in the app.py except branch; structural
   markers for the todo.md row + lessons.md section. Final stdout
   line on a clean run: `PLAN 21 DEMO OK`.
2. **Lessons.** Plan 21 closure section in `tasks/lessons.md`:
   - "Content-based walk-up beats depth-based index" — the
     `parents[4]` failure under uv editable install + iCloud `.pth`
     masking generalized to a class lesson: code that assumes a
     specific depth-from-`__file__` is fragile across install modes
     / symlinks / filesystem quirks; prefer content markers (`.git`,
     `pyproject.toml`, dedicated sentinel files).
   - "Silent-degrade-by-design needs observability" — the
     `try: ... except RuntimeError: pass` pattern is correct for
     intentional headless mode but masks unintentional failures
     when the same code path runs in dev. Structured warnings on
     "intentional silent" branches give devs immediate signal when
     the silence is accidental.
   - "Plan 16/19/20 grep-before-assuming generalizes to code-content
     assumptions" — the lesson started as a plan-authoring + impl
     practice (Plan 16: grep before assuming a symbol exists; Plan
     19/20: grep before assuming a path/file). Plan 21 extends it
     to code-content assumptions: don't assume `parents[N]` reaches
     a specific place; verify via filesystem markers. Same principle
     applied at the runtime layer.
   - Anything else surfaced during T1-T2 review.
3. **todo.md update.** Row 21 marked ✅; tail block becomes
   "Plan 22 candidate scope" with the 4 preserved NOT-DOING
   carry-forwards per D5 (unchanged from Plan 20 tail). No new
   Plan-21-surfaced candidates expected unless T1/T2 review surfaces
   something material.
4. **Tag.** `plan-21-resolve-out-dir-hardening` cut on green
   `scripts/demo-plan-21.py` + green pytest + green CI on macos-14
   + windows-2022. Lightweight tag per project convention (Plans
   17-20 all `commit` type).
5. **Push.** Per D10, after closure tag: single `git push origin
   main` covers Plan 21's commits PLUS explicit `git push origin
   plan-21-resolve-out-dir-hardening` for the lightweight tag (since
   `--follow-tags` skips lightweight tags per Plan 20 closure
   observation). User authorization required.

**Per-task review:** combined spec + code-quality. Demo gate count
is not pinned per D7; closure shape mirrors Plan 20 T4.

## Owning subagents

- **brain-mcp-engineer (role-overloaded as brain-api-engineer)** —
  T1 (walk-up helper in `static_ui.py` + tests) + T2 (silent-degrade
  warning in `app.py` + tests). The CLAUDE.md subagent list does NOT
  include a dedicated `brain-api-engineer` type;
  `brain-mcp-engineer` has handled brain_api work across Plans
  11/13/14/15/17/19/20.
- **brain-core-engineer** — T3 (demo + lessons + closure
  carry-forward management). Demo script asserts structural file +
  AST shapes; brain-core-engineer's polish-pass closure precedent
  (Plan 17 T17 / Plan 18 T5 / Plan 19 T6 / Plan 20 T4) holds.
- **brain-installer-engineer** — NOT primary owner per scope check.
  The `resolve_out_dir` seam was historically flagged as Plan 13 +
  Plan 15 cross-platform sweep territory (auto-memory
  `feedback_brain_web_out_dir.md`), but Plan 21's scope is a
  resolver-internal fix inside brain_api, not a broader install /
  cross-platform sweep. If T1 review surfaces a Windows-specific
  edge case (e.g., walk-up across UNC paths), bounce to
  brain-installer-engineer.
- **brain-test-engineer** — may collaborate on T1/T2 if the
  monkeypatch / log-capture fixtures need nuance; T1/T2 implementers
  empowered to land tests inline per Plan 18 D5's "combined review"
  practice.
- (No new tasks for brain-prompt-engineer, brain-ui-designer,
  brain-frontend-engineer in Plan 21. No new prompts; no UI surface
  change; no frontend code change.)

## Workflow rules

Same as Plans 16 + 17 + 18 + 19 + 20:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- Implementer routes back to plan author on any unrecognized rule
  edge case (e.g., T1's marker-choice adjudication if sub-pyprojects
  exist; T2's monkeypatch-binding adjudication if
  `brain_api.app.resolve_out_dir` import-binding differs from the
  helper location).
- Pause every ~3 tasks for user check-in. Plan 21's 3-task budget
  means a pause before T3 closure + plan-close after T3.
- No push without explicit user authorization at Plan 21 close
  (D10).
- pytest recipe on this iCloud-synced repo:
  `find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; uv run pytest <args>`
  on ONE command line. Or PYTHONPATH bypass:
  `unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src uv run --package <pkg> pytest packages/<pkg>/tests -q`.
- Frontend per-task verification (`pnpm vitest run` + `pnpm tsc --noEmit`)
  not relevant for Plan 21 (no frontend changes).
- Visual QA (relevant for Plan 21!): if T1 fix actually works under
  the iCloud-masked environment, a supplemental visual-QA
  verification SHOULD run `uvicorn` WITHOUT `BRAIN_WEB_OUT_DIR` set,
  with chflags-0'd `.pth` files, and verify SPA serves at `/`. If
  the walk-up resolves correctly, the env-override workaround should
  no longer be required for the SPA mount. Optional but valuable
  receipt for the T1 outcome section.
- Radix dialogs + axe `waitForAnimationsToFinish` — N/A for Plan 21.
- Monkeypatching internal helper calls: patch BOTH helper's
  resolved-at-call-time namespace AND caller's namespace (latter
  `raising=False`) per Plan 17 T17 lesson. **RELEVANT for T2** —
  `brain_api.app` does `from brain_api.static_ui import resolve_out_dir`;
  monkeypatching `brain_api.static_ui.resolve_out_dir` does NOT
  intercept the import-bound reference inside `brain_api.app`. Patch
  `brain_api.app.resolve_out_dir` directly for T2 unit tests.
- Pydantic v2 `model_validator(mode="after")` does NOT roll back the
  triggering field mutation on raise (CLAUDE.md "What NOT to do").
  Unlikely relevant for Plan 21 (no schema mutations).
- Hypothesis-first diagnosis (auto-memory
  `feedback_hypothesis_first_diagnosis.md`) — if T1's walk-up
  surfaces unexpected behavior (e.g., test finds `.git` from an
  unexpected ancestor), INSTRUMENT before assuming the cause.

## File inventory (summary)

```
tasks/plans/
└── 21-resolve-out-dir-hardening.md         # SELF (this doc);
                                            # T1/T2 outcomes appended
                                            # at exec time

packages/brain_api/
├── src/brain_api/
│   ├── static_ui.py                        # MODIFY: add _find_repo_root
│   │                                       # helper + use in resolve_out_dir (T1)
│   └── app.py                              # MODIFY: log.warning in
│                                           # mount_static_ui except branch (T2)
└── tests/
    ├── test_static_ui_find_repo_root.py    # CREATE: walk-up unit tests (T1)
    └── test_app_silent_degrade_warning.py  # CREATE: warning unit tests (T2)

scripts/
└── demo-plan-21.py                         # CREATE (T3)

tasks/
├── lessons.md                              # MODIFY: Plan 21 closure section (T3)
└── todo.md                                 # MODIFY: row 21 ✅ + Plan 22
                                            # candidate scope tail (T3)
```

## T1 outcome

**(a) Marker choice + D4 adjudication.** Chose `.git` as the walk-up
marker, matching the plan-doc recommendation. Exec-time verification:

- `/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.git` is a
  real directory (drwxr-xr-x, 24 entries) — NOT a git-worktree pointer
  file. Walk-up will reach it via pathlib's `.exists()`.
- `find . -name .git` (excluding `node_modules` / `.venv`) returned
  EXACTLY ONE hit at the repo root. No nested `.git` files or directories
  at `packages/<name>/.git` or `apps/<name>/.git` would short-circuit the
  walk-up incorrectly. No git-submodule edge cases on this repo.
- `find . -name pyproject.toml` returned 5 hits: root + each of
  `packages/{brain_api,brain_cli,brain_core,brain_mcp}/pyproject.toml`.
  This confirms uv-workspace layout and rules OUT `pyproject.toml` as a
  marker — it would short-circuit at the sub-package level
  (`parents[3]`) instead of repo root (`parents[4]`). `.git` is the
  unambiguous choice.

**(b) Helper added at** `packages/brain_api/src/brain_api/static_ui.py`
**lines 70-89.** Pure pathlib (no `os.path`, no `shell=True`), with the
docstring referencing Plan 21 T1 + the auto-memory `feedback_brain_web_out_dir.md`.
Default `marker=".git"`. Returns `None` if walk-up reaches `/` without a
hit. Accepts both directory and file starting paths (`start.parent` for
files).

**(c) `resolve_out_dir` updated at** `static_ui.py` **lines 115-129
(the dev-fallback block; full function spans lines 92-141).**
Walk-up is the primary dev-fallback; `here.parents[4]` retained as
secondary inside `try: ... except IndexError: pass` (preserves
tarball-extracted source-dir behavior when `.git` is absent). The
env-override (`BRAIN_WEB_OUT_DIR`) and install-layout
(`BRAIN_INSTALL_DIR/web/out`) candidates are unchanged.

**(d) Test file +
count.** `packages/brain_api/tests/test_static_ui_find_repo_root.py`
(95 LOC). 5 tests covering: marker-at-start, intermediate first-hit-
wins, missing-marker-returns-None, starting-path-as-directory,
starting-path-as-file. All use unique sentinel names
(`BRAIN_TEST_SENTINEL` / `UNLIKELY_NAME_BRAIN_TEST_SENTINEL`) so the
test runner's own `.git` ancestor chain cannot contaminate assertions.

```
$ uv run --active --no-sync pytest packages/brain_api/tests/test_static_ui_find_repo_root.py -v
...
collected 5 items

test_find_repo_root_finds_marker_at_start PASSED                [ 20%]
test_find_repo_root_finds_marker_at_intermediate_level PASSED   [ 40%]
test_find_repo_root_returns_none_when_marker_absent PASSED      [ 60%]
test_find_repo_root_accepts_starting_path_as_directory PASSED   [ 80%]
test_find_repo_root_accepts_starting_path_as_file PASSED        [100%]

5 passed, 5 warnings in 0.01s
```

**(e) Brain_api full-suite run.** Regression coverage for
`resolve_out_dir`'s production callers:

```
$ uv run --active --no-sync pytest packages/brain_api/tests/ -q
ssss.................................................................... [ 33%]
........................................................................ [ 67%]
....................................................................     [100%]
208 passed, 4 skipped, 5 warnings in 3.31s
```

**(f) Optional visual-QA receipt.** Ran in-process (lighter than full
uvicorn boot, same code-path correctness):

```python
from brain_api.static_ui import resolve_out_dir, _find_repo_root
# Walk-up from .venv site-packages copy (the path resolve_out_dir() sees
# in production under uv non-editable install + iCloud .pth masking):
_find_repo_root(Path(".venv/lib/python3.12/site-packages/brain_api/static_ui.py"))
#   -> Path('/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb')
# Walk-up from source location (the path under editable install):
_find_repo_root(Path("packages/brain_api/src/brain_api/static_ui.py"))
#   -> Path('/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb')
# resolve_out_dir() with no env overrides:
resolve_out_dir()
#   -> Path('/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/apps/brain_web/out')
```

Both walk-up entry points resolve correctly to the iCloud repo root.
`resolve_out_dir()` returns the right path WITHOUT `BRAIN_WEB_OUT_DIR`
set — the env-override workaround documented in the auto-memory is now
unnecessary in dev. (Full uvicorn `curl /` skipped to avoid the
additional flake surface; the in-process check exercises the exact
code path the static-mount uses.)

**Implementer note re: chflags recipe.** During verification the
existing iCloud `.venv` was found in an inconsistent state (every
file duplicated with " 2.py", " 3.py" suffixes — symptoms of iCloud
sync corruption beyond simple `.pth` hidden-flag masking). Resolved by
`rm -rf .venv && uv sync --all-packages` and then
`uv pip install --reinstall-package brain_api -e packages/brain_api`
to switch brain_api to editable mode (the workspace pyproject pins
`editable = false`, so source edits do not auto-propagate to
site-packages). Documented here so future implementers reaching
the same state know the recovery path. The chflags+pytest recipe from
auto-memory `feedback_uv_uf_hidden.md` is still correct for the
NORMAL state; the venv-rebuild was a deeper recovery step.

## T2 outcome

_Filled in at T2 close. Per-step receipts: app.py warning added at line
<N>; logger convention used (structlog vs stdlib logging); test file +
test count + pass/fail; brain_api full-suite run output; monkeypatch-
binding pattern used per Plan 17 T17 lesson._

## T3 outcome

_Filled in at T3 close. Demo gate count + commits + tag SHA + push
receipt._

## Plan 22 candidate scope

Filled in at T3 closure. The canonical record is the tail block of
`tasks/todo.md`; this section is a brief pointer. Preserved Plan 17 /
earlier carry-forwards per D5 (4 NOT-DOING items, unchanged from Plan
20 tail):

- `seedBrainMd` / `seedScope` rule-of-three (threshold not met).
- Per-thread cross-domain confirmation (architectural NO per spec §3 +
  Plan 16 D36).
- Topbar scope chip drift watch (lesson-only per Plan 12).
- Free-threaded Python PEP 703 for `_cached_ctx` (3.14 timeline
  trigger).

Plus any new candidates surfacing from Plan 21 execution.

## Review

_Filled in at T3 close. Tag SHA + closure summary + bumps + verification
receipts + backlog forward._

---

**End of Plan 21.**
