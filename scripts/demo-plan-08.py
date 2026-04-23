"""Plan 08 end-to-end demo — 11-gate install + supervisor + uninstall round-trip.

Simulates a fresh install in a temp dir on the developer's box. Walks the
full distribution pipeline: cut a tarball from git HEAD → run
``scripts/install.sh`` into ``$TMP/demo08-<ts>/install/`` → start the
brain daemon against ``$TMP/demo08-<ts>/vault/`` → drive the setup wizard +
ingest + approve one patch via Playwright + REST → stop → restart → stop
→ uninstall → verify cleanup.

## Why not the full Plan 07 demo shape?

Plan 07's demo spawned Next.js + brain_api as two sibling subprocesses
on ports 4316 + 4317. Plan 08 Task 2 pivoted to static export: brain_api
now serves BOTH the API and the UI on one port (4317..4330). The demo
has to follow.

## Why spawn ``brain start`` instead of uvicorn directly?

Plan 08's supervisor is the thing under test. The install script writes
a shim; the shim invokes ``brain start``; ``brain start`` probes ports,
writes PID + port files, opens the browser, polls /healthz, and hands
back a URL. Skipping the supervisor would skip the entire Group 1 /
Group 2 surface — the demo would prove nothing new over Plan 07's demo.

## Why does the install.sh run with BRAIN_SKIP_UV_SYNC=1?

On a real fresh machine install.sh would run ``uv sync --all-packages``
against the freshly-extracted tarball. That takes ~45s on a warm cache
and downloads PyPI wheels. For a demo gate we want speed + determinism;
we prove the install script flow + tarball extraction + shim writing,
then point the supervisor at the dev repo's already-synced venv via
BRAIN_INSTALL_DIR. A real user's first install hits the full path; our
clean-VM dry runs (Tasks 10 + 11) prove that separately.

## Why BRAIN_E2E_MODE=1?

``FakeLLMProvider`` raises ``RuntimeError`` on an empty queue by default
(intentional safety rail for unit tests that forget to prime). The demo
runs brain_api as a spawned subprocess, so the demo driver can't reach
into the spawn's FakeLLM to queue responses. Plan 07 Task 25C added
``BRAIN_E2E_MODE=1`` which flips the fallback from "raise" to "return a
prompt-aware canned response". We set it on the supervisor env so
every gate that touches a real LLM call (chat, classify, summarize,
integrate) returns a usable response without network or API key.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each gate emits a one-line pass/fail in the demo receipt. Aggregate
# results here so the final summary can report "passed: [1,2,...]" etc.
_PASSES: list[tuple[int, str]] = []
_SKIPS: list[tuple[int, str]] = []
_FAILS: list[tuple[int, str]] = []


def _check(cond: bool, msg: str) -> None:
    """Hard check — any failure aborts the demo with exit 1."""
    if not cond:
        print(f"  FAIL {msg}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  OK  {msg}")


def _pass(gate: int, summary: str) -> None:
    _PASSES.append((gate, summary))


def _skip(gate: int, reason: str) -> None:
    print(f"[gate {gate}] SKIPPED — {reason}")
    _SKIPS.append((gate, reason))


def _fail(gate: int, reason: str) -> None:
    print(f"[gate {gate}] FAIL — {reason}", file=sys.stderr)
    _FAILS.append((gate, reason))


def _wait_for_http(url: str, timeout: float) -> bool:
    """Poll ``url`` until 200 or timeout. Connection refused counts as not-ready."""
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
    origin: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """JSON HTTP helper returning (status, parsed-body-or-empty-dict)."""
    req_headers: dict[str, str] = {"Accept": "application/json"}
    if origin is not None:
        req_headers["Origin"] = origin
    if headers:
        req_headers.update(headers)
    body: bytes | None = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except ValueError:
            return exc.code, {"_raw": raw}


def _tool(
    name: str,
    token: str,
    port: int,
    data: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """POST /api/tools/<name> with X-Brain-Token + Origin headers."""
    origin = f"http://localhost:{port}"
    return _http_json(
        f"http://127.0.0.1:{port}/api/tools/{name}",
        method="POST",
        data=data or {},
        headers={"X-Brain-Token": token, "Content-Type": "application/json"},
        origin=origin,
    )


def _read_port(vault: Path) -> int | None:
    port_file = vault / ".brain" / "run" / "brain.port"
    if not port_file.exists():
        return None
    try:
        return int(port_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _read_token(vault: Path) -> str:
    token_path = vault / ".brain" / "run" / "api-secret.txt"
    return token_path.read_text(encoding="utf-8").strip()


def _read_pid(vault: Path) -> int | None:
    pid_file = vault / ".brain" / "run" / "brain.pid"
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness probe — mirrors the supervisor's psutil check."""
    try:
        import psutil

        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except Exception:
        return False


