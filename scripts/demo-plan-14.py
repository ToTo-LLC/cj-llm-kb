"""Plan 14 end-to-end demo — hardening + CI restoration.

Walks the twelve gates locked in the Plan 14 demo-gate header (D10):

    1. SPAStaticFiles WS-scope guard (B1): build a fake WebSocket scope
       dict; pass to ``SPAStaticFiles.__call__``; assert the response is
       a 404 (NOT the parent ``StaticFiles.__call__`` AssertionError).
       Production-shape test mirroring lesson 343.
    2. ``request_id`` 500-envelope pin (B2): run
       ``packages/brain_api/tests/test_envelope_shape_parity.py::
       test_route_500_envelope_shape_includes_request_id``; assert
       exit code 0 — the new pin asserts ``'request_id' in
       body['detail']`` AND ``len(...) > 0`` (D4 wording-shape, not
       UUID-shape).
    3. a11y populated chat-thread w/ prose (C2.a subset): run the
       ``patch-card edit (edit-approve) dialog`` test in
       ``a11y-populated.spec.ts`` — opens the patch-card edit modal
       which renders the seeded note's prose body (the canonical
       chat-thread-with-prose surface live in the app today). 0
       color-contrast violations on the rendered ``.prose`` content
       (Task 5 ``--tt-cyan`` route validates here).
    4. a11y populated dialogs (C2.a): run the remaining 5 dialog
       cases in ``a11y-populated.spec.ts`` (rename-domain, delete-
       domain, fork-thread, backup-restore, cross-domain modal); 0
       violations each.
    5. a11y populated menus (C2.b): run the ``topbar scope picker
       dropdown`` + ``Settings tabs (all 8)`` cases in
       ``a11y-populated.spec.ts``; 0 violations.
    6. a11y populated overlays (C2.b): run the ``search overlay``,
       ``drop-zone overlay``, and ``toast notifications`` cases in
       ``a11y-populated.spec.ts``; 0 violations.
    7. ``.prose a`` dark-mode contrast (C3): assert
       ``apps/brain_web/src/styles/tokens.css`` routes ``.prose a``
       through ``var(--tt-cyan)`` (single source of truth) and that
       the hardcoded ``[data-theme="dark"] .prose a:hover`` rule has
       been removed from ``brand-skin.css`` (D7).
    8. ingest-drag-drop spec stability (D8): run
       ``apps/brain_web/tests/e2e/ingest-drag-drop.spec.ts`` with
       ``--repeat-each=5``; assert all 5 runs pass. The test-side
       ``waitForResponse`` arm closed the harness flake (the
       production race in ``inbox-store.loadRecent`` is documented
       for Plan 15).
    9. GitHub Actions workflow file shape (C1): parse
       ``.github/workflows/playwright.yml``; assert ``runs-on``
       matrix includes ``macos-14`` AND ``windows-2022``; assert the
       Mac leg includes a ``chflags`` step (lesson 341); assert the
       Windows leg uses ``shell: pwsh`` (sibling-step pattern, Task 8
       review).
   10. Full local Playwright suite (regression guard): run
       ``npx playwright test`` against the entire ``tests/e2e/``
       directory (32 tests across 11 spec files); assert exit 0.
   11. brain_api full pytest (regression guard): run ``pytest
       packages/brain_api -q``; assert exit 0 with no regressions
       vs the Plan 13 baseline (173 → ~178 in Plan 14).
   12. ``PLAN 14 DEMO OK`` sentinel.

Prints ``PLAN 14 DEMO OK`` on exit 0; non-zero on any gate failure.
Mirrors the Plan 11/12/13 demo-gate split: gates 1, 7, and 9 are
in-process Python; gates 2-6, 8, 10, 11 shell out to pytest /
Playwright with the canonical chflags + PYTHONPATH execution prefix
per lesson 341.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml
from brain_api.static_ui import SPAStaticFiles


def _gate(label: str) -> None:
    print(f"  ✓ Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  ✗ Gate {label}: {why}", file=sys.stderr)
    return 1


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_PATHS = (
    _REPO_ROOT / "packages" / "brain_core" / "src",
    _REPO_ROOT / "packages" / "brain_mcp" / "src",
    _REPO_ROOT / "packages" / "brain_api" / "src",
    _REPO_ROOT / "packages" / "brain_cli" / "src",
)
_PYTHONPATH = os.pathsep.join(str(p) for p in _SRC_PATHS)
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"


def _subprocess_env() -> dict[str, str]:
    """Mirror the canonical chflags + PYTHONPATH recipe (lesson 341)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _PYTHONPATH + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


