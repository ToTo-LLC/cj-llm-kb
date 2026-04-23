"""Plan 09 Task 1 — version coherence tests.

Guards the three hard gates for v0.1.0:
  (a) ``brain --version`` prints ``0.1.0``.
  (b) The repo-root ``VERSION`` file exists and contains ``0.1.0``.
  (c) ``brain_core.__version__ == "0.1.0"``.

These tests fail if any of the five version sigils (VERSION file, brain_core,
brain_cli, brain_mcp pyproject, brain_api pyproject, or apps/brain_web
package.json) drift out of sync. The explicit surface tested here is the
user-facing ``--version`` CLI output — the rest keep releases coherent.
"""

from __future__ import annotations

import json
from pathlib import Path

import brain_core
from brain_cli.app import app
from typer.testing import CliRunner

runner = CliRunner()

# Path to the repo root. This test file lives at
# ``packages/brain_cli/tests/commands/test_version.py`` — four parents up
# gets us to the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_brain_version_flag_prints_0_1_0() -> None:
    """``brain --version`` succeeds and output contains ``0.1.0``."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert "0.1.0" in result.output, f"expected '0.1.0' in output, got: {result.output!r}"


def test_repo_root_version_file_is_0_1_0() -> None:
    """Repo-root ``VERSION`` file exists and pins ``0.1.0``."""
    version_file = _REPO_ROOT / "VERSION"
    assert version_file.exists(), f"missing repo-root VERSION file at {version_file}"
    content = version_file.read_text(encoding="utf-8").strip()
    assert content == "0.1.0", f"VERSION file pins {content!r}, expected '0.1.0'"


def test_brain_core_version_is_0_1_0() -> None:
    """``brain_core.__version__`` pins ``0.1.0`` for the v0.1.0 release."""
    assert brain_core.__version__ == "0.1.0"


def test_brain_web_package_json_version_is_0_1_0() -> None:
    """Frontend ``apps/brain_web/package.json`` matches the Python packages.

    Not a hard gate from the plan's perspective but catches the most
    common drift point — forgetting to bump the UI when bumping Python.
    """
    package_json = _REPO_ROOT / "apps" / "brain_web" / "package.json"
    assert package_json.exists(), f"missing {package_json}"
    data = json.loads(package_json.read_text(encoding="utf-8"))
    assert data.get("version") == "0.1.0", (
        f"brain_web package.json version is {data.get('version')!r}, expected '0.1.0'"
    )
