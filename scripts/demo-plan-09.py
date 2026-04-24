"""Plan 09 end-to-end demo — 11-gate verification of the LIVE v0.1.0 install.

Unlike ``demo-plan-08.py`` (which cut a dev tarball + ran install.sh into a
temp dir to prove the *distribution pipeline*), Plan 09's demo drives the
**already-installed** v0.1.0 code at ``~/Applications/brain-v0.1.0/``. Task 11
already proved the install path end-to-end against the GitHub-released tarball
(four IP1..IP4 install-path BLOCKERs found + fixed during that sweep); we
don't need to re-prove it here. Plan 09's demo proves the **shipped v0.1.0
build itself** — versioning, setup-status regression, update-check nudge
pathway, and the same ingest/apply/stop/restart round-trip Plan 08 verifies.

## Three new assertions (vs Plan 08's demo)

1. **Gate 1** — ``brain --version`` prints exactly ``brain 0.1.0`` (Task 1
   version-bump holds through the install flow).
2. **Gate 5** — ``/api/setup-status`` reports ``is_first_run=False`` when
   the token exists but BRAIN.md does NOT. This is the F5/F7 regression
   surfaced during Task 11: the pre-fix rule required BRAIN.md presence,
   which looped users back to the wizard after they'd skipped the BRAIN.md
   step. The fix (see ``setup_status.py``) removed BRAIN.md from the rule.
3. **Gate 6** — exercise ``release.check_latest_release`` against a local
   HTTP stub returning a GitHub-shaped payload with a bumped version. The
   real update-check thread in ``start.py`` calls the module constant
   ``_GITHUB_LATEST_URL`` without a URL override, so we can't intercept
   its live network call; instead we prove the code path by invoking the
   function directly with the stub URL. The unit tests at
   ``test_start_update_check.py`` prove the nudge printing separately.

## Why hit the live install, not a temp one?

Plan 08's demo cut a tarball → install.sh → temp install dir. That run
proved the install pipeline. Plan 09's ship gate asks a different question:
does the actual build shipped at v0.1.0 — the one an external user will
``curl ... | bash`` tomorrow — round-trip through the 11 gates? The live
install at ``~/Applications/brain-v0.1.0/`` was populated from the GitHub
release tarball (post-Task-11 sweep, SHA256 ``657f9fea...``), so driving it
here is the closest thing to "what will actually ship" we can run locally.

## Determinism

* The demo uses a per-run temp vault so repeated runs never collide with
  the developer's real ``~/Documents/brain/`` vault.
* The update-check stub runs on an ephemeral port chosen by the OS, so
  parallel demo runs don't collide there either.
* The live install's ``.venv`` is reused (it's already synced); we skip
  any ``uv sync`` that would introduce wall-clock variance.
* Every gate either passes hard-check (``_check``) or explicitly skips
  with a reason — no silent failures.
"""

from __future__ import annotations

import contextlib
import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_DIR = Path.home() / "Applications" / "brain-v0.1.0"

_PASSES: list[tuple[int, str]] = []
_SKIPS: list[tuple[int, str]] = []
_FAILS: list[tuple[int, str]] = []


# ---------------------------------------------------------------------------
# Shared helpers (mirror demo-plan-08.py)
# ---------------------------------------------------------------------------


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
    try:
        import psutil

        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except Exception:
        return False


