"""Unit tests for ``scripts/serve-local-tarball.py`` (Plan 08 Task 10+11).

Scope: exercise the staging logic + manifest generation + CLI parsing
without ever binding the real HTTP port. The live serve path is
covered by the manual VM dry run — automating it would tie tests to
network config that flickers in CI.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SERVE_SCRIPT = SCRIPTS_DIR / "serve-local-tarball.py"


def _load_serve_module() -> object:
    """Import the hyphenated script file as a Python module.

    ``serve-local-tarball.py`` isn't a valid package name, so standard
    ``import`` can't reach it. We use ``importlib.util.spec_from_file_location``
    to load it by path — same trick Python's own test runner uses for
    script-style entry points.
    """
    spec = importlib.util.spec_from_file_location(
        "serve_local_tarball", str(SERVE_SCRIPT)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def serve_mod() -> object:
    return _load_serve_module()


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def test_parser_defaults(serve_mod: object) -> None:
    parser = serve_mod.build_parser()  # type: ignore[attr-defined]
    ns = parser.parse_args([])
    assert ns.port == serve_mod.DEFAULT_PORT  # type: ignore[attr-defined]
    assert ns.tarball is None
    assert ns.sha256 is None
    assert ns.staging_dir is None
    assert ns.dry_run is False
    assert ns.keep_staging is False


def test_parser_custom_port(serve_mod: object) -> None:
    parser = serve_mod.build_parser()  # type: ignore[attr-defined]
    ns = parser.parse_args(["--port", "19000"])
    assert ns.port == 19000


def test_parser_reject_out_of_range_port(serve_mod: object) -> None:
    # main() is the one that validates the range; the parser itself
    # accepts any int. Call main() with a bogus port and expect exit=2.
    with pytest.raises(SystemExit) as excinfo:
        serve_mod.main(["--port", "70000"])  # type: ignore[attr-defined]
    # argparse's parser.error() exits with code 2.
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# Staging + manifest
# ---------------------------------------------------------------------------


def test_dry_run_stages_and_writes_manifest(
    serve_mod: object, tmp_path: Path
) -> None:
    """--dry-run: full staging path (real git archive), no HTTP bind.

    We point --staging-dir at a tmp_path so we can inspect the output.
    """
    staging = tmp_path / "staging"
    rc = serve_mod.main(  # type: ignore[attr-defined]
        [
            "--dry-run",
            "--staging-dir",
            str(staging),
            "--port",
            "19001",
        ]
    )
    assert rc == 0

    # Files the VM would fetch.
    assert (staging / "brain-dev.tar.gz").is_file()
    assert (staging / "brain-dev.tar.gz.sha256").is_file()
    assert (staging / "install.sh").is_file()
    assert (staging / "install.ps1").is_file()
    # install_lib/ is served as a sibling dir so install.sh/.ps1 find it.
    assert (staging / "install_lib").is_dir()
    assert (staging / "install_lib" / "fetch_tarball.sh").is_file()
    assert (staging / "install_lib" / "fetch_tarball.ps1").is_file()

    # Manifest shape.
    manifest = json.loads((staging / "manifest.json").read_text())
    assert manifest["tarball_filename"] == "brain-dev.tar.gz"
    assert len(manifest["tarball_sha256"]) == 64  # hex sha256
    assert manifest["port"] == 19001
    assert manifest["install_sh"] == "install.sh"
    assert manifest["install_ps1"] == "install.ps1"
    assert manifest["tarball_url"].startswith("http://")
    assert manifest["tarball_url"].endswith(":19001/brain-dev.tar.gz")
    assert manifest["install_sh_url"].endswith(":19001/install.sh")
    assert manifest["install_ps1_url"].endswith(":19001/install.ps1")
    assert isinstance(manifest["host_ips"], list)
    assert manifest["primary_host_ip"] in manifest["host_ips"]
    # Tarball bytes match the sidecar hash.
    sidecar = (staging / "brain-dev.tar.gz.sha256").read_text().strip().split()[0]
    assert sidecar == manifest["tarball_sha256"]


def test_dry_run_with_prebuilt_tarball(
    serve_mod: object, tmp_path: Path
) -> None:
    """--tarball <path>: skip the cut step + reuse a prebuilt archive."""
    # Fake tarball — contents don't matter for staging, only the path.
    fake_tarball = tmp_path / "prebuilt.tar.gz"
    fake_tarball.write_bytes(b"not-really-a-tarball-but-fine-for-staging")
    # Sidecar in shasum format.
    expected_sha = "a" * 64
    fake_tarball.with_suffix(fake_tarball.suffix + ".sha256").write_text(
        f"{expected_sha}  {fake_tarball.name}\n"
    )

    staging = tmp_path / "staging"
    rc = serve_mod.main(  # type: ignore[attr-defined]
        [
            "--dry-run",
            "--tarball",
            str(fake_tarball),
            "--staging-dir",
            str(staging),
        ]
    )
    assert rc == 0

    manifest = json.loads((staging / "manifest.json").read_text())
    assert manifest["tarball_sha256"] == expected_sha
    # Copied under the stable served filename regardless of original name.
    assert (staging / "brain-dev.tar.gz").read_bytes() == fake_tarball.read_bytes()


# ---------------------------------------------------------------------------
# IP discovery
# ---------------------------------------------------------------------------


def test_iter_candidate_ips_always_returns_loopback(
    serve_mod: object,
) -> None:
    """127.0.0.1 is always present so single-host demos work even
    when no LAN interface is up (common inside a nested VM)."""
    ips = serve_mod._iter_candidate_ips()  # type: ignore[attr-defined]
    assert "127.0.0.1" in ips
    # All entries must be valid IPv4.
    import ipaddress

    for ip in ips:
        ipaddress.IPv4Address(ip)
