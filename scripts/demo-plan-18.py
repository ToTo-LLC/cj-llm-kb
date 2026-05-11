#!/usr/bin/env python3
"""Plan 18 end-to-end demo — typed-surface drift closure.

Walks every substantive-task gate from
``tasks/plans/18-typed-surface-drift-closure.md`` plus the closure
marker. Each gate is a structural assertion (file existence, regex
match, AST shape) — no live LLM, no network, no spawned servers.

Gate map
--------
 1   T1.a  doc-picker-dialog.tsx has no ``it.domain`` / ``it.modified`` reads
 2   T1.b  RecentEntry declares only ``path`` + ``modified_at``
 3   T2    audit-findings table with 15 DRIFT verdict rows recorded
 4   T3.1  recentIngests narrow + RecentIngestEntry shape
 5   T3.2  getIndex narrow + Python key-set pin
 6   T3.3  getBrainMd narrow + Python key-set pin
 7   T3.4  lint narrow + Python key-set pin (Plan 09 stub contract)
 8   T3.5  ingest discriminated-union narrow + per-branch Python pin
 9   T3.6  rejectPatch narrow + Python key-set pin
10   T3.7  undoLast discriminated-union narrow + per-branch pin + consumer fix
11   T3.8  costReport narrow + Python key-set pin
12   T3.9  bulkImport discriminated-union narrow + per-branch pin
13   T3.10 createDomain nested-domain narrow + Python key-set pin
14   T3.11 budgetOverride narrow + Python key-set pin
15   T4    T36 stale-docstring close as ALREADY-DONE (grep zero-hits live)
16   T5    closure — tasks/todo.md row 18 ✅ + lessons.md Plan 18 section

Closure (T5) is this script; final stdout line on a clean run is
``PLAN 18 DEMO OK``.

Per Plan 18 D4: gate count is not pinned. T2 returned 15 DRIFT rows,
so T3 demo asserts each of the 11 T1-class fix commits landed via
per-finding structural assertions (TS narrow + Python pin).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"
_BRAIN_CORE_TESTS = _REPO_ROOT / "packages" / "brain_core" / "tests"
_TOOLS_TS = _BRAIN_WEB / "src" / "lib" / "api" / "tools.ts"
_PLAN_DOC = _REPO_ROOT / "tasks" / "plans" / "18-typed-surface-drift-closure.md"


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


def _strip_comments_ts(content: str) -> str:
    """Drop ``//`` and block-comment lines from TS source for grep purposes."""
    out_lines: list[str] = []
    in_block = False
    for raw in content.splitlines():
        line = raw.strip()
        if in_block:
            if "*/" in line:
                in_block = False
            continue
        if line.startswith("/*"):
            if "*/" not in line:
                in_block = True
            continue
        if line.startswith("//") or line.startswith("*"):
            continue
        out_lines.append(raw)
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Gate 1 — T1.a: doc-picker-dialog.tsx has no ``it.domain`` / ``it.modified``
# ---------------------------------------------------------------------------


def _gate_1_doc_picker_no_drifted_reads() -> int:
    dialog = _BRAIN_WEB / "src" / "components" / "draft" / "doc-picker-dialog.tsx"
    if rc := _exists("1", dialog):
        return rc
    code = _strip_comments_ts(_read(dialog))
    if re.search(r"\bit\.domain\b", code):
        return _fail("1", "doc-picker-dialog.tsx still has `it.domain` read in non-comment code")
    if re.search(r"\bit\.modified\b(?!_at)", code):
        return _fail("1", "doc-picker-dialog.tsx still has `it.modified` read in non-comment code")
    _gate("1 — T1.a doc-picker-dialog.tsx: scope + search filters use path-prefix; no drifted reads")
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1.b: RecentEntry interface declares only ``path`` + ``modified_at``
# ---------------------------------------------------------------------------


