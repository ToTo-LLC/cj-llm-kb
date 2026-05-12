#!/usr/bin/env python3
"""Plan 22 end-to-end demo — watched-folders sync closure.

Walks every substantive-task gate from
``tasks/plans/22-watched-folders-sync.md`` plus the closure marker.
Each gate is a structural assertion (file existence, regex match,
inspect.signature, list_tools registry walk) — no live LLM, no network,
no spawned servers, no started watchers. Mirrors the demo-plan-19 /
demo-plan-20 / demo-plan-21 shape (cached file reads, single-purpose
gate functions, fail-fast main loop).

Gate map
--------
 1   T0     spec edits — §4 has 4 new frontmatter fields, §5 has
            "Watched folders" subsection, §10 has watched-folders bullet
 2   T1     ``WatchedFolder`` class + ``Config.watched_folders`` field
            (pydantic introspection)
 3   T2     ``IngestPipeline.update_source`` method exists
 4   T3     ``IngestPipeline.mark_orphaned`` method exists
 5   T4     ``scope_guard`` accepts ``include_orphans`` kwarg (default False)
 6   T5     7 watched-folder tools registered in ``brain_core.tools.list_tools()``
 7   T6     ``WatchedFolderWatcher`` class in ``brain_core.watch.folder_watcher``
 8   T7     brain_api ``app.py`` imports + uses ``WatchedFolderWatcher``
 9   T8     brain_mcp ``__main__.py`` imports + uses ``WatchedFolderWatcher``
10   T9     ``"pre_watched_folder_sync"`` in ``backup_create._VALID_TRIGGERS``
11   T10    backend integration test files exist
            (``test_folder_watcher_integration.py`` +
            ``test_watched_folders_integration.py``)
12   T10.5  ``IngestPipeline.ingest`` accepts ``source_path`` +
            ``watched_folder_id`` kwargs (inspect.signature)
13   T11    brain-ui-designer mockups landed at ``docs/design/plan-22/``
            (6 mockup files + README)
14   T12    ``panel-watched-folders.tsx`` exists
15   T13    ``panel-orphans.tsx`` exists
16   T14    ``watched-folders-topbar-indicator.tsx`` exists
17   T14.5  ``brain_watch_folder`` INPUT_SCHEMA contains ``dry_run`` property
18   T15    3 modal components + Bulk Import → Watch CTA exist
19   T16    ``apps/brain_web/tests/e2e/watched-folders.spec.ts`` exists
20   T17/.5 ``test_tools_listing.py`` constant matches actual tool count
21   T17    closure — ``tasks/todo.md`` row 22 ✅ + ``tasks/lessons.md``
            has ``## Plan 22`` closure section

Closure (T17) is this script; final stdout line on a clean run is
``PLAN 22 DEMO OK``.

Per Plan 22 D14: gate count is informational (target ~16-18 per plan
doc §99-159). This script lands 21 gates — the 7 substantive tools
(T5) collapse to a single gate via list-comprehension over the
registry; T10/T10.5/T11 each get their own gate per the
T10.5-discovered correctness pin; 3 modals (T15) bundle to one gate
with explicit per-file existence checks. Mirrors Plan 16's gate density
on a multi-theme plan.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_CORE = _REPO_ROOT / "packages" / "brain_core"
_BRAIN_API = _REPO_ROOT / "packages" / "brain_api"
_BRAIN_MCP = _REPO_ROOT / "packages" / "brain_mcp"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"
_SPEC = _REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-04-13-cj-llm-kb-design.md"
_BRAIN_API_APP = _BRAIN_API / "src" / "brain_api" / "app.py"
_BRAIN_MCP_MAIN = _BRAIN_MCP / "src" / "brain_mcp" / "__main__.py"
_WATCH_FOLDER_TOOL = _BRAIN_CORE / "src" / "brain_core" / "tools" / "watch_folder.py"
_DESIGN_DIR = _REPO_ROOT / "docs" / "design" / "plan-22"
_PANEL_WATCHED = _BRAIN_WEB / "src" / "components" / "settings" / "panel-watched-folders.tsx"
_PANEL_ORPHANS = _BRAIN_WEB / "src" / "components" / "settings" / "panel-orphans.tsx"
_TOPBAR_INDICATOR = _BRAIN_WEB / "src" / "components" / "shell" / "watched-folders-topbar-indicator.tsx"
_WATCH_ENABLE_MODAL = _BRAIN_WEB / "src" / "components" / "dialogs" / "watch-enable-modal.tsx"
_WATCH_DISABLE_MODAL = _BRAIN_WEB / "src" / "components" / "dialogs" / "watch-disable-modal.tsx"
_ORPHAN_DELETE_MODAL = _BRAIN_WEB / "src" / "components" / "dialogs" / "orphan-delete-modal.tsx"
_STEP_APPLY = _BRAIN_WEB / "src" / "components" / "bulk" / "step-apply.tsx"
_E2E_SPEC = _BRAIN_WEB / "tests" / "e2e" / "watched-folders.spec.ts"
_TOOLS_LISTING_TEST = _BRAIN_API / "tests" / "test_tools_listing.py"
_TODO = _REPO_ROOT / "tasks" / "todo.md"
_LESSONS = _REPO_ROOT / "tasks" / "lessons.md"


_WATCHED_FOLDER_TOOL_NAMES = (
    "brain_watch_folder",
    "brain_unwatch_folder",
    "brain_list_watched_folders",
    "brain_list_orphans",
    "brain_resync_folder",
    "brain_restore_orphan",
    "brain_delete_orphan",
)


def _gate(label: str) -> None:
    print(f"  ok Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  FAIL Gate {label}: {why}", file=sys.stderr)
    return 1


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exists(label: str, path: Path) -> int:
    if not path.is_file():
        return _fail(label, f"file missing: {path}")
    return 0


# ---------------------------------------------------------------------------
# Gate 1 — T0: spec edits in §4 / §5 / §10 (regex matches per gate map).
# ---------------------------------------------------------------------------


def _gate_1_t0_spec_edits() -> int:
    if rc := _exists("1", _SPEC):
        return rc
    spec = _read(_SPEC)
    # §4 — 4 new frontmatter fields (source_path / orphaned / orphaned_at /
    # watched_folder_id). Verify all 4 occur in the spec text.
    missing_fm = [
        name
        for name in ("source_path", "orphaned", "orphaned_at", "watched_folder_id")
        if name not in spec
    ]
    if missing_fm:
        return _fail("1", f"spec §4 missing frontmatter field(s): {missing_fm}")
    # §5 — "Watched folders" subsection header (any depth ##/###/####).
    if not re.search(r"^#{2,5}\s+Watched folders\b", spec, re.MULTILINE):
        return _fail("1", "spec §5 missing 'Watched folders' subsection heading")
    # §10 — watched-folders safety-rails bullet (mentions
    # pre_watched_folder_sync OR include_orphans in the safety-rails context).
    if "pre_watched_folder_sync" not in spec:
        return _fail("1", "spec §10 missing `pre_watched_folder_sync` backup trigger reference")
    _gate("1 — T0 spec edits: §4 4 frontmatter fields + §5 Watched folders subsection + §10 backup-trigger bullet")
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1: WatchedFolder Pydantic model + Config.watched_folders field.
# ---------------------------------------------------------------------------


def _gate_2_t1_schema() -> int:
    try:
        from brain_core.config import schema as schema_mod
        from brain_core.config.schema import Config
    except ImportError as exc:
        return _fail("2", f"cannot import brain_core.config.schema: {exc}")
    if not hasattr(schema_mod, "WatchedFolder"):
        return _fail("2", "brain_core.config.schema missing `WatchedFolder` class")
    if "watched_folders" not in Config.model_fields:
        return _fail("2", "Config missing `watched_folders` field")
    # WatchedFolder field-set: at minimum path / domain / enabled / policy.
    wf_fields = set(schema_mod.WatchedFolder.model_fields.keys())
    required_subset = {"path", "domain", "enabled", "policy"}
    if not required_subset.issubset(wf_fields):
        return _fail(
            "2",
            f"WatchedFolder fields {sorted(wf_fields)} missing required subset {sorted(required_subset)}",
        )
    _gate(
        f"2 — T1 schema: WatchedFolder({sorted(wf_fields)}) + Config.watched_folders field"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T2: IngestPipeline.update_source method exists.
# ---------------------------------------------------------------------------


def _gate_3_t2_update_source() -> int:
    try:
        from brain_core.ingest.pipeline import IngestPipeline
    except ImportError as exc:
        return _fail("3", f"cannot import IngestPipeline: {exc}")
    if not hasattr(IngestPipeline, "update_source"):
        return _fail("3", "IngestPipeline missing `update_source` method")
    if not callable(IngestPipeline.update_source):
        return _fail("3", "`IngestPipeline.update_source` is not callable")
    _gate("3 — T2 IngestPipeline.update_source: method exists (re-ingest path; D1 overwrite contract)")
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T3: IngestPipeline.mark_orphaned method exists.
# ---------------------------------------------------------------------------


def _gate_4_t3_mark_orphaned() -> int:
    try:
        from brain_core.ingest.pipeline import IngestPipeline
    except ImportError as exc:
        return _fail("4", f"cannot import IngestPipeline: {exc}")
    if not hasattr(IngestPipeline, "mark_orphaned"):
        return _fail("4", "IngestPipeline missing `mark_orphaned` method")
    if not callable(IngestPipeline.mark_orphaned):
        return _fail("4", "`IngestPipeline.mark_orphaned` is not callable")
    _gate("4 — T3 IngestPipeline.mark_orphaned: method exists (D2 non-destructive orphan mark)")
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T4: scope_guard accepts include_orphans kwarg (default False).
# ---------------------------------------------------------------------------


def _gate_5_t4_scope_guard_include_orphans() -> int:
    try:
        from brain_core.vault.paths import scope_guard
    except ImportError as exc:
        return _fail("5", f"cannot import scope_guard: {exc}")
    sig = inspect.signature(scope_guard)
    if "include_orphans" not in sig.parameters:
        return _fail("5", f"scope_guard missing `include_orphans` kwarg; params={list(sig.parameters)}")
    param = sig.parameters["include_orphans"]
    if param.default is not False:
        return _fail("5", f"scope_guard `include_orphans` default is {param.default!r}, expected False")
    _gate("5 — T4 scope_guard: `include_orphans: bool = False` kwarg present (D2 default-filter)")
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T5: all 7 watched-folder tools registered in list_tools().
# ---------------------------------------------------------------------------


def _gate_6_t5_seven_tools_registered() -> int:
    try:
        from brain_core.tools import _TOOL_MODULES
    except ImportError as exc:
        return _fail("6", f"cannot import brain_core.tools: {exc}")
    registered = {m.NAME for m in _TOOL_MODULES}
    missing = [name for name in _WATCHED_FOLDER_TOOL_NAMES if name not in registered]
    if missing:
        return _fail("6", f"watched-folder tools not registered: {missing}")
    _gate(
        f"6 — T5 watched-folder tools: 7 registered "
        f"({', '.join(_WATCHED_FOLDER_TOOL_NAMES)})"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T6: WatchedFolderWatcher class in brain_core.watch.folder_watcher.
# ---------------------------------------------------------------------------


def _gate_7_t6_watcher_core() -> int:
    try:
        from brain_core.watch import WatchedFolderWatcher
        from brain_core.watch import folder_watcher as fw_mod
    except ImportError as exc:
        return _fail("7", f"cannot import WatchedFolderWatcher: {exc}")
    if not inspect.isclass(WatchedFolderWatcher):
        return _fail("7", "WatchedFolderWatcher is not a class")
    # Must mirror ConfigWatcher shape: start + stop methods at minimum.
    for method in ("start", "stop"):
        if not hasattr(WatchedFolderWatcher, method):
            return _fail("7", f"WatchedFolderWatcher missing `{method}` method")
    # Verify the class is defined in folder_watcher.py (not re-exported from
    # elsewhere) so a future refactor that moves the implementation fails the
    # gate and re-validates the symmetric-watcher contract.
    if WatchedFolderWatcher.__module__ != fw_mod.__name__:
        return _fail(
            "7",
            f"WatchedFolderWatcher.__module__ is {WatchedFolderWatcher.__module__!r}, "
            "expected brain_core.watch.folder_watcher",
        )
    _gate("7 — T6 WatchedFolderWatcher: class in brain_core.watch.folder_watcher with start/stop (D7 symmetric)")
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T7: brain_api app.py imports + uses WatchedFolderWatcher.
# ---------------------------------------------------------------------------


def _gate_8_t7_brain_api_lifespan() -> int:
    if rc := _exists("8", _BRAIN_API_APP):
        return rc
    text = _read(_BRAIN_API_APP)
    if "WatchedFolderWatcher" not in text:
        return _fail("8", "brain_api/app.py does not reference `WatchedFolderWatcher`")
    if "from brain_core.watch import" not in text:
        return _fail("8", "brain_api/app.py does not import from `brain_core.watch`")
    # Confirm the lifespan integration includes a builder call site.
    if "_build_watched_folder_watcher" not in text:
        return _fail("8", "brain_api/app.py missing `_build_watched_folder_watcher` helper")
    _gate("8 — T7 brain_api lifespan: imports WatchedFolderWatcher + has _build_watched_folder_watcher helper")
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T8: brain_mcp __main__.py imports + uses WatchedFolderWatcher.
# ---------------------------------------------------------------------------


def _gate_9_t8_brain_mcp_watcher() -> int:
    if rc := _exists("9", _BRAIN_MCP_MAIN):
        return rc
    text = _read(_BRAIN_MCP_MAIN)
    if "WatchedFolderWatcher" not in text:
        return _fail("9", "brain_mcp/__main__.py does not reference `WatchedFolderWatcher`")
    if "from brain_core.watch import" not in text:
        return _fail("9", "brain_mcp/__main__.py does not import from `brain_core.watch`")
    # Symmetric helper name pattern (mirrors brain_api).
    if "_build_watched_folder_watcher" not in text:
        return _fail(
            "9",
            "brain_mcp/__main__.py missing `_build_watched_folder_watcher` helper "
            "(D7 symmetric watcher pattern)",
        )
    _gate("9 — T8 brain_mcp _cached_ctx: imports WatchedFolderWatcher + has symmetric builder (D7)")
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T9: pre_watched_folder_sync in backup_create._VALID_TRIGGERS.
# ---------------------------------------------------------------------------


def _gate_10_t9_backup_trigger() -> int:
    try:
        from brain_core.tools import backup_create
    except ImportError as exc:
        return _fail("10", f"cannot import brain_core.tools.backup_create: {exc}")
    valid = getattr(backup_create, "_VALID_TRIGGERS", None)
    if valid is None:
        return _fail("10", "backup_create missing `_VALID_TRIGGERS` constant")
    if "pre_watched_folder_sync" not in valid:
        return _fail("10", f"`pre_watched_folder_sync` not in _VALID_TRIGGERS={valid!r}")
    _gate(f"10 — T9 backup trigger: `pre_watched_folder_sync` in _VALID_TRIGGERS={valid!r}")
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T10: backend integration test files exist.
# ---------------------------------------------------------------------------


def _gate_11_t10_integration_tests() -> int:
    core_test = _BRAIN_CORE / "tests" / "watch" / "test_folder_watcher_integration.py"
    api_test = _BRAIN_API / "tests" / "test_watched_folders_integration.py"
    if rc := _exists("11", core_test):
        return rc
    if rc := _exists("11", api_test):
        return rc
    _gate(
        "11 — T10 backend integration tests: "
        "test_folder_watcher_integration.py + test_watched_folders_integration.py"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T10.5: pipeline.ingest accepts source_path + watched_folder_id.
# ---------------------------------------------------------------------------


def _gate_12_t10_5_ingest_kwargs() -> int:
    try:
        from brain_core.ingest.pipeline import IngestPipeline
    except ImportError as exc:
        return _fail("12", f"cannot import IngestPipeline: {exc}")
    sig = inspect.signature(IngestPipeline.ingest)
    params = set(sig.parameters.keys())
    for required in ("source_path", "watched_folder_id"):
        if required not in params:
            return _fail(
                "12",
                f"IngestPipeline.ingest missing `{required}` kwarg "
                f"(T10.5 lookup-gap fix); params={sorted(params)}",
            )
    _gate(
        "12 — T10.5 lookup gap closed: IngestPipeline.ingest accepts "
        "`source_path` + `watched_folder_id` kwargs"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T11: brain-ui-designer mockups landed at docs/design/plan-22/.
# ---------------------------------------------------------------------------


_T11_MOCKUPS = (
    "watched-folders-settings.md",
    "orphan-management.md",
    "topbar-status.md",
    "modal-watch-enable.md",
    "modal-watch-disable.md",
    "modal-orphan-delete.md",
    "README.md",
)


def _gate_13_t11_mockups() -> int:
    if not _DESIGN_DIR.is_dir():
        return _fail("13", f"design dir missing: {_DESIGN_DIR}")
    missing = [name for name in _T11_MOCKUPS if not (_DESIGN_DIR / name).is_file()]
    if missing:
        return _fail("13", f"T11 mockup files missing: {missing}")
    _gate(f"13 — T11 mockups: 6 mockup files + README at docs/design/plan-22/")
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T12: panel-watched-folders.tsx exists.
# ---------------------------------------------------------------------------


def _gate_14_t12_panel_watched_folders() -> int:
    if rc := _exists("14", _PANEL_WATCHED):
        return rc
    _gate("14 — T12 Settings panel: panel-watched-folders.tsx exists")
    return 0


# ---------------------------------------------------------------------------
# Gate 15 — T13: panel-orphans.tsx exists.
# ---------------------------------------------------------------------------


def _gate_15_t13_panel_orphans() -> int:
    if rc := _exists("15", _PANEL_ORPHANS):
        return rc
    _gate("15 — T13 Orphan panel: panel-orphans.tsx exists")
    return 0


# ---------------------------------------------------------------------------
# Gate 16 — T14: watched-folders-topbar-indicator.tsx exists.
# ---------------------------------------------------------------------------


def _gate_16_t14_topbar_indicator() -> int:
    if rc := _exists("16", _TOPBAR_INDICATOR):
        return rc
    _gate("16 — T14 Topbar indicator: watched-folders-topbar-indicator.tsx exists")
    return 0


# ---------------------------------------------------------------------------
# Gate 17 — T14.5: brain_watch_folder INPUT_SCHEMA contains `dry_run` property.
# ---------------------------------------------------------------------------


def _gate_17_t14_5_dry_run_mode() -> int:
    try:
        from brain_core.tools import watch_folder
    except ImportError as exc:
        return _fail("17", f"cannot import brain_core.tools.watch_folder: {exc}")
    schema = getattr(watch_folder, "INPUT_SCHEMA", None)
    if not isinstance(schema, dict):
        return _fail("17", "watch_folder.INPUT_SCHEMA missing or not a dict")
    properties = schema.get("properties", {})
    if "dry_run" not in properties:
        return _fail(
            "17",
            f"watch_folder INPUT_SCHEMA.properties missing `dry_run`; keys={sorted(properties)}",
        )
    _gate("17 — T14.5 dry_run mode: brain_watch_folder INPUT_SCHEMA.properties.dry_run exists")
    return 0


# ---------------------------------------------------------------------------
# Gate 18 — T15: 3 modal components + Bulk Import → Watch CTA.
# ---------------------------------------------------------------------------


def _gate_18_t15_modals_and_cta() -> int:
    for label, path in (
        ("watch-enable-modal.tsx", _WATCH_ENABLE_MODAL),
        ("watch-disable-modal.tsx", _WATCH_DISABLE_MODAL),
        ("orphan-delete-modal.tsx", _ORPHAN_DELETE_MODAL),
    ):
        if not path.is_file():
            return _fail("18", f"T15 modal missing: {label} at {path}")
    if rc := _exists("18", _STEP_APPLY):
        return rc
    step_text = _read(_STEP_APPLY)
    # Bulk Import CTA: must mention "Watch this folder" microcopy AND the
    # watch-enable modal kind (`kind: "watch-enable"`) to confirm wiring.
    if "Watch this folder" not in step_text:
        return _fail("18", "step-apply.tsx missing `Watch this folder` CTA microcopy")
    if 'kind: "watch-enable"' not in step_text:
        return _fail("18", "step-apply.tsx missing `kind: \"watch-enable\"` modal dispatch")
    _gate(
        "18 — T15 modals + CTA: 3 modal components + Bulk Import "
        '"Watch this folder" CTA wired to watch-enable modal'
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 19 — T16: watched-folders.spec.ts exists.
# ---------------------------------------------------------------------------


def _gate_19_t16_e2e_spec() -> int:
    if rc := _exists("19", _E2E_SPEC):
        return rc
    _gate("19 — T16 e2e: apps/brain_web/tests/e2e/watched-folders.spec.ts exists")
    return 0


# ---------------------------------------------------------------------------
# Gate 20 — T17 fix: test_tools_listing.py constant matches actual tool count.
# ---------------------------------------------------------------------------


def _gate_20_t17_test_tools_listing_fixed() -> int:
    try:
        from brain_core.tools import _TOOL_MODULES
    except ImportError as exc:
        return _fail("20", f"cannot import brain_core.tools._TOOL_MODULES: {exc}")
    actual = len(_TOOL_MODULES)
    if rc := _exists("20", _TOOLS_LISTING_TEST):
        return rc
    text = _read(_TOOLS_LISTING_TEST)
    # Pin matches the canonical `assert len(body["tools"]) == <N>` line.
    m = re.search(r'assert\s+len\(body\["tools"\]\)\s*==\s*(\d+)', text)
    if m is None:
        return _fail("20", "test_tools_listing.py missing `assert len(body[\"tools\"]) == N` literal")
    pinned = int(m.group(1))
    if pinned != actual:
        return _fail(
            "20",
            f"test_tools_listing.py pinned {pinned} tools; actual list_tools() returns {actual}",
        )
    _gate(f"20 — T17 fix: test_tools_listing.py constant = {pinned} matches actual {actual} registered tools")
    return 0


# ---------------------------------------------------------------------------
# Gate 21 — T17 closure: tasks/todo.md row 22 ✅ + lessons.md Plan 22 section.
# ---------------------------------------------------------------------------


def _gate_21_t17_closure() -> int:
    if rc := _exists("21", _TODO):
        return rc
    todo_text = _read(_TODO)
    if re.search(r"\|\s*22\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail("21", "tasks/todo.md row 22 not marked `✅ Complete`")
    if rc := _exists("21", _LESSONS):
        return rc
    lessons_text = _read(_LESSONS)
    if "## Plan 22" not in lessons_text:
        return _fail("21", "tasks/lessons.md missing `## Plan 22` closure section")
    _gate("21 — T17 closure: tasks/todo.md row 22 ✅; tasks/lessons.md has Plan 22 section")
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t0_spec_edits,
    _gate_2_t1_schema,
    _gate_3_t2_update_source,
    _gate_4_t3_mark_orphaned,
    _gate_5_t4_scope_guard_include_orphans,
    _gate_6_t5_seven_tools_registered,
    _gate_7_t6_watcher_core,
    _gate_8_t7_brain_api_lifespan,
    _gate_9_t8_brain_mcp_watcher,
    _gate_10_t9_backup_trigger,
    _gate_11_t10_integration_tests,
    _gate_12_t10_5_ingest_kwargs,
    _gate_13_t11_mockups,
    _gate_14_t12_panel_watched_folders,
    _gate_15_t13_panel_orphans,
    _gate_16_t14_topbar_indicator,
    _gate_17_t14_5_dry_run_mode,
    _gate_18_t15_modals_and_cta,
    _gate_19_t16_e2e_spec,
    _gate_20_t17_test_tools_listing_fixed,
    _gate_21_t17_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 22 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
