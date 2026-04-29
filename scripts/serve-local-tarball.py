"""Serve a local brain tarball + install scripts to a VM on the LAN.

Plan 08 Task 10 + 11. Harness for the clean-Mac / clean-Windows VM dry
runs: the host machine runs this script to publish:

    - ``brain-dev-<sha>.tar.gz``   (cut via ``cut_local_tarball.py``)
    - ``brain-dev-<sha>.tar.gz.sha256``
    - ``install.sh``                (copied from ``scripts/install.sh``)
    - ``install.ps1``               (copied from ``scripts/install.ps1``)
    - ``manifest.json``             (machine-readable pointer for scripted flows)

over plain HTTP on the host's LAN. Inside the VM, the tester runs a
single copy-paste command pointed at the host IP and walks through a
real install round-trip.

Usage
-----

    # Happy path: cut a fresh tarball + serve on port 9000.
    python scripts/serve-local-tarball.py

    # Serve an existing tarball (skip the cut step).
    python scripts/serve-local-tarball.py --tarball dist/brain-dev-abc123.tar.gz

    # Custom port.
    python scripts/serve-local-tarball.py --port 19000

    # Dry run: print what would be served, don't bind.
    python scripts/serve-local-tarball.py --dry-run

The server binds ``0.0.0.0`` so a VM reachable on the host's LAN (or
via a VM-host-only network, as Tart + UTM both offer) can curl/irm it.
Ctrl+C shuts the server down cleanly and removes the staging directory.

No third-party deps. Everything is stdlib so this script runs on a
fresh macOS / Windows box with no extra setup.
"""

from __future__ import annotations

import argparse
import contextlib
import ipaddress
import json
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_PORT = 9000


# ---------------------------------------------------------------------------
# Host IP discovery
# ---------------------------------------------------------------------------