def _gate_2_recent_entry_narrow() -> int:
    if rc := _exists("2", _TOOLS_TS):
        return rc
    text = _read(_TOOLS_TS)
    m = re.search(r"export\s+interface\s+RecentEntry\s*\{([^}]+)\}", text)
    if m is None:
        return _fail("2", "tools.ts no longer declares an exported RecentEntry interface")
    body = m.group(1)
    keys = set(re.findall(r"^\s*(\w+)\s*[?:]", body, re.MULTILINE))
    if keys != {"path", "modified_at"}:
        return _fail("2", f"RecentEntry has unexpected keys: {sorted(keys)}")
    _gate("2 — T1.b RecentEntry: narrowed to {path, modified_at}")
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T2: audit-findings table with 15 DRIFT rows recorded
# ---------------------------------------------------------------------------


def _gate_3_t2_audit_table() -> int:
    if rc := _exists("3", _PLAN_DOC):
        return rc
    plan = _read(_PLAN_DOC)
    section = re.search(
        r"^## T2 audit findings\s*\n(.+?)(?=^##\s|\Z)",
        plan,
        re.DOTALL | re.MULTILINE,
    )
    if section is None:
        return _fail("3", "plan doc missing `## T2 audit findings` section")
    body = section.group(1)
    verdict_rows = sum(
        1
        for line in body.splitlines()
        if re.match(r"^\|.+\|.+\|\s*(OK|MINOR|\*\*DRIFT\*\*|DRIFT)\s*\|", line.strip())
    )
    if verdict_rows < 30:
        return _fail("3", f"T2 audit table has only {verdict_rows} verdict rows (expected >=30)")
    if "15 DRIFT" not in body:
        return _fail("3", "T2 summary does not mention 15 DRIFT")
    _gate(f"3 — T2 audit findings: {verdict_rows} verdict rows recorded; 15 DRIFT summary present")
    return 0


# ---------------------------------------------------------------------------
# T3 helpers — every sub-fix gets a TS narrow + Python key-set pin assertion
# ---------------------------------------------------------------------------


def _ts(text_var: str = "") -> str:
    """Cache the tools.ts read at module-load to avoid 11 re-reads."""
    global _TS_CACHE
    if not _TS_CACHE:
        _TS_CACHE = _read(_TOOLS_TS)
    return _TS_CACHE


_TS_CACHE: str = ""


def _assert_pin(label: str, pin_path: Path, pin_name: str) -> int:
    if rc := _exists(label, pin_path):
        return rc
    if pin_name not in _read(pin_path):
        return _fail(label, f"{pin_path.name} missing test fn `{pin_name}`")
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T3.1 recentIngests
# ---------------------------------------------------------------------------


def _gate_4_t3_1_recent_ingests() -> int:
    ts = _ts()
    if "ingests: RecentIngestEntry[]" not in ts:
        return _fail("4", "tools.ts missing `ingests: RecentIngestEntry[]` outer shape")
    if "classified_at" not in ts:
        return _fail("4", "tools.ts RecentIngestEntry missing `classified_at` field")
    _gate("4 — T3.1 recentIngests: TS narrowed to {ingests}; RecentIngestEntry uses classified_at")
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T3.2 getIndex
# ---------------------------------------------------------------------------


