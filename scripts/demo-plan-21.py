#!/usr/bin/env python3
"""Plan 21 end-to-end demo — resolve_out_dir + silent-degrade hardening closure.

Walks every substantive-task gate from
``tasks/plans/21-resolve-out-dir-hardening.md`` plus the closure marker.
Each gate is a structural assertion (file existence, regex match, test
function count) — no live LLM, no network, no spawned servers, no
``import brain_api`` (Plan 21 T2 surfaced the install-as-copy class so
file-content regex is more robust than runtime introspection here).

Gate map
--------
 1   T1.a  ``static_ui.py`` defines a ``_find_repo_root(start, *, marker)``
            helper. Regex match on the source for ``def _find_repo_root(``
            + the ``marker`` keyword arg.
 2   T1.b  ``resolve_out_dir`` body references ``_find_repo_root`` AND
            retains a ``.parents[4]`` secondary fallback wrapped in
            ``try/except IndexError``.
 3   T1.c  ``packages/brain_api/tests/test_static_ui_find_repo_root.py``
            exists with at least 5 ``def test_`` functions.
 4   T2.a  ``packages/brain_api/src/brain_api/app.py``'s
            ``mount_static_ui`` ``except RuntimeError`` branch contains a
            ``_lifespan_logger.warning`` call.
 5   T2.b  ``packages/brain_api/tests/test_app_silent_degrade_warning.py``
            exists with at least 3 ``def test_`` functions.
 6   T3    ``tasks/todo.md`` row 21 marked ✅ + ``tasks/lessons.md`` has
            a ``## Plan 21`` closure section.

Closure (T3) is this script; final stdout line on a clean run is
``PLAN 21 DEMO OK``.

Per Plan 21 D7: gate count is not pinned. 6 gates is the natural count
for Plan 21's surface (2 sub-gates per substantive task + 1 closure
gate). Plan 20 used 7 gates for a similar 2-theme shape; Plan 21's T1
+ T2 each split into a code-content gate + a test-existence gate.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_API = _REPO_ROOT / "packages" / "brain_api"
_STATIC_UI = _BRAIN_API / "src" / "brain_api" / "static_ui.py"
_APP = _BRAIN_API / "src" / "brain_api" / "app.py"
_T1_TESTS = _BRAIN_API / "tests" / "test_static_ui_find_repo_root.py"
_T2_TESTS = _BRAIN_API / "tests" / "test_app_silent_degrade_warning.py"
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
# Gate 1 — T1.a: _find_repo_root helper exists with marker keyword arg.
# ---------------------------------------------------------------------------


def _gate_1_t1_find_repo_root_helper() -> int:
    if rc := _exists("1", _STATIC_UI):
        return rc
    text = _read(_STATIC_UI)
    # Match `def _find_repo_root(<start_param>, *, marker[: type] = ...):`
    # Keyword-only marker arg is required by D4 (marker default = ".git").
    helper_re = re.compile(
        r"def\s+_find_repo_root\s*\([^)]*\bmarker\b[^)]*\)",
        re.DOTALL,
    )
    if not helper_re.search(text):
        return _fail(
            "1",
            "static_ui.py missing `def _find_repo_root(..., marker=...)` helper",
        )
    _gate(
        "1 — T1.a _find_repo_root helper: defined in static_ui.py with "
        "`marker` keyword arg"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1.b: resolve_out_dir uses _find_repo_root AND retains
# parents[4] secondary fallback inside try/except IndexError.
# ---------------------------------------------------------------------------


def _gate_2_t1_resolve_out_dir_uses_walkup() -> int:
    text = _read(_STATIC_UI)
    # Extract the resolve_out_dir function body (def to next top-level def
    # or EOF) to constrain the regex search to that scope.
    body_match = re.search(
        r"def\s+resolve_out_dir\s*\([^)]*\)[^:]*:\s*\n(.+?)(?=\n(?:def |class )|\Z)",
        text,
        re.DOTALL,
    )
    if body_match is None:
        return _fail("2", "static_ui.py missing `def resolve_out_dir(...)`")
    body = body_match.group(1)
    if "_find_repo_root" not in body:
        return _fail(
            "2",
            "resolve_out_dir body missing `_find_repo_root(...)` call",
        )
    # Secondary fallback: `.parents[4]` retained inside try/except
    # IndexError (preserves tarball-extracted source-dir behavior when
    # .git is absent).
    if not re.search(r"\bparents\[4\]", body):
        return _fail(
            "2",
            "resolve_out_dir body missing `.parents[4]` secondary fallback",
        )
    if not re.search(r"except\s+IndexError", body):
        return _fail(
            "2",
            "resolve_out_dir body missing `except IndexError` guard around parents[4]",
        )
    _gate(
        "2 — T1.b resolve_out_dir: calls _find_repo_root AND retains "
        "parents[4] under try/except IndexError"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T1.c: test_static_ui_find_repo_root.py exists with >= 5 tests.
# ---------------------------------------------------------------------------


def _gate_3_t1_helper_tests_exist() -> int:
    if rc := _exists("3", _T1_TESTS):
        return rc
    text = _read(_T1_TESTS)
    test_count = len(re.findall(r"^def\s+test_\w+", text, re.MULTILINE))
    if test_count < 5:
        return _fail(
            "3",
            f"test_static_ui_find_repo_root.py has only {test_count} test "
            "functions; expected >= 5",
        )
    _gate(
        f"3 — T1.c helper tests: {test_count} test functions in "
        "test_static_ui_find_repo_root.py (>= 5)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T2.a: app.py mount_static_ui branch contains a
# _lifespan_logger.warning call inside an except RuntimeError block.
# ---------------------------------------------------------------------------


def _gate_4_t2_silent_degrade_warning_call() -> int:
    if rc := _exists("4", _APP):
        return rc
    text = _read(_APP)
    # Constrain the search to the body of `if mount_static_ui:` so the
    # gate fails RED if the warning gets moved out of the SPA-mount
    # silent-degrade branch.
    body_match = re.search(
        r"if\s+mount_static_ui\s*:\s*\n(.+?)(?=\n    return app|\n\n[a-zA-Z_]|\Z)",
        text,
        re.DOTALL,
    )
    if body_match is None:
        return _fail("4", "app.py missing `if mount_static_ui:` block")
    body = body_match.group(1)
    if "except RuntimeError" not in body:
        return _fail(
            "4",
            "app.py `if mount_static_ui:` block missing `except RuntimeError` guard",
        )
    if not re.search(r"_lifespan_logger\.warning\s*\(", body):
        return _fail(
            "4",
            "app.py `if mount_static_ui:` block missing "
            "`_lifespan_logger.warning(...)` call",
        )
    # The event name must be `spa_mount_skipped` (structured-logging
    # event-name convention; future log-grepping depends on it).
    if "spa_mount_skipped" not in body:
        return _fail(
            "4",
            "app.py silent-degrade warning missing `spa_mount_skipped` event name",
        )
    _gate(
        "4 — T2.a app.py silent-degrade: _lifespan_logger.warning("
        "\"spa_mount_skipped\", ...) inside except RuntimeError"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T2.b: test_app_silent_degrade_warning.py exists with >= 3 tests.
# ---------------------------------------------------------------------------


def _gate_5_t2_silent_degrade_tests_exist() -> int:
    if rc := _exists("5", _T2_TESTS):
        return rc
    text = _read(_T2_TESTS)
    test_count = len(re.findall(r"^def\s+test_\w+", text, re.MULTILINE))
    if test_count < 3:
        return _fail(
            "5",
            f"test_app_silent_degrade_warning.py has only {test_count} test "
            "functions; expected >= 3",
        )
    _gate(
        f"5 — T2.b silent-degrade tests: {test_count} test functions in "
        "test_app_silent_degrade_warning.py (>= 3)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T3 closure: todo.md row 21 ✅ + lessons.md Plan 21 section.
# ---------------------------------------------------------------------------


def _gate_6_t3_closure() -> int:
    if rc := _exists("6", _TODO):
        return rc
    todo_text = _read(_TODO)
    if re.search(r"\|\s*21\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail("6", "tasks/todo.md row 21 not marked `✅ Complete`")
    if rc := _exists("6", _LESSONS):
        return rc
    lessons_text = _read(_LESSONS)
    if "## Plan 21" not in lessons_text:
        return _fail("6", "tasks/lessons.md missing `## Plan 21` closure section")
    _gate(
        "6 — T3 closure: tasks/todo.md row 21 ✅; tasks/lessons.md has Plan 21 section"
    )
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t1_find_repo_root_helper,
    _gate_2_t1_resolve_out_dir_uses_walkup,
    _gate_3_t1_helper_tests_exist,
    _gate_4_t2_silent_degrade_warning_call,
    _gate_5_t2_silent_degrade_tests_exist,
    _gate_6_t3_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 21 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