def _iter_candidate_ips() -> list[str]:
    """Return a list of IPv4 addresses that a VM might reach us on.

    Strategy (stdlib-only, cross-platform):

      1. ``socket.gethostbyname_ex`` — works on Mac + Linux; often empty
         on Windows but never raises.
      2. UDP "connect" trick — open a datagram socket toward a public
         IP without actually sending, read back ``getsockname`` to find
         the default-route interface.
      3. Parse ``ifconfig`` / ``ipconfig`` output as plain strings —
         picks up host-only + bridged VM interfaces that the other two
         may miss.

    Dedup + preserve order. Always include ``127.0.0.1`` last as a
    fallback for single-host demos.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(ip: str) -> None:
        ip = ip.strip()
        if not ip:
            return
        try:
            # Reject IPv6 + garbage. VM flows only care about v4.
            ipaddress.IPv4Address(ip)
        except (ipaddress.AddressValueError, ValueError):
            return
        if ip in seen:
            return
        seen.add(ip)
        ordered.append(ip)

    # 1. Hostname-based lookup (fastest, often useful on Mac).
    try:
        _hostname, _aliases, addrs = socket.gethostbyname_ex(socket.gethostname())
        for a in addrs:
            _add(a)
    except OSError:
        pass

    # 2. UDP default-route trick.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 203.0.113.1 is TEST-NET-3 — routable, never actually reached.
            s.connect(("203.0.113.1", 80))
            _add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass

    # 3. Parse ifconfig / ipconfig. Best-effort: helps surface host-only
    # adapters that neither (1) nor (2) picks up.
    for ip in _parse_ifconfig_like_output():
        _add(ip)

    _add("127.0.0.1")
    return ordered


def _parse_ifconfig_like_output() -> list[str]:
    """Run ``ifconfig`` (Unix) or ``ipconfig`` (Windows); yield IPv4s."""
    if sys.platform.startswith("win"):
        cmd = ["ipconfig"]
    else:
        # ``ifconfig`` may not be on PATH on minimal Linux images; try
        # ``ip addr`` as a fallback so we don't explode.
        cmd = ["ifconfig"] if shutil.which("ifconfig") else ["ip", "addr"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    text = (result.stdout or "") + "\n" + (result.stderr or "")
    # Only take the address following an ``inet`` / ``IPv4 Address`` marker
    # so we skip netmasks, broadcasts, and subnet prefixes like ``/24``.
    # On macOS + BSD: ``inet 192.168.1.42 netmask 0xffffff00 broadcast ...``
    # On Linux:       ``inet 192.168.1.42/24 brd 192.168.1.255 scope ...``
    # On Windows:     ``IPv4 Address. . . . . . . . . . . : 192.168.1.42``
    patterns = [
        re.compile(r"\binet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
        re.compile(r"IPv4 Address[^:]*:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
    ]
    found: list[str] = []
    for pat in patterns:
        found.extend(pat.findall(text))
    return found


# ---------------------------------------------------------------------------
# Staging: collect everything that needs serving into one flat dir
# ---------------------------------------------------------------------------


def _cut_tarball(staging_dir: Path) -> Path:
    """Invoke cut_local_tarball.py and return the path of the .tar.gz.

    We call the sibling script via ``subprocess.run`` instead of
    importing it so the behavior stays identical to what the user
    would run by hand.
    """
    cut_script = SCRIPTS_DIR / "cut_local_tarball.py"
    if not cut_script.exists():
        raise FileNotFoundError(f"cut_local_tarball.py not found at {cut_script}")

    dist_dir = staging_dir / "_cut"
    dist_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [sys.executable, str(cut_script), str(dist_dir)],
        check=True,
        cwd=REPO_ROOT,
    )

    tarballs = sorted(dist_dir.glob("brain-dev-*.tar.gz"))
    if not tarballs:
        raise RuntimeError(f"cut_local_tarball.py produced no brain-dev-*.tar.gz in {dist_dir}")
    # If the cut script emitted more than one (shouldn't), take the newest.
    return tarballs[-1]


def _read_sha256_sidecar(tarball: Path) -> str:
    """Read the ``<tarball>.sha256`` sidecar written by cut_local_tarball.py."""
    sidecar = tarball.with_suffix(tarball.suffix + ".sha256")
    if not sidecar.exists():
        # Fallback: compute it ourselves so serve still works if the
        # sidecar was missed.
        import hashlib

        h = hashlib.sha256()
        with tarball.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()

    line = sidecar.read_text(encoding="utf-8").strip()
    # Sidecar format is ``<sha256>  <filename>\n`` (``shasum`` style).
    return line.split()[0]


def _stage_files(
    staging_dir: Path,
    tarball: Path,
    sha256: str,
    host_ips: list[str],
    port: int,
) -> dict[str, Any]:
    """Copy the tarball + install scripts into staging + write manifest.

    Returns the manifest dict so the caller can print a nice summary.
    """
    install_sh = SCRIPTS_DIR / "install.sh"
    install_ps1 = SCRIPTS_DIR / "install.ps1"
    install_lib = SCRIPTS_DIR / "install_lib"

    if not install_sh.exists():
        raise FileNotFoundError(f"install.sh not found at {install_sh}")
    if not install_ps1.exists():
        raise FileNotFoundError(f"install.ps1 not found at {install_ps1}")
    if not install_lib.exists():
        raise FileNotFoundError(f"install_lib/ not found at {install_lib}")

    # Flat layout served at the root of the HTTP server.
    served_tarball_name = "brain-dev.tar.gz"
    shutil.copy2(tarball, staging_dir / served_tarball_name)
    shutil.copy2(install_sh, staging_dir / "install.sh")
    shutil.copy2(install_ps1, staging_dir / "install.ps1")

    # The install scripts look for ``install_lib/`` as a sibling of the
    # install.sh/.ps1 file they were invoked from. Mirror that.
    shutil.copytree(install_lib, staging_dir / "install_lib", dirs_exist_ok=True)

    # Write the sidecar too for humans + scripts that want it.
    (staging_dir / f"{served_tarball_name}.sha256").write_text(
        f"{sha256}  {served_tarball_name}\n",
        encoding="utf-8",
    )

    # Primary IP — first non-loopback if any, else loopback.
    primary = next((ip for ip in host_ips if ip != "127.0.0.1"), "127.0.0.1")

    manifest: dict[str, Any] = {
        "version": "plan-08-dryrun",
        "tarball_filename": served_tarball_name,
        "tarball_sha256": sha256,
        "install_sh": "install.sh",
        "install_ps1": "install.ps1",
        "primary_host_ip": primary,
        "host_ips": host_ips,
        "port": port,
        "tarball_url": f"http://{primary}:{port}/{served_tarball_name}",
        "install_sh_url": f"http://{primary}:{port}/install.sh",
        "install_ps1_url": f"http://{primary}:{port}/install.ps1",
    }
    (staging_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------


class _QuietHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with a less-noisy log format."""

    # Set by serve_staging() before we hand the class to the server.
    _serve_dir: str = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=self._serve_dir, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Match access-log style used by most dev servers: just the
        # status + path. Keeps the terminal readable during a live run.
        sys.stderr.write(
            f"[{self.log_date_time_string()}] {self.address_string()} {format % args}\n"
        )