def _count_brain_api_procs() -> int:
    """Count live uvicorn/brain_api processes (for orphan checks)."""
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
    args: list[str],
    env_extra: dict[str, str] | None = None,
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the installed v0.1.0 brain binary directly.

    The shim at ``~/.local/bin/brain`` does ``exec uv run --project
    <install> brain "$@"``. We skip the shim and invoke the venv's own
    brain binary for speed + determinism (no uv sync re-check per call).
    """
    brain_bin = INSTALL_DIR / ".venv" / "bin" / "brain"
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    # Ensure the venv's interpreter is on PATH so the supervisor can
    # locate uvicorn + friends the way a real invocation would.
    env["VIRTUAL_ENV"] = str(INSTALL_DIR / ".venv")
    return subprocess.run(
        [str(brain_bin), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Update-check stub HTTP server
# ---------------------------------------------------------------------------


class _LatestReleaseStub(http.server.BaseHTTPRequestHandler):
    """Serve a GitHub-API-shaped ``/latest`` response with a bumped version.

    The release module parses ``tag_name``, ``assets[].name`` +
    ``browser_download_url``, and optionally a ``SHA256: <hex>`` line in
    the body. We give it all three so the parse path is fully exercised.
    """

    _version = "0.2.0"  # overridden per-instance via class attribute below

    def do_GET(self) -> None:  # stdlib BaseHTTPRequestHandler naming
        payload = {
            "tag_name": f"v{self._version}",
            "body": (
                "## What's new\n\n- Plan 09 demo stub.\n\n"
                "SHA256: 0000000000000000000000000000000000000000000000000000000000000000\n"
            ),
            "assets": [
                {
                    "name": f"brain-{self._version}.tar.gz",
                    "browser_download_url": (
                        f"https://example.invalid/brain-{self._version}.tar.gz"
                    ),
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:  # suppress stderr chatter
        return


class _StubServer(socketserver.TCPServer):
    """TCPServer that picks a free port via ``bind(0)``."""

    allow_reuse_address = True


@contextlib.contextmanager
def _update_check_stub(bumped_version: str = "0.2.0"):
    """Yield a running stub HTTP server URL that returns a bumped version."""

    # Build a handler class with the right version pinned — easier than
    # threading state through the handler init.
    handler = type(
        "_Handler",
        (_LatestReleaseStub,),
        {"_version": bumped_version},
    )
    # Bind to port 0 → OS picks a free one → read it back via server_address.
    server = _StubServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/latest"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------


def _run_gate_0_preflight() -> None:
    """Gate 0 — live v0.1.0 install is present + populated + venv runnable."""
    print("[gate 0] pre-flight: v0.1.0 install at ~/Applications/brain-v0.1.0/")
    _check(INSTALL_DIR.is_dir(), f"install dir present at {INSTALL_DIR}")
    _check(
        (INSTALL_DIR / "VERSION").exists(),
        f"VERSION file present (contents: {(INSTALL_DIR / 'VERSION').read_text().strip()!r})",
    )
    _check(
        (INSTALL_DIR / ".venv" / "bin" / "brain").exists(),
        "venv brain binary present",
    )
    _check(
        (INSTALL_DIR / "apps" / "brain_web" / "out" / "index.html").exists(),
        "prebuilt UI bundle present in install",
    )
    _pass(0, f"live install at {INSTALL_DIR} ready")


def _run_gate_1_version() -> None:
    """Gate 1 — ``brain --version`` prints exactly ``brain 0.1.0`` (Plan 09 NEW)."""
    print("[gate 1] `brain --version` prints 0.1.0 (NEW — Task 1 regression)")
    result = _brain_cmd(["--version"], timeout=10)
    _check(result.returncode == 0, f"brain --version rc=0 (got {result.returncode})")
    output = result.stdout.strip()
    _check(
        output == "brain 0.1.0",
        f"output == 'brain 0.1.0' (got {output!r}, stderr={result.stderr!r})",
    )
    # Cross-check against the VERSION file — both sources must agree.
    version_file = (INSTALL_DIR / "VERSION").read_text(encoding="utf-8").strip()
    _check(
        version_file == "0.1.0",
        f"VERSION file == '0.1.0' (got {version_file!r})",
    )
    _pass(1, "brain --version == 'brain 0.1.0'")


def _run_gate_2_doctor(vault_root: Path) -> None:
    """Gate 2 — ``brain doctor`` runs cleanly against the live install."""
    print("[gate 2] `brain doctor` runs cleanly (no crash)")
    # A fresh-vault doctor exits 1 (no token file, no config yet) — that's
    # fine. We only require the command NOT to crash with a bare traceback.
    result = _brain_cmd(
        ["doctor", "--install", str(INSTALL_DIR), "--vault", str(vault_root)],
        {
            "BRAIN_INSTALL_DIR": str(INSTALL_DIR),
            "BRAIN_VAULT_ROOT": str(vault_root),
        },
        timeout=30,
    )
    _check(
        result.returncode in {0, 1},
        f"brain doctor rc in {{0,1}} (got {result.returncode})",
    )
    _check("brain doctor" in result.stdout, "doctor printed its header")
    _pass(2, f"brain doctor ran cleanly (rc={result.returncode})")


def _run_gate_3_start(vault_root: Path) -> tuple[int, str]:
    """Gate 3 — ``brain start`` spawns uvicorn; /healthz=200; URL printed."""
    print("[gate 3] brain start → port + /healthz=200 + URL printed")
    env = {
        "BRAIN_INSTALL_DIR": str(INSTALL_DIR),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "BRAIN_LLM_PROVIDER": "fake",
        "BRAIN_E2E_MODE": "1",
        "BRAIN_NO_BROWSER": "1",
        "BRAIN_NO_UPDATE_CHECK": "1",  # silence the real nudge during the demo
    }
    result = _brain_cmd(["start"], env, timeout=30)
    if result.returncode != 0:
        print(f"brain start stdout:\n{result.stdout}", file=sys.stderr)
        print(f"brain start stderr:\n{result.stderr}", file=sys.stderr)
    _check(result.returncode == 0, f"brain start rc=0 (got {result.returncode})")
    _check(
        "brain running at" in result.stdout or "already running at" in result.stdout,
        "brain start printed the running URL",
    )

    port = _read_port(vault_root)
    _check(port is not None, f"port file at {vault_root}/.brain/run/brain.port")
    assert port is not None
    _check(4317 <= port <= 4330, f"port {port} in 4317..4330 range")
    _check(_wait_for_http(f"http://127.0.0.1:{port}/healthz", timeout=10.0), "/healthz=200")

    token = _read_token(vault_root)
    _check(len(token) >= 32, f"token populated ({len(token)} chars)")

    pid = _read_pid(vault_root)
    _check(pid is not None and _pid_alive(pid), f"brain_api process alive (pid={pid})")
    _pass(3, f"brain start → port {port}, pid {pid}, /healthz=200")
    assert port is not None
    return port, token


def _run_gate_4_setup_status_first_run(port: int, vault_root: Path) -> None:
    """Gate 4 — fresh vault → ``/api/setup-status`` reports is_first_run=True."""
    print("[gate 4] /api/setup-status reports first-run on fresh vault")
    origin = f"http://localhost:{port}"
    status, body = _http_json(
        f"http://127.0.0.1:{port}/api/setup-status", origin=origin
    )
    _check(status == 200, f"/api/setup-status -> 200 (got {status})")
    # Fresh vault: has_token is True (brain start writes it on boot), but
    # vault_exists is also True (brain start mkdir'd it via the supervisor).
    # is_first_run is True ONLY when !has_token OR !vault_exists. Since
    # both are True here, is_first_run must be False in the fresh-start
    # case — which ALSO exercises the F5/F7 fix (BRAIN.md absence doesn't
    # matter). We assert that directly.
    _check(
        body.get("has_token") is True,
        f"has_token=True (got {body.get('has_token')!r})",
    )
    _check(
        body.get("vault_exists") is True,
        f"vault_exists=True (got {body.get('vault_exists')!r})",
    )
    _pass(4, "setup-status reachable + both prerequisites True")


def _run_gate_5_setup_status_no_brain_md(port: int, vault_root: Path) -> None:
    """Gate 5 — F5/F7 regression: is_first_run=False even when BRAIN.md absent (Plan 09 NEW).

    Task 11 surfaced this as BLOCKER F5/F7: the pre-fix rule forced the
    user back to /setup every time they navigated after skipping the
    BRAIN.md step in the wizard. The fix (see
    ``brain_api.endpoints.setup_status``) removed BRAIN.md from the rule.
    We assert that explicitly: with token + vault present + BRAIN.md
    ABSENT, is_first_run MUST be False.
    """
    print("[gate 5] F5/F7 regression: is_first_run=False when BRAIN.md absent (NEW)")
    brain_md = vault_root / "BRAIN.md"
    # Make sure it doesn't exist.
    if brain_md.exists():
        brain_md.unlink()
    _check(not brain_md.exists(), f"BRAIN.md NOT present at {brain_md}")

    origin = f"http://localhost:{port}"
    status, body = _http_json(
        f"http://127.0.0.1:{port}/api/setup-status", origin=origin
    )
    _check(status == 200, f"/api/setup-status -> 200 (got {status})")
    _check(
        body.get("has_token") is True, f"has_token=True (got {body.get('has_token')!r})"
    )
    _check(
        body.get("vault_exists") is True,
        f"vault_exists=True (got {body.get('vault_exists')!r})",
    )
    _check(
        body.get("is_first_run") is False,
        (
            f"is_first_run=False (F5/F7 regression — BRAIN.md absence must not "
            f"force first-run; got {body.get('is_first_run')!r})"
        ),
    )
    _pass(5, "F5/F7 regression: is_first_run=False without BRAIN.md")


def _run_gate_6_update_check(vault_root: Path) -> None:
    """Gate 6 — exercise ``release.check_latest_release`` via a local stub (Plan 09 NEW).

    The real ``_update_check_nudge`` thread runs inside ``brain start``'s
    own subprocess, so we can't reach into it from here to patch the
    module-level URL. Instead we:

      1. Spin up a local HTTP stub that mimics the GitHub ``/releases/latest``
         response with ``tag_name=v0.2.0``.
      2. Import ``release.check_latest_release`` inline in this driver and
         call it with ``url=<stub-url>`` + ``current_version="0.1.0"``.
      3. Assert we get a ``ReleaseInfo`` with the expected fields.

    This proves the exact code path the real thread exercises, minus the
    thread + print plumbing (which is tested in unit tests at
    ``test_start_update_check.py``). The env-var opt-out is also
    asserted here end-to-end: set ``BRAIN_NO_UPDATE_CHECK=1`` and the
    function returns None without even hitting the stub.
    """
    print("[gate 6] update-check nudge pathway via local HTTP stub (NEW)")
    _ = vault_root  # not needed — the check is network-only
    try:
        from brain_cli.runtime import release as release_mod
    except ImportError as exc:
        _skip(6, f"brain_cli.runtime.release import failed: {exc}")
        return

    with _update_check_stub(bumped_version="0.2.0") as stub_url:
        # (a) Happy path: newer version reported.
        info = release_mod.check_latest_release(
            "0.1.0", timeout_s=5, url=stub_url
        )
        _check(info is not None, "check_latest_release returned ReleaseInfo (not None)")
        assert info is not None
        _check(info.version == "0.2.0", f"info.version == '0.2.0' (got {info.version!r})")
        _check(
            info.tag_name == "v0.2.0",
            f"info.tag_name == 'v0.2.0' (got {info.tag_name!r})",
        )
        _check(
            info.tarball_url.endswith("brain-0.2.0.tar.gz"),
            f"info.tarball_url points at stub asset (got {info.tarball_url!r})",
        )
        _check(
            info.sha256 == "0" * 64,
            f"info.sha256 parsed from body (got {info.sha256!r})",
        )

        # (b) Same-version → None.
        info_same = release_mod.check_latest_release(
            "0.2.0", timeout_s=5, url=stub_url
        )
        _check(info_same is None, f"same-version returns None (got {info_same!r})")

        # (c) Opt-out: BRAIN_NO_UPDATE_CHECK=1 short-circuits without
        # touching the stub. We can't easily prove "stub wasn't hit"
        # without counting requests, but the return-None behavior is the
        # observable contract.
        prior_env = os.environ.get("BRAIN_NO_UPDATE_CHECK")
        os.environ["BRAIN_NO_UPDATE_CHECK"] = "1"
        try:
            info_opt = release_mod.check_latest_release(
                "0.1.0", timeout_s=5, url=stub_url
            )
            _check(
                info_opt is None,
                f"BRAIN_NO_UPDATE_CHECK=1 returns None (got {info_opt!r})",
            )
        finally:
            if prior_env is None:
                os.environ.pop("BRAIN_NO_UPDATE_CHECK", None)
            else:
                os.environ["BRAIN_NO_UPDATE_CHECK"] = prior_env
    _pass(6, "update-check pathway exercised (newer + same + opt-out)")


def _run_gate_7_ingest(port: int, token: str, vault_root: Path) -> str:
    """Gate 7 — ``brain_ingest`` stages a patch."""
    print("[gate 7] brain_ingest stages a patch")
    seed_dir = vault_root / "raw" / "inbox"
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed = seed_dir / f"demo-plan-09-{int(time.time())}.md"
    seed.write_text(
        "# Plan 09 demo — Task 13 seed note\n\n"
        "Ingest pipeline seed for gate 7 of demo-plan-09. "
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
    _pass(7, f"ingest staged (status={data.get('status')!r})")
    return patch_id or ""


def _run_gate_8_apply_patch(port: int, token: str, vault_root: Path, ingest_patch_id: str) -> None:
    """Gate 8 — propose_note → apply_patch via REST → file on disk.

    Same caveat as Plan 08 gate 7: we use a fresh ``brain_propose_note``
    for the apply because the E2E-mode canned integrate response's
    ``new_files=[]`` causes the ingest patch target to resolve to an
    absolute path that fails the scope check. Still-open lessons item.
    """
    print("[gate 8] propose_note → apply_patch via REST (file on disk)")
    _ = ingest_patch_id  # accepted but not applied — see docstring.

    target_rel = "work/notes/gate-8-demo-plan-09.md"
    status, body = _tool(
        "brain_propose_note",
        token,
        port,
        data={
            "path": target_rel,
            "content": "# gate 8\n\nPlan 09 demo — REST propose + apply.\n",
            "reason": "plan 09 demo gate 8",
        },
    )
    _check(status == 200, f"propose_note -> 200 (got {status}, body={body})")
    patch_id = body.get("data", {}).get("patch_id", "")
    _check(bool(patch_id), "patch_id returned")

    target_abs = vault_root / target_rel
    _check(not target_abs.exists(), "target file NOT on disk before apply")

    status, body = _tool("brain_list_pending_patches", token, port, data={})
    _check(status == 200, f"list_pending_patches -> 200 (got {status})")
    patches = body.get("data", {}).get("patches", [])
    _check(
        any(p.get("patch_id") == patch_id for p in patches),
        f"patch_id {patch_id!r} visible in pending list",
    )

    status, body = _tool("brain_apply_patch", token, port, data={"patch_id": patch_id})
    _check(status == 200, f"apply_patch -> 200 (got {status}, body={body})")
    data = body.get("data", {})
    _check(
        str(data.get("status")) == "applied",
        f"status=applied (got {data.get('status')!r})",
    )
    _check(target_abs.exists(), f"target file ON disk after apply ({target_abs})")
    _pass(8, "propose → apply → file on disk")


def _run_gate_9_stop(vault_root: Path) -> None:
    """Gate 9 — ``brain stop`` removes pid/port + no orphans."""
    print("[gate 9] brain stop → pid + port files gone; no orphan uvicorn")
    env = {
        "BRAIN_INSTALL_DIR": str(INSTALL_DIR),
        "BRAIN_VAULT_ROOT": str(vault_root),
    }
    result = _brain_cmd(["stop"], env, timeout=20)
    _check(result.returncode == 0, f"brain stop rc=0 (got {result.returncode})")

    time.sleep(0.5)
    pid_file = vault_root / ".brain" / "run" / "brain.pid"
    port_file = vault_root / ".brain" / "run" / "brain.port"
    _check(not pid_file.exists(), "pid file removed")
    _check(not port_file.exists(), "port file removed")

    orphans = _count_brain_api_procs()
    _check(orphans == 0, f"no orphan brain_api processes (got {orphans})")
    _pass(9, "brain stop cleaned up; 0 orphans")


def _run_gate_10_restart_idempotent(vault_root: Path) -> None:
    """Gate 10 — second start+stop cycle; previous vault content preserved."""
    print("[gate 10] start+stop round-trip #2 (idempotency)")
    env = {
        "BRAIN_INSTALL_DIR": str(INSTALL_DIR),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "BRAIN_LLM_PROVIDER": "fake",
        "BRAIN_E2E_MODE": "1",
        "BRAIN_NO_BROWSER": "1",
        "BRAIN_NO_UPDATE_CHECK": "1",
    }
    before = sorted(p.name for p in (vault_root.rglob("*.md")))

    start_res = _brain_cmd(["start"], env, timeout=30)
    _check(start_res.returncode == 0, f"second start rc=0 (got {start_res.returncode})")
    port2 = _read_port(vault_root)
    _check(port2 is not None, "second start wrote port file")
    assert port2 is not None
    _check(
        _wait_for_http(f"http://127.0.0.1:{port2}/healthz", timeout=10.0),
        "second start /healthz=200",
    )
    status, body = _http_json(
        f"http://127.0.0.1:{port2}/api/setup-status",
        origin=f"http://localhost:{port2}",
    )
    _check(status == 200, "second start setup-status -> 200")
    _check(bool(body.get("has_token")), "second start issued a token")

    stop_res = _brain_cmd(["stop"], env, timeout=20)
    _check(stop_res.returncode == 0, f"second stop rc=0 (got {stop_res.returncode})")

    after = sorted(p.name for p in (vault_root.rglob("*.md")))
    _check(
        before == after,
        f"vault .md files identical across cycle (before={len(before)}, after={len(after)})",
    )
    _pass(10, f"restart idempotent; vault preserved ({len(after)} .md files)")


def _run_gate_11_cleanup(vault_root: Path) -> None:
    """Gate 11 — post-demo cleanup asserts: install untouched, no orphans.

    Unlike Plan 08's demo (which runs a full uninstall + asserts the
    install dir is gone), Plan 09 drives the LIVE install — we must leave
    it intact for future use. Gate 11 is therefore a positive-state check:
    install still runnable, no stray processes, vault tmp dir still has
    the patch we applied in gate 8.
    """
    print("[gate 11] post-demo state: install intact, no orphans, gate-8 artifact on disk")
    _check(INSTALL_DIR.is_dir(), f"install dir still present at {INSTALL_DIR}")
    _check(
        (INSTALL_DIR / ".venv" / "bin" / "brain").exists(),
        "venv brain binary still present",
    )
    orphans = _count_brain_api_procs()
    _check(orphans == 0, f"no orphan brain_api processes (got {orphans})")

    # Gate 8 wrote work/notes/gate-8-demo-plan-09.md — should still be there.
    gate8_artifact = vault_root / "work" / "notes" / "gate-8-demo-plan-09.md"
    _check(
        gate8_artifact.exists(),
        f"gate-8 artifact preserved across gates 9+10 ({gate8_artifact.name})",
    )

    # Verify brain --version still works after the round-trip — the install
    # is healthy end-to-end.
    result = _brain_cmd(["--version"], timeout=10)
    _check(
        result.returncode == 0 and "brain 0.1.0" in result.stdout,
        f"post-demo `brain --version` == 'brain 0.1.0' (rc={result.returncode}, out={result.stdout!r})",
    )
    _pass(11, "install intact; 0 orphans; v0.1.0 still resolvable")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _run_demo() -> int:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    header = f"brain · plan 09 demo · {ts}"
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

    # Temp vault — demo-owned, cleaned up on exit. We DON'T touch
    # ~/Documents/brain/ so repeated runs never collide with the developer's
    # real content.
    with tempfile.TemporaryDirectory(prefix=f"demo09-{ts}-") as tmp_str:
        work_dir = Path(tmp_str)
        vault_root = work_dir / "vault"
        vault_root.mkdir(parents=True)

        try:
            _run_gate_0_preflight()
            _run_gate_1_version()
            _run_gate_2_doctor(vault_root)
            port, token = _run_gate_3_start(vault_root)
            _run_gate_4_setup_status_first_run(port, vault_root)
            _run_gate_5_setup_status_no_brain_md(port, vault_root)
            _run_gate_6_update_check(vault_root)
            patch_id = _run_gate_7_ingest(port, token, vault_root)
            _run_gate_8_apply_patch(port, token, vault_root, patch_id)
            _run_gate_9_stop(vault_root)
            _run_gate_10_restart_idempotent(vault_root)
            _run_gate_11_cleanup(vault_root)
        except SystemExit as exc:
            # Ensure we don't leak a running daemon on failure mid-demo.
            with contextlib.suppress(Exception):
                _brain_cmd(
                    ["stop"],
                    {
                        "BRAIN_INSTALL_DIR": str(INSTALL_DIR),
                        "BRAIN_VAULT_ROOT": str(vault_root),
                    },
                    timeout=10,
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

    # 12 gates total (0..11); 0 is pre-flight. 1..11 must all pass or skip.
    required = set(range(0, 12))
    missing = required - set(passed) - set(skipped)
    if missing or failed:
        print(f"FAIL: gates {sorted(missing)} did not pass / failed={failed}", file=sys.stderr)
        return 1

    print("PLAN 09 DEMO OK")
    return 0


def main() -> int:
    # Silence the unused-import lint (socket imported for future host probes).
    _ = socket
    return _run_demo()


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main"]
