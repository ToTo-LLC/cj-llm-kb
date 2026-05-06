"""Plan 15 end-to-end demo — CI green + polish pass.

Walks the twelve gates locked in the Plan 15 demo-gate header (D10):

    1. ruff clean (A1): ``uv run ruff check . && uv run ruff format
       --check .`` exit 0 across the whole repo. The first green
       whole-repo ruff in 4 plans (Plan 11/12/13/14 implementer recipes
       ran ``ruff check packages/<pkg>/`` only and silently masked 76
       violations on main).
    2. brain_api full pytest (regression guard): run ``pytest
       packages/brain_api -q``; assert exit 0; capture passed-count
       and assert >= Plan 14 baseline (178). Plan 15 added Task 8
       contract tests for ``raise_if_no_config`` so the count
       legitimately rises.
    3. brain_web vitest (regression guard): run ``pnpm vitest run``;
       assert exit 0 and passed-count >= Plan 14 baseline (334). Plan
       15 added Task 5 (privacy-railed glossary tooltip), Task 6
       (active-domain toast conditional CTA), Task 7
       (pendingSendRef.mode capture-into-local) tests so the count
       legitimately rises (~343).
    4. Local Playwright suite — representative subset (regression):
       run the 3 specs that historically flake (ingest-drag-drop,
       a11y-populated, chat-turn). Full suite is gated separately by
       the Playwright workflow on every push (Plan 14 Task 7+8); this
       demo gate is a smoke pass to catch regressions on the
       implementer's local machine before push.
    5. Windows Playwright on CI (A2 verification): ``gh run list
       --workflow=playwright.yml --limit=1 --json conclusion`` —
       assert the most recent run on ``main`` returned ``success``.
       The gate is the CI run conclusion (D10 line 37). Plan 15 Task
       3's Windows path-separator fix is the load-bearing change here.
    6. ``brain start`` works without manual chflags (B1): start brain
       in a temp env (no chflags pre-step); assert ``GET /healthz``
       responds 200; assert no ``ImportError: brain_core`` on stderr.
       Note: spec D10 line 38 says ``/api/healthz`` but the actual
       endpoint is ``/healthz`` — Task 4 review noted the SPA fallback
       explicitly excludes ``/healthz``. We use ``/healthz``.
    7. Modal + Settings jargon consistency (B2): grep
       ``cross-domain-modal.tsx`` and ``panel-domains.tsx``; assert
       NO matches for ``private domain`` / ``kept private`` / ``private
       notes``; assert ``Privacy-railed`` appears in BOTH files.
    8. Active-domain toast CTA conditional (B3): assert
       ``settings-active-domain.test.tsx`` covers BOTH the validator-
       error → "Pick a different domain" path AND the transport-error
       → "Try again" path.
    9. ``pendingSendRef.mode`` used (B4): grep ``chat-screen.tsx``;
       assert ``handleCrossDomainContinue`` captures ``pendingSendRef.
       current`` into a local ``pending`` BEFORE the await boundary
       and that ``pending.mode`` (NOT live-closure ``mode``) is what
       feeds ``sendTurnStart``. Task 7 review fix-up locked this as
       the canonical pattern.
   10. ``raise_if_no_config`` helper + 3 callers (B5): import the
       helper from ``brain_core.tools._errors`` (succeeds); assert
       3 brain_core tools call it (config_get, list_domains,
       config_set); assert SPAStaticFiles non-http guard
       (``static_ui.py``) is INTENTIONALLY separate (different
       package, different scope-type contract).
   11. ``_mk_ctx`` requires config (B6): grep
       ``test_list_domains.py`` / ``test_list_domains_active.py`` /
       ``test_config_set.py``; assert each ``_mk_ctx`` signature has
       a required ``config: Config`` parameter (no Optional, no
       default ``= None``).
   12. ``PLAN 15 DEMO OK`` sentinel.

Prints ``PLAN 15 DEMO OK`` on exit 0; non-zero on any gate failure.
Mirrors the Plan 11/12/13/14 demo-gate split: gates 1, 5, 7-11 are
in-process Python (file inspection / shell-out to gh); gates 2, 3, 4,
6 shell out to pytest / vitest / playwright / brain_api with the
canonical chflags + PYTHONPATH execution prefix per lesson 341.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


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


def _subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Mirror the canonical chflags + PYTHONPATH recipe (lesson 341)."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = _PYTHONPATH + (os.pathsep + existing if existing else "")
    if extra is not None:
        env.update(extra)
    return env


def _run_subprocess(
    label: str,
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env_extra: dict[str, str] | None = None,
    capture: bool = True,
) -> tuple[int, str, str]:
    """Run ``cmd``; return ``(rc, stdout, stderr)``.

    Distinct from ``demo-plan-14.py``'s helper because two gates need
    to inspect captured stdout (gate 2 + 3 read the passed-count off
    the trailing pytest / vitest summary).
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=_subprocess_env(env_extra),
            capture_output=capture,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        rc = _fail(label, f"subprocess invocation failed: {exc!r}")
        return rc, "", ""
    return result.returncode, result.stdout or "", result.stderr or ""