def _make_handler_class(serve_dir: Path) -> type[_QuietHandler]:
    """Build a handler class bound to ``serve_dir`` (subclass trick).

    We can't just pass ``directory=`` through ThreadingHTTPServer's
    constructor because the server instantiates the handler per-request
    with only ``(request, client_address, server)``.
    """
    cls_dict = {"_serve_dir": str(serve_dir)}
    return type("_BoundHandler", (_QuietHandler,), cls_dict)


def _run_server(serve_dir: Path, port: int) -> None:
    """Bind + serve until SIGINT."""
    handler_cls = _make_handler_class(serve_dir)
    server = ThreadingHTTPServer(("0.0.0.0", port), handler_cls)

    # SIGINT → clean shutdown. Windows does support SIGINT in console apps,
    # and signal.signal in the main thread is portable enough for this harness.
    stop_event = threading.Event()

    def _handle_sigint(_signum: int, _frame: Any) -> None:
        if not stop_event.is_set():
            stop_event.set()
            # Run shutdown in a background thread: server.shutdown blocks
            # until the serve loop exits, and the serve loop runs here.
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _handle_sigint)
    # SIGTERM isn't defined on Windows in every Python build.
    with contextlib.suppress(ValueError, AttributeError):
        signal.signal(signal.SIGTERM, _handle_sigint)

    sys.stderr.write(f"serving {serve_dir} on http://0.0.0.0:{port}/  (Ctrl+C to stop)\n")
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        sys.stderr.write("server stopped.\n")


# ---------------------------------------------------------------------------
# Reachability summary printer
# ---------------------------------------------------------------------------