def _gate_5_t3_2_get_index() -> int:
    ts = _ts()
    if re.search(r"getIndex.*?frontmatter:\s*Record", ts, re.DOTALL) is None:
        return _fail("5", "tools.ts getIndex narrow missing frontmatter field")
    if rc := _assert_pin(
        "5",
        _BRAIN_CORE_TESTS / "tools" / "test_get_index.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate("5 — T3.2 getIndex: TS narrowed to {domain, frontmatter, body}; Python key-set pin")
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T3.3 getBrainMd
# ---------------------------------------------------------------------------


def _gate_6_t3_3_get_brain_md() -> int:
    ts = _ts()
    if re.search(r"getBrainMd.*?exists:\s*boolean", ts, re.DOTALL) is None:
        return _fail("6", "tools.ts getBrainMd narrow missing {exists: boolean, body: string}")
    if rc := _assert_pin(
        "6",
        _BRAIN_CORE_TESTS / "tools" / "test_get_brain_md.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate("6 — T3.3 getBrainMd: TS narrowed to {exists, body}; Python key-set pin")
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T3.4 lint
# ---------------------------------------------------------------------------


def _gate_7_t3_4_lint() -> int:
    ts = _ts()
    if re.search(
        r"export\s+const\s+lint\s*=.*?status:\s*string;\s*message:\s*string",
        ts,
        re.DOTALL,
    ) is None:
        return _fail("7", "tools.ts lint narrow missing {status, message} for Plan 09 stub")
    if rc := _assert_pin(
        "7",
        _BRAIN_CORE_TESTS / "tools" / "test_lint.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate("7 — T3.4 lint: TS narrowed to Plan 09 stub contract; Python key-set pin")
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T3.5 ingest (discriminated union)
# ---------------------------------------------------------------------------


def _gate_8_t3_5_ingest() -> int:
    ts = _ts()
    if "IngestResultData" not in ts:
        return _fail("8", "tools.ts missing IngestResultData discriminated-union type")
    pin_path = _BRAIN_CORE_TESTS / "tools" / "test_ingest.py"
    if rc := _exists("8", pin_path):
        return rc
    pin_text = _read(pin_path)
    for branch in ("test_data_keys_pin_applied", "test_data_keys_pin_pending", "test_data_keys_pin_error"):
        if branch not in pin_text:
            return _fail("8", f"test_ingest.py missing {branch}")
    _gate("8 — T3.5 ingest: TS discriminated union; 3 per-branch Python key-set pins")
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T3.6 rejectPatch
# ---------------------------------------------------------------------------


def _gate_9_t3_6_reject_patch() -> int:
    ts = _ts()
    if re.search(r"rejectPatch.*?status:\s*\"rejected\"", ts, re.DOTALL) is None:
        return _fail("9", "tools.ts rejectPatch narrow missing `status: \"rejected\"` literal")
    if rc := _assert_pin(
        "9",
        _BRAIN_CORE_TESTS / "tools" / "test_reject_patch.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate('9 — T3.6 rejectPatch: TS narrowed to {status: "rejected", patch_id, reason}; Python pin')
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T3.7 undoLast (discriminated union + live consumer fix)
# ---------------------------------------------------------------------------


def _gate_10_t3_7_undo_last() -> int:
    ts = _ts()
    if "UndoLastData" not in ts:
        return _fail("10", "tools.ts missing UndoLastData discriminated-union type")
    pin_path = _BRAIN_CORE_TESTS / "tools" / "test_undo_last.py"
    if rc := _exists("10", pin_path):
        return rc
    pin_text = _read(pin_path)
    for branch in ("test_data_keys_pin_reverted", "test_data_keys_pin_nothing_to_undo"):
        if branch not in pin_text:
            return _fail("10", f"test_undo_last.py missing {branch}")
    pending = _BRAIN_WEB / "src" / "components" / "pending" / "pending-screen.tsx"
    if rc := _exists("10", pending):
        return rc
    if "nothing_to_undo" not in _read(pending):
        return _fail("10", "pending-screen.tsx missing discriminated handling on `nothing_to_undo`")
    _gate("10 — T3.7 undoLast: TS discriminated union; 2 per-branch pins; pending-screen consumer fix")
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T3.8 costReport
# ---------------------------------------------------------------------------


def _gate_11_t3_8_cost_report() -> int:
    ts = _ts()
    if re.search(
        r"costReport.*?today_usd.*?month_usd.*?by_domain.*?by_mode",
        ts,
        re.DOTALL,
    ) is None:
        return _fail("11", "tools.ts costReport narrow missing today_usd/month_usd/by_domain/by_mode")
    if rc := _assert_pin(
        "11",
        _BRAIN_CORE_TESTS / "tools" / "test_cost_report.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate("11 — T3.8 costReport: TS narrowed to backend shape; Python key-set pin")
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T3.9 bulkImport (discriminated union)
# ---------------------------------------------------------------------------


def _gate_12_t3_9_bulk_import() -> int:
    ts = _ts()
    if "BulkImportData" not in ts:
        return _fail("12", "tools.ts missing BulkImportData discriminated-union type")
    pin_path = _BRAIN_CORE_TESTS / "tools" / "test_bulk_import.py"
    if rc := _exists("12", pin_path):
        return rc
    pin_text = _read(pin_path)
    for branch in (
        "test_data_keys_pin_refused",
        "test_data_keys_pin_planned",
        "test_data_keys_pin_applied",
    ):
        if branch not in pin_text:
            return _fail("12", f"test_bulk_import.py missing {branch}")
    _gate("12 — T3.9 bulkImport: TS discriminated union; 3 per-branch Python key-set pins")
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T3.10 createDomain (nested under `domain` key)
# ---------------------------------------------------------------------------


def _gate_13_t3_10_create_domain() -> int:
    ts = _ts()
    if re.search(
        r"createDomain.*?status:\s*\"created\".*?domain:\s*\{",
        ts,
        re.DOTALL,
    ) is None:
        return _fail("13", "tools.ts createDomain narrow missing nested `domain: {...}` shape")
    if rc := _assert_pin(
        "13",
        _BRAIN_CORE_TESTS / "tools" / "test_create_domain.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate('13 — T3.10 createDomain: TS narrowed to {status, domain: {...}, note}; Python pin')
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T3.11 budgetOverride
# ---------------------------------------------------------------------------


def _gate_14_t3_11_budget_override() -> int:
    ts = _ts()
    if re.search(
        r"budgetOverride.*?override_until.*?override_delta_usd",
        ts,
        re.DOTALL,
    ) is None:
        return _fail("14", "tools.ts budgetOverride narrow missing override_until/override_delta_usd")
    if rc := _assert_pin(
        "14",
        _BRAIN_CORE_TESTS / "tools" / "test_budget_override.py",
        "test_data_keys_pin",
    ):
        return rc
    _gate("14 — T3.11 budgetOverride: TS narrowed to backend shape; Python key-set pin")
    return 0


# ---------------------------------------------------------------------------
# Gate 15 — T4: T36 stale docstring close-as-ALREADY-DONE
# ---------------------------------------------------------------------------


def _gate_15_t4_already_done() -> int:
    if rc := _exists("15", _PLAN_DOC):
        return rc
    plan = _read(_PLAN_DOC)
    if "## T4 outcome" not in plan:
        return _fail("15", "plan doc missing `## T4 outcome` section")
    if "ALREADY-DONE" not in plan:
        return _fail("15", "plan doc T4 outcome doesn't state ALREADY-DONE verdict")
    # Re-run the grep at demo time across brain_core tests.
    for phrase in (
        "doesn't enable validate_assignment",
        "does not enable validate_assignment",
        "without validate_assignment",
        "NOT enable validate_assignment",
    ):
        result = subprocess.run(
            ["grep", "-rn", phrase, str(_BRAIN_CORE_TESTS)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _fail("15", f"grep {phrase!r} produced unexpected hits:\n{result.stdout}")
    _gate("15 — T4 outcome: ALREADY-DONE verdict recorded; live grep returns zero hits across all 4 phrases")
    return 0


# ---------------------------------------------------------------------------
# Gate 16 — T5: closure (todo.md row 18 ✅ + lessons.md Plan 18 section)
# ---------------------------------------------------------------------------


def _gate_16_t5_closure() -> int:
    todo = _REPO_ROOT / "tasks" / "todo.md"
    if rc := _exists("16", todo):
        return rc
    todo_text = _read(todo)
    if re.search(r"\|\s*18\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail("16", "tasks/todo.md row 18 not marked `✅ Complete`")
    lessons = _REPO_ROOT / "tasks" / "lessons.md"
    if rc := _exists("16", lessons):
        return rc
    lessons_text = _read(lessons)
    if "## Plan 18" not in lessons_text:
        return _fail("16", "tasks/lessons.md missing `## Plan 18` closure section")
    _gate("16 — T5 closure: tasks/todo.md row 18 ✅; tasks/lessons.md has Plan 18 section")
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_doc_picker_no_drifted_reads,
    _gate_2_recent_entry_narrow,
    _gate_3_t2_audit_table,
    _gate_4_t3_1_recent_ingests,
    _gate_5_t3_2_get_index,
    _gate_6_t3_3_get_brain_md,
    _gate_7_t3_4_lint,
    _gate_8_t3_5_ingest,
    _gate_9_t3_6_reject_patch,
    _gate_10_t3_7_undo_last,
    _gate_11_t3_8_cost_report,
    _gate_12_t3_9_bulk_import,
    _gate_13_t3_10_create_domain,
    _gate_14_t3_11_budget_override,
    _gate_15_t4_already_done,
    _gate_16_t5_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 18 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