def _run_subprocess(label: str, cmd: list[str], *, cwd: Path | None = None) -> int:
    """Run ``cmd``; return 0 on success, 1 on failure (printing tail of output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=_subprocess_env(),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return _fail(label, f"subprocess invocation failed: {exc!r}")
    if result.returncode != 0:
        tail = "\n".join(
            (result.stdout or "").splitlines()[-25:] + (result.stderr or "").splitlines()[-15:]
        )
        return _fail(
            label,
            f"exit code {result.returncode}; tail:\n{tail}",
        )
    return 0


# ---------------------------------------------------------------------------
# Gate 1 — SPAStaticFiles WS-scope guard (Task 1)
# ---------------------------------------------------------------------------


async def _gate_1_spa_static_ws_guard() -> int:
    """Production-shape WebSocket scope hits SPAStaticFiles.__call__.

    The latent bug Plan 13 Task 5 review M1 surfaced: ``SPAStaticFiles``
    inherits ``__call__`` from ``StaticFiles``, whose first line asserts
    ``scope["type"] == "http"``. Plan 14 Task 1 / D3 overrode ``__call__``
    to return a 404 ASGI response for non-http scopes. We construct a
    real ASGI WebSocket scope dict and capture the response messages
    sent through the ``send`` callable — exactly mirroring how a real
    Starlette WebSocket route would be invoked.
    """
    static_root = _REPO_ROOT / "apps" / "brain_web" / "out"
    if not static_root.exists():
        return _fail(
            "1",
            f"apps/brain_web/out/ does not exist at {static_root}; "
            "run `pnpm --filter brain_web build` first.",
        )

    spa = SPAStaticFiles(directory=str(static_root), html=True)

    sent_messages: list[dict[str, object]] = []

    async def send(message: dict[str, object]) -> None:
        sent_messages.append(message)

    async def receive() -> dict[str, object]:  # pragma: no cover — never fires
        return {"type": "websocket.connect"}

    ws_scope: dict[str, object] = {
        "type": "websocket",
        "path": "/ws/chat",
        "raw_path": b"/ws/chat",
        "query_string": b"",
        "headers": [],
        "scheme": "ws",
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 4317),
    }

    try:
        await spa(ws_scope, receive, send)
    except AssertionError as exc:
        return _fail(
            "1",
            "SPAStaticFiles.__call__ raised AssertionError on WebSocket "
            f"scope — Plan 14 Task 1 D3 override did not land: {exc!r}",
        )
    except Exception as exc:
        return _fail(
            "1",
            f"SPAStaticFiles.__call__ raised unexpected exception on WebSocket scope: {exc!r}",
        )

    # Assert at least one message was sent and that the http.response.start
    # message carries status 404. The Starlette PlainTextResponse splits
    # into a start frame + a body frame.
    # Starlette's PlainTextResponse on a WebSocket scope sends
    # ``websocket.http.response.start`` + ``websocket.http.response.body``
    # frames (the WS-shaped HTTP response shape from RFC 6455 close
    # negotiation). Match either ``http.response.start`` (plain HTTP) OR
    # ``websocket.http.response.start`` (WS reject-with-HTTP) — both are
    # valid 404 ASGI responses for a WS scope.
    start_frames = [
        m
        for m in sent_messages
        if m.get("type") in {"http.response.start", "websocket.http.response.start"}
    ]
    if not start_frames:
        return _fail(
            "1",
            "SPAStaticFiles.__call__ on WS scope sent no response "
            f"start message; got: {sent_messages!r}",
        )
    status = start_frames[0].get("status")
    if status != 404:
        return _fail(
            "1",
            f"SPAStaticFiles.__call__ on WS scope returned status {status!r}; "
            "expected 404 (D3 override).",
        )

    _gate(
        "1 — SPAStaticFiles non-http scope guard: WebSocket scope returns "
        "404 (NOT the parent StaticFiles AssertionError); D3 override landed"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — request_id 500-envelope pin (Task 2)
# ---------------------------------------------------------------------------


def _gate_2_request_id_envelope_pin() -> int:
    """Run the request_id pin sub-test."""
    rc = _run_subprocess(
        "2",
        [
            str(_VENV_PYTHON),
            "-m",
            "pytest",
            "packages/brain_api/tests/test_envelope_shape_parity.py::test_route_500_envelope_shape_includes_request_id",
            "-q",
        ],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return rc
    _gate(
        "2 — request_id pin in 500 envelope: 'request_id' in "
        "body['detail'] AND len > 0 (D4 wording-shape pin green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — a11y populated chat-thread w/ prose (C2.a subset)
# ---------------------------------------------------------------------------


def _gate_3_a11y_chat_thread_prose() -> int:
    """The patch-card edit dialog renders the seeded note's prose body —
    the canonical chat-thread-with-prose surface live in the app today
    (the Plan 14 D5 dispatch text framed this as the chat-thread-with-
    prose case; the patch-card-edit dialog IS where ``.prose`` markup
    renders user-visible body text in a populated state).
    """
    rc = _run_subprocess(
        "3",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/a11y-populated.spec.ts",
            "--grep",
            "patch-card edit",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "3 — a11y populated chat-thread w/ prose: patch-card edit dialog "
        "renders .prose body; 0 color-contrast violations (Task 5 --tt-cyan "
        "route validated through axe-core scan)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — a11y populated dialogs (C2.a)
# ---------------------------------------------------------------------------


def _gate_4_a11y_populated_dialogs() -> int:
    """Run the 5 remaining populated-dialog cases (rename-domain,
    delete-domain, fork-thread, backup-restore, cross-domain modal)."""
    rc = _run_subprocess(
        "4",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/a11y-populated.spec.ts",
            "--grep",
            "rename-domain|delete-domain|fork-thread|backup-restore|cross-domain modal",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "4 — a11y populated dialogs: rename-domain + delete-domain + "
        "fork-thread + backup-restore + cross-domain modal; "
        "0 violations across 5 dialogs (D5 / Task 3)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — a11y populated menus (C2.b)
# ---------------------------------------------------------------------------


def _gate_5_a11y_populated_menus() -> int:
    """Run the topbar-scope-picker + Settings-tabs-walk cases."""
    rc = _run_subprocess(
        "5",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/a11y-populated.spec.ts",
            "--grep",
            "topbar scope picker|Settings tabs",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "5 — a11y populated menus: topbar scope picker dropdown + "
        "Settings tabs walk (8 panels); 0 violations (D5 / Task 4)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — a11y populated overlays (C2.b)
# ---------------------------------------------------------------------------


def _gate_6_a11y_populated_overlays() -> int:
    """Run the search-overlay + drop-zone-overlay + toast cases."""
    rc = _run_subprocess(
        "6",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/a11y-populated.spec.ts",
            "--grep",
            "search overlay|drop-zone overlay|toast notifications",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "6 — a11y populated overlays: search overlay (⌘K) + drop-zone "
        "overlay + toast notifications; 0 violations (D5 / Task 4)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — `.prose a` routes through `var(--tt-cyan)` (C3)
# ---------------------------------------------------------------------------


_BRAND_SKIN_CSS = _REPO_ROOT / "apps" / "brain_web" / "src" / "styles" / "brand-skin.css"


def _gate_7_prose_a_tt_cyan() -> int:
    """Pin the single-source-of-truth ``.prose a`` rule + confirm the
    hardcoded ``[data-theme="dark"] .prose a:hover`` override has been
    removed (Plan 14 Task 5 / D7). The ``.prose a`` rule lives in
    ``brand-skin.css`` (Task 5 audit confirmed; the plan's
    ``tokens.css`` reference was speculative).
    """
    if not _BRAND_SKIN_CSS.exists():
        return _fail("7", f"brand-skin.css not found at {_BRAND_SKIN_CSS}")

    raw_skin = _BRAND_SKIN_CSS.read_text(encoding="utf-8")
    # Strip CSS block comments before matching — Plan 14 Task 5 left a
    # multi-line comment IN brand-skin.css that quotes the old
    # ``[data-theme="dark"] .prose a:hover { #E06A4A }`` rule (as a
    # justification for the cleanup). Without comment stripping the
    # ``bad_pattern`` regex matches inside the comment and false-
    # positives the gate.
    skin = re.sub(r"/\*.*?\*/", "", raw_skin, flags=re.DOTALL)

    # Match the ``.prose a`` rule body and assert it cites
    # ``var(--tt-cyan)`` for color (NOT ``var(--brand-ember)``
    # directly). Tolerant of the ``.prose a, .msg-body a`` selector
    # group (Task 5 lined them up to share the same color via the
    # token route).
    prose_a_pattern = re.compile(
        r"\.prose\s+a[^{]*\{[^}]*color\s*:\s*var\(\s*--tt-cyan\s*\)",
        re.MULTILINE,
    )
    if not prose_a_pattern.search(skin):
        return _fail(
            "7",
            ".prose a rule in brand-skin.css does NOT route through "
            "var(--tt-cyan); D7 single-source-of-truth refactor "
            "regressed.",
        )

    # The hardcoded dark-mode hover override should be gone (excluding
    # comments stripped above).
    bad_pattern = re.compile(
        r'\[data-theme="dark"\]\s+\.prose\s+a:hover\s*\{[^}]*#E06A4A',
        re.MULTILINE,
    )
    if bad_pattern.search(skin):
        return _fail(
            "7",
            'brand-skin.css still contains [data-theme="dark"] .prose '
            "a:hover with hardcoded #E06A4A; D7 cleanup regressed.",
        )

    _gate(
        "7 — .prose a routes through var(--tt-cyan) in brand-skin.css; "
        "hardcoded [data-theme='dark'] .prose a:hover #E06A4A removed "
        "(D7 single-source-of-truth)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — ingest-drag-drop spec stability (D8)
# ---------------------------------------------------------------------------


def _gate_8_ingest_drag_drop_stability() -> int:
    """Run ingest-drag-drop.spec.ts with repeat-each=5 — Task 6's
    test-side waitForResponse arm should make the spec deterministic
    in isolation. The production race in ``inbox-store.loadRecent`` is
    documented for Plan 15."""
    rc = _run_subprocess(
        "8",
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/ingest-drag-drop.spec.ts",
            "--repeat-each=5",
        ],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "8 — ingest-drag-drop spec stability: 5/5 runs pass with "
        "repeat-each=5 (D8 waitForResponse fix landed)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — GitHub Actions workflow file shape (C1)
# ---------------------------------------------------------------------------


_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "playwright.yml"


def _gate_9_workflow_file_shape() -> int:
    """Parse playwright.yml and assert the shape Plan 14 Tasks 7+8
    locked: matrix includes macos-14 + windows-2022; Mac leg has a
    chflags step; Windows leg uses ``shell: pwsh`` (sibling-step
    pattern from Task 8 review).
    """
    if not _WORKFLOW_PATH.exists():
        return _fail(
            "9",
            f"playwright.yml not found at {_WORKFLOW_PATH}",
        )
    try:
        wf = yaml.safe_load(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return _fail("9", f"playwright.yml YAML parse error: {exc!r}")

    jobs = wf.get("jobs") or {}
    if "e2e" not in jobs:
        return _fail("9", f"playwright.yml has no 'e2e' job; jobs: {list(jobs)}")
    e2e = jobs["e2e"]

    # Matrix entries
    matrix = (e2e.get("strategy") or {}).get("matrix") or {}
    os_list = matrix.get("os") or []
    for required in ("macos-14", "windows-2022"):
        if required not in os_list:
            return _fail(
                "9",
                f"playwright.yml matrix.os does NOT include {required!r}; got {os_list!r}",
            )

    # Steps inspection
    steps = e2e.get("steps") or []
    mac_chflags_found = False
    windows_pwsh_found = False
    for step in steps:
        if not isinstance(step, dict):
            continue
        run = step.get("run") or ""
        cond = step.get("if") or ""
        shell = step.get("shell") or ""
        if "macOS" in cond and "chflags" in run:
            mac_chflags_found = True
        if "Windows" in cond and shell == "pwsh":
            windows_pwsh_found = True

    if not mac_chflags_found:
        return _fail(
            "9",
            "playwright.yml has no Mac-conditioned step running chflags; "
            "lesson 341 recipe regressed.",
        )
    if not windows_pwsh_found:
        return _fail(
            "9",
            "playwright.yml has no Windows-conditioned step using "
            "shell: pwsh; sibling-step pattern (Task 8 review) regressed.",
        )

    _gate(
        "9 — GitHub Actions workflow file shape: matrix includes "
        "macos-14 + windows-2022; Mac leg has chflags step (lesson 341); "
        "Windows leg uses shell: pwsh (sibling-step pattern)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — Full local Playwright suite (regression guard)
# ---------------------------------------------------------------------------


def _gate_10_full_playwright() -> int:
    """Run the entire e2e suite — 32 tests across 11 files."""
    rc = _run_subprocess(
        "10",
        ["npx", "playwright", "test"],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        return rc
    _gate(
        "10 — Full local Playwright suite: all 32 tests across 11 spec "
        "files pass (regression guard)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — brain_api full pytest (regression guard)
# ---------------------------------------------------------------------------


def _gate_11_brain_api_full_pytest() -> int:
    """Run packages/brain_api full pytest. Plan 13 baseline was 173
    passed; Plan 14 should be ~178 (Task 1 ws_guard + Task 2
    request_id pin sub-test add new cases)."""
    rc = _run_subprocess(
        "11",
        [str(_VENV_PYTHON), "-m", "pytest", "packages/brain_api", "-q"],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return rc
    _gate(
        "11 — brain_api full pytest: green (Plan 14 ~178 passed; "
        "+5 from Plan 13 baseline of 173 = Task 1 ws_guard + Task 2 "
        "request_id pin sub-test)"
    )
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def _run() -> int:
    rc = await _gate_1_spa_static_ws_guard()
    if rc != 0:
        return rc

    rc = _gate_2_request_id_envelope_pin()
    if rc != 0:
        return rc

    rc = _gate_3_a11y_chat_thread_prose()
    if rc != 0:
        return rc

    rc = _gate_4_a11y_populated_dialogs()
    if rc != 0:
        return rc

    rc = _gate_5_a11y_populated_menus()
    if rc != 0:
        return rc

    rc = _gate_6_a11y_populated_overlays()
    if rc != 0:
        return rc

    rc = _gate_7_prose_a_tt_cyan()
    if rc != 0:
        return rc

    rc = _gate_8_ingest_drag_drop_stability()
    if rc != 0:
        return rc

    rc = _gate_9_workflow_file_shape()
    if rc != 0:
        return rc

    rc = _gate_10_full_playwright()
    if rc != 0:
        return rc

    rc = _gate_11_brain_api_full_pytest()
    if rc != 0:
        return rc

    print()
    print("PLAN 14 DEMO OK")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