def _print_summary(
    staging_dir: Path,
    manifest: dict[str, Any],
    host_ips: list[str],
    port: int,
) -> None:
    sys.stdout.write("\n")
    sys.stdout.write("=" * 72 + "\n")
    sys.stdout.write(" brain install harness — ready to serve\n")
    sys.stdout.write("=" * 72 + "\n")
    sys.stdout.write(f"  staging dir:     {staging_dir}\n")
    sys.stdout.write(f"  port:            {port}\n")
    sys.stdout.write(f"  tarball sha256:  {manifest['tarball_sha256']}\n")
    sys.stdout.write("\n  reachable URLs (try each from the VM):\n")
    for ip in host_ips:
        sys.stdout.write(f"    http://{ip}:{port}/install.sh\n")
        sys.stdout.write(f"    http://{ip}:{port}/install.ps1\n")
        sys.stdout.write(f"    http://{ip}:{port}/{manifest['tarball_filename']}\n")
        sys.stdout.write("\n")
    primary = manifest["primary_host_ip"]
    sys.stdout.write("  VM copy-paste (Mac):\n")
    sys.stdout.write(
        f"    HOST_IP={primary}\n"
        f'    curl -fsSL "http://${{HOST_IP}}:{port}/install.sh" -o install.sh\n'
        f'    BRAIN_RELEASE_URL="http://${{HOST_IP}}:{port}/brain-dev.tar.gz" \\\n'
        f"      bash install.sh\n\n"
    )
    sys.stdout.write("  VM copy-paste (Windows PowerShell):\n")
    sys.stdout.write(
        f"    $HOST_IP = '{primary}'\n"
        f'    iwr "http://${{HOST_IP}}:{port}/install.ps1" -OutFile install.ps1\n'
        f'    $env:BRAIN_RELEASE_URL = "http://${{HOST_IP}}:{port}/brain-dev.tar.gz"\n'
        f"    powershell.exe -ExecutionPolicy Bypass -File .\\install.ps1\n\n"
    )
    sys.stdout.write("=" * 72 + "\n\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Argparse parser — split out so tests can exercise it in isolation."""
    p = argparse.ArgumentParser(
        prog="serve-local-tarball.py",
        description=(
            "Serve a brain tarball + install scripts over HTTP on the LAN "
            "for clean-VM dry runs (Plan 08 Tasks 10+11)."
        ),
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port to bind (default: {DEFAULT_PORT})",
    )
    p.add_argument(
        "--tarball",
        type=Path,
        default=None,
        help=("Path to a prebuilt brain-*.tar.gz. If omitted, cut a fresh tarball from git HEAD."),
    )
    p.add_argument(
        "--sha256",
        type=str,
        default=None,
        help=(
            "SHA256 of --tarball (hex). If omitted, we either read a sibling .sha256 or compute it."
        ),
    )
    p.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        help=("Where to stage served files. Default: a fresh tempdir, cleaned up on exit."),
    )
    p.add_argument(
        "--keep-staging",
        action="store_true",
        help="Don't delete the staging dir on exit (useful for debugging).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Stage files + print summary, but don't bind the HTTP port.",
    )
    return p


def _stage_and_summarize(args: argparse.Namespace) -> tuple[Path, dict[str, Any], bool]:
    """Stage the serve dir + return (staging_dir, manifest, we_own_cleanup).

    Shared between the live-serve path and ``--dry-run`` so both exercise
    identical staging logic.
    """
    if args.staging_dir is not None:
        staging_dir = args.staging_dir
        staging_dir.mkdir(parents=True, exist_ok=True)
        we_own_cleanup = False
    else:
        staging_dir = Path(tempfile.mkdtemp(prefix="brain-serve-"))
        we_own_cleanup = True

    if args.tarball is not None:
        tarball = args.tarball.resolve()
        if not tarball.exists():
            raise FileNotFoundError(f"tarball not found: {tarball}")
        sha256 = args.sha256 or _read_sha256_sidecar(tarball)
    else:
        tarball = _cut_tarball(staging_dir)
        sha256 = _read_sha256_sidecar(tarball)

    host_ips = _iter_candidate_ips()
    manifest = _stage_files(staging_dir, tarball, sha256, host_ips, args.port)
    return staging_dir, manifest, we_own_cleanup


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.port < 1 or args.port > 65535:
        parser.error(f"--port must be 1..65535 (got {args.port})")

    try:
        staging_dir, manifest, we_own_cleanup = _stage_and_summarize(args)
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    host_ips = manifest["host_ips"]
    try:
        _print_summary(staging_dir, manifest, host_ips, args.port)

        if args.dry_run:
            sys.stdout.write("--dry-run set; skipping HTTP bind.\n")
            return 0

        _run_server(staging_dir, args.port)
        return 0
    finally:
        if we_own_cleanup and not args.keep_staging:
            shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
