from __future__ import annotations

from pathlib import Path

from brain_core.vault.index import IndexEntry, IndexFile


def test_parse_and_roundtrip(ephemeral_vault: Path) -> None:
    idx_path = ephemeral_vault / "research" / "index.md"
    idx_path.write_text(
        "# research — index\n\n"
        "## Sources\n"
        "- [[alpha]] — first source\n"
        "- [[beta]] — second\n\n"
        "## Entities\n\n"
        "## Concepts\n"
        "- [[knowledge-compilation]] — core concept\n\n"
        "## Synthesis\n",
        encoding="utf-8",
    )
    idx = IndexFile.load(idx_path)
    assert [e.target for e in idx.sections["Sources"]] == ["alpha", "beta"]
    assert idx.sections["Concepts"][0].summary == "core concept"

    idx.add_entry("Sources", IndexEntry(target="gamma", summary="third"))
    idx.save()

    reloaded = IndexFile.load(idx_path)
    assert [e.target for e in reloaded.sections["Sources"]] == ["alpha", "beta", "gamma"]


def test_remove_entry(ephemeral_vault: Path) -> None:
    idx_path = ephemeral_vault / "research" / "index.md"
    idx_path.write_text(
        "# research — index\n\n## Sources\n- [[alpha]] — x\n- [[beta]] — y\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    idx = IndexFile.load(idx_path)
    idx.remove_entry("Sources", target="alpha")
    idx.save()

    reloaded = IndexFile.load(idx_path)
    assert [e.target for e in reloaded.sections["Sources"]] == ["beta"]
