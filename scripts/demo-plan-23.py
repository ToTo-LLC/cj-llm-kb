#!/usr/bin/env python3
"""Plan 23 end-to-end demo — watched-folders hot-fix + UX one-liners closure.

Walks every substantive-task gate from
``tasks/plans/23-watched-folders-hotfix-ux.md`` plus the closure marker.
Each gate is a structural assertion (file existence, regex match, test
function pin) — no live LLM, no network, no spawned servers. Mirrors
the demo-plan-20 / demo-plan-21 / demo-plan-22 shape (cached file reads,
single-purpose gate functions, fail-fast main loop).

Gate map
--------
 1   T1.a  ``packages/brain_core/src/brain_core/tools/list_watched_folders.py``
            ``_walk_watched_folder_counts`` catches ``ValidationError``
            alongside the existing ``FrontmatterError`` (regex match on
            the ``except`` tuple).
 2   T1.b  ``packages/brain_core/tests/tools/test_list_watched_folders.py``
            has the regression-pin test
            ``test_validation_error_note_skipped_without_crash`` AND
            imports ``capture_logs`` from ``structlog.testing``.
 3   T2.a  ``apps/brain_web/src/components/dialogs/watch-enable-modal.tsx``
            domain dropdown initial value derives from ``activeDomain``
            (regex match on the ``useState`` initializer).
 4   T2.b  ``apps/brain_web/tests/unit/watch-modals.test.tsx`` has the
            Plan 23 T2.a default-activeDomain test (regex match on the
            test-name pattern).
 5   T2.c  ``apps/brain_web/src/components/shell/watched-folders-topbar-indicator.tsx``
            has a mount-time ``useEffect`` block that calls ``refresh()``
            (regex match constrained to the component body).
 6   T2.d  ``apps/brain_web/tests/unit/topbar-watched-status.test.tsx``
            has the Plan 23 T2.b mount-fetch describe block + at least
            one test asserting ``refresh()`` fires on mount.
 7   T3    ``tasks/todo.md`` row 23 ✅ + ``tasks/lessons.md`` has a
            ``## Plan 23`` closure section.

Closure (T3) is this script; final stdout line on a clean run is
``PLAN 23 DEMO OK``.

Per Plan 23 D8: gate count ~6-8 mirroring Plan 21's 6 + Plan 20's 7
shape. This script lands 7 gates — 2 per substantive task (code +
test) + 1 closure. Matches the plan-doc §"Demo gate description"
mapping exactly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_CORE = _REPO_ROOT / "packages" / "brain_core"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"
_LIST_WATCHED = (
    _BRAIN_CORE / "src" / "brain_core" / "tools" / "list_watched_folders.py"
)
_LIST_WATCHED_TEST = (
    _BRAIN_CORE / "tests" / "tools" / "test_list_watched_folders.py"
)
_WATCH_ENABLE_MODAL = (
    _BRAIN_WEB / "src" / "components" / "dialogs" / "watch-enable-modal.tsx"
)
_WATCH_MODALS_TEST = (
    _BRAIN_WEB / "tests" / "unit" / "watch-modals.test.tsx"
)
_TOPBAR_INDICATOR = (
    _BRAIN_WEB
    / "src"
    / "components"
    / "shell"
    / "watched-folders-topbar-indicator.tsx"
)
_TOPBAR_TEST = (
    _BRAIN_WEB / "tests" / "unit" / "topbar-watched-status.test.tsx"
)
_TODO = _REPO_ROOT / "tasks" / "todo.md"
_LESSONS = _REPO_ROOT / "tasks" / "lessons.md"


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
# Gate 1 — T1.a: _walk_watched_folder_counts catches ValidationError.
# ---------------------------------------------------------------------------


def _gate_1_t1_validation_error_caught() -> int:
    if rc := _exists("1", _LIST_WATCHED):
        return rc
    text = _read(_LIST_WATCHED)
    # Must import ValidationError from pydantic (T1 outcome: public alias
    # for pydantic_core.ValidationError; used for consistency with the
    # rest of the codebase's pydantic-public imports).
    if not re.search(
        r"from\s+pydantic\s+import\s+(?:[^()\n]*,\s*)?ValidationError",
        text,
    ):
        return _fail(
            "1",
            "list_watched_folders.py missing `from pydantic import ValidationError`",
        )
    # Extract the _walk_watched_folder_counts function body so the except
    # tuple regex can't accidentally match an except clause elsewhere in
    # the module.
    body_match = re.search(
        r"def\s+_walk_watched_folder_counts\s*\([^)]*\)[^:]*:\s*\n"
        r"(.+?)(?=\n(?:def |class |async def )|\Z)",
        text,
        re.DOTALL,
    )
    if body_match is None:
        return _fail(
            "1",
            "list_watched_folders.py missing `_walk_watched_folder_counts` helper",
        )
    body = body_match.group(1)
    # T1 outcome shape: split into `except (OSError, UnicodeDecodeError):`
    # (silent skip for transient I/O) AND `except (FrontmatterError,
    # ValidationError):` (warn + skip for content corruption). Pin the
    # latter shape — both names must appear together inside the same
    # except clause tuple to catch the Plan 23 crash class.
    if not re.search(
        r"except\s*\(\s*FrontmatterError\s*,\s*ValidationError\s*\)\s*as\s+\w+\s*:",
        body,
    ):
        return _fail(
            "1",
            "_walk_watched_folder_counts missing "
            "`except (FrontmatterError, ValidationError) as ...:` clause "
            "(Plan 23 T1 crash-class fix)",
        )
    # Observability uplift: the warn-branch must call structlog (any
    # bound logger reference is fine — verify the warning event name +
    # structlog.warning shape).
    if not re.search(r"logger\.warning\s*\(", body):
        return _fail(
            "1",
            "_walk_watched_folder_counts warn-branch missing `logger.warning(...)` call",
        )
    _gate(
        "1 — T1.a ValidationError catch: _walk_watched_folder_counts "
        "catches (FrontmatterError, ValidationError) + logger.warning"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1.b: regression-pin test exists with capture_logs.
# ---------------------------------------------------------------------------


def _gate_2_t1_regression_pin_test() -> int:
    if rc := _exists("2", _LIST_WATCHED_TEST):
        return rc
    text = _read(_LIST_WATCHED_TEST)
    if "from structlog.testing import capture_logs" not in text:
        return _fail(
            "2",
            "test_list_watched_folders.py missing "
            "`from structlog.testing import capture_logs` import",
        )
    # The exact test-function name is contract — locks the pin in place
    # against future renames that would silently weaken coverage.
    if not re.search(
        r"^async\s+def\s+test_validation_error_note_skipped_without_crash\b",
        text,
        re.MULTILINE,
    ):
        return _fail(
            "2",
            "test_list_watched_folders.py missing "
            "`test_validation_error_note_skipped_without_crash` pin test",
        )
    # The pin must drive capture_logs to assert the warn-and-skip
    # observability contract (Plan 23 T1 outcome receipt).
    if not re.search(r"with\s+capture_logs\s*\(\s*\)\s+as\s+\w+\s*:", text):
        return _fail(
            "2",
            "test_validation_error_note_skipped_without_crash missing "
            "`with capture_logs() as ...:` block",
        )
    _gate(
        "2 — T1.b regression pin: "
        "test_validation_error_note_skipped_without_crash + capture_logs"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T2.a: watch-enable modal initial value derives from activeDomain.
# ---------------------------------------------------------------------------


def _gate_3_t2_active_domain_default() -> int:
    if rc := _exists("3", _WATCH_ENABLE_MODAL):
        return rc
    text = _read(_WATCH_ENABLE_MODAL)
    # The component must destructure activeDomain from useDomains() (the
    # Plan 11 T6 selector that exposes Config.active_domain).
    if not re.search(
        r"const\s*\{\s*(?:[^}]*,\s*)?activeDomain\s*(?:,[^}]*)?\}\s*=\s*useDomains\s*\(",
        text,
    ):
        return _fail(
            "3",
            "watch-enable-modal.tsx missing "
            "`const { ..., activeDomain, ... } = useDomains()` destructure",
        )
    # The domain useState initializer must reference activeDomain. T2.a
    # outcome shape: useState lazy-init with `if (activeDomain) return
    # activeDomain;` falling back to `domains[0]?.slug`. Pin the
    # activeDomain return clause to ensure the precedence isn't flipped.
    state_match = re.search(
        r"useState<string>\s*\(\s*\(\s*\)\s*=>\s*\{(.+?)\}\s*\)",
        text,
        re.DOTALL,
    )
    if state_match is None:
        return _fail(
            "3",
            "watch-enable-modal.tsx missing "
            "`useState<string>(() => { ... })` lazy domain initializer",
        )
    init_body = state_match.group(1)
    if "activeDomain" not in init_body:
        return _fail(
            "3",
            "watch-enable-modal.tsx domain useState initializer body "
            "does not reference `activeDomain`",
        )
    if not re.search(
        r"if\s*\(\s*activeDomain\s*\)\s*return\s+activeDomain",
        init_body,
    ):
        return _fail(
            "3",
            "watch-enable-modal.tsx domain initializer missing "
            "`if (activeDomain) return activeDomain;` precedence "
            "(T2.a contract)",
        )
    _gate(
        "3 — T2.a activeDomain default: useState lazy init derives "
        "domain from activeDomain via useDomains()"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T2.b: unit test asserts activeDomain default.
# ---------------------------------------------------------------------------


def _gate_4_t2_active_domain_test() -> int:
    if rc := _exists("4", _WATCH_MODALS_TEST):
        return rc
    text = _read(_WATCH_MODALS_TEST)
    # Plan 23 T2.a default-activeDomain test name (verbatim from the T2
    # outcome receipt's "Plan 23 T2.a — defaults the domain dropdown to
    # Config.active_domain (not domains[0])" pattern).
    if not re.search(
        r'test\s*\(\s*"Plan 23 T2\.a — defaults the domain dropdown to '
        r'Config\.active_domain \(not domains\[0\]\)"',
        text,
    ):
        return _fail(
            "4",
            "watch-modals.test.tsx missing Plan 23 T2.a "
            "`defaults the domain dropdown to Config.active_domain` test",
        )
    # The test must drive _setDomainsCacheForTesting so the seeded
    # activeDomain reaches the component (T2 outcome's mechanism).
    if "_setDomainsCacheForTesting" not in text:
        return _fail(
            "4",
            "watch-modals.test.tsx missing `_setDomainsCacheForTesting` "
            "import/usage to seed activeDomain",
        )
    _gate(
        "4 — T2.b activeDomain default test: Plan 23 T2.a test exists "
        "+ uses _setDomainsCacheForTesting"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T2.c: topbar indicator has mount-time useEffect calling refresh().
# ---------------------------------------------------------------------------


def _gate_5_t2_topbar_mount_fetch() -> int:
    if rc := _exists("5", _TOPBAR_INDICATOR):
        return rc
    text = _read(_TOPBAR_INDICATOR)
    # The component must subscribe to `loaded` AND `refresh` selectors
    # from useWatchedFoldersStore — both are required for the !loaded
    # gate + the fetch action call.
    if not re.search(
        r"const\s+loaded\s*=\s*useWatchedFoldersStore\s*\(\s*\(\s*s\s*\)\s*=>\s*s\.loaded\s*\)",
        text,
    ):
        return _fail(
            "5",
            "topbar indicator missing "
            "`const loaded = useWatchedFoldersStore((s) => s.loaded)` selector",
        )
    if not re.search(
        r"const\s+refresh\s*=\s*useWatchedFoldersStore\s*\(\s*\(\s*s\s*\)\s*=>\s*s\.refresh\s*\)",
        text,
    ):
        return _fail(
            "5",
            "topbar indicator missing "
            "`const refresh = useWatchedFoldersStore((s) => s.refresh)` selector",
        )
    # Pin the !loaded -> refresh() useEffect (T2.b contract). T2 outcome
    # chose `!loaded` gate over the plan-doc's literal `folders.length === 0`
    # phrasing — locks the correct shape so a regression that weakens to
    # the empty-check shape fails RED.
    effect_match = re.search(
        r"React\.useEffect\s*\(\s*\(\s*\)\s*=>\s*\{(.+?)\}\s*,\s*\[\s*loaded\s*,\s*refresh\s*\]\s*\)",
        text,
        re.DOTALL,
    )
    if effect_match is None:
        return _fail(
            "5",
            "topbar indicator missing "
            "`React.useEffect(() => { ... }, [loaded, refresh])` mount-fetch hook",
        )
    effect_body = effect_match.group(1)
    if not re.search(r"if\s*\(\s*!\s*loaded\s*\)", effect_body):
        return _fail(
            "5",
            "topbar indicator mount-fetch useEffect missing `if (!loaded)` gate",
        )
    if not re.search(r"void\s+refresh\s*\(\s*\)", effect_body):
        return _fail(
            "5",
            "topbar indicator mount-fetch useEffect missing `void refresh()` call",
        )
    _gate(
        "5 — T2.c topbar mount-fetch: useEffect with !loaded gate + "
        "void refresh() call (Plan 23 T2.b contract)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T2.d: unit test asserts mount-time fetch.
# ---------------------------------------------------------------------------


def _gate_6_t2_topbar_mount_fetch_test() -> int:
    if rc := _exists("6", _TOPBAR_TEST):
        return rc
    text = _read(_TOPBAR_TEST)
    # Plan 23 T2.b mount-fetch describe block (the T2 outcome receipt
    # cites this header verbatim).
    if not re.search(
        r'describe\s*\(\s*"WatchedFoldersTopbarIndicator — Plan 23 T2\.b mount-fetch"',
        text,
    ):
        return _fail(
            "6",
            "topbar-watched-status.test.tsx missing "
            "`Plan 23 T2.b mount-fetch` describe block",
        )
    # The mount-fetch test name (T2 outcome receipt phrasing).
    if not re.search(
        r'test\s*\(\s*"fires\s+refresh\(\)\s+on\s+mount\s+when\s+the\s+store\s+is\s+uninitialized',
        text,
    ):
        return _fail(
            "6",
            "topbar-watched-status.test.tsx missing "
            "`fires refresh() on mount when the store is uninitialized` test",
        )
    _gate(
        "6 — T2.d topbar mount-fetch test: Plan 23 T2.b describe + "
        "fires-refresh-on-mount test present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T3 closure: todo.md row 23 ✅ + lessons.md Plan 23 section.
# ---------------------------------------------------------------------------


def _gate_7_t3_closure() -> int:
    if rc := _exists("7", _TODO):
        return rc
    todo_text = _read(_TODO)
    if re.search(r"\|\s*23\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail("7", "tasks/todo.md row 23 not marked `✅ Complete`")
    if rc := _exists("7", _LESSONS):
        return rc
    lessons_text = _read(_LESSONS)
    if "## Plan 23" not in lessons_text:
        return _fail(
            "7",
            "tasks/lessons.md missing `## Plan 23` closure section",
        )
    _gate(
        "7 — T3 closure: tasks/todo.md row 23 ✅; tasks/lessons.md has Plan 23 section"
    )
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t1_validation_error_caught,
    _gate_2_t1_regression_pin_test,
    _gate_3_t2_active_domain_default,
    _gate_4_t2_active_domain_test,
    _gate_5_t2_topbar_mount_fetch,
    _gate_6_t2_topbar_mount_fetch_test,
    _gate_7_t3_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 23 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