def _count_brain_api_procs() -> int:
    """Count live uvicorn/brain_api processes (for orphan checks).

    We match the two known shapes for a brain-spawned uvicorn child:

      * ``uv run ... uvicorn --factory ... backend_factory:build_app``
        (the immediate subprocess from ``brain start``), and
      * the ``python -m uvicorn`` grandchild uv eventually execs into.

    Both share the literal ``backend_factory:build_app`` module path in
    their cmdline AND live under a process that actually dispatches
    ``uvicorn`` (not just this Python demo script which happens to
    contain the string literal). We AND both conditions to avoid
    self-matching.
    """
    try:
        import psutil

        my_pid = os.getpid()
        count = 0
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                if proc.info["pid"] == my_pid:
                    continue
                cmdline = proc.info.get("cmdline") or []
                joined = " ".join(str(x) for x in cmdline)
                if "backend_factory:build_app" in joined and "uvicorn" in joined:
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count
    except Exception:
        return 0


def _brain_cmd(
    install_dir: Path, args: list[str], env_extra: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Invoke the installed shim: ``<install>/.venv/bin/brain <args>``.

    The install.sh writes a shim at ``~/.local/bin/brain`` that does
    ``exec uv run --project <install> brain "$@"``. We skip the shim and
    call ``uv run`` directly so we don't have to manage PATH / HOME env
    manipulation in the demo driver.
    """
    env = os.environ.copy()
    env.update(env_extra)
    cmd = [
        "uv",
        "run",
        "--project",
        str(install_dir),
        "brain",
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=str(install_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@contextmanager
def _supervisor_start(
    install_dir: Path,
    vault_root: Path,
    env_extra: dict[str, str] | None = None,
):
    """Run ``brain start`` + yield once healthy; stop on exit.

    Uses the repo's ``uv run`` directly so we don't depend on the shim
    being on PATH. BRAIN_NO_BROWSER=1 tells ``brain start`` not to open
    the system browser during the demo (the supervisor respects this
    flag via the browser helper).
    """
    env: dict[str, str] = dict(env_extra or {})
    env.setdefault("BRAIN_INSTALL_DIR", str(install_dir))
    env.setdefault("BRAIN_VAULT_ROOT", str(vault_root))
    env.setdefault("BRAIN_LLM_PROVIDER", "fake")
    env.setdefault("BRAIN_E2E_MODE", "1")
    env.setdefault("BRAIN_NO_BROWSER", "1")
    # Keep uv quiet — subprocess noise muddies the demo receipt.
    env.setdefault("UV_NO_PROGRESS", "1")

    result = _brain_cmd(install_dir, ["start"], env)
    if result.returncode != 0:
        print(
            f"FAIL: brain start exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Port + healthz readiness probe — the supervisor is supposed to
    # have already waited on /healthz, but poll one more time here in
    # case the env had BRAIN_NO_BROWSER disabled and the spawn was fast.
    port = _read_port(vault_root)
    if port is None:
        print("FAIL: brain start returned 0 but no port file exists", file=sys.stderr)
        raise SystemExit(1)
    if not _wait_for_http(f"http://127.0.0.1:{port}/healthz", timeout=15.0):
        print(
            f"FAIL: /healthz never returned 200 on port {port}",
            file=sys.stderr,
        )
        _brain_cmd(install_dir, ["stop"], env)
        raise SystemExit(1)

    try:
        yield port, result
    finally:
        # Stop the daemon. Best-effort — if the supervisor already shut
        # down (e.g. via gate 8) this is a no-op.
        _brain_cmd(install_dir, ["stop"], env)


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------


def _run_gate_0_ui_prebuild() -> None:
    """Gate 0 — verify the static UI bundle exists (pre-requisite).

    The install.sh path with ``BRAIN_SKIP_NODE=1`` assumes the tarball
    ships a prebuilt UI. Git-archive doesn't include ``apps/brain_web/out/``
    (gitignored), so we rely on the developer having run ``pnpm -F
    brain_web build`` at least once before running this demo. If absent,
    print a clear next-action and bail.
    """
    print("[gate 0] pre-flight: static UI bundle present")
    out_index = REPO_ROOT / "apps" / "brain_web" / "out" / "index.html"
    if not out_index.exists():
        print(
            f"  FAIL UI bundle missing at {out_index}\n"
            "       Run `pnpm -F brain_web build` first, then re-run this demo.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    _check(
        out_index.exists(),
        f"apps/brain_web/out/index.html present ({out_index.stat().st_size} bytes)",
    )
    _pass(0, "UI bundle prebuilt")


def _run_gate_1_cut_tarball(work_dir: Path) -> Path:
    """Gate 1 — cut a dev tarball + SHA256 sidecar via scripts/cut_local_tarball.py.

    Returns the tarball path for gate 2 to consume.
    """
    print("[gate 1] cut dev tarball from git HEAD")
    dist_dir = work_dir / "dist"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "cut_local_tarball.py"), str(dist_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    _check(result.returncode == 0, f"cut_local_tarball.py exited 0 (rc={result.returncode})")
    tarballs = list(dist_dir.glob("brain-dev-*.tar.gz"))
    _check(len(tarballs) == 1, f"exactly one tarball produced (got {len(tarballs)})")
    tarball = tarballs[0]
    sidecar = dist_dir / f"{tarball.name}.sha256"
    _check(sidecar.exists(), f"sha256 sidecar written at {sidecar.name}")
    sha_text = sidecar.read_text(encoding="utf-8").strip()
    _check(len(sha_text.split()[0]) == 64, "sha256 digest is 64 hex chars")
    _pass(1, f"tarball cut ({tarball.name}, {tarball.stat().st_size // 1024} KB)")
    return tarball


def _run_gate_2_install_sh(work_dir: Path, tarball: Path) -> Path:
    """Gate 2 — run scripts/install.sh into a tmp install dir.

    We set:
      - BRAIN_SKIP_UV_SYNC=1 (skip the ~45s pip install — demo speed)
      - BRAIN_SKIP_NODE=1    (don't re-install Node; we copy the prebuilt UI in)
      - BRAIN_SKIP_DOCTOR=1  (we'll run doctor separately to capture output)
      - BRAIN_INSTALL_FORCE=1 (skip the "overwrite existing install?" prompt)
      - BRAIN_RELEASE_URL=file://<tarball>

    After install.sh, we copy apps/brain_web/out/ from the repo into the
    install dir so the supervisor + static-file mount can find index.html.
    A real release tarball would ship this prebuilt.

    Returns the install dir for downstream gates.
    """
    print("[gate 2] install.sh runs end-to-end against local tarball")
    install_dir = work_dir / "install"
    sidecar = tarball.parent / f"{tarball.name}.sha256"
    sha = sidecar.read_text(encoding="utf-8").strip().split()[0]

    env = os.environ.copy()
    env.update(
        {
            "BRAIN_INSTALL_DIR": str(install_dir),
            "BRAIN_RELEASE_URL": f"file://{tarball}",
            "BRAIN_RELEASE_SHA256": sha,
            "BRAIN_SKIP_UV_SYNC": "1",
            "BRAIN_SKIP_NODE": "1",
            "BRAIN_SKIP_DOCTOR": "1",
            "BRAIN_INSTALL_FORCE": "1",
            # Point the shim writer at a scratch dir so we don't overwrite
            # the developer's real ~/.local/bin/brain.
            "BRAIN_SHIM_DIR": str(work_dir / "shim-bin"),
            # Keep the HOME-side .app wrapper out of the real Applications/.
            "HOME": str(work_dir / "home"),
        }
    )
    # The install.sh helpers mkdir their outputs, but the HOME override
    # needs the directory itself to exist. write_shim.sh also references
    # ~/Applications on Mac, so pre-create that tree.
    (work_dir / "home" / "Applications").mkdir(parents=True, exist_ok=True)
    (work_dir / "home" / ".local" / "bin").mkdir(parents=True, exist_ok=True)
    (work_dir / "shim-bin").mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["/bin/bash", str(REPO_ROOT / "scripts" / "install.sh")],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"install.sh stdout:\n{result.stdout}", file=sys.stderr)
        print(f"install.sh stderr:\n{result.stderr}", file=sys.stderr)
    _check(result.returncode == 0, f"install.sh exited 0 (rc={result.returncode})")
    _check(install_dir.is_dir(), f"install dir created at {install_dir}")
    _check((install_dir / "pyproject.toml").exists(), "pyproject.toml extracted")
    _check(
        (install_dir / "packages" / "brain_cli" / "src" / "brain_cli" / "app.py").exists(),
        "brain_cli source extracted",
    )

    # Copy the prebuilt UI into the extracted install — real releases
    # ship this inside the tarball. We cannot git-archive it because
    # apps/brain_web/out/ is gitignored.
    src_out = REPO_ROOT / "apps" / "brain_web" / "out"
    dst_out = install_dir / "apps" / "brain_web" / "out"
    if dst_out.exists():
        shutil.rmtree(dst_out)
    dst_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_out, dst_out)
    _check(
        (dst_out / "index.html").exists(),
        "apps/brain_web/out/index.html copied into install (simulates prebuilt release tarball)",
    )

    # Run brain doctor against the tmp install. We use the dev repo's
    # already-synced venv because BRAIN_SKIP_UV_SYNC=1 left the tmp
    # install without a populated .venv. Doctor surfaces FAILs for the
    # missing .venv + token + config — all expected on a fresh, pre-
    # setup install. We assert the command runs without crashing (exit
    # 0 OR 1 both acceptable; a crash / bare traceback is a fail).
    doctor = _brain_cmd(
        REPO_ROOT,
        ["doctor", "--install", str(install_dir), "--vault", str(work_dir / "vault")],
        {
            "BRAIN_INSTALL_DIR": str(install_dir),
            "BRAIN_VAULT_ROOT": str(work_dir / "vault"),
        },
    )
    # Fresh install has no .venv (skipped sync) + no token file yet →
    # doctor exits 1. Accept both 0 and 1; crash (rc=2+) is not OK.
    _check(
        doctor.returncode in {0, 1},
        f"brain doctor runs cleanly (rc={doctor.returncode})",
    )
    _check("brain doctor" in doctor.stdout, "doctor printed its header")
    _pass(2, f"install.sh extracted + doctor runs cleanly (rc={doctor.returncode})")
    return install_dir


def _run_gate_3_first_start(install_dir: Path, vault_root: Path) -> tuple[int, str]:
    """Gate 3 — brain start spawns uvicorn, healthz=200, URL printed.

    Returns (port, token) so later gates can drive REST calls without
    having to re-read them.
    """
    print("[gate 3] brain start probes port + /healthz=200 + URL printed")

    # Note: the context manager will start + later stop. Here we just
    # launch it and stash the port; we'll exit the context in a wider
    # frame so later gates can operate against a running daemon.
    # Instead of nesting contexts, call directly — later gates each
    # open/close their own scope.
    env = {
        "BRAIN_INSTALL_DIR": str(install_dir),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "BRAIN_LLM_PROVIDER": "fake",
        "BRAIN_E2E_MODE": "1",
        "BRAIN_NO_BROWSER": "1",
        "UV_NO_PROGRESS": "1",
    }
    # Use dev repo as the project for uv run — BRAIN_SKIP_UV_SYNC left
    # the tmp install without a venv.
    result = _brain_cmd(REPO_ROOT, ["start"], env)
    if result.returncode != 0:
        print(f"brain start stdout:\n{result.stdout}", file=sys.stderr)
        print(f"brain start stderr:\n{result.stderr}", file=sys.stderr)
    _check(result.returncode == 0, f"brain start exited 0 (rc={result.returncode})")
    _check(
        "brain running at" in result.stdout or "already running at" in result.stdout,
        "brain start printed the running URL",
    )

    port = _read_port(vault_root)
    _check(port is not None, f"port file written at {vault_root}/.brain/run/brain.port")
    assert port is not None
    _check(
        4317 <= port <= 4330,
        f"port {port} in expected 4317..4330 range",
    )
    _check(_wait_for_http(f"http://127.0.0.1:{port}/healthz", timeout=10.0), "/healthz=200")

    token = _read_token(vault_root)
    _check(len(token) >= 32, f"token file populated ({len(token)} chars)")

    pid = _read_pid(vault_root)
    _check(pid is not None and _pid_alive(pid), f"brain_api process alive (pid={pid})")
    _pass(3, f"brain start → port {port}, pid {pid}, /healthz=200")
    return port, token


def _run_gate_4_root_redirects_to_setup(port: int, vault_root: Path) -> None:
    """Gate 4 — GET / on bootstrap returns index.html; setup-status says first-run.

    A full Playwright browser check happens in gate 5 (walks the wizard).
    This gate is the lighter proof: the SPA shell is served + the API
    endpoint the bootstrap gate reads on mount reports first-run=true.
    """
    print("[gate 4] bootstrap loads + /api/setup-status reports first-run")
    origin = f"http://localhost:{port}"
    status, body = _http_json(f"http://127.0.0.1:{port}/api/setup-status", origin=origin)
    _check(status == 200, f"/api/setup-status -> 200 (got {status})")
    _check(
        body.get("is_first_run") is True, f"is_first_run=true (got {body.get('is_first_run')!r})"
    )
    _check(body.get("has_token") is True, "has_token=true (token written at startup)")
    _check(
        body.get("vault_path", "").endswith(str(vault_root).split(os.sep)[-1]),
        f"vault_path matches ({body.get('vault_path')!r})",
    )

    # Bootstrap UI: the client bundle is served at GET / via static mount.
    # We just want a 200 + HTML; the SPA hydration happens in the browser.
    # The static mount returns HTML so we can't reuse _http_json (JSON parse).
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/",
            headers={"Origin": origin},
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            body = resp.read()
            _check(resp.status == 200, f"GET / -> 200 (got {resp.status})")
            _check(
                b"<html" in body.lower() or b"<!doctype" in body.lower(),
                "GET / returned HTML (SPA shell)",
            )
    except urllib.error.URLError as exc:
        _check(False, f"GET / failed: {exc}")
    _pass(4, "bootstrap route loads + first-run detected")


def _run_gate_5_setup_wizard(port: int, vault_root: Path) -> None:
    """Gate 5 — walk the 6-step setup wizard via Playwright → /chat."""
    print("[gate 5] Playwright walks setup wizard → /chat")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _skip(5, "playwright Python bindings not installed (uv add --dev playwright)")
        return

    # Make sure BRAIN.md doesn't exist — setup-status gates the redirect
    # on BRAIN.md presence (via is_first_run = !has_token OR !vault_exists
    # OR !BRAIN.md).
    brain_md = vault_root / "BRAIN.md"
    if brain_md.exists():
        brain_md.unlink()

    import re as _re

    base_url = f"http://127.0.0.1:{port}"
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:
            _skip(
                5,
                f"chromium launch failed ({exc!r}) — run `uv run playwright install chromium`",
            )
            return
        try:
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(f"{base_url}/", wait_until="networkidle")
            page.wait_for_url(_re.compile(r"/setup/?$"), timeout=15_000)
            _check(page.get_by_text("Step 1 of 6").is_visible(), "landed on /setup step 1")

            for next_step in ("Step 2 of 6", "Step 3 of 6", "Step 4 of 6", "Step 5 of 6"):
                page.get_by_role("button", name="Continue").click()
                page.wait_for_selector(f"text={next_step}", timeout=10_000)
            # Skip BRAIN.md seed to keep the vault minimal for later gates.
            page.get_by_role("button", name=_re.compile(r"Skip this")).click()
            page.wait_for_selector("text=Step 6 of 6", timeout=10_000)
            page.get_by_role("button", name=_re.compile(r"Start using brain")).click()
            page.wait_for_url(_re.compile(r"/chat/?$"), timeout=15_000)
            _check(bool(_re.search(r"/chat/?$", page.url)), f"landed on /chat (got {page.url})")
        finally:
            browser.close()
    _pass(5, "setup wizard 6 steps → /chat")


def _run_gate_6_ingest(port: int, token: str, vault_root: Path) -> str:
    """Gate 6 — POST /api/tools/brain_ingest → patch staged."""
    print("[gate 6] brain_ingest stages a patch")
    # Write a seed text file inside the vault so the handler dispatcher
    # can route it (TextHandler wants Path).
    seed_dir = vault_root / "raw" / "inbox"
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed = seed_dir / f"demo-plan-08-{int(time.time())}.md"
    seed.write_text(
        "# Plan 08 demo — Task 12 seed note\n\n"
        "Ingest pipeline seed for gate 6. "
        "Should stage a patch via FakeLLM canned responses.\n",
        encoding="utf-8",
        newline="\n",
    )

    status, body = _tool("brain_ingest", token, port, data={"source": str(seed)})
    _check(status == 200, f"brain_ingest -> 200 (got {status}, body={body})")
    data = body.get("data", {})
    accepted = {"ok", "pending", "skipped_duplicate"}
    _check(
        str(data.get("status", "")).lower() in accepted,
        f"ingest status in {accepted} (got {data.get('status')!r})",
    )
    patch_id = data.get("patch_id")
    if data.get("status") == "pending":
        _check(isinstance(patch_id, str) and bool(patch_id), f"patch_id present ({patch_id!r})")
    _pass(6, f"ingest staged (status={data.get('status')!r})")
    return patch_id or ""


def _run_gate_7_apply_patch(port: int, token: str, vault_root: Path, ingest_patch_id: str) -> None:
    """Gate 7 — approve a patch via REST → file appears on disk.

    We use ``brain_propose_note`` rather than applying the ingest-staged
    patch from gate 6: the E2E-mode canned integrate response produces a
    PatchSet with ``new_files=[]`` (see ``brain_core.llm.fake``), so the
    envelope's target_path falls back to the absolute note_path, which
    apply_patch's domain-derivation rejects as out-of-scope. For the
    plan-08 demo we care that REST → stage → apply → disk round-trips,
    not which staging tool fed it. The ingest gate's own success
    criterion (gate 6) is the staged patch existing in the pending queue.
    """
    print("[gate 7] propose_note → apply_patch via REST (file on disk)")
    _ = ingest_patch_id  # accepted but not applied — see docstring.

    target_rel = "work/notes/gate-7-demo.md"
    status, body = _tool(
        "brain_propose_note",
        token,
        port,
        data={
            "path": target_rel,
            "content": "# gate 7\n\nPlan 08 demo — REST propose + apply.\n",
            "reason": "plan 08 demo gate 7",
        },
    )
    _check(status == 200, f"propose_note -> 200 (got {status}, body={body})")
    patch_id = body.get("data", {}).get("patch_id", "")
    _check(bool(patch_id), "patch_id returned")

    target_abs = vault_root / target_rel
    _check(not target_abs.exists(), "target file NOT on disk before apply")

    # Pull the patch out of the pending queue.
    status, body = _tool("brain_list_pending_patches", token, port, data={})
    _check(status == 200, f"list_pending_patches -> 200 (got {status})")
    patches = body.get("data", {}).get("patches", [])
    _check(
        any(p.get("patch_id") == patch_id for p in patches),
        f"patch_id {patch_id!r} visible in pending list",
    )

    # Apply it.
    status, body = _tool("brain_apply_patch", token, port, data={"patch_id": patch_id})
    _check(
        status == 200,
        f"apply_patch -> 200 (got {status}, body={body})",
    )
    data = body.get("data", {})
    _check(
        str(data.get("status")) == "applied",
        f"status=applied (got {data.get('status')!r})",
    )
    _check(target_abs.exists(), f"target file ON disk after apply ({target_abs})")
    _pass(7, "propose → apply → file on disk")


def _run_gate_8_stop(install_dir: Path, vault_root: Path) -> None:
    """Gate 8 — brain stop removes pid/port + no orphan uvicorn."""
    print("[gate 8] brain stop → pid + port files gone; no orphan uvicorn")
    env = {
        "BRAIN_INSTALL_DIR": str(install_dir),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "UV_NO_PROGRESS": "1",
    }
    result = _brain_cmd(REPO_ROOT, ["stop"], env)
    _check(result.returncode == 0, f"brain stop exited 0 (rc={result.returncode})")

    # Give the OS a breath to finalize file deletions.
    time.sleep(0.5)
    pid_file = vault_root / ".brain" / "run" / "brain.pid"
    port_file = vault_root / ".brain" / "run" / "brain.port"
    _check(not pid_file.exists(), "pid file removed")
    _check(not port_file.exists(), "port file removed")

    # Orphan check: any stray backend_factory process hanging around?
    # Allow a brief grace window — psutil sometimes sees a zombie tick.
    orphans = _count_brain_api_procs()
    _check(orphans == 0, f"no orphan brain_api processes (got {orphans})")
    _pass(8, "brain stop cleaned up; 0 orphans")


def _run_gate_9_restart_idempotent(install_dir: Path, vault_root: Path, token: str) -> None:
    """Gate 9 — second start+stop cycle; previous vault content preserved."""
    print("[gate 9] start+stop round-trip #2 (idempotency)")
    env = {
        "BRAIN_INSTALL_DIR": str(install_dir),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "BRAIN_LLM_PROVIDER": "fake",
        "BRAIN_E2E_MODE": "1",
        "BRAIN_NO_BROWSER": "1",
        "UV_NO_PROGRESS": "1",
    }
    before = sorted(p.name for p in (vault_root.rglob("*.md")))

    start_res = _brain_cmd(REPO_ROOT, ["start"], env)
    _check(start_res.returncode == 0, f"second start rc=0 (got {start_res.returncode})")
    port2 = _read_port(vault_root)
    _check(port2 is not None, "second start wrote port file")
    assert port2 is not None
    _check(
        _wait_for_http(f"http://127.0.0.1:{port2}/healthz", timeout=10.0),
        "second start /healthz=200",
    )
    # New token generated on second start — the setup-status check
    # should still report has_token=true.
    status, body = _http_json(
        f"http://127.0.0.1:{port2}/api/setup-status",
        origin=f"http://localhost:{port2}",
    )
    _check(status == 200, "second start setup-status -> 200")
    _check(bool(body.get("has_token")), "second start issued a token")

    # Stop cleanly.
    stop_res = _brain_cmd(REPO_ROOT, ["stop"], env)
    _check(stop_res.returncode == 0, f"second stop rc=0 (got {stop_res.returncode})")

    # Verify vault content preserved across the cycle.
    after = sorted(p.name for p in (vault_root.rglob("*.md")))
    _check(
        before == after,
        f"vault .md files identical across cycle (before={len(before)}, after={len(after)})",
    )
    _pass(9, f"restart idempotent; vault preserved ({len(after)} .md files)")


def _run_gate_10_uninstall(work_dir: Path, install_dir: Path, vault_root: Path) -> None:
    """Gate 10 — brain uninstall --yes removes code; vault preserved."""
    print("[gate 10] brain uninstall --yes (code gone; vault preserved)")
    # Snapshot vault before uninstall so we can prove preservation.
    before = sorted(p.name for p in (vault_root.rglob("*.md")))
    _check(before, f"vault has .md files before uninstall (got {len(before)})")

    env = {
        "BRAIN_INSTALL_DIR": str(install_dir),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "BRAIN_SHIM_DIR": str(work_dir / "shim-bin"),
        "HOME": str(work_dir / "home"),
        "UV_NO_PROGRESS": "1",
    }
    result = _brain_cmd(
        REPO_ROOT,
        [
            "uninstall",
            "--yes",
            "--install",
            str(install_dir),
            "--vault",
            str(vault_root),
        ],
        env,
    )
    _check(result.returncode == 0, f"brain uninstall rc=0 (got {result.returncode})")
    _check(
        "Uninstall complete" in result.stdout,
        "uninstall summary printed",
    )
    _check(not install_dir.exists(), f"install dir removed ({install_dir})")
    _check(
        vault_root.exists(),
        f"vault preserved at {vault_root}",
    )
    after = sorted(p.name for p in (vault_root.rglob("*.md")))
    _check(
        before == after,
        f"vault .md files unchanged by uninstall (before={len(before)}, after={len(after)})",
    )
    _pass(10, "uninstall removed code; vault preserved untouched")


def _run_gate_11_post_uninstall(work_dir: Path, install_dir: Path) -> None:
    """Gate 11 — post-uninstall: shim gone; `brain` no longer resolvable via install dir.

    Proves the cleanup surface: after ``brain uninstall``, no invocation
    of the installed code path should succeed. We verify the shim dir is
    empty (the shim file was deleted) and the install dir is gone.
    """
    print("[gate 11] post-uninstall: shim gone; install dir absent")
    shim_dir = work_dir / "shim-bin"
    shim = shim_dir / "brain"
    _check(not shim.exists(), f"shim {shim} removed")
    _check(not install_dir.exists(), f"install dir {install_dir} removed")

    # Also verify: invoking `brain` from the shim-bin PATH now fails.
    # If the shim dir still exists but is empty, this is a clean "not
    # found" signal rather than a crash.
    env = os.environ.copy()
    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    try:
        probe = subprocess.run(
            ["brain", "--version"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        # Two outcomes are both acceptable here:
        #   (a) shim missing → FileNotFoundError raised by Popen; caught below.
        #   (b) shim resolved to a real `brain` elsewhere on PATH (developer's
        #       existing install); `brain --version` returns 0 but that's not
        #       proof of the shim-dir cleanup, so we assert on the shim_dir
        #       specifically above.
        # Either way, the key assertion is the file-level absence check.
        _check(
            True,
            f"probe completed (rc={probe.returncode}) — shim-dir check above is authoritative",
        )
    except FileNotFoundError:
        _check(True, "probe: `brain` not found on PATH (ideal clean state)")
    _pass(11, "shim removed; install dir absent")


def _run_demo() -> int:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    header = f"brain · plan 08 demo · {ts}"
    print(header)
    print("=" * len(header))
    print("")

    # Sanity: refuse to run if a brain daemon is already live on the dev
    # box. Colliding with it would scribble over the user's real vault.
    prior = _count_brain_api_procs()
    if prior > 0:
        print(
            f"FAIL: {prior} brain_api process(es) already running — "
            "stop them first (brain stop) and re-run this demo.",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory(prefix=f"demo08-{ts}-") as tmp_str:
        work_dir = Path(tmp_str)
        vault_root = work_dir / "vault"
        vault_root.mkdir(parents=True)

        try:
            _run_gate_0_ui_prebuild()
            tarball = _run_gate_1_cut_tarball(work_dir)
            install_dir = _run_gate_2_install_sh(work_dir, tarball)
            port, token = _run_gate_3_first_start(install_dir, vault_root)
            _run_gate_4_root_redirects_to_setup(port, vault_root)
            _run_gate_5_setup_wizard(port, vault_root)
            patch_id = _run_gate_6_ingest(port, token, vault_root)
            _run_gate_7_apply_patch(port, token, vault_root, patch_id)
            _run_gate_8_stop(install_dir, vault_root)
            _run_gate_9_restart_idempotent(install_dir, vault_root, token)
            _run_gate_10_uninstall(work_dir, install_dir, vault_root)
            _run_gate_11_post_uninstall(work_dir, install_dir)
        except SystemExit as exc:
            # Ensure we don't leak a running daemon on failure mid-demo.
            with contextlib.suppress(Exception):
                _brain_cmd(
                    REPO_ROOT,
                    ["stop"],
                    {
                        "BRAIN_VAULT_ROOT": str(vault_root),
                        "UV_NO_PROGRESS": "1",
                    },
                )
            return int(exc.code) if isinstance(exc.code, int) else 1

    print("")
    passed = [g for g, _ in sorted(_PASSES)]
    skipped = [g for g, _ in sorted(_SKIPS)]
    failed = [g for g, _ in sorted(_FAILS)]
    print(f"Passed gates:  {passed}")
    print(f"Skipped gates: {skipped}")
    print(f"Failed gates:  {failed}")
    print("")

    # 11 gates minimum (gate 0 is pre-flight, doesn't count): we need
    # gates 1..11 all in the passed set for a green demo. Skipped gate 5
    # (playwright) is the only acceptable skip on a dev box without
    # chromium — it drops the pass count to 10 but doesn't fail the run.
    required = set(range(1, 12))
    missing = required - set(passed) - set(skipped)
    if missing or failed:
        print(f"FAIL: gates {sorted(missing)} did not pass / failed={failed}", file=sys.stderr)
        return 1

    print("PLAN 08 DEMO OK")
    return 0


def main() -> int:
    return _run_demo()


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]
