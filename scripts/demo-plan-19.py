#!/usr/bin/env python3
"""Plan 19 end-to-end demo — REST-endpoint drift + typed-surface polish closure.

Walks every substantive-task gate from
``tasks/plans/19-rest-drift-and-typed-polish.md`` plus the closure
marker. Each gate is a structural assertion (file existence, regex
match, grep) — no live LLM, no network, no spawned servers.

Gate map
--------
 1   T1.a  plan doc ``## T1 audit findings`` section + ≥3 verdict rows
 2   T1.b  audit table includes ``/api/upload`` row marked DRIFT
 3   T2.a  UploadResult narrowed to ``{patch_id: string}`` only
 4   T2.b  drop-zone.tsx no longer writes ``res.domain`` (non-comment)
 5   T2.c  app-shell.tsx no longer writes ``res.domain`` (non-comment)
 6   T2.d  test_endpoint_upload_shape.py pins UploadResponse field set
 7   T3.a  source-row.tsx ``cost > 0`` suppression pattern present
 8   T3.b  inbox-store.ts breadcrumb references Plan 19 T3 resolution
 9   T4.1  tools.ts recent() return type widened with ``limit_used``
10   T4.2  tools.ts proposeNote() return type includes ``status``
11   T4.3  tools.ts listPendingPatches() return type includes ``count``
12   T4.4  tools.ts ConfigSetData = {status,key,value,persisted,note}
            + 7 downstream configSet wrappers return ConfigSetData
13   T4 pins — 4 Python key-set pin test files exist
14   T5.a  step-pick-folder.tsx ``planToFiles`` accepts
            ``readonly BulkImportPlannedItem[]``
15   T5.b  step-pick-folder.tsx no ``as unknown as Array<Record...>``
            cast at the planToFiles call site
16   T6    closure — tasks/todo.md row 19 ✅ + lessons.md Plan 19
            section

Closure (T6) is this script; final stdout line on a clean run is
``PLAN 19 DEMO OK``.

Per Plan 19 D7: gate count is not pinned. T1's audit returned 3
endpoint rows with 1 DRIFT; T4 bundled 4 sub-fixes under one gate
(plus a shared pins-existence gate). Total: 16 gates, mirroring
Plan 18's shape.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"
_BRAIN_CORE_TESTS = _REPO_ROOT / "packages" / "brain_core" / "tests"
_BRAIN_API_TESTS = _REPO_ROOT / "packages" / "brain_api" / "tests"
_TOOLS_TS = _BRAIN_WEB / "src" / "lib" / "api" / "tools.ts"
_UPLOAD_TS = _BRAIN_WEB / "src" / "lib" / "ingest" / "upload.ts"
_DROP_ZONE = _BRAIN_WEB / "src" / "components" / "inbox" / "drop-zone.tsx"
_APP_SHELL = _BRAIN_WEB / "src" / "components" / "shell" / "app-shell.tsx"
_SOURCE_ROW = _BRAIN_WEB / "src" / "components" / "inbox" / "source-row.tsx"
_INBOX_STORE = _BRAIN_WEB / "src" / "lib" / "state" / "inbox-store.ts"
_STEP_PICK = _BRAIN_WEB / "src" / "components" / "bulk" / "step-pick-folder.tsx"
_PLAN_DOC = _REPO_ROOT / "tasks" / "plans" / "19-rest-drift-and-typed-polish.md"


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
# Cache tools.ts read at module-load to avoid 8+ re-reads.
# ---------------------------------------------------------------------------


_TS_CACHE: str = ""


def _ts() -> str:
    global _TS_CACHE
    if not _TS_CACHE:
        _TS_CACHE = _read(_TOOLS_TS)
    return _TS_CACHE


# ---------------------------------------------------------------------------
# Gate 1 — T1.a: plan doc has non-empty ``## T1 audit findings`` section
# with a markdown table containing ≥3 verdict rows.
# ---------------------------------------------------------------------------


def _gate_1_t1_audit_findings_section() -> int:
    if rc := _exists("1", _PLAN_DOC):
        return rc
    plan = _read(_PLAN_DOC)
    section = re.search(
        r"^## T1 audit findings\s*\n(.+?)(?=^##\s|\Z)",
        plan,
        re.DOTALL | re.MULTILINE,
    )
    if section is None:
        return _fail("1", "plan doc missing `## T1 audit findings` section")
    body = section.group(1)
    # Plan 19 T1 table columns: endpoint | model | consumer | Verdict | Notes.
    # Each verdict cell is bolded in the audit table (e.g. ``| **OK** |``).
    # Match any row whose verdict cell carries an OK / MINOR / DRIFT literal
    # (bolded or unbolded) flanked by pipes.
    verdict_pat = re.compile(
        r"\|\s*(?:\*\*)?(OK|MINOR|DRIFT)(?:\*\*)?\s*\|",
    )
    verdict_rows = sum(
        1
        for line in body.splitlines()
        if line.strip().startswith("|") and verdict_pat.search(line)
    )
    if verdict_rows < 3:
        return _fail("1", f"T1 audit table has only {verdict_rows} verdict rows (expected >=3)")
    _gate(f"1 — T1.a audit findings: {verdict_rows} verdict rows recorded (3 REST endpoints)")
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T1.b: audit table includes /api/upload row marked DRIFT
# ---------------------------------------------------------------------------


def _gate_2_t1_upload_drift_row() -> int:
    plan = _read(_PLAN_DOC)
    section = re.search(
        r"^## T1 audit findings\s*\n(.+?)(?=^##\s|\Z)",
        plan,
        re.DOTALL | re.MULTILINE,
    )
    if section is None:
        return _fail("2", "plan doc missing `## T1 audit findings` section")
    body = section.group(1)
    # Find an /api/upload row with DRIFT verdict. The verdict cell can be
    # bolded or unbolded; require the row line to start with ``|`` and
    # contain both ``/api/upload`` and a DRIFT-verdict cell.
    upload_row = None
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if "/api/upload" not in s:
            continue
        if re.search(r"\|\s*(?:\*\*)?DRIFT(?:\*\*)?\s*\|", s):
            upload_row = s
            break
    if upload_row is None:
        return _fail("2", "T1 audit table missing `/api/upload` row marked DRIFT")
    _gate("2 — T1.b /api/upload row marked DRIFT in audit table")
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T2.a: UploadResult narrowed to {patch_id: string} only
# ---------------------------------------------------------------------------


def _gate_3_t2_upload_result_narrow() -> int:
    if rc := _exists("3", _UPLOAD_TS):
        return rc
    text = _read(_UPLOAD_TS)
    m = re.search(r"export\s+interface\s+UploadResult\s*\{([^}]+)\}", text)
    if m is None:
        return _fail("3", "upload.ts no longer declares an exported UploadResult interface")
    body = m.group(1)
    keys = set(re.findall(r"^\s*(\w+)\s*[?:]", body, re.MULTILINE))
    if keys != {"patch_id"}:
        return _fail("3", f"UploadResult has unexpected keys: {sorted(keys)} (expected {{patch_id}})")
    _gate("3 — T2.a UploadResult: narrowed to {patch_id}")
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T2.b: drop-zone.tsx does NOT write ``res.domain`` (in non-comment code)
# ---------------------------------------------------------------------------


def _gate_4_t2_drop_zone_no_res_domain() -> int:
    if rc := _exists("4", _DROP_ZONE):
        return rc
    code = _strip_comments_ts(_read(_DROP_ZONE))
    if re.search(r"\bres\.domain\b", code):
        return _fail("4", "drop-zone.tsx still has `res.domain` read in non-comment code")
    _gate("4 — T2.b drop-zone.tsx: no `res.domain` write (consumer fix landed)")
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T2.c: app-shell.tsx does NOT write ``res.domain`` (in non-comment code)
# ---------------------------------------------------------------------------


def _gate_5_t2_app_shell_no_res_domain() -> int:
    if rc := _exists("5", _APP_SHELL):
        return rc
    code = _strip_comments_ts(_read(_APP_SHELL))
    if re.search(r"\bres\.domain\b", code):
        return _fail("5", "app-shell.tsx still has `res.domain` read in non-comment code")
    _gate("5 — T2.c app-shell.tsx: no `res.domain` write (consumer fix landed)")
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T2.d: test_endpoint_upload_shape.py pins UploadResponse field set
# ---------------------------------------------------------------------------


def _gate_6_t2_upload_pin_test() -> int:
    pin_path = _BRAIN_API_TESTS / "test_endpoint_upload_shape.py"
    if rc := _exists("6", pin_path):
        return rc
    text = _read(pin_path)
    # The pin body asserts `set(UploadResponse.model_fields.keys()) == {"patch_id"}`.
    if "UploadResponse.model_fields" not in text:
        return _fail("6", "test_endpoint_upload_shape.py missing UploadResponse.model_fields check")
    if '"patch_id"' not in text:
        return _fail("6", "test_endpoint_upload_shape.py missing `\"patch_id\"` field literal")
    _gate("6 — T2.d test_endpoint_upload_shape.py: UploadResponse.model_fields == {patch_id} pin")
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T3.a: source-row.tsx contains the ``cost > 0`` suppression pattern
# ---------------------------------------------------------------------------


def _gate_7_t3_source_row_cost_suppression() -> int:
    if rc := _exists("7", _SOURCE_ROW):
        return rc
    text = _read(_SOURCE_ROW)
    # Match the strict ``source.cost > 0`` form (defensive over loose-truthy).
    if not re.search(r"source\.cost\s*>\s*0", text):
        return _fail("7", "source-row.tsx missing `source.cost > 0` suppression pattern")
    _gate("7 — T3.a source-row.tsx: `source.cost > 0` suppression pattern present")
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T3.b: inbox-store.ts breadcrumb updated to reference Plan 19 T3 resolution
# ---------------------------------------------------------------------------


def _gate_8_t3_inbox_store_breadcrumb() -> int:
    if rc := _exists("8", _INBOX_STORE):
        return rc
    text = _read(_INBOX_STORE)
    if "Plan 19 T3" not in text:
        return _fail("8", "inbox-store.ts breadcrumb missing `Plan 19 T3` reference")
    # The "Plan 19 candidate" wording should be gone — it's been resolved.
    if "Plan 19 candidate" in text:
        return _fail("8", "inbox-store.ts still has `Plan 19 candidate` pending wording")
    _gate("8 — T3.b inbox-store.ts breadcrumb: references Plan 19 T3 resolution")
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T4.1: tools.ts recent() return type widened with ``limit_used``
# ---------------------------------------------------------------------------


def _gate_9_t4_1_recent_limit_used() -> int:
    ts = _ts()
    # Find the `export const recent` declaration and confirm `limit_used`
    # appears within ~10 lines of the declaration (the return-type body).
    lines = ts.splitlines()
    found_idx = None
    for idx, line in enumerate(lines):
        if re.match(r"\s*export\s+const\s+recent\s*=", line):
            found_idx = idx
            break
    if found_idx is None:
        return _fail("9", "tools.ts missing `export const recent` declaration")
    window = "\n".join(lines[found_idx : found_idx + 10])
    if not re.search(r"limit_used\s*:\s*number", window):
        return _fail("9", "tools.ts recent() return type missing `limit_used: number`")
    if "items" not in window:
        return _fail("9", "tools.ts recent() return type missing `items` field")
    _gate("9 — T4.1 recent(): TS widened to {items, limit_used}")
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T4.2: tools.ts proposeNote() return type includes ``status``
# ---------------------------------------------------------------------------


def _gate_10_t4_2_propose_note_status() -> int:
    ts = _ts()
    lines = ts.splitlines()
    found_idx = None
    for idx, line in enumerate(lines):
        if re.match(r"\s*export\s+const\s+proposeNote\s*=", line):
            found_idx = idx
            break
    if found_idx is None:
        return _fail("10", "tools.ts missing `export const proposeNote` declaration")
    window = "\n".join(lines[found_idx : found_idx + 15])
    if not re.search(r"status\s*:\s*string", window):
        return _fail("10", "tools.ts proposeNote() return type missing `status: string`")
    if "patch_id" not in window or "target_path" not in window:
        return _fail("10", "tools.ts proposeNote() return type missing patch_id/target_path")
    _gate("10 — T4.2 proposeNote(): TS widened with `status` field")
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T4.3: tools.ts listPendingPatches() return type includes ``count``
# ---------------------------------------------------------------------------


def _gate_11_t4_3_list_pending_count() -> int:
    ts = _ts()
    lines = ts.splitlines()
    found_idx = None
    for idx, line in enumerate(lines):
        if re.match(r"\s*export\s+const\s+listPendingPatches\s*=", line):
            found_idx = idx
            break
    if found_idx is None:
        return _fail("11", "tools.ts missing `export const listPendingPatches` declaration")
    window = "\n".join(lines[found_idx : found_idx + 10])
    if not re.search(r"count\s*:\s*number", window):
        return _fail("11", "tools.ts listPendingPatches() return type missing `count: number`")
    if "patches" not in window:
        return _fail("11", "tools.ts listPendingPatches() return type missing `patches`")
    _gate("11 — T4.3 listPendingPatches(): TS widened to {count, patches}")
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T4.4: tools.ts ConfigSetData = {status,key,value,persisted,note};
# all 7 downstream configSet wrappers return Promise<ToolResponse<ConfigSetData>>.
# ---------------------------------------------------------------------------


_DOWNSTREAM_CONFIGSET_WRAPPERS = (
    "setDomainOverride",
    "setPrivacyRailed",
    "setDomainBudget",
    "setDomainRateLimit",
    "setDomainAutonomy",
    "setActiveDomain",
    "setCrossDomainWarningAcknowledged",
)


def _gate_12_t4_4_config_set_data_shape() -> int:
    ts = _ts()
    # ConfigSetData interface must declare exactly {status, key, value, persisted, note}.
    iface = re.search(
        r"export\s+interface\s+ConfigSetData\s*\{([^}]+)\}",
        ts,
    )
    if iface is None:
        return _fail("12", "tools.ts missing `export interface ConfigSetData`")
    iface_body = iface.group(1)
    keys = set(re.findall(r"^\s*(\w+)\s*[?:]", iface_body, re.MULTILINE))
    expected = {"status", "key", "value", "persisted", "note"}
    if keys != expected:
        return _fail(
            "12",
            f"ConfigSetData has unexpected keys: {sorted(keys)} (expected {sorted(expected)})",
        )
    # Each configSet-routed wrapper must declare
    # ``Promise<ToolResponse<ConfigSetData>>`` within ~10 lines of its
    # ``export const <name> =`` line. The root wrapper ``configSet`` plus
    # the 7 downstream helpers.
    ts_lines = ts.splitlines()
    for wrapper in ("configSet", *_DOWNSTREAM_CONFIGSET_WRAPPERS):
        found_idx = None
        for idx, line in enumerate(ts_lines):
            if re.match(rf"\s*export\s+const\s+{wrapper}\s*=", line):
                found_idx = idx
                break
        if found_idx is None:
            return _fail("12", f"tools.ts missing `export const {wrapper}` declaration")
        window = "\n".join(ts_lines[found_idx : found_idx + 10])
        if "Promise<ToolResponse<ConfigSetData>>" not in window:
            return _fail(
                "12",
                f"wrapper `{wrapper}` not declared as Promise<ToolResponse<ConfigSetData>>",
            )
    _gate(
        "12 — T4.4 ConfigSetData {status,key,value,persisted,note}; "
        "configSet + 7 downstream wrappers all return ToolResponse<ConfigSetData>"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T4 pins: 4 Python key-set pin test files exist
# ---------------------------------------------------------------------------


_T4_PIN_FILES = (
    "test_recent_outer_shape_pin.py",
    "test_propose_note_data_shape_pin.py",
    "test_list_pending_patches_outer_shape_pin.py",
    "test_config_set_data_shape_pin.py",
)


def _gate_13_t4_pin_files_exist() -> int:
    tools_dir = _BRAIN_CORE_TESTS / "tools"
    missing: list[str] = []
    for fname in _T4_PIN_FILES:
        path = tools_dir / fname
        if not path.is_file():
            missing.append(fname)
            continue
        # Each pin file must contain at least one strict key-set equality
        # against ``result.data.keys()``.
        body = _read(path)
        if "result.data.keys()" not in body and "data.keys()" not in body:
            return _fail("13", f"{fname} missing `data.keys()` strict equality assertion")
    if missing:
        return _fail("13", f"missing T4 pin test files: {missing}")
    _gate("13 — T4 pins: 4 Python key-set pin test files exist with strict `data.keys()` asserts")
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T5.a: step-pick-folder.tsx planToFiles signature is
# ``readonly BulkImportPlannedItem[]``
# ---------------------------------------------------------------------------


def _gate_14_t5_plan_to_files_signature() -> int:
    if rc := _exists("14", _STEP_PICK):
        return rc
    text = _read(_STEP_PICK)
    if not re.search(
        r"function\s+planToFiles\s*\(\s*plan\s*:\s*readonly\s+BulkImportPlannedItem\[\]",
        text,
    ):
        return _fail(
            "14",
            "step-pick-folder.tsx planToFiles signature not `readonly BulkImportPlannedItem[]`",
        )
    _gate("14 — T5.a planToFiles: signature tightened to `readonly BulkImportPlannedItem[]`")
    return 0


# ---------------------------------------------------------------------------
# Gate 15 — T5.b: no `as unknown as Array<Record<string, unknown>>` cast at
# planToFiles call site in step-pick-folder.tsx
# ---------------------------------------------------------------------------


def _gate_15_t5_no_cast_at_call_site() -> int:
    text = _read(_STEP_PICK)
    code = _strip_comments_ts(text)
    if re.search(r"as\s+unknown\s+as\s+Array<Record<string,\s*unknown>>", code):
        return _fail(
            "15",
            "step-pick-folder.tsx still has `as unknown as Array<Record<string, unknown>>` cast",
        )
    _gate("15 — T5.b step-pick-folder.tsx: no widening cast at planToFiles call site")
    return 0


# ---------------------------------------------------------------------------
# Gate 16 — T6: closure (todo.md row 19 ✅ + lessons.md Plan 19 section)
# ---------------------------------------------------------------------------


def _gate_16_t6_closure() -> int:
    todo = _REPO_ROOT / "tasks" / "todo.md"
    if rc := _exists("16", todo):
        return rc
    todo_text = _read(todo)
    if re.search(r"\|\s*19\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail("16", "tasks/todo.md row 19 not marked `✅ Complete`")
    lessons = _REPO_ROOT / "tasks" / "lessons.md"
    if rc := _exists("16", lessons):
        return rc
    lessons_text = _read(lessons)
    if "## Plan 19" not in lessons_text:
        return _fail("16", "tasks/lessons.md missing `## Plan 19` closure section")
    _gate("16 — T6 closure: tasks/todo.md row 19 ✅; tasks/lessons.md has Plan 19 section")
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t1_audit_findings_section,
    _gate_2_t1_upload_drift_row,
    _gate_3_t2_upload_result_narrow,
    _gate_4_t2_drop_zone_no_res_domain,
    _gate_5_t2_app_shell_no_res_domain,
    _gate_6_t2_upload_pin_test,
    _gate_7_t3_source_row_cost_suppression,
    _gate_8_t3_inbox_store_breadcrumb,
    _gate_9_t4_1_recent_limit_used,
    _gate_10_t4_2_propose_note_status,
    _gate_11_t4_3_list_pending_count,
    _gate_12_t4_4_config_set_data_shape,
    _gate_13_t4_pin_files_exist,
    _gate_14_t5_plan_to_files_signature,
    _gate_15_t5_no_cast_at_call_site,
    _gate_16_t6_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 19 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
