#!/usr/bin/env python3
"""Plan 20 end-to-end demo — response_model pins + tools.ts wrapper audit closure.

Walks every substantive-task gate from
``tasks/plans/20-response-model-pins-and-wrapper-audit.md`` plus the
closure marker. Each gate is a structural assertion (file existence,
regex match, Pydantic introspection) — no live LLM, no network, no
spawned servers.

Gate map
--------
 1   T1.1  test_endpoint_setup_status_shape.py exists and pins
            ``set(SetupStatusResponse.model_fields.keys())`` to
            ``{has_token, is_first_run, vault_exists, vault_path}``
 2   T1.2  test_endpoint_token_shape.py exists and pins
            ``set(TokenResponse.model_fields.keys()) == {"token"}``
 3   T1.3  test_response_envelope_shapes.py exists and pins
            ``set(ToolResponse.model_fields.keys()) == {"text", "data"}``
 4   T1.4  same file pins
            ``set(ErrorResponse.model_fields.keys()) == {"error",
            "message", "detail"}``
 5   T2    plan-doc ``## T2 audit findings`` section is non-empty with
            a ``### Verdict summary`` sub-table containing the 4 verdict
            rows (OK-PROPAGATES, OK-NARROW-INTENTIONAL,
            DRIFT-HARDCODED, INVESTIGATE) plus the TOTAL row
 6   T3    zero-fix closure — plan-doc ``## T3 outcome`` section
            contains the phrase "zero-fix closure"
 7   T4    closure — tasks/todo.md row 20 ✅ + lessons.md ``## Plan 20``
            section

Closure (T4) is this script; final stdout line on a clean run is
``PLAN 20 DEMO OK``.

Per Plan 20 D7: gate count is not pinned. T1 bundled 4 sub-pins under
one task; T2 was a single-output audit; T3 collapsed to zero-fix
closure per the user's tiered AskUserQuestion at exec time. Total: 7
gates, the natural count for Plan 20's surface.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_API_TESTS = _REPO_ROOT / "packages" / "brain_api" / "tests"
_SETUP_STATUS_PIN = _BRAIN_API_TESTS / "test_endpoint_setup_status_shape.py"
_TOKEN_PIN = _BRAIN_API_TESTS / "test_endpoint_token_shape.py"
_ENVELOPE_PIN = _BRAIN_API_TESTS / "test_response_envelope_shapes.py"
_PLAN_DOC = (
    _REPO_ROOT / "tasks" / "plans" / "20-response-model-pins-and-wrapper-audit.md"
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
# Gate 1 — T1.1: SetupStatusResponse field-set pin
# ---------------------------------------------------------------------------


def _gate_1_t1_setup_status_pin() -> int:
    if rc := _exists("1", _SETUP_STATUS_PIN):
        return rc
    # Structural: file exists + has the field-set assertion.
    text = _read(_SETUP_STATUS_PIN)
    if "SetupStatusResponse" not in text:
        return _fail("1", "test_endpoint_setup_status_shape.py missing SetupStatusResponse import")
    if not re.search(r"set\(SetupStatusResponse\.model_fields\.keys\(\)\)\s*==", text):
        return _fail(
            "1",
            "test_endpoint_setup_status_shape.py missing strict field-set equality assertion",
        )
    # Functional: import + verify the actual model emits the pinned set.
    try:
        from brain_api.endpoints.setup_status import SetupStatusResponse
    except ImportError as exc:
        return _fail("1", f"failed to import SetupStatusResponse: {exc}")
    expected = {"has_token", "is_first_run", "vault_exists", "vault_path"}
    actual = set(SetupStatusResponse.model_fields.keys())
    if actual != expected:
        return _fail(
            "1",
            f"SetupStatusResponse.model_fields drift: expected {expected}, got {actual}",
        )
    _gate(
        "1 — T1.1 SetupStatusResponse: pin file exists; "
        "model_fields == {has_token, is_first_run, vault_exists, vault_path}"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1.2: TokenResponse field-set pin
# ---------------------------------------------------------------------------


def _gate_2_t1_token_pin() -> int:
    if rc := _exists("2", _TOKEN_PIN):
        return rc
    text = _read(_TOKEN_PIN)
    if "TokenResponse" not in text:
        return _fail("2", "test_endpoint_token_shape.py missing TokenResponse import")
    if not re.search(r"set\(TokenResponse\.model_fields\.keys\(\)\)\s*==", text):
        return _fail(
            "2",
            "test_endpoint_token_shape.py missing strict field-set equality assertion",
        )
    try:
        from brain_api.endpoints.token import TokenResponse
    except ImportError as exc:
        return _fail("2", f"failed to import TokenResponse: {exc}")
    expected = {"token"}
    actual = set(TokenResponse.model_fields.keys())
    if actual != expected:
        return _fail(
            "2",
            f"TokenResponse.model_fields drift: expected {expected}, got {actual}",
        )
    _gate("2 — T1.2 TokenResponse: pin file exists; model_fields == {token}")
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T1.3: ToolResponse field-set pin
# ---------------------------------------------------------------------------


def _gate_3_t1_tool_response_pin() -> int:
    if rc := _exists("3", _ENVELOPE_PIN):
        return rc
    text = _read(_ENVELOPE_PIN)
    if "ToolResponse" not in text:
        return _fail("3", "test_response_envelope_shapes.py missing ToolResponse import")
    if not re.search(r"set\(ToolResponse\.model_fields\.keys\(\)\)\s*==", text):
        return _fail(
            "3",
            "test_response_envelope_shapes.py missing strict ToolResponse field-set equality assertion",
        )
    try:
        from brain_api.responses import ToolResponse
    except ImportError as exc:
        return _fail("3", f"failed to import ToolResponse: {exc}")
    expected = {"text", "data"}
    actual = set(ToolResponse.model_fields.keys())
    if actual != expected:
        return _fail(
            "3",
            f"ToolResponse.model_fields drift: expected {expected}, got {actual}",
        )
    _gate("3 — T1.3 ToolResponse: pin file exists; model_fields == {text, data}")
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T1.4: ErrorResponse field-set pin
# ---------------------------------------------------------------------------


def _gate_4_t1_error_response_pin() -> int:
    # _ENVELOPE_PIN already verified to exist by gate 3.
    text = _read(_ENVELOPE_PIN)
    if "ErrorResponse" not in text:
        return _fail("4", "test_response_envelope_shapes.py missing ErrorResponse import")
    if not re.search(r"set\(ErrorResponse\.model_fields\.keys\(\)\)\s*==", text):
        return _fail(
            "4",
            "test_response_envelope_shapes.py missing strict ErrorResponse field-set equality assertion",
        )
    try:
        from brain_api.responses import ErrorResponse
    except ImportError as exc:
        return _fail("4", f"failed to import ErrorResponse: {exc}")
    expected = {"error", "message", "detail"}
    actual = set(ErrorResponse.model_fields.keys())
    if actual != expected:
        return _fail(
            "4",
            f"ErrorResponse.model_fields drift: expected {expected}, got {actual}",
        )
    _gate(
        "4 — T1.4 ErrorResponse: pin sibling-pinned in same file; "
        "model_fields == {error, message, detail}"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T2: plan-doc has non-empty ``## T2 audit findings`` with
# verdict-summary table containing all 4 verdict rows + TOTAL.
# ---------------------------------------------------------------------------


def _gate_5_t2_audit_findings_section() -> int:
    if rc := _exists("5", _PLAN_DOC):
        return rc
    text = _read(_PLAN_DOC)
    # The section header must exist and be non-empty (followed by content,
    # not the next ## header immediately).
    section_match = re.search(
        r"## T2 audit findings\s*\n(.+?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    if section_match is None:
        return _fail("5", "plan-doc missing `## T2 audit findings` section")
    section_body = section_match.group(1)
    if section_body.strip() == "":
        return _fail("5", "plan-doc `## T2 audit findings` section is empty")
    # Verdict summary sub-table must include all 4 verdict labels + TOTAL.
    for verdict in (
        "OK-PROPAGATES",
        "OK-NARROW-INTENTIONAL",
        "DRIFT-HARDCODED",
        "INVESTIGATE",
        "TOTAL",
    ):
        if verdict not in section_body:
            return _fail(
                "5",
                f"plan-doc `## T2 audit findings` missing verdict-summary row for `{verdict}`",
            )
    _gate(
        "5 — T2 audit findings: section non-empty; verdict-summary "
        "covers 4 verdicts + TOTAL"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T3: zero-fix closure phrase present in ``## T3 outcome``
# ---------------------------------------------------------------------------


def _gate_6_t3_zero_fix_closure() -> int:
    text = _read(_PLAN_DOC)
    section_match = re.search(
        r"## T3 outcome\s*\n(.+?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    if section_match is None:
        return _fail("6", "plan-doc missing `## T3 outcome` section")
    section_body = section_match.group(1)
    if "zero-fix closure" not in section_body:
        return _fail(
            "6",
            "plan-doc `## T3 outcome` missing the phrase `zero-fix closure`",
        )
    _gate("6 — T3 outcome: zero-fix closure phrase present in plan-doc")
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T4: closure (todo.md row 20 ✅ + lessons.md Plan 20 section)
# ---------------------------------------------------------------------------


def _gate_7_t4_closure() -> int:
    todo = _REPO_ROOT / "tasks" / "todo.md"
    if rc := _exists("7", todo):
        return rc
    todo_text = _read(todo)
    if re.search(r"\|\s*20\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail("7", "tasks/todo.md row 20 not marked `✅ Complete`")
    lessons = _REPO_ROOT / "tasks" / "lessons.md"
    if rc := _exists("7", lessons):
        return rc
    lessons_text = _read(lessons)
    if "## Plan 20" not in lessons_text:
        return _fail("7", "tasks/lessons.md missing `## Plan 20` closure section")
    _gate(
        "7 — T4 closure: tasks/todo.md row 20 ✅; tasks/lessons.md has Plan 20 section"
    )
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t1_setup_status_pin,
    _gate_2_t1_token_pin,
    _gate_3_t1_tool_response_pin,
    _gate_4_t1_error_response_pin,
    _gate_5_t2_audit_findings_section,
    _gate_6_t3_zero_fix_closure,
    _gate_7_t4_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 20 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
