"""Plan 12 Task 4 — production-shape stdio integration regression test.

Plan 11 Task 4 wired ``save_config()`` into 5 mutation tools assuming
``ctx.config`` is set. Plan 11 Task 7 fixed brain_api's ``build_app_context``
to thread Config through; Plan 12 Task 4 ports the same fix to
``brain_mcp.server._build_ctx``. Without this fix, every Plan 11 mutation
dispatched via Claude Desktop → brain_mcp would silently land on the
``ctx.config is None`` no-op branch — the tool would report success but the
disk write would never happen.

These tests are the regression guard. They SPAWN ``python -m brain_mcp`` as
a subprocess (not call functions in-process), drive it via the MCP SDK's
stdio client, and assert on the on-disk ``config.json`` bytes after each
tool call. This is the brain_mcp equivalent of brain_web's
``persistence.spec.ts`` Playwright spec — production-shape, transport-end-to-
end, byte-level disk verification.

Plan 11 lesson 343 (verbatim) calls for exactly this shape:
  > load-bearing wiring needs production-shape integration tests, not just
  > unit-test-with-explicit-config tests.

Subprocess gotcha (project lessons.md #341):
  ``python -m brain_mcp`` resolves ``brain_mcp`` and ``brain_core`` via
  ``.venv`` editable ``.pth`` files that Spotlight (UF_HIDDEN) keeps re-
  hiding. We bypass that resolution entirely by setting ``PYTHONPATH`` in
  the subprocess env to point at the source dirs directly. Robust against
  the Spotlight race; doesn't require running ``chflags`` from the test.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Repo root resolved relative to this test file: ``<repo>/packages/brain_mcp/tests/``
# → up three levels lands on ``<repo>``. Used to compute the source-tree
# PYTHONPATH that bypasses the editable-install ``.pth`` Spotlight issue.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATHS = (
    _REPO_ROOT / "packages" / "brain_core" / "src",
    _REPO_ROOT / "packages" / "brain_mcp" / "src",
)


def _subprocess_env(vault_root: Path) -> dict[str, str]:
    """Build the env dict for the spawned brain_mcp subprocess.

    PYTHONPATH points at the source trees so the spawned interpreter can
    import ``brain_core`` and ``brain_mcp`` without traversing the editable-
    install ``.pth`` files (which Spotlight intermittently hides).

    BRAIN_VAULT_ROOT and BRAIN_ALLOWED_DOMAINS are read by ``brain_mcp.__main__``;
    we set them per-test so each test gets its own isolated tmp_vault.
    """
    pythonpath_parts = [str(p) for p in _SRC_PATHS]
    if existing := os.environ.get("PYTHONPATH"):
        pythonpath_parts.append(existing)
    return {
        # Pass through PATH so the subprocess can find any system tools it
        # might shell out to (none today, but cheap insurance).
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join(pythonpath_parts),
        "BRAIN_VAULT_ROOT": str(vault_root),
        # ``research`` is in DEFAULT_DOMAINS; using it here means
        # brain_create_domain tests need a fresh slug not in DEFAULT_DOMAINS.
        "BRAIN_ALLOWED_DOMAINS": "research,work",
    }


@asynccontextmanager
async def _stdio_session(vault_root: Path) -> AsyncIterator[ClientSession]:
    """Spawn ``python -m brain_mcp`` and yield an initialized MCP client session.

    Mirrors the canonical recipe in
    ``brain_cli.commands.mcp._subprocess_tools_list``: ``stdio_client`` owns
    the subprocess lifecycle (spawn on ``__aenter__``, terminate on
    ``__aexit__``). Tests that spawn brain_mcp MUST go through this helper
    so cleanup happens via the SDK's tested teardown path, not ad-hoc
    ``Popen.terminate`` calls in finally blocks (which race against the
    subprocess's own asyncio shutdown).
    """
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "brain_mcp"],
        env=_subprocess_env(vault_root),
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        yield session


def _read_disk_config(vault_root: Path) -> dict[str, object]:
    """Read ``<vault>/.brain/config.json`` and return the parsed JSON dict.

    Asserts the file exists — failing here means the persistence write
    didn't land, which is the exact regression these tests are guarding
    against. ``pytest.fail`` rather than a bare ``assert`` so the failure
    message is actionable in CI logs.
    """
    config_path = vault_root / ".brain" / "config.json"
    if not config_path.exists():
        pytest.fail(
            f"expected {config_path} to exist after a persisting tool call — "
            "did Plan 12 Task 4's _build_ctx fix regress?"
        )
    return json.loads(config_path.read_text(encoding="utf-8"))


@pytest.mark.slow
async def test_brain_config_set_persists_via_stdio_transport(tmp_path: Path) -> None:
    """The canonical regression: brain_config_set over stdio writes config.json.

    Pre-fix behavior: the tool would return ``persisted=False`` because
    ``ctx.config`` was ``None``, no config.json would land on disk, but
    the tool response would still say "updated" (the in-memory mutation
    is a no-op against a None Config, which silently succeeds via the
    ``ctx.config is None`` short-circuit in
    ``brain_core.tools.config_set._persist_via_save_config``).

    Post-fix behavior: ``persisted=True`` and the on-disk JSON contains
    ``"log_llm_payloads": true``.
    """
    vault = tmp_path / "vault"
    vault.mkdir()

    async with _stdio_session(vault) as session:
        result = await session.call_tool(
            "brain_config_set",
            {"key": "log_llm_payloads", "value": True},
        )

    assert result.isError is False, f"tool errored: {result.content}"
    # Inline-JSON shape: result.content[1] is the data block.
    data_text = result.content[1].text  # type: ignore[union-attr]
    data = json.loads(data_text)
    assert data["status"] == "updated"
    assert data["persisted"] is True

    on_disk = _read_disk_config(vault)
    assert on_disk["log_llm_payloads"] is True


@pytest.mark.slow
async def test_brain_create_domain_persists_via_stdio_transport(tmp_path: Path) -> None:
    """brain_create_domain over stdio appends the slug to Config.domains on disk.

    Uses a slug not in DEFAULT_DOMAINS so the ``slug already in
    Config.domains`` pre-check doesn't trip. ``research`` and ``work`` are
    pre-seeded by Config defaults; ``hobbyplan12`` is a fresh slug.

    Pre-fix: the on-disk folder ``<vault>/hobbyplan12/`` would be created
    (that path doesn't depend on Config), but ``Config.domains`` would not
    be persisted — so a fresh ``load_config`` afterward would not see the
    new slug, and ``brain_list_domains`` would mark it as
    ``configured=False, on_disk=True``. Post-fix, the slug is in
    ``config.json``'s ``domains`` array.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    fresh_slug = "hobbyplan12"

    async with _stdio_session(vault) as session:
        result = await session.call_tool(
            "brain_create_domain",
            {"slug": fresh_slug, "name": "Hobby Plan 12"},
        )

    assert result.isError is False, f"tool errored: {result.content}"

    # Domain folder exists on disk — sanity check that the tool got past
    # the slug-validation step.
    assert (vault / fresh_slug / "index.md").exists()

    on_disk = _read_disk_config(vault)
    domains = on_disk.get("domains")
    assert isinstance(domains, list)
    assert fresh_slug in domains
    # Default domains preserved (the append shouldn't drop them).
    assert "research" in domains
    assert "work" in domains
    assert "personal" in domains


@pytest.mark.slow
async def test_build_ctx_loads_config_from_existing_disk_file(tmp_path: Path) -> None:
    """brain_config_get reflects values from a pre-existing config.json on disk.

    Pre-fix: ``_build_ctx`` constructed ToolContext with ``config=None``
    (or, depending on call path, with ``Config()`` defaults), so
    ``brain_config_get`` would mirror those defaults regardless of what was
    written to ``<vault>/.brain/config.json``. The on-disk file was simply
    ignored at session-init time.

    Post-fix: ``_build_ctx`` calls ``load_config(config_file=...)`` which
    reads the on-disk JSON, so ``brain_config_get`` reflects what the user
    persisted.

    This is the regression test for the original bug shape.
    """
    vault = tmp_path / "vault"
    brain_dir = vault / ".brain"
    brain_dir.mkdir(parents=True)

    # Pre-write a config.json with non-default values. ``log_llm_payloads``
    # defaults to False; flip it to True so a default-Config read would
    # fail this assertion. ``budget.daily_usd`` defaults to 1.0; bump it
    # to 42.0 for a clearly non-default sentinel.
    pre_written = {
        "log_llm_payloads": True,
        "budget": {"daily_usd": 42.0},
    }
    (brain_dir / "config.json").write_text(json.dumps(pre_written), encoding="utf-8")

    async with _stdio_session(vault) as session:
        log_result = await session.call_tool(
            "brain_config_get",
            {"key": "log_llm_payloads"},
        )
        budget_result = await session.call_tool(
            "brain_config_get",
            {"key": "budget.daily_usd"},
        )

    assert log_result.isError is False, f"log_result errored: {log_result.content}"
    assert budget_result.isError is False, f"budget_result errored: {budget_result.content}"

    log_data = json.loads(log_result.content[1].text)  # type: ignore[union-attr]
    budget_data = json.loads(budget_result.content[1].text)  # type: ignore[union-attr]

    assert log_data["key"] == "log_llm_payloads"
    assert log_data["value"] is True
    assert budget_data["key"] == "budget.daily_usd"
    assert budget_data["value"] == 42.0
