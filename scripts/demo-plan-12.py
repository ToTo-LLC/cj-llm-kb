"""Plan 12 end-to-end demo — Settings UX completion + Plan 11 correctness cleanup.

Walks the seven gates locked in the Plan 12 demo-gate header:

    1. Schema gate: ``Config(cross_domain_warning_acknowledged=True)``
       round-trips through ``save_config`` + ``load_config``;
       ``_PERSISTED_FIELDS`` includes the new key; ``from
       brain_core.llm import resolve_autonomous_mode`` raises
       ``ImportError``; ``DomainOverride(autonomous_mode=True)`` raises
       (``extra="forbid"`` after Plan 12 Task 1's field removal).
    2. Read-tool audit gate: build a sentinel-bearing ``Config(
       active_domain="sentinel-domain", domains=[..., "sentinel-domain"])``;
       monkeypatch ``ctx.config`` to it; invoke each entry of
       ``_READ_TOOLS_THAT_THREAD_CTX_CONFIG`` and assert the response
       reflects the sentinel (not the schema default ``"research"``).
    3. brain_mcp gate: spawn brain_mcp via stdio in a subprocess against
       a temp vault; dispatch a ``brain_config_set`` tool call with
       ``{key: "log_llm_payloads", value: true}``; assert
       ``<vault>/.brain/config.json`` on disk contains
       ``"log_llm_payloads": true``. This is the Plan 11 lesson 343
       production-shape regression guard.
    4. zustand pubsub gate: covered by ``apps/brain_web/tests/e2e/domains.spec.ts``
       (Plan 12 Task 5 removed the ``page.reload()`` workaround between
       a panel mutation and the topbar's verification — that spec IS the
       live cross-instance pubsub assertion). This script prints a
       chained-runner hint per the same convention as Plan 11 gate 8.
    5. active_domain Settings UI gate: covered by
       ``apps/brain_web/tests/e2e/active-domain.spec.ts``. This script
       prints the runner hint.
    6. Cross-domain modal trigger parametrized gate: covered by
       ``apps/brain_web/tests/e2e/cross-domain-modal.spec.ts``. This
       script prints the runner hint.
    7. Acknowledgment lifecycle gate: continued in
       ``cross-domain-modal.spec.ts``.

Prints ``PLAN 12 DEMO OK`` on exit 0; non-zero on any gate failure.
Uses ``FakeLLMProvider``-equivalent stubs and avoids any live LLM call.

Mirrors the Plan 11 demo-gate split: gates 1-3 are in-process Python
and run here; gates 4-7 are Playwright surface-level walks and run
via ``cd apps/brain_web && PYTHONPATH=packages/brain_core/src:packages/brain_api/src npx playwright test``
per the Plan 12 Task 10 execution prefix. The script's exit-0
guarantee covers the Python gates; the Playwright invocation is the
parallel artifact for the e2e gates.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from brain_core.config.loader import load_config
from brain_core.config.schema import (
    _PERSISTED_FIELDS,
    Config,
    DomainOverride,
)
from brain_core.config.writer import save_config
from brain_core.tools import config_get, list_domains
from brain_core.tools.base import ToolContext


def _gate(label: str) -> None:
    print(f"  ✓ Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  ✗ Gate {label}: {why}", file=sys.stderr)
    return 1


def _scaffold_vault(root: Path) -> None:
    """Build a v0.1 default vault: research / work / personal + ``.brain/``.

    Mirrors :func:`scripts.demo_plan_11._scaffold_vault` — Plan 12's gates
    don't ingest, so we only need the bare folder shape + ``.brain``
    directory the writer expects.
    """
    root.mkdir(parents=True)
    (root / ".brain").mkdir()
    for domain in ("research", "work", "personal"):
        d = root / domain
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (d / sub).mkdir(parents=True)
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")


def _ctx(root: Path, *, allowed: tuple[str, ...], cfg: Config | None) -> ToolContext:
    """Build a ToolContext for the demo's read-tool gate. The Plan 12 read
    tools we exercise (``config_get`` + ``list_domains``) only need
    ``vault_root`` + ``allowed_domains`` + ``config``; the heavier primitives
    are ``None``.
    """
    return ToolContext(
        vault_root=root,
        allowed_domains=allowed,
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=cfg,
    )


def _config_path(root: Path) -> Path:
    """Canonical on-disk path for the persisted Config blob."""
    return root / ".brain" / "config.json"


# ---------------------------------------------------------------------------
# Gate 1 — schema round-trip + DELETE markers
# ---------------------------------------------------------------------------


def _gate_1_schema(root: Path) -> int:
    """Schema gate.

    1a. ``Config(cross_domain_warning_acknowledged=True)`` round-trips
        through ``save_config`` + ``load_config`` — bool survives the
        disk hop with the right value.
    1b. ``"cross_domain_warning_acknowledged"`` is in
        ``_PERSISTED_FIELDS`` — pin against the frozenset so a future
        whitelist drift fails fast.
    1c. ``from brain_core.llm import resolve_autonomous_mode`` raises
        ``ImportError`` — proof Plan 12 Task 2's DELETE landed.
    1d. ``DomainOverride(autonomous_mode=True)`` raises a validation
        error (``extra="forbid"`` post-Task-1 field removal).
    """
    cfg_path = _config_path(root)

    # ---- 1a — round-trip the bool through save_config + load_config ----
    cfg = Config(
        vault_path=root,
        domains=["research", "work", "personal"],
        cross_domain_warning_acknowledged=True,
    )
    save_config(cfg, root)
    rehydrated = load_config(
        config_file=cfg_path,
        env={},
        cli_overrides={"vault_path": root},
    )
    if rehydrated.cross_domain_warning_acknowledged is not True:
        return _fail(
            "1",
            "round-trip lost cross_domain_warning_acknowledged: "
            f"got {rehydrated.cross_domain_warning_acknowledged!r}",
        )

    # ---- 1b — _PERSISTED_FIELDS includes the new key ------------------
    if "cross_domain_warning_acknowledged" not in _PERSISTED_FIELDS:
        return _fail(
            "1",
            "_PERSISTED_FIELDS missing cross_domain_warning_acknowledged; "
            f"current set={sorted(_PERSISTED_FIELDS)}",
        )

    # ---- 1c — resolve_autonomous_mode is gone -------------------------
    try:
        from brain_core.llm import resolve_autonomous_mode  # noqa: F401
    except ImportError:
        pass
    else:
        return _fail(
            "1",
            "from brain_core.llm import resolve_autonomous_mode SUCCEEDED — "
            "Plan 12 Task 2 DELETE didn't land",
        )

    # ---- 1d — DomainOverride.autonomous_mode field removed ------------
    try:
        DomainOverride(autonomous_mode=True)
    except Exception as exc:
        msg = str(exc).lower()
        if "extra" not in msg and "forbidden" not in msg and "autonomous_mode" not in msg:
            return _fail(
                "1",
                f"DomainOverride(autonomous_mode=True) raised but for the wrong reason: {exc!r}",
            )
    else:
        return _fail(
            "1",
            "DomainOverride(autonomous_mode=True) accepted — Plan 12 Task 1 "
            "field removal didn't land (extra='forbid' should reject).",
        )

    _gate(
        "1 — Config.cross_domain_warning_acknowledged round-trips; "
        "_PERSISTED_FIELDS pinned; resolve_autonomous_mode gone; "
        "DomainOverride.autonomous_mode rejected"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — read-tool audit
# ---------------------------------------------------------------------------


_SENTINEL_DOMAIN = "sentinel-domain"


async def _gate_2_read_tools(root: Path) -> int:
    """Read-tool audit gate (D5).

    Build a sentinel-bearing Config; monkeypatch ``ctx.config`` to it;
    invoke each tool from a parametrized list (mirroring the contract
    test ``_READ_TOOLS_THAT_THREAD_CTX_CONFIG``) and assert the
    response reflects the sentinel — proving the tool actually reads
    ``ctx.config`` rather than constructing a fresh ``Config()``.
    """
    cfg = Config(
        vault_path=root,
        active_domain=_SENTINEL_DOMAIN,
        domains=["research", "work", "personal", _SENTINEL_DOMAIN],
    )
    ctx = _ctx(
        root,
        allowed=("research", "work", "personal", _SENTINEL_DOMAIN),
        cfg=cfg,
    )

    # ---- 2a — brain_config_get ----------------------------------------
    cg_result = await config_get.handle({"key": "active_domain"}, ctx)
    if cg_result.data is None:
        return _fail("2", "brain_config_get returned no data")
    if cg_result.data.get("key") != "active_domain":
        return _fail(
            "2",
            f"brain_config_get returned wrong key: {cg_result.data.get('key')!r}",
        )
    if cg_result.data.get("value") != _SENTINEL_DOMAIN:
        return _fail(
            "2",
            f"brain_config_get returned value={cg_result.data.get('value')!r}; "
            f"expected sentinel {_SENTINEL_DOMAIN!r} (Config() snapshot drift "
            "regressed — see Plan 12 Task 3 / D5).",
        )

    # ---- 2b — brain_list_domains --------------------------------------
    ld_result = await list_domains.handle({}, ctx)
    if ld_result.data is None:
        return _fail("2", "brain_list_domains returned no data")
    if ld_result.data.get("active_domain") != _SENTINEL_DOMAIN:
        return _fail(
            "2",
            f"brain_list_domains returned active_domain={ld_result.data.get('active_domain')!r}; "
            f"expected sentinel {_SENTINEL_DOMAIN!r}.",
        )
    domains_list = ld_result.data.get("domains") or []
    if _SENTINEL_DOMAIN not in domains_list:
        return _fail(
            "2",
            f"brain_list_domains.domains={domains_list!r} did not include the sentinel; "
            "tool isn't reading ctx.config.domains.",
        )

    _gate(
        "2 — brain_config_get + brain_list_domains both surface the sentinel "
        "from ctx.config (no Config() snapshot drift)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — brain_mcp stdio Config-wiring regression
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_PATHS = (
    _REPO_ROOT / "packages" / "brain_core" / "src",
    _REPO_ROOT / "packages" / "brain_mcp" / "src",
    _REPO_ROOT / "packages" / "brain_api" / "src",
)


def _subprocess_env(vault_root: Path) -> dict[str, str]:
    """Mirror packages/brain_mcp/tests/test_config_persistence_stdio.py.

    PYTHONPATH points at the source trees so the spawned interpreter can
    import ``brain_core`` / ``brain_mcp`` without traversing the editable-
    install ``.pth`` files (which Spotlight intermittently hides per
    lesson 341).
    """
    pythonpath_parts = [str(p) for p in _SRC_PATHS]
    if existing := os.environ.get("PYTHONPATH"):
        pythonpath_parts.append(existing)
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join(pythonpath_parts),
        "BRAIN_VAULT_ROOT": str(vault_root),
        "BRAIN_ALLOWED_DOMAINS": "research,work",
    }


@asynccontextmanager
async def _stdio_session(vault_root: Path) -> AsyncIterator[Any]:
    """Spawn ``python -m brain_mcp`` and yield an initialized MCP client session."""
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

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


async def _gate_3_mcp_stdio(root: Path) -> int:
    """brain_mcp stdio gate (D6).

    Spawn brain_mcp as a subprocess against a fresh temp vault; dispatch
    ``brain_config_set log_llm_payloads=true``; assert the on-disk
    ``config.json`` contains the new value. Pre-Task-4 fix this would
    silently fall to the ``ctx.config is None`` no-op branch — the
    response would say "updated" but no disk bytes would land.
    """
    # Use a separate sub-vault so the gate-1/gate-2 vault state doesn't
    # bleed in. The stdio test's subprocess wants an empty .brain/ dir.
    sub = root / "mcp-sub"
    sub.mkdir()

    try:
        async with _stdio_session(sub) as session:
            result = await session.call_tool(
                "brain_config_set",
                {"key": "log_llm_payloads", "value": True},
            )
    except Exception as exc:
        return _fail("3", f"stdio session raised: {exc!r}")

    if getattr(result, "isError", False):
        return _fail("3", f"tool errored over stdio: {result.content!r}")

    # Inline-JSON shape: result.content[1] is the data block. Mirror the
    # Plan 12 Task 4 stdio test parsing.
    try:
        data_text = result.content[1].text  # type: ignore[union-attr]
        data = json.loads(data_text)
    except Exception as exc:
        return _fail("3", f"could not parse tool response: {exc!r}; raw={result.content!r}")

    if data.get("status") != "updated":
        return _fail("3", f"tool data.status={data.get('status')!r}; expected 'updated'")
    if data.get("persisted") is not True:
        return _fail(
            "3",
            f"tool data.persisted={data.get('persisted')!r}; expected True — "
            "brain_mcp Config-wiring regressed (Plan 12 Task 4 fix didn't take).",
        )

    cfg_path = sub / ".brain" / "config.json"
    if not cfg_path.exists():
        return _fail(
            "3",
            f"expected {cfg_path} to exist after brain_config_set; on-disk write didn't land.",
        )
    on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
    if on_disk.get("log_llm_payloads") is not True:
        return _fail(
            "3",
            f"on-disk config.json log_llm_payloads={on_disk.get('log_llm_payloads')!r}; "
            "expected True — Plan 12 Task 4 brain_mcp Config-wiring regression.",
        )

    _gate(
        "3 — brain_mcp via stdio: brain_config_set landed on disk "
        "(<vault>/.brain/config.json log_llm_payloads=true)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gates 4-7 - Playwright e2e (out-of-process)
# ---------------------------------------------------------------------------


def _gate_4_zustand_pubsub() -> None:
    """Plan 12 Task 5's zustand-store refactor of ``useDomains()`` is the
    fix for the Plan 11 closure addendum's cross-instance pubsub gap.
    The proof is that ``apps/brain_web/tests/e2e/domains.spec.ts``
    (Plan 10 spec, updated in Task 5 to drop the ``page.reload()``
    workaround between a panel mutation and the topbar's verification)
    passes without that workaround. That spec IS the live cross-instance
    pubsub assertion.
    """
    print(
        "  ✓ Gate 4 — see apps/brain_web/tests/e2e/domains.spec.ts "
        "(Plan 12 Task 5 removed page.reload(); zustand subscription is the proof)"
    )


def _gate_5_active_domain_ui() -> None:
    """Active-domain Settings UI persistence gate."""
    print(
        "  ✓ Gate 5 — see apps/brain_web/tests/e2e/active-domain.spec.ts "
        "(persist active_domain via Settings → reload → topbar reflects)"
    )


def _gate_6_cross_domain_trigger() -> None:
    """Cross-domain modal trigger gate (parametrized)."""
    print(
        "  ✓ Gate 6 — see apps/brain_web/tests/e2e/cross-domain-modal.spec.ts "
        "(modal trigger: cross-with-rail vs cross-without-rail vs single-rail)"
    )


def _gate_7_acknowledgment_lifecycle() -> None:
    """Acknowledgment lifecycle gate."""
    print(
        "  ✓ Gate 7 — see apps/brain_web/tests/e2e/cross-domain-modal.spec.ts "
        "(acknowledgment lifecycle: Don't show again → reload → Settings toggle re-enables)"
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def _run() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "brain"
        _scaffold_vault(root)

        rc = _gate_1_schema(root)
        if rc != 0:
            return rc

        rc = await _gate_2_read_tools(root)
        if rc != 0:
            return rc

        rc = await _gate_3_mcp_stdio(root)
        if rc != 0:
            return rc

        # Out-of-process gates surfaced as runner hints (the Plan 11
        # convention): the Python script doesn't drive Playwright, but
        # the closure receipt requires running them green via the
        # documented command. Their proof artifact is the spec output,
        # not this script's exit code.
        _gate_4_zustand_pubsub()
        _gate_5_active_domain_ui()
        _gate_6_cross_domain_trigger()
        _gate_7_acknowledgment_lifecycle()

        print()
        print("PLAN 12 DEMO OK")
        return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
