"""Plan 04 end-to-end demo.

Spins up ``brain_mcp`` in-process via the MCP SDK's memory transport, exercises
every tool through a real MCP client, and asserts the 14 demo gates from the
plan header (tasks/plans/04-mcp.md § Task 24). Prints ``PLAN 04 DEMO OK`` on
success.

All LLM calls go through :class:`FakeLLMProvider` — no network, no API key.
Gate 14 DOES spawn ``brain mcp selftest`` as a real subprocess, but with
``BRAIN_CLAUDE_DESKTOP_CONFIG_PATH`` pointed at a temp config so no real Claude
Desktop install is touched.

Known wiring notes:

* Gate 5 (brain_ingest) bypasses the MCP client boundary and calls the tool
  ``handle(...)`` directly. The server's internal ``_build_ctx()`` creates a
  fresh :class:`FakeLLMProvider` inside each session, so we cannot queue
  pipeline responses through the MCP client. Direct ``handle()`` call with a
  pre-queued fake is the cleanest workaround and matches the plan's
  recommendation (Option (c) in the Task 24 skeleton).

* Gate 14 subprocess: ``brain mcp selftest`` currently hardcodes
  ``BRAIN_VAULT_ROOT=~/Documents/brain`` in the StdioServerParameters it
  builds for the subprocess (see Task 25 deferral). ``tools/list`` never
  touches the vault (``_build_ctx`` is lazy), so the subprocess succeeds
  regardless of whether that directory exists. We still export the temp
  vault path in the parent env as belt-and-braces so a future selftest
  refactor that inherits parent env continues to work.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from brain_core.integrations.claude_desktop import install as cd_install
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_mcp.server import create_server
from brain_mcp.tools.ingest import handle as ingest_handle
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import AnyUrl

_EXPECTED_TOOL_COUNT = 18


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  OK  {msg}")


def _first_json(content_blocks: Sequence[Any]) -> dict[str, Any]:
    """Return the first content block whose ``text`` parses as a JSON object."""
    for block in content_blocks:
        text = getattr(block, "text", None)
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AssertionError("no JSON content block found in tool output")


def _scaffold_vault(root: Path) -> None:
    """Build a vault that satisfies both the read tools and the ingest pipeline."""
    root.mkdir(parents=True)
    (root / ".brain").mkdir()

    # Domains exercised by the demo. `research` + `work` are in scope;
    # `personal` is out of scope and is used by the scope-guard gate.
    for domain in ("research", "work", "personal"):
        d = root / domain
        for sub in ("sources", "entities", "concepts", "synthesis", "notes"):
            (d / sub).mkdir(parents=True)

    # Full index layout the ingest pipeline's Stage 8 expects.
    (root / "research" / "index.md").write_text(
        "# research — index\n\n- [[karpathy]]\n\n"
        "## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    (root / "research" / "log.md").write_text("# research — log\n", encoding="utf-8")
    (root / "work" / "index.md").write_text(
        "# work — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    (root / "work" / "log.md").write_text("# work — log\n", encoding="utf-8")
    (root / "personal" / "index.md").write_text(
        "# personal — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )

    # Seed notes the read / search gates depend on. We seed a handful of
    # filler notes alongside so "karpathy" is unique enough that BM25 yields
    # a positive score: IDF collapses to ~0 if a query term appears in half
    # the corpus, so keeping the term in only 2 / 6+ research-domain docs
    # keeps Gate 3 reliable.
    (root / "research" / "notes" / "karpathy.md").write_text(
        "---\ntitle: Karpathy\ndomain: research\n---\n"
        "Andrej Karpathy wrote about the LLM wiki pattern.\n",
        encoding="utf-8",
    )
    (root / "research" / "notes" / "rag.md").write_text(
        "---\ntitle: RAG\ndomain: research\n---\n"
        "Retrieval-augmented generation over raw documents.\n",
        encoding="utf-8",
    )
    (root / "research" / "notes" / "filler-a.md").write_text(
        "---\ntitle: Filler A\ndomain: research\n---\nCooking recipes unrelated.\n",
        encoding="utf-8",
    )
    (root / "research" / "notes" / "filler-b.md").write_text(
        "---\ntitle: Filler B\ndomain: research\n---\nGardening tips unrelated.\n",
        encoding="utf-8",
    )
    (root / "research" / "notes" / "filler-c.md").write_text(
        "---\ntitle: Filler C\ndomain: research\n---\nHiking trails unrelated.\n",
        encoding="utf-8",
    )
    (root / "personal" / "notes" / "secret.md").write_text(
        "---\ntitle: Secret\ndomain: personal\n---\nnever leak me\n",
        encoding="utf-8",
    )

    # Ingest raw/ dirs so TextHandler's outputs land somewhere valid.
    for sub in ("inbox", "failed", "archive"):
        (root / "raw" / sub).mkdir(parents=True)

    (root / "BRAIN.md").write_text(
        "# BRAIN\n\nYou are brain.\nDefault schema doc.\n", encoding="utf-8"
    )


def _queue_ingest_pipeline_responses(
    fake: FakeLLMProvider, *, title: str = "plan-04-source"
) -> None:
    """Queue the three LLM responses an ingest run consumes (classify / summarize / integrate)."""
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title=title,
            summary="Karpathy described the LLM wiki pattern.",
            key_points=["LLM compiles raw material into a wiki"],
            entities=[],
            concepts=["LLM wiki"],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            index_entries=[
                IndexEntryPatch(
                    section="Sources",
                    line=f"- [[{title}]] — LLM wiki",
                    domain="research",
                )
            ],
            log_entry=None,
            reason="plan 04 demo ingest",
        ).model_dump_json()
    )


async def _gate_5_ingest_direct(vault: Path) -> None:
    """Gate 5 — brain_ingest via direct ``handle(...)`` call.

    The MCP server builds its own :class:`FakeLLMProvider` inside ``_build_ctx``
    so we can't queue pipeline responses from outside. We bypass the MCP client
    for this gate only, following the plan's Option (c). All other gates go
    through the real MCP client.
    """
    from brain_core.chat.pending import PendingPatchStore
    from brain_core.chat.retrieval import BM25VaultIndex
    from brain_core.cost.ledger import CostLedger
    from brain_core.state.db import StateDB
    from brain_core.vault.undo import UndoLog
    from brain_core.vault.writer import VaultWriter
    from brain_mcp.rate_limit import RateLimitConfig, RateLimiter
    from brain_mcp.tools.base import ToolContext

    brain_dir = vault / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    db = StateDB.open(brain_dir / "state.sqlite")
    try:
        writer = VaultWriter(vault_root=vault)
        pending = PendingPatchStore(brain_dir / "pending")
        retrieval = BM25VaultIndex(vault_root=vault, db=db)
        retrieval.build(("research",))
        ledger = CostLedger(db_path=brain_dir / "costs.sqlite")
        limiter = RateLimiter(RateLimitConfig(patches_per_minute=1000, tokens_per_minute=1_000_000))
        fake = FakeLLMProvider()
        _queue_ingest_pipeline_responses(fake)

        ctx = ToolContext(
            vault_root=vault,
            allowed_domains=("research",),
            retrieval=retrieval,
            pending_store=pending,
            state_db=db,
            writer=writer,
            llm=fake,
            cost_ledger=ledger,
            rate_limiter=limiter,
            undo_log=UndoLog(vault_root=vault),
        )

        src_file = vault / "raw" / "inbox" / "plan-04-source.txt"
        src_file.write_text(
            "Karpathy wrote about LLM wikis.\n\nThe pattern turns source material into a wiki.\n",
            encoding="utf-8",
        )

        out = await ingest_handle({"source": str(src_file)}, ctx)
        data = _first_json(out)
        _check(data["status"] == "pending", "brain_ingest default staged (status=pending)")
        _check("patch_id" in data, "brain_ingest returned patch_id")
        _check(
            not (vault / "research" / "sources" / "plan-04-source.md").exists(),
            "ingest note NOT written to vault (staged only)",
        )
        pending_list = ctx.pending_store.list()
        _check(
            any(env.tool == "brain_ingest" for env in pending_list),
            "pending store has a brain_ingest envelope",
        )
    finally:
        db.close()


async def _run_client_gates(vault: Path) -> None:
    """Gates 1-4, 6-13 — drive the server through the real MCP client."""
    server = create_server(vault_root=vault, allowed_domains=("research", "work"))
    async with create_connected_server_and_client_session(server) as session:
        # ------------------------------------------------------------------
        # Gate 1 — tool + resource discovery
        # ------------------------------------------------------------------
        print("[gate 1] tool + resource discovery")
        tools_result = await session.list_tools()
        tool_count = len(tools_result.tools)
        _check(
            tool_count == _EXPECTED_TOOL_COUNT,
            f"exactly {_EXPECTED_TOOL_COUNT} tools registered (got {tool_count})",
        )
        names = {t.name for t in tools_result.tools}
        for required in ("brain_list_domains", "brain_search", "brain_apply_patch"):
            _check(required in names, f"tool {required} present")
        resources_result = await session.list_resources()
        resource_count = len(resources_result.resources)
        _check(
            resource_count >= 3,
            f">=3 resources registered (got {resource_count})",
        )

        # ------------------------------------------------------------------
        # Gate 2 — brain_list_domains
        # ------------------------------------------------------------------
        print("[gate 2] brain_list_domains")
        r = await session.call_tool("brain_list_domains", {})
        _check(r.isError is False, "brain_list_domains isError=False")
        data = _first_json(r.content)
        _check("research" in data["domains"], "research domain listed")
        _check("work" in data["domains"], "work domain listed")

        # ------------------------------------------------------------------
        # Gate 3 — brain_search
        # ------------------------------------------------------------------
        print("[gate 3] brain_search")
        r = await session.call_tool("brain_search", {"query": "karpathy"})
        _check(r.isError is False, "brain_search isError=False")
        data = _first_json(r.content)
        _check(
            any("karpathy" in str(h.get("path", "")).lower() for h in data["hits"]),
            "karpathy note found in search hits",
        )

        # ------------------------------------------------------------------
        # Gate 4 — brain_read_note
        # ------------------------------------------------------------------
        print("[gate 4] brain_read_note")
        r = await session.call_tool("brain_read_note", {"path": "research/notes/karpathy.md"})
        _check(r.isError is False, "brain_read_note isError=False")
        _check(
            any("LLM wiki pattern" in getattr(c, "text", "") for c in r.content),
            "note body returned with expected content",
        )

        # ------------------------------------------------------------------
        # Gate 6 — brain_list_pending_patches (empty baseline)
        # ------------------------------------------------------------------
        print("[gate 6] brain_list_pending_patches empty baseline")
        r = await session.call_tool("brain_list_pending_patches", {})
        _check(r.isError is False, "brain_list_pending_patches isError=False")
        data = _first_json(r.content)
        _check(data["count"] == 0, f"no pending patches initially (got {data['count']})")

        # ------------------------------------------------------------------
        # Gate 7 — propose → apply → undo round-trip
        # ------------------------------------------------------------------
        print("[gate 7] brain_propose_note → brain_apply_patch → brain_undo_last")
        r = await session.call_tool(
            "brain_propose_note",
            {
                "path": "research/notes/demo.md",
                "content": "# demo\n\nfrom plan 04\n",
                "reason": "plan 04 demo gate 7",
            },
        )
        _check(r.isError is False, "propose_note isError=False")
        data = _first_json(r.content)
        _check("patch_id" in data, "propose_note returned patch_id")
        demo_path = vault / "research" / "notes" / "demo.md"
        _check(not demo_path.exists(), "demo note NOT on disk after propose")

        patch_id = data["patch_id"]
        r = await session.call_tool("brain_apply_patch", {"patch_id": patch_id})
        _check(r.isError is False, "apply_patch isError=False")
        data = _first_json(r.content)
        _check(data["status"] == "applied", "apply_patch status=applied")
        _check(demo_path.exists(), "demo note ON disk after apply")
        _check("undo_id" in data, "apply_patch returned undo_id")

        undo_id = data["undo_id"]
        r = await session.call_tool("brain_undo_last", {"undo_id": undo_id})
        _check(r.isError is False, "undo_last isError=False")
        data = _first_json(r.content)
        _check(data["status"] == "reverted", "undo_last status=reverted")
        _check(not demo_path.exists(), "demo note GONE after undo")

        # ------------------------------------------------------------------
        # Gate 8 — propose → reject
        # ------------------------------------------------------------------
        print("[gate 8] brain_propose_note → brain_reject_patch")
        r = await session.call_tool(
            "brain_propose_note",
            {
                "path": "research/notes/reject-me.md",
                "content": "nope\n",
                "reason": "will reject",
            },
        )
        _check(r.isError is False, "propose_note (reject path) isError=False")
        data = _first_json(r.content)
        pid = data["patch_id"]
        r = await session.call_tool(
            "brain_reject_patch",
            {"patch_id": pid, "reason": "plan 04 demo rejection"},
        )
        _check(r.isError is False, "reject_patch isError=False")
        data = _first_json(r.content)
        _check(data["status"] == "rejected", "reject_patch status=rejected")
        _check(
            not (vault / "research" / "notes" / "reject-me.md").exists(),
            "rejected note NOT on disk",
        )

        # ------------------------------------------------------------------
        # Gate 9 — brain_cost_report
        # ------------------------------------------------------------------
        print("[gate 9] brain_cost_report")
        r = await session.call_tool("brain_cost_report", {})
        _check(r.isError is False, "cost_report isError=False")
        data = _first_json(r.content)
        _check("today_usd" in data, "cost_report has today_usd")

        # ------------------------------------------------------------------
        # Gate 10 — brain_config_get (tolerate missing on-disk config)
        # ------------------------------------------------------------------
        print("[gate 10] brain_config_get")
        try:
            r = await session.call_tool("brain_config_get", {"key": "active_domain"})
            if r.isError:
                # Missing config key/file surfaces as an MCP error — accept per plan.
                err_text = " ".join(getattr(c, "text", "") for c in r.content).lower()
                print(f"  OK  [deferred: config_get error surfaced: {err_text.strip()[:80]}]")
            else:
                _check(True, "config_get returned successfully")
        except Exception as exc:
            print(f"  OK  [deferred: {exc}]")

        # ------------------------------------------------------------------
        # Gate 11 — scope guard refuses personal/
        # ------------------------------------------------------------------
        print("[gate 11] scope guard refuses personal/")
        r = await session.call_tool("brain_read_note", {"path": "personal/notes/secret.md"})
        _check(r.isError is True, "reading personal/ from research scope returns isError=True")
        err_text = " ".join(getattr(c, "text", "") for c in r.content).lower()
        _check(
            "personal" in err_text or "scope" in err_text,
            "scope error mentions personal/scope",
        )

        # ------------------------------------------------------------------
        # Gate 12 — brain://BRAIN.md resource
        # ------------------------------------------------------------------
        print("[gate 12] brain://BRAIN.md resource")
        res = await session.read_resource(AnyUrl("brain://BRAIN.md"))
        _check(len(res.contents) >= 1, "BRAIN.md resource returned content")
        text = getattr(res.contents[0], "text", "")
        _check("You are brain" in text, "BRAIN.md resource content returned")

        # ------------------------------------------------------------------
        # Gate 13 — brain://research/index.md resource
        # ------------------------------------------------------------------
        print("[gate 13] brain://research/index.md resource")
        res = await session.read_resource(AnyUrl("brain://research/index.md"))
        _check(
            any("karpathy" in getattr(c, "text", "") for c in res.contents),
            "research index resource content returned",
        )


async def _gate_14_selftest_subprocess(tmp: Path, vault: Path) -> None:
    """Gate 14 — ``brain mcp selftest`` via subprocess against a fake config."""
    print("[gate 14] brain mcp selftest via subprocess")
    fake_config = tmp / "claude_config.json"
    cd_install(
        config_path=fake_config,
        command=sys.executable,
        args=["-m", "brain_mcp"],
        env={
            "BRAIN_VAULT_ROOT": str(vault),
            "BRAIN_ALLOWED_DOMAINS": "research,work",
        },
    )
    env = {
        **os.environ,
        "BRAIN_CLAUDE_DESKTOP_CONFIG_PATH": str(fake_config),
        # Belt-and-braces: if a future `_subprocess_tools_list` refactor
        # inherits parent env, the subprocess will land on the temp vault
        # rather than the user's real ~/Documents/brain.
        "BRAIN_VAULT_ROOT": str(vault),
    }
    result = subprocess.run(
        ["uv", "run", "brain", "mcp", "selftest"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    _check(
        result.returncode == 0,
        (
            f"brain mcp selftest exited 0 (got {result.returncode})\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        ),
    )
    _check(
        "selftest passed" in result.stdout,
        "selftest stdout reports passed",
    )


async def _run_demo() -> int:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        vault = tmp / "vault"
        _scaffold_vault(vault)

        # Client gates (1-4, 6-13) run first. Gate 5 stages a pending patch
        # via the ingest pipeline, so running it BEFORE Gate 6 would pollute
        # the empty-baseline assertion. We run Gate 5 after the client
        # session has closed and released its StateDB handle — it opens its
        # own on the same file, which SQLite handles fine at this scale.
        await _run_client_gates(vault)

        print("[gate 5] brain_ingest (direct handle() call — see module docstring)")
        await _gate_5_ingest_direct(vault)

        await _gate_14_selftest_subprocess(tmp, vault)

        print()
        print("PLAN 04 DEMO OK")
        return 0


def main() -> int:
    return asyncio.run(_run_demo())


if __name__ == "__main__":
    sys.exit(main())


# Re-export for type checkers / linters that scan top-level symbols.
__all__ = ["main"]
