"""Plan 07 end-to-end demo — Task 24 scaffold.

Walks the 14-gate demo matrix from ``tasks/plans/07-frontend.md`` § Task 24.
Spawns ``brain_api`` (via uvicorn --factory against
``apps/brain_web/scripts/e2e_backend.py``) on port 4317 and Next.js
``next start`` on port 4316 as real subprocesses, seeds a temp vault,
and drives the app.

## Pragmatic scoping note

Plan 07 Task 24 is the SCAFFOLD pass. Of the 14 gates, several depend on
tools or test hooks that Task 25 will add:

* Gates 3, 4, 5, 8, 9, 11 need ``FakeLLMProvider`` queue priming behind a
  ``BRAIN_E2E_MODE=1`` backdoor. Without that, a turn against an empty
  FakeLLM queue raises ``RuntimeError`` and the UI can't stream a reply.
* Gate 10 needs the browse edit-mode save path wired — currently a UI-
  only mutation; Task 25 closes it.
* Gate 12 needs the Settings → Domains rename UI wired to the existing
  ``brain_rename_domain`` tool.
* Gate 14 needs four new MCP install tools (``brain_mcp_install`` /
  ``uninstall`` / ``status`` / ``selftest``).

This scaffold wires the gates that ARE ready — 1 (health), 2 (setup
wizard lands on /chat), 6 (approve patch via REST), 7 (undo via REST),
13 (budget override via REST) — and prints each Task-25-blocked gate as
``SKIPPED`` with a one-line reason. Minimum 5 gates must pass for this
scaffold to return 0. Task 25's demo flips the bar to all 14 green and
renames the success banner from ``PLAN 07 DEMO SCAFFOLD OK`` to
``PLAN 07 DEMO OK``.

## Why subprocesses and not in-process TestClient

Plans 04 and 05 demos run the MCP server / FastAPI app in-process through
a TestClient. Plan 07 exercises the browser layer — the real Next.js
server-side proxy has to read the token file brain_api wrote, and the
browser has to talk to both servers over HTTP. An in-process TestClient
would skip the Next.js layer entirely, which defeats the point of the
demo. So we spawn both as real subprocesses, just like CI does.

All LLM calls still go through :class:`FakeLLMProvider` — no network, no
API key required.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_BACKEND_PORT = 4317
_FRONTEND_PORT = 4316

_PASSES: list[str] = []
_SKIPS: list[tuple[int, str]] = []
_FAILS: list[tuple[int, str]] = []


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  OK  {msg}")


def _skip(gate: int, reason: str) -> None:
    """Mark a gate SKIPPED with an explanation. Does not fail the run."""
    print(f"[gate {gate}] SKIPPED — {reason}")
    _SKIPS.append((gate, reason))


def _pass(gate: int, summary: str) -> None:
    _PASSES.append(f"gate {gate}: {summary}")


def _scaffold_vault(root: Path) -> None:
    """Seed a vault that satisfies /browse, /pending, and the setup wizard.

    Deliberately does NOT seed BRAIN.md — the setup wizard's first-run
    detection relies on BRAIN.md absence to route ``/`` to ``/setup``.
    Gate 2 walks the wizard, which eventually writes BRAIN.md through the
    real tool surface.
    """
    (root / "research" / "notes").mkdir(parents=True)
    (root / "work" / "notes").mkdir(parents=True)
    (root / ".brain" / "run").mkdir(parents=True)

    (root / "research" / "notes" / "welcome.md").write_text(
        "---\ntitle: Welcome\n---\n\nThis is a seeded note for the demo.\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "research" / "index.md").write_text(
        "# research\n\n- [[welcome]]\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "work" / "index.md").write_text(
        "# work\n\n_Nothing here yet._\n",
        encoding="utf-8",
        newline="\n",
    )


def _port_is_free(port: int) -> bool:
    """Return True if the port is not currently LISTENing.

    SO_REUSEADDR makes TIME_WAIT sockets from a prior run not count
    against us — a common pitfall on macOS where a freshly-killed
    server's port can linger in TIME_WAIT for up to 60s even though
    nobody's listening. We're probing for "can I bind here cleanly",
    which is the same thing uvicorn will try to do.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.2)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _wait_for_http(url: str, timeout: float) -> bool:
    """Poll ``url`` until it returns 200 or timeout expires.

    Any non-200 (including connection refused) counts as not-ready and
    the poll loop retries. We accept the loose semantics because both
    health endpoints return 200 quickly once the process is listening.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.25)
    return False


def _http_json(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """POST/GET helper returning (status, parsed-json-or-empty-dict)."""
    import json as _json

    req_headers = {"Accept": "application/json", "Origin": f"http://localhost:{_BACKEND_PORT}"}
    if headers:
        req_headers.update(headers)
    body: bytes | None = None
    if data is not None:
        body = _json.dumps(data).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, _json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, _json.loads(raw) if raw else {}
        except ValueError:
            return exc.code, {"_raw": raw}


@contextmanager
def _spawn_backend(vault: Path):
    """Start brain_api via uvicorn --factory against the e2e shim.

    Mirrors ``apps/brain_web/scripts/start-backend-for-e2e.sh`` but in
    Python so it runs cross-platform without a shell wrapper. Uses
    ``sys.executable -m uv run`` is NOT an option — ``uv run`` is a
    standalone binary. Instead we use ``uv run uvicorn ...`` which works
    identically on Mac + Windows as long as ``uv`` is on PATH.
    """
    env = {
        **os.environ,
        "BRAIN_VAULT_ROOT": str(vault),
        "BRAIN_ALLOWED_DOMAINS": "research,work",
    }
    repo_root = Path(__file__).resolve().parent.parent
    app_dir = repo_root / "apps" / "brain_web" / "scripts"

    # shell=False is mandatory — CLAUDE.md principle #8 and prevents
    # Windows shell-quoting surprises. We pass argv as a list.
    cmd = [
        "uv",
        "run",
        "uvicorn",
        "--factory",
        "--app-dir",
        str(app_dir),
        "--host",
        "127.0.0.1",
        "--port",
        str(_BACKEND_PORT),
        "--log-level",
        "warning",
        "e2e_backend:build_app",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    try:
        ok = _wait_for_http(f"http://127.0.0.1:{_BACKEND_PORT}/healthz", timeout=45.0)
        if not ok:
            # Dump stderr so a boot failure isn't silent.
            try:
                proc.terminate()
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            print("FAIL: brain_api did not become healthy in 45s", file=sys.stderr)
            print(f"stdout:\n{(out or b'').decode(errors='replace')}", file=sys.stderr)
            print(f"stderr:\n{(err or b'').decode(errors='replace')}", file=sys.stderr)
            raise SystemExit(1)
        yield proc
    finally:
        if proc.poll() is None:
            # SIGTERM on POSIX, CTRL_BREAK_EVENT on Windows.
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


@contextmanager
def _spawn_frontend(vault: Path):
    """Start Next.js ``next start`` on port 4316 against the built app.

    Requires a prior ``pnpm build`` in ``apps/brain_web/``. The scaffold
    relies on the build artifact being present; Task 25 can add an
    auto-build fallback if needed.
    """
    repo_root = Path(__file__).resolve().parent.parent
    web_dir = repo_root / "apps" / "brain_web"
    if not (web_dir / ".next" / "BUILD_ID").exists():
        print(
            "FAIL: apps/brain_web/.next is missing — run `pnpm --dir apps/brain_web build` first",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Resolve pnpm absolute path to avoid shell lookup on Windows.
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        print("FAIL: pnpm is not on PATH", file=sys.stderr)
        raise SystemExit(1)

    env = {
        **os.environ,
        "BRAIN_VAULT_ROOT": str(vault),
        "PORT": str(_FRONTEND_PORT),
    }
    cmd = [pnpm, "start", "--port", str(_FRONTEND_PORT)]
    proc = subprocess.Popen(
        cmd,
        cwd=str(web_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    try:
        ok = _wait_for_http(f"http://127.0.0.1:{_FRONTEND_PORT}", timeout=60.0)
        if not ok:
            try:
                proc.terminate()
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            print("FAIL: next start did not become healthy in 60s", file=sys.stderr)
            print(f"stdout:\n{(out or b'').decode(errors='replace')}", file=sys.stderr)
            print(f"stderr:\n{(err or b'').decode(errors='replace')}", file=sys.stderr)
            raise SystemExit(1)
        yield proc
    finally:
        if proc.poll() is None:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def _read_token(vault: Path) -> str:
    """Read the brain_api-issued token from the seeded vault."""
    token_path = vault / ".brain" / "run" / "api-secret.txt"
    return token_path.read_text(encoding="utf-8").strip()


def _run_gate_1_healthz() -> None:
    """Gate 1 — backend + frontend /healthz both respond 200."""
    print("[gate 1] backend + frontend health")
    status, body = _http_json(f"http://127.0.0.1:{_BACKEND_PORT}/healthz")
    _check(status == 200, f"backend /healthz -> 200 (got {status})")
    _check(body.get("status") == "ok", "backend reports status=ok")

    # Frontend: Next.js has no /healthz — the / route serves a redirect or
    # the chat shell. A 200 on / (or a 200-equivalent redirect chain
    # landing on any of our routes) is sufficient proof of life.
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{_FRONTEND_PORT}/",
            timeout=5.0,
        ) as resp:
            _check(
                resp.status == 200,
                f"frontend / -> 200 (got {resp.status})",
            )
    except urllib.error.HTTPError as exc:
        # 3xx redirects are surfaced as HTTPError by urllib when
        # redirect following is off; we allow them here.
        _check(
            300 <= exc.code < 400,
            f"frontend / -> 2xx/3xx (got {exc.code})",
        )
    _pass(1, "both services healthy")


def _run_gate_2_setup_wizard(vault: Path) -> None:
    """Gate 2 — setup wizard walks 6 steps and lands on /chat.

    Drives the real browser via Playwright. We reuse the exact flow the
    ``tests/e2e/setup-wizard.spec.ts`` test covers: click through Welcome
    → Vault → API key → Theme → BRAIN.md (skip) → Claude Desktop (skip)
    and assert we're on /chat.
    """
    print("[gate 2] setup wizard end-to-end via Playwright")
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        _skip(2, "playwright Python bindings not installed (uv add --dev playwright)")
        return

    # Make sure BRAIN.md is absent so the root redirect lands on /setup.
    brain_md = vault / "BRAIN.md"
    if brain_md.exists():
        brain_md.unlink()

    import re as _re

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{_FRONTEND_PORT}/", wait_until="networkidle")
            page.wait_for_url("**/setup", timeout=15_000)
            _check(
                page.get_by_text("Step 1 of 6").is_visible(),
                "landed on /setup step 1",
            )

            # Walk the 6 steps. At each step we click the primary button
            # (Continue) or the Skip affordance for steps 4 + 5 which
            # would otherwise write real content (theme pref + BRAIN.md
            # seed) that muddy the scaffold's minimalism. Matches the
            # setup-wizard.spec.ts Playwright test.
            #
            # Why the regex name matcher? The Skip button reads "Skip this →"
            # (with a right-arrow glyph). Exact name="Skip this" would miss
            # depending on Playwright substring-match semantics; regex is
            # bulletproof and matches how the TS spec is written.
            for next_step_text in ("Step 2 of 6", "Step 3 of 6", "Step 4 of 6", "Step 5 of 6"):
                page.get_by_role("button", name="Continue").click()
                page.wait_for_selector(f"text={next_step_text}", timeout=10_000)
            # Step 5 → 6 via Skip to avoid writing a real BRAIN.md.
            page.get_by_role("button", name=_re.compile(r"Skip this")).click()
            page.wait_for_selector("text=Step 6 of 6", timeout=10_000)
            # Step 6 → /chat. The wizard's "Start using brain" button
            # calls ``onDone`` → ``router.push("/chat")``. /chat's server
            # component reads the token and renders chat on success.
            #
            # Cross-platform note (fixed inline in this task): /chat/page.tsx
            # now declares ``export const dynamic = "force-dynamic"`` so
            # Next.js re-runs ``readToken()`` per request. Without it,
            # ``pnpm build`` pre-rendered the redirect-to-/setup branch
            # (no BRAIN_VAULT_ROOT at build time → token missing) and
            # the cached redirect bounced every /chat request back to
            # /setup, which broke this demo on every run after the first.
            page.get_by_role(
                "button", name=_re.compile(r"Start using brain")
            ).click()
            page.wait_for_url("**/chat", timeout=15_000)
            _check(
                page.url.endswith("/chat"),
                f"landed on /chat (got {page.url})",
            )
        finally:
            browser.close()
    _pass(2, "setup wizard → /chat")


def _run_gate_3_chat_turn() -> None:
    """Gate 3 — Chat turn with FakeLLM-primed response.

    Pending Task 25: needs ``BRAIN_E2E_MODE=1`` + queue-priming endpoint
    so the WS turn doesn't raise on an empty FakeLLM queue.
    """
    _skip(3, "needs FakeLLM queue priming via BRAIN_E2E_MODE (Task 25)")


def _run_gate_4_tool_call_card() -> None:
    """Gate 4 — Tool call rendering (brain_search card)."""
    _skip(4, "depends on Gate 3's chat turn plumbing (Task 25)")


def _run_gate_5_patch_proposed_event() -> None:
    """Gate 5 — patch_proposed WS event renders inline + in rail."""
    _skip(5, "needs FakeLLM-primed patch-producing turn (Task 25)")


def _run_gate_6_approve_via_rest(vault: Path, token: str) -> None:
    """Gate 6 — Approve a patch through the REST layer.

    Task 24 scope: we prove the HTTP round-trip that the rail UI triggers
    from the approve button. Gate 11 — the ``doc_edit_proposed`` merge
    path — still needs Task 25 priming; this gate is the minimal "patch
    appears on disk" flow.
    """
    print("[gate 6] propose_note → apply_patch via REST")
    headers = {
        "X-Brain-Token": token,
        "Content-Type": "application/json",
    }
    # Propose a note.
    status, body = _http_json(
        f"http://127.0.0.1:{_BACKEND_PORT}/api/tools/brain_propose_note",
        method="POST",
        data={
            "path": "research/notes/gate-6.md",
            "content": "# gate 6\n\nplan 07 task 24 scaffold\n",
            "reason": "plan 07 demo gate 6",
        },
        headers=headers,
    )
    _check(status == 200, f"propose_note -> 200 (got {status})")
    patch_id = body.get("data", {}).get("patch_id")
    _check(bool(patch_id), "patch_id present")
    target = vault / "research" / "notes" / "gate-6.md"
    _check(not target.exists(), "target file NOT on disk before apply")

    # Apply it.
    status, body = _http_json(
        f"http://127.0.0.1:{_BACKEND_PORT}/api/tools/brain_apply_patch",
        method="POST",
        data={"patch_id": patch_id},
        headers=headers,
    )
    _check(status == 200, f"apply_patch -> 200 (got {status})")
    data = body.get("data", {})
    _check(data.get("status") == "applied", f"status=applied (got {data.get('status')!r})")
    undo_id = data.get("undo_id")
    _check(bool(undo_id), "undo_id present")
    _check(target.exists(), "target file ON disk after apply")
    # Stash for gate 7.
    _run_gate_6_approve_via_rest._undo_id = undo_id  # type: ignore[attr-defined]
    _run_gate_6_approve_via_rest._target = target  # type: ignore[attr-defined]
    _pass(6, "propose → apply → file on disk")


def _run_gate_7_undo_via_rest(token: str) -> None:
    """Gate 7 — Undo the last write."""
    print("[gate 7] brain_undo_last via REST")
    undo_id = getattr(_run_gate_6_approve_via_rest, "_undo_id", None)
    target = getattr(_run_gate_6_approve_via_rest, "_target", None)
    if undo_id is None or target is None:
        _skip(7, "gate 6 did not complete — nothing to undo")
        return
    headers = {
        "X-Brain-Token": token,
        "Content-Type": "application/json",
    }
    status, body = _http_json(
        f"http://127.0.0.1:{_BACKEND_PORT}/api/tools/brain_undo_last",
        method="POST",
        data={"undo_id": undo_id},
        headers=headers,
    )
    _check(status == 200, f"undo_last -> 200 (got {status})")
    data = body.get("data", {})
    _check(data.get("status") == "reverted", f"status=reverted (got {data.get('status')!r})")
    _check(not target.exists(), "target file GONE after undo")
    _pass(7, "undo reverts the applied patch")


def _run_gate_8_inbox_drag_drop() -> None:
    """Gate 8 — Drop a text file into inbox → classify → stage patch."""
    _skip(8, "needs BRAIN_E2E_MODE for classify step (Task 25)")


def _run_gate_9_bulk_import() -> None:
    """Gate 9 — Bulk dry-run → review → apply all."""
    _skip(9, "bulk import needs FakeLLM priming + multi-file queue (Task 25)")


def _run_gate_10_browse_edit() -> None:
    """Gate 10 — Browse: open note, edit, save → patch stages."""
    _skip(10, "browse edit-save wiring completes in Task 25")


def _run_gate_11_doc_edit_proposed() -> None:
    """Gate 11 — Draft mode: doc_edit_proposed WS event → Apply merges."""
    _skip(11, "draft mode needs doc_edit_proposed priming (Task 25)")


def _run_gate_12_rename_domain() -> None:
    """Gate 12 — Settings → Domains → Rename research → lab-notes."""
    _skip(12, "rename UI in settings/domains not wired until Task 25")


def _run_gate_13_budget_override(token: str) -> None:
    """Gate 13 — Budget override via brain_budget_override REST tool.

    Task 24 scope: exercise the HTTP path the BudgetWall UI calls. The UI
    polish (dismiss toast, raise cap inline) is a Task 25 frontend item;
    the TOOL surface is ready now.
    """
    print("[gate 13] brain_budget_override via REST")
    headers = {
        "X-Brain-Token": token,
        "Content-Type": "application/json",
    }
    status, body = _http_json(
        f"http://127.0.0.1:{_BACKEND_PORT}/api/tools/brain_budget_override",
        method="POST",
        data={"amount_usd": 5.0, "duration_hours": 24},
        headers=headers,
    )
    _check(status == 200, f"budget_override -> 200 (got {status})")
    data = body.get("data", {})
    _check(
        data.get("status") == "override_set",
        f"status=override_set (got {data.get('status')!r})",
    )
    _check("override_until" in data, "override_until present")
    _check(
        abs(float(data.get("override_delta_usd", 0)) - 5.0) < 0.001,
        f"override_delta_usd=5.0 (got {data.get('override_delta_usd')!r})",
    )
    _pass(13, "budget override applied + override_until set")


def _run_gate_14_mcp_install() -> None:
    """Gate 14 — Settings → Install Claude Desktop integration → selftest."""
    _skip(
        14,
        "brain_mcp_install/status/selftest tools land in Task 25",
    )


def _run_demo() -> int:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        vault = tmp / "vault"
        _scaffold_vault(vault)

        # Ports must be free — if a previous run left stragglers, bail
        # loudly rather than interleave with them. This is the same
        # policy Playwright's webServer.reuseExistingServer controls.
        if not _port_is_free(_BACKEND_PORT):
            print(
                f"FAIL: port {_BACKEND_PORT} is already in use — stop the other brain_api first",
                file=sys.stderr,
            )
            return 1
        if not _port_is_free(_FRONTEND_PORT):
            print(
                f"FAIL: port {_FRONTEND_PORT} is already in use — stop the other next start first",
                file=sys.stderr,
            )
            return 1

        with _spawn_backend(vault):
            # Backend has written the token to disk by now.
            token = _read_token(vault)

            with _spawn_frontend(vault):
                # --- Gate 1 --------------------------------------------
                _run_gate_1_healthz()
                # --- Gate 2 --------------------------------------------
                _run_gate_2_setup_wizard(vault)
                # --- Gate 3 (skipped — needs Task 25) ------------------
                _run_gate_3_chat_turn()
                # --- Gate 4 (skipped) ----------------------------------
                _run_gate_4_tool_call_card()
                # --- Gate 5 (skipped) ----------------------------------
                _run_gate_5_patch_proposed_event()
                # --- Gate 6 --------------------------------------------
                _run_gate_6_approve_via_rest(vault, token)
                # --- Gate 7 --------------------------------------------
                _run_gate_7_undo_via_rest(token)
                # --- Gate 8 (skipped) ----------------------------------
                _run_gate_8_inbox_drag_drop()
                # --- Gate 9 (skipped) ----------------------------------
                _run_gate_9_bulk_import()
                # --- Gate 10 (skipped) ---------------------------------
                _run_gate_10_browse_edit()
                # --- Gate 11 (skipped) ---------------------------------
                _run_gate_11_doc_edit_proposed()
                # --- Gate 12 (skipped) ---------------------------------
                _run_gate_12_rename_domain()
                # --- Gate 13 -------------------------------------------
                _run_gate_13_budget_override(token)
                # --- Gate 14 (skipped) ---------------------------------
                _run_gate_14_mcp_install()

        # ------------------------------------------------------------------
        # Scaffold acceptance gate — minimum set of passes for Task 24 sign-off
        # ------------------------------------------------------------------
        required = {1, 2, 6, 7, 13}
        passed_nums = {int(p.split(":", 1)[0].split(" ", 1)[1]) for p in _PASSES}
        missing = required - passed_nums
        if missing:
            print(
                f"\nFAIL: required gates {sorted(missing)} did not pass",
                file=sys.stderr,
            )
            return 1

        print()
        print(f"Passed gates: {sorted(passed_nums)}")
        print(f"Skipped gates: {[g for g, _ in sorted(_SKIPS)]}")
        print()
        print("PLAN 07 DEMO SCAFFOLD OK")
        return 0


def main() -> int:
    return _run_demo()


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]