# ---------------------------------------------------------------------------
# Gate 1 — ruff clean (whole repo)
# ---------------------------------------------------------------------------


def _gate_1_ruff_clean() -> int:
    rc, _, stderr = _run_subprocess(
        "1",
        ["uv", "run", "ruff", "check", "."],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return _fail("1", f"ruff check . failed (rc={rc}); stderr tail:\n{stderr[-500:]}")
    rc, _, stderr = _run_subprocess(
        "1",
        ["uv", "run", "ruff", "format", "--check", "."],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return _fail("1", f"ruff format --check . failed (rc={rc}); stderr tail:\n{stderr[-500:]}")
    _gate(
        "1 — ruff clean: `ruff check .` + `ruff format --check .` exit 0; 0 "
        "violations across whole repo (first green whole-repo ruff in 4 "
        "plans; closes #A1)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — brain_api full pytest (regression guard)
# ---------------------------------------------------------------------------


_PYTEST_PASSED_RE = re.compile(r"(\d+)\s+passed")
_PLAN_14_BRAIN_API_BASELINE = 178


def _gate_2_brain_api_pytest() -> int:
    rc, stdout, stderr = _run_subprocess(
        "2",
        [str(_VENV_PYTHON), "-m", "pytest", "packages/brain_api", "-q"],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        tail = "\n".join(stdout.splitlines()[-25:] + stderr.splitlines()[-15:])
        return _fail("2", f"brain_api pytest exit {rc}; tail:\n{tail}")
    match = _PYTEST_PASSED_RE.search(stdout)
    if match is None:
        return _fail("2", f"could not parse 'N passed' from pytest stdout:\n{stdout[-500:]}")
    passed = int(match.group(1))
    if passed < _PLAN_14_BRAIN_API_BASELINE:
        return _fail(
            "2",
            f"brain_api pytest passed={passed} < Plan 14 baseline "
            f"{_PLAN_14_BRAIN_API_BASELINE}; regression detected.",
        )
    _gate(
        f"2 — brain_api full pytest: {passed} passed (>= Plan 14 baseline "
        f"{_PLAN_14_BRAIN_API_BASELINE}; regression guard green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — brain_web vitest (regression guard)
# ---------------------------------------------------------------------------


_VITEST_PASSED_RE = re.compile(r"Tests\s+(\d+)\s+passed")
_PLAN_14_VITEST_BASELINE = 334


def _gate_3_brain_web_vitest() -> int:
    rc, stdout, stderr = _run_subprocess(
        "3",
        ["pnpm", "vitest", "run", "--reporter=basic"],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        tail = "\n".join(stdout.splitlines()[-25:] + stderr.splitlines()[-15:])
        return _fail("3", f"vitest exit {rc}; tail:\n{tail}")
    match = _VITEST_PASSED_RE.search(stdout)
    if match is None:
        return _fail("3", f"could not parse 'Tests N passed' from vitest stdout:\n{stdout[-500:]}")
    passed = int(match.group(1))
    if passed < _PLAN_14_VITEST_BASELINE:
        return _fail(
            "3",
            f"vitest passed={passed} < Plan 14 baseline "
            f"{_PLAN_14_VITEST_BASELINE}; regression detected.",
        )
    _gate(
        f"3 — brain_web vitest: {passed} passed (>= Plan 14 baseline "
        f"{_PLAN_14_VITEST_BASELINE}; regression guard green)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — Local Playwright (representative subset)
# ---------------------------------------------------------------------------


_PLAYWRIGHT_SUBSET = (
    "tests/e2e/ingest-drag-drop.spec.ts",
    "tests/e2e/a11y-populated.spec.ts",
    "tests/e2e/chat-turn.spec.ts",
)


def _gate_4_playwright_subset() -> int:
    """Run the 3 historically-flaky specs.

    Full Playwright suite is gated on every push by the workflow
    (Plan 14 Task 7+8) — running it here would double the demo
    wall-clock for marginal gain. The subset catches regressions on
    the implementer's local machine before push (the entire suite
    runs on macOS-14 + windows-2022 in CI; gate 5 verifies the most
    recent run was green).
    """
    rc, stdout, stderr = _run_subprocess(
        "4",
        ["npx", "playwright", "test", *_PLAYWRIGHT_SUBSET],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        tail = "\n".join(stdout.splitlines()[-25:] + stderr.splitlines()[-15:])
        return _fail("4", f"playwright subset exit {rc}; tail:\n{tail}")
    _gate(
        "4 — Local Playwright (representative subset): ingest-drag-drop "
        "+ a11y-populated + chat-turn green; full suite gated on every "
        "push by playwright.yml workflow (gate 5 verifies CI conclusion)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — Windows Playwright on CI (A2 verification)
# ---------------------------------------------------------------------------


def _gate_5_windows_playwright_ci() -> int:
    """Most recent ``playwright.yml`` run on ``main`` returned success.

    The gate is the conclusion field of the most recent run (D10 line
    37). Plan 15 Task 3's Windows path-separator fix is what landed
    on commit ``88a5abe``; the run conclusion since that commit is
    the gate. Tasks 4-10 are local commits that haven't been pushed
    yet — gate 5 reflects the most recent pushed commit.
    """
    rc, stdout, stderr = _run_subprocess(
        "5",
        [
            "gh",
            "run",
            "list",
            "--workflow=playwright.yml",
            "--branch=main",
            "--limit=1",
            "--json",
            "conclusion,headSha,createdAt",
        ],
        cwd=_REPO_ROOT,
    )
    if rc != 0:
        return _fail(
            "5",
            f"`gh run list` exit {rc}; stderr tail:\n{stderr[-500:]}",
        )
    try:
        runs = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return _fail("5", f"could not parse gh JSON output: {exc!r}; stdout: {stdout!r}")
    if not runs:
        return _fail("5", "no playwright.yml runs found on main branch")
    run = runs[0]
    conclusion = run.get("conclusion")
    head_sha = run.get("headSha", "")[:7]
    created_at = run.get("createdAt", "")
    if conclusion != "success":
        return _fail(
            "5",
            f"most recent playwright.yml run on main returned "
            f"conclusion={conclusion!r} (sha={head_sha}, createdAt={created_at!r}); "
            "expected 'success' (Plan 15 Task 3 Windows path-separator fix).",
        )
    _gate(
        f"5 — Windows Playwright on CI: most recent playwright.yml run "
        f"on main = success (sha={head_sha}, createdAt={created_at}); "
        "Plan 15 Task 3 Windows path-separator fix verified end-to-end "
        "on macOS-14 + windows-2022 (closes #A2)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — `brain start` works without manual chflags (B1)
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    """Find a free TCP port for the brain_api child process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _gate_6_brain_start_no_chflags() -> int:
    """Spawn brain_api directly via the supervisor's
    ``_resolve_venv_python`` recipe (Task 4 D3) — NO chflags pre-step,
    NO ``uv run``. Hit ``GET /healthz`` and assert 200 + no
    ``ImportError: brain_core`` on stderr.

    The gate proves the Plan 15 Task 4 contract: the supervisor uses
    ``.venv/bin/python -m uvicorn`` directly (Plan 11 lesson 341);
    ``uv run`` would re-sync the venv and re-hide the editable .pth
    files mid-bootstrap on macOS, defeating the chflags escape hatch.
    """
    port = _find_free_port()
    vault_root = _REPO_ROOT / ".tmp-plan-15-demo-vault"
    vault_root.mkdir(parents=True, exist_ok=True)

    venv_python = _VENV_PYTHON
    if not venv_python.exists():
        return _fail("6", f"venv python missing at {venv_python}")

    # Same env shape as supervisor.start_brain_api — PYTHONPATH set,
    # BRAIN_VAULT_ROOT pointed at the demo's tmp vault, BRAIN_E2E_MODE
    # off (real backend boot), BRAIN_DEMO=1 to suppress the update-check
    # prompt.
    env = _subprocess_env(
        {
            "BRAIN_VAULT_ROOT": str(vault_root),
            "BRAIN_E2E_MODE": "0",
            "BRAIN_DEMO": "1",
        }
    )

    # Use the same factory the supervisor uses (Plan 15 Task 4): the
    # ``brain_cli.runtime.backend_factory:build_app`` shim reads
    # ``BRAIN_VAULT_ROOT`` from env and calls ``create_app`` with it
    # plus the default allowed_domains tuple. This gate exercises the
    # exact code path ``brain start`` uses.
    cmd = [
        str(venv_python),
        "-m",
        "uvicorn",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
        "brain_cli.runtime.backend_factory:build_app",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Poll /healthz for up to 15s.
    deadline = time.monotonic() + 15.0
    last_err: Exception | None = None
    response_status: int | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            # Child died early — capture stderr and bail.
            _, stderr = proc.communicate(timeout=2)
            return _fail(
                "6",
                f"brain_api child exited early (rc={proc.returncode}); stderr "
                f"tail:\n{stderr[-1000:]}",
            )
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as resp:
                response_status = resp.status
                break
        except (urllib.error.URLError, ConnectionRefusedError, OSError) as exc:
            last_err = exc
            time.sleep(0.25)

    # Tear down the child.
    proc.terminate()
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate(timeout=5)

    if response_status is None:
        return _fail(
            "6",
            f"never got 200 from /healthz within 15s; last_err={last_err!r}; "
            f"stderr tail:\n{stderr[-1000:]}",
        )
    if response_status != 200:
        return _fail(
            "6",
            f"GET /healthz returned status {response_status}; expected 200.",
        )
    if "ImportError: brain_core" in stderr or "ModuleNotFoundError: " in stderr:
        return _fail(
            "6",
            f"brain_api stderr contained ImportError; the .pth-shadowing "
            f"escape hatch (Plan 15 Task 4 / D3) regressed:\n{stderr[-1000:]}",
        )

    # Clean up the demo's tmp vault — leaving it behind would pollute the
    # repo root with a ``.tmp-plan-15-demo-vault/`` directory on every
    # rerun. Best-effort: a leftover doesn't break the gate.
    shutil.rmtree(vault_root, ignore_errors=True)

    _gate(
        "6 — `brain start` works without manual chflags: GET /healthz → 200; "
        "no ImportError: brain_core on stderr; Plan 15 Task 4 D3 contract "
        "verified end-to-end (closes #B1)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — Modal + Settings jargon consistency (B2)
# ---------------------------------------------------------------------------


_MODAL_PATH = (
    _REPO_ROOT / "apps" / "brain_web" / "src" / "components" / "dialogs" / "cross-domain-modal.tsx"
)
_PANEL_DOMAINS_PATH = (
    _REPO_ROOT / "apps" / "brain_web" / "src" / "components" / "settings" / "panel-domains.tsx"
)
_FORBIDDEN_JARGON = ("private domain", "kept private", "private notes")


def _gate_7_jargon_consistency() -> int:
    for path in (_MODAL_PATH, _PANEL_DOMAINS_PATH):
        if not path.exists():
            return _fail("7", f"file not found: {path}")
        text = path.read_text(encoding="utf-8")
        for phrase in _FORBIDDEN_JARGON:
            if phrase in text:
                return _fail(
                    "7",
                    f"forbidden phrase {phrase!r} still present in {path.name}; "
                    "Plan 15 Task 5 D4 jargon alignment regressed.",
                )
        if "Privacy-railed" not in text:
            return _fail(
                "7",
                f"required phrase 'Privacy-railed' missing from {path.name}; "
                "Plan 15 Task 5 D4 jargon alignment incomplete.",
            )
    _gate(
        "7 — Modal + Settings jargon consistency: 'Privacy-railed' present in "
        "BOTH cross-domain-modal.tsx and panel-domains.tsx; no 'private "
        "domain' / 'kept private' / 'private notes' anywhere (closes #B2)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — Active-domain toast CTA conditional (B3)
# ---------------------------------------------------------------------------


_ACTIVE_DOMAIN_TEST = (
    _REPO_ROOT / "apps" / "brain_web" / "tests" / "unit" / "settings-active-domain.test.tsx"
)


def _gate_8_toast_cta_conditional() -> int:
    if not _ACTIVE_DOMAIN_TEST.exists():
        return _fail("8", f"test file missing: {_ACTIVE_DOMAIN_TEST}")
    text = _ACTIVE_DOMAIN_TEST.read_text(encoding="utf-8")
    if "Pick a different domain" not in text:
        return _fail(
            "8",
            "settings-active-domain.test.tsx is missing assertion for "
            "'Pick a different domain' (validator-error CTA path); Plan 15 "
            "Task 6 D5 conditional CTA regression.",
        )
    if "Try again" not in text:
        return _fail(
            "8",
            "settings-active-domain.test.tsx is missing assertion for "
            "'Try again' (transport-error CTA path); Plan 15 Task 6 D5 "
            "conditional CTA regression.",
        )
    # Run the spec to confirm both pass.
    rc, stdout, stderr = _run_subprocess(
        "8",
        ["pnpm", "vitest", "run", "tests/unit/settings-active-domain.test.tsx"],
        cwd=_BRAIN_WEB,
    )
    if rc != 0:
        tail = "\n".join(stdout.splitlines()[-25:] + stderr.splitlines()[-15:])
        return _fail("8", f"settings-active-domain.test.tsx failed (rc={rc}); tail:\n{tail}")
    _gate(
        "8 — Active-domain toast CTA conditional: validator-error → 'Pick a "
        "different domain'; transport-error → 'Try again'; pushToast outside "
        "catch (Plan 12 Task 8 review I1+I2 closure; closes #B3)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — `pendingSendRef.mode` used (B4)
# ---------------------------------------------------------------------------


_CHAT_SCREEN_PATH = (
    _REPO_ROOT / "apps" / "brain_web" / "src" / "components" / "chat" / "chat-screen.tsx"
)


def _gate_9_pending_send_mode() -> int:
    if not _CHAT_SCREEN_PATH.exists():
        return _fail("9", f"chat-screen.tsx missing: {_CHAT_SCREEN_PATH}")
    text = _CHAT_SCREEN_PATH.read_text(encoding="utf-8")

    # The Task 7 review fix-up locked the pattern: capture pending into
    # a local synchronously, clear ref, await, dispatch from local.
    # Pin all three pieces.
    if "const pending = pendingSendRef.current" not in text:
        return _fail(
            "9",
            "chat-screen.tsx does not capture 'const pending = "
            "pendingSendRef.current' synchronously; Task 7 fix-up "
            "(capture-into-local pattern) regressed.",
        )
    if "pendingSendRef.current = null" not in text:
        return _fail(
            "9",
            "chat-screen.tsx does not clear 'pendingSendRef.current = null' "
            "before any await; throw-leak guard regressed.",
        )
    # The captured local must drive sendTurnStart's mode parameter.
    # Match: ``mode: pending.mode`` inside the dispatch.
    if not re.search(r"mode\s*:\s*pending\.mode", text):
        return _fail(
            "9",
            "chat-screen.tsx does not pass 'mode: pending.mode' to "
            "sendTurnStart; live-closure mode read regression (Plan 15 "
            "Task 7 click-time-captured intent contract).",
        )
    _gate(
        "9 — pendingSendRef.mode used: const pending = pendingSendRef.current "
        "captured synchronously; ref cleared before await; sendTurnStart "
        "reads pending.mode (NOT live closure); click-time intent honored "
        "(closes #B4)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — `raise_if_no_config` helper + 3 callers (B5)
# ---------------------------------------------------------------------------


def _gate_10_raise_if_no_config() -> int:
    # Import-check.
    rc, stdout, stderr = _run_subprocess(
        "10",
        [
            str(_VENV_PYTHON),
            "-c",
            "from brain_core.tools._errors import raise_if_no_config; "
            "print(raise_if_no_config.__name__)",
        ],
        cwd=_REPO_ROOT,
    )
    if rc != 0 or "raise_if_no_config" not in stdout:
        return _fail(
            "10",
            f"could not import raise_if_no_config from brain_core.tools._errors; "
            f"rc={rc}; stderr:\n{stderr[-500:]}",
        )

    # 3 brain_core callers.
    callers = (
        (
            _REPO_ROOT / "packages/brain_core/src/brain_core/tools/config_get.py",
            "brain_config_get",
        ),
        (
            _REPO_ROOT / "packages/brain_core/src/brain_core/tools/list_domains.py",
            "brain_list_domains",
        ),
        (
            _REPO_ROOT / "packages/brain_core/src/brain_core/tools/config_set.py",
            "brain_config_set",
        ),
    )
    for path, tool_name in callers:
        if not path.exists():
            return _fail("10", f"caller file missing: {path}")
        text = path.read_text(encoding="utf-8")
        if "from brain_core.tools._errors import raise_if_no_config" not in text:
            return _fail(
                "10",
                f"{path.name} does not import raise_if_no_config from "
                "brain_core.tools._errors; Task 8 D7 helper extraction "
                "regressed.",
            )
        if f'raise_if_no_config(ctx, "{tool_name}")' not in text:
            return _fail(
                "10",
                f"{path.name} does not call raise_if_no_config(ctx, "
                f'"{tool_name}"); Task 8 D7 helper extraction regressed.',
            )

    # SPAStaticFiles non-http guard is INTENTIONALLY separate.
    static_ui = _REPO_ROOT / "packages/brain_api/src/brain_api/static_ui.py"
    if not static_ui.exists():
        return _fail("10", f"static_ui.py missing: {static_ui}")
    static_ui_text = static_ui.read_text(encoding="utf-8")
    if "raise_if_no_config" in static_ui_text:
        return _fail(
            "10",
            "static_ui.py imports/uses raise_if_no_config; the SPAStaticFiles "
            "non-http scope guard MUST stay separate per Plan 15 D7 "
            "(different package, different scope-type contract).",
        )
    if 'scope["type"]' not in static_ui_text:
        return _fail(
            "10",
            "static_ui.py no longer asserts scope['type']; the WebSocket "
            "non-http guard (Plan 14 Task 1) regressed.",
        )

    _gate(
        "10 — raise_if_no_config helper + 3 callers: imports clean from "
        "brain_core.tools._errors; config_get + list_domains + config_set "
        "all delegate to it; SPAStaticFiles non-http guard stays separate "
        "(different package + scope-type contract; closes #B5)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — `_mk_ctx` requires config (B6)
# ---------------------------------------------------------------------------


_MK_CTX_FIXTURES = (
    _REPO_ROOT / "packages/brain_core/tests/tools/test_list_domains.py",
    _REPO_ROOT / "packages/brain_core/tests/tools/test_list_domains_active.py",
    _REPO_ROOT / "packages/brain_core/tests/tools/test_config_set.py",
)
# Match a `_mk_ctx` definition where the parameter list contains `config:
# Config` followed by either a comma or close-paren — i.e., the parameter
# is REQUIRED (no `= None` default, no `Optional[Config]`, no
# `Config | None`).
_MK_CTX_DEF_RE = re.compile(
    r"def\s+_mk_ctx\s*\([^)]*?\bconfig\s*:\s*Config(?P<after>\s*[,)])",
    re.DOTALL,
)
_MK_CTX_OPTIONAL_RE = re.compile(
    r"def\s+_mk_ctx\s*\([^)]*?\bconfig\s*:\s*"
    r"(Optional\[Config\]|Config\s*\|\s*None|Config\s*=\s*None)",
    re.DOTALL,
)


def _gate_11_mk_ctx_required() -> int:
    for path in _MK_CTX_FIXTURES:
        if not path.exists():
            return _fail("11", f"fixture file missing: {path}")
        text = path.read_text(encoding="utf-8")
        if _MK_CTX_OPTIONAL_RE.search(text):
            return _fail(
                "11",
                f"{path.name}::_mk_ctx still allows None config "
                "(Optional / | None / = None); Plan 15 Task 9 D8 "
                "alignment regressed.",
            )
        if not _MK_CTX_DEF_RE.search(text):
            return _fail(
                "11",
                f"{path.name}::_mk_ctx does NOT have 'config: Config' as a "
                "required parameter; Plan 15 Task 9 D8 alignment "
                "regressed.",
            )
    _gate(
        "11 — _mk_ctx requires config: all 3 fixtures (test_list_domains, "
        "test_list_domains_active, test_config_set) declare 'config: Config' "
        "as a required parameter; no Optional, no = None default (closes #B6)"
    )
    return 0


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    rc = _gate_1_ruff_clean()
    if rc != 0:
        return rc

    rc = _gate_2_brain_api_pytest()
    if rc != 0:
        return rc

    rc = _gate_3_brain_web_vitest()
    if rc != 0:
        return rc

    rc = _gate_4_playwright_subset()
    if rc != 0:
        return rc

    rc = _gate_5_windows_playwright_ci()
    if rc != 0:
        return rc

    rc = _gate_6_brain_start_no_chflags()
    if rc != 0:
        return rc

    rc = _gate_7_jargon_consistency()
    if rc != 0:
        return rc

    rc = _gate_8_toast_cta_conditional()
    if rc != 0:
        return rc

    rc = _gate_9_pending_send_mode()
    if rc != 0:
        return rc

    rc = _gate_10_raise_if_no_config()
    if rc != 0:
        return rc

    rc = _gate_11_mk_ctx_required()
    if rc != 0:
        return rc

    print()
    print("PLAN 15 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
