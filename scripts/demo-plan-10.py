"""Plan 10 end-to-end demo — configurable domains.

Walks the seven gates in the plan's demo-gate section:

    1. Vault boots with the v0.1 ``{research, work, personal}`` set.
    2. ``brain_create_domain`` adds ``hobby``;
       ``brain_list_domains`` returns 4.
    3. Ingest a fixture into ``hobby``; assert the source note + index
       entry land under ``hobby/``.
    4. ``brain_rename_domain`` flips ``work`` → ``consulting``;
       wikilinks across the vault are rewritten.
    5. ``brain_rename_domain`` for ``personal`` is refused (D5).
    6. ``brain_delete_domain consulting`` moves the folder to
       ``.brain/trash/`` and writes the undo log entry.
    7. Restart classifier with ``{research, hobby, personal}``;
       assert classify renders the prompt with the new enum and the
       LLM reply round-trips.

Prints ``PLAN 10 DEMO OK`` on exit 0; non-zero exit + a printed gate
label on any failure.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from brain_core.config.schema import Config
from brain_core.ingest.classifier import classify
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import ClassifyOutput, SummarizeOutput
from brain_core.tools.base import ToolContext
from brain_core.tools.create_domain import handle as create_domain_handle
from brain_core.tools.delete_domain import handle as delete_domain_handle
from brain_core.tools.list_domains import handle as list_domains_handle
from brain_core.tools.rename_domain import handle as rename_domain_handle
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


def _gate(label: str) -> None:
    print(f"  ✓ Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  ✗ Gate {label}: {why}", file=sys.stderr)
    return 1


def _scaffold_vault(root: Path) -> None:
    """Build a v0.1 default vault: research / work / personal + ``.brain/``."""
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
    # Seed a wikilink that will be rewritten when ``work`` → ``consulting``.
    (root / "research" / "concepts" / "alpha.md").write_text(
        "---\ntitle: Alpha\ndomain: research\n---\n\n"
        "# Alpha\n\nReferences [[work/sources/helios-call]] in the work domain.\n",
        encoding="utf-8",
    )


def _ctx(root: Path, *, allowed: tuple[str, ...], cfg: Config | None = None) -> ToolContext:
    """Build a ToolContext for the demo. Most fields are unused by the
    domain-admin tools; we wire the bare minimum (vault + undo log)."""
    return ToolContext(
        vault_root=root,
        allowed_domains=allowed,
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=VaultWriter(vault_root=root),
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=UndoLog(vault_root=root),
        config=cfg,
    )


async def _run() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "brain"
        _scaffold_vault(root)

        # ---- Gate 1: boots with default set ---------------------------
        cfg = Config(domains=["research", "work", "personal"])
        ctx = _ctx(root, allowed=("research", "work", "personal"), cfg=cfg)
        listing = await list_domains_handle({}, ctx)
        if listing.data is None or sorted(listing.data["domains"]) != [
            "personal",
            "research",
            "work",
        ]:
            return _fail("1", f"unexpected initial domain set: {listing.data}")
        _gate("1 — default set {research, work, personal}")

        # ---- Gate 2: brain_create_domain hobby ------------------------
        await create_domain_handle({"slug": "hobby", "name": "Hobby"}, ctx)
        listing = await list_domains_handle({}, ctx)
        if listing.data is None or "hobby" not in listing.data["domains"]:
            return _fail("2", f"hobby not in list_domains after create: {listing.data}")
        if len(listing.data["domains"]) != 4:
            return _fail("2", f"expected 4 domains, got {len(listing.data['domains'])}")
        if "hobby" not in cfg.domains:
            return _fail("2", "hobby not appended to Config.domains in-memory")
        _gate("2 — hobby created; list_domains returns 4")

        # ---- Gate 3: ingest into hobby --------------------------------
        # Use ``domain_override="hobby"`` to skip classify so the
        # demo doesn't need to coordinate the classify prompt's enum
        # with the FakeLLMProvider queue. Stage 5 still validates
        # the override is in ``allowed_domains``.
        fake = FakeLLMProvider()
        fake.queue(
            SummarizeOutput(
                title="My Fishing Rod",
                summary="A short note about a 7-foot graphite spinning rod.",
                key_points=["graphite blank", "trout-rated"],
                entities=[],
                concepts=[],
                open_questions=[],
            ).model_dump_json()
        )
        fake.queue(
            PatchSet(
                new_files=[],
                index_entries=[
                    IndexEntryPatch(
                        section="Sources",
                        line="- [[my-fishing-rod]] — first hobby note",
                        domain="hobby",
                    )
                ],
                log_entry="## [2026-04-27 11:45] ingest | source | [[my-fishing-rod]]",
                reason="plan-10 demo: hobby ingest",
            ).model_dump_json()
        )
        # Pipeline writes ``hobby/index.md`` + ``hobby/log.md`` lazily;
        # seed them so the integrate step has a target.
        (root / "hobby").mkdir(exist_ok=True)
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (root / "hobby" / sub).mkdir(exist_ok=True)
        (root / "hobby" / "index.md").write_text(
            "# hobby — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (root / "hobby" / "log.md").write_text("# hobby — log\n", encoding="utf-8")
        pipeline = IngestPipeline(
            vault_root=root,
            writer=VaultWriter(vault_root=root),
            llm=fake,
            summarize_model="claude-sonnet-4-6",
            integrate_model="claude-sonnet-4-6",
            classify_model="claude-haiku-4-5-20251001",
        )
        # ``IngestPipeline.ingest`` dispatches by handler — TextHandler
        # claims ``.txt`` / ``.md`` Path objects. Write a fixture in
        # tmp and pass its absolute Path so the pipeline runs end-to-end
        # (handler → extract → summarize → integrate → apply).
        fixture = Path(tmp) / "fishing-rod.txt"
        fixture.write_text(
            "Bought a 7-foot graphite spinning rod for trout fishing.\n",
            encoding="utf-8",
        )
        result = await pipeline.ingest(
            fixture,
            allowed_domains=("research", "work", "personal", "hobby"),
            domain_override="hobby",
        )
        if result.status is not IngestStatus.OK:
            return _fail("3", f"ingest status was {result.status}, expected OK")
        if result.note_path is None or "hobby" not in str(result.note_path):
            return _fail("3", f"note_path not under hobby/: {result.note_path}")
        # Index entry landed.
        hobby_index = (root / "hobby" / "index.md").read_text(encoding="utf-8")
        if "[[my-fishing-rod]]" not in hobby_index:
            return _fail("3", "hobby/index.md missing the new source line")
        _gate("3 — fishing-rod ingest landed under hobby/")

        # ---- Gate 4: rename work → consulting -------------------------
        # Drop a wikilink-target file so the rewrite step has something
        # to walk. The seeded ``research/concepts/alpha.md`` already
        # references ``work/sources/helios-call``; ensure that file
        # exists so the wikilink resolves.
        (root / "work" / "sources").mkdir(exist_ok=True)
        (root / "work" / "sources" / "helios-call.md").write_text(
            "---\ntitle: Helios call\ndomain: work\n---\n\n# Helios call\n\nNotes.\n",
            encoding="utf-8",
        )
        rename_res = await rename_domain_handle({"from": "work", "to": "consulting"}, ctx)
        if rename_res.data is None or rename_res.data.get("status") != "renamed":
            return _fail("4", f"rename failed: {rename_res.data}")
        if (root / "work").exists():
            return _fail("4", "old work/ folder still exists after rename")
        if not (root / "consulting").exists():
            return _fail("4", "new consulting/ folder missing after rename")
        alpha = (root / "research" / "concepts" / "alpha.md").read_text(encoding="utf-8")
        if "[[consulting/sources/helios-call]]" not in alpha:
            return _fail("4", "wikilink not rewritten in research/concepts/alpha.md")
        if "consulting" not in cfg.domains or "work" in cfg.domains:
            return _fail("4", f"Config.domains not updated: {cfg.domains}")
        _gate("4 — work → consulting; wikilinks rewritten")

        # ---- Gate 5: rename personal is refused (D5) ------------------
        try:
            await rename_domain_handle({"from": "personal", "to": "private"}, ctx)
            return _fail("5", "rename personal succeeded — privacy rail breached")
        except PermissionError as exc:
            if "privacy" not in str(exc):
                return _fail("5", f"unexpected error: {exc}")
        _gate("5 — rename(personal) refused with privacy-rail error")

        # ---- Gate 6: delete consulting --------------------------------
        # Note: the delete-domain tool now requires there to be at
        # least 2 non-personal domains so the user can't accidentally
        # leave only ``personal``. After the rename, the live set is
        # {research, consulting, personal, hobby}. Deleting consulting
        # leaves {research, hobby, personal} — non-personal count = 2.
        delete_res = await delete_domain_handle({"slug": "consulting", "typed_confirm": True}, ctx)
        if delete_res.data is None or delete_res.data.get("status") != "deleted":
            return _fail("6", f"delete failed: {delete_res.data}")
        trash_path = Path(delete_res.data["trash_path"])
        if not trash_path.exists():
            return _fail("6", f"trash path missing: {trash_path}")
        undo_id = delete_res.data["undo_id"]
        undo_file = root / ".brain" / "undo" / f"{undo_id}.txt"
        if not undo_file.exists():
            return _fail("6", "undo record not written")
        if "consulting" in cfg.domains:
            return _fail("6", f"Config.domains still contains consulting: {cfg.domains}")
        _gate("6 — consulting moved to trash; undo log entry written")

        # ---- Gate 7: classifier renders prompt with the live enum -----
        # The pipeline's classify step is wired to ``allowed_domains``
        # per Plan 10 Task 4. Build a tiny standalone classify call
        # with the new domain set and assert the prompt advertises the
        # new slugs.
        fake_classify = FakeLLMProvider()
        fake_classify.queue(
            ClassifyOutput(
                source_type="text",
                domain="hobby",
                confidence=0.9,
            ).model_dump_json()
        )
        post_restart_domains = ("research", "hobby", "personal")
        cls = await classify(
            llm=fake_classify,
            model="test-model",
            title="Trout outing",
            snippet="Drove up to the river for a morning of fishing.",
            allowed_domains=post_restart_domains,
        )
        if cls.domain != "hobby":
            return _fail("7", f"classify returned {cls.domain!r}, expected hobby")
        if cls.needs_user_pick:
            return _fail("7", "needs_user_pick flipped True for an in-set reply")
        sent_system = fake_classify.requests[0].system or ""
        if "`hobby`" not in sent_system or "`work`" in sent_system:
            return _fail(
                "7",
                "classify prompt did not render the post-restart enum "
                f"(saw: {sent_system[:120]!r})",
            )
        _gate("7 — classify renders {research, hobby, personal}; routes to hobby")

        # All seven gates green. Print the canonical success marker so
        # CI / the calling shell can grep for it.
        print()
        print("PLAN 10 DEMO OK")
        return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
