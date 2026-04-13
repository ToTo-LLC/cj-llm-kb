"""Plan 01 end-to-end demo.

Runs in a temp directory, exercises the full brain_core surface with FakeLLMProvider,
and prints a success report. This is the plan 01 demo gate.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from brain_core.config.loader import load_config
from brain_core.cost.budget import BudgetEnforcer
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.vault.index import IndexFile
from brain_core.vault.log import LogEntry, LogFile
from brain_core.vault.types import IndexEntryPatch, NewFile, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "brain"
        _scaffold_vault(root)

        # 1. Config layered resolution
        cfg = load_config(
            config_file=None,
            env={"BRAIN_WEB_PORT": "5555"},
            cli_overrides={"vault_path": root},
        )
        assert cfg.web_port == 5555
        assert cfg.vault_path == root
        print(f"✓ config loaded: port={cfg.web_port} vault={cfg.vault_path}")

        # 2. FakeLLMProvider round trip
        fake = FakeLLMProvider()
        fake.queue("ok")
        resp = await fake.complete(
            LLMRequest(
                model="claude-sonnet-4-6",
                messages=[LLMMessage(role="user", content="hi")],
            )
        )
        assert resp.content == "ok"
        print("✓ FakeLLMProvider round trip")

        # 3. Cost ledger + budget enforcer
        ledger = CostLedger(db_path=root / ".brain" / "costs.sqlite")
        ledger.record(
            CostEntry(
                timestamp=datetime.now(tz=UTC),
                operation="ingest",
                model="claude-sonnet-4-6",
                input_tokens=1000,
                output_tokens=300,
                cost_usd=0.0075,
                domain="research",
            )
        )
        today = datetime.now(tz=UTC).date()
        assert round(ledger.total_for_day(today), 4) == 0.0075
        be = BudgetEnforcer(ledger=ledger, daily_usd=1.0, monthly_usd=10.0)
        be.check_can_spend(0.1)
        print(f"✓ cost ledger + budget enforcer (today=${ledger.total_for_day(today):.4f})")

        # 4. VaultWriter applies a real PatchSet
        vw = VaultWriter(vault_root=root)
        note_path = root / "research" / "sources" / "demo.md"
        patch = PatchSet(
            new_files=[
                NewFile(
                    path=note_path,
                    content=(
                        "---\n"
                        "title: Demo note\n"
                        "domain: research\n"
                        "type: source\n"
                        "---\n\n"
                        "This is a demo note written through VaultWriter.\n"
                    ),
                )
            ],
            index_entries=[
                IndexEntryPatch(
                    section="Sources",
                    line="- [[demo]] — plan 01 demo note",
                    domain="research",
                )
            ],
            log_entry="## [2026-04-13 12:00] ingest | source | [[demo]] | touched: sources, index",
            reason="plan 01 demo",
        )
        receipt = vw.apply(patch, allowed_domains=("research",))
        assert note_path.exists()
        idx = IndexFile.load(root / "research" / "index.md")
        assert any(e.target == "demo" for e in idx.sections["Sources"])
        print(f"✓ VaultWriter applied patch: {[str(p) for p in receipt.applied_files]}")

        # 5. Log appended
        LogFile(root / "research" / "log.md").append(
            LogEntry(
                timestamp=datetime.now(tz=UTC),
                op="ingest",
                summary="demo | source | [[demo]]",
            )
        )
        print("✓ log.md appended")

        # 6. Undo revert
        UndoLog(vault_root=root).revert(receipt.undo_id or "")
        assert not note_path.exists()
        print("✓ undo log reverts the patch")

        print("\nPLAN 01 DEMO OK")
        return 0


def _scaffold_vault(root: Path) -> None:
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


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
