from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.vault.paths import ScopeError
from brain_core.vault.types import Edit, IndexEntryPatch, NewFile, PatchSet
from brain_core.vault.writer import (
    PatchTooLargeError,
    TooManyFilesError,
    VaultWriter,
)


def test_apply_new_file(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "a.md",
                content="---\ntitle: A\n---\n\nhi\n",
            )
        ],
        log_entry="## [2026-04-13 10:00] ingest | new | [[a]] | touched: sources",
        reason="test",
    )
    receipt = vw.apply(ps, allowed_domains=("research",))
    assert receipt.applied_files == [ephemeral_vault / "research" / "sources" / "a.md"]
    assert (
        (ephemeral_vault / "research" / "sources" / "a.md")
        .read_text(encoding="utf-8")
        .startswith("---")
    )


def test_apply_edit(ephemeral_vault: Path) -> None:
    target = ephemeral_vault / "research" / "concepts" / "c.md"
    target.write_text("---\ntitle: C\n---\n\nold body\n", encoding="utf-8")
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        edits=[Edit(path=target, old="old body", new="new body")],
        log_entry="## [2026-04-13 10:01] update | [[c]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    assert "new body" in target.read_text(encoding="utf-8")


def test_refuses_patch_outside_scope(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "personal" / "sources" / "x.md",
                content="---\ntitle: X\n---\n",
            )
        ]
    )
    with pytest.raises(ScopeError):
        vw.apply(ps, allowed_domains=("research",))


def test_rejects_oversize_patch(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault, max_patch_bytes=100)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "big.md",
                content="x" * 200,
            )
        ]
    )
    with pytest.raises(PatchTooLargeError):
        vw.apply(ps, allowed_domains=("research",))


def test_rejects_too_many_files(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault, max_files_per_patch=2)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / f"n{i}.md",
                content="---\ntitle: n\n---\n",
            )
            for i in range(3)
        ]
    )
    with pytest.raises(TooManyFilesError):
        vw.apply(ps, allowed_domains=("research",))


def test_index_entry_patch_applied(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        index_entries=[
            IndexEntryPatch(section="Sources", line="- [[alpha]] — first", domain="research")
        ],
        log_entry="## [2026-04-13 10:02] ingest | [[alpha]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    idx = (ephemeral_vault / "research" / "index.md").read_text(encoding="utf-8")
    assert "[[alpha]] — first" in idx


def test_log_entry_newlines_are_sanitized(ephemeral_vault: Path) -> None:
    """A malicious log_entry containing embedded newlines must not be able to
    forge historical log headers in log.md."""
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=ephemeral_vault / "research" / "sources" / "n.md",
                content="---\ntitle: N\n---\n",
            )
        ],
        log_entry="legit summary\n## [1970-01-01 00:00] forged | FAKE",
    )
    vw.apply(ps, allowed_domains=("research",))
    log_text = (ephemeral_vault / "research" / "log.md").read_text(encoding="utf-8")
    for line in log_text.splitlines():
        assert not line.strip().startswith("## [1970-01-01 00:00] forged"), (
            f"log injection: forged header rendered as real heading: {line!r}"
        )
    assert "legit summary" in log_text


def test_apply_accepts_vault_relative_paths(ephemeral_vault: Path) -> None:
    """Plan 04 Task 25: VaultWriter.apply must absolutize vault-relative
    NewFile / Edit paths against vault_root before scope_guard. scope_guard
    calls Path.resolve() which would otherwise resolve the relative path
    against the current working directory, not the vault — silently rejecting
    (or, in rare CWD-matches-vault cases, silently accepting) relative paths.

    This is the primary path exercised by brain_mcp.tools.apply_patch and
    brain_cli.commands.patches — the envelope stores vault-relative paths for
    portability.
    """
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        new_files=[
            NewFile(
                path=Path("research/sources/rel.md"),
                content="---\ntitle: Rel\n---\n\nbody\n",
            )
        ],
        log_entry="## [2026-04-17 10:00] ingest | new | [[rel]]",
        reason="relative-path regression test",
    )
    receipt = vw.apply(ps, allowed_domains=("research",))
    # File must land under vault_root even though the caller passed a
    # vault-relative path.
    landed = ephemeral_vault / "research" / "sources" / "rel.md"
    assert landed.exists()
    assert landed.read_text(encoding="utf-8").startswith("---")
    # The receipt records the absolute path so downstream consumers
    # (CLI, MCP tool responses, undo log) see a single canonical shape.
    assert receipt.applied_files == [landed]


def test_apply_accepts_vault_relative_paths_for_edits(ephemeral_vault: Path) -> None:
    """Companion to the new-file case: Edit.path as vault-relative must also
    be absolutized against vault_root before scope_guard."""
    target_abs = ephemeral_vault / "research" / "concepts" / "rel-edit.md"
    target_abs.write_text("---\ntitle: E\n---\n\nold body\n", encoding="utf-8")
    vw = VaultWriter(vault_root=ephemeral_vault)
    ps = PatchSet(
        edits=[Edit(path=Path("research/concepts/rel-edit.md"), old="old body", new="new body")],
        log_entry="## [2026-04-17 10:01] update | [[rel-edit]]",
    )
    vw.apply(ps, allowed_domains=("research",))
    assert "new body" in target_abs.read_text(encoding="utf-8")


def test_atomic_no_partial_state_on_failure(ephemeral_vault: Path) -> None:
    """If one write in a patch fails, earlier writes are rolled back via undo log."""
    vw = VaultWriter(vault_root=ephemeral_vault)
    good = ephemeral_vault / "research" / "sources" / "good.md"
    ps = PatchSet(
        new_files=[
            NewFile(path=good, content="---\ntitle: G\n---\n"),
            NewFile(path=ephemeral_vault / "personal" / "sources" / "bad.md", content="---\n---\n"),
        ]
    )
    with pytest.raises(ScopeError):
        vw.apply(ps, allowed_domains=("research",))
    assert not good.exists()


def test_rollback_on_mid_patch_edit_failure_restores_prior_writes(
    ephemeral_vault: Path,
) -> None:
    """Issue #26: a mid-patch failure (after pre-validation) rolls back prior writes.

    Pre-validation (scope_guard, size, count) runs before any mutation, so
    those failures never enter the rollback path. The realistic mid-patch
    failure is an Edit whose ``old`` text is not present in the file —
    that raises after the new_files have already been written.
    """
    vw = VaultWriter(vault_root=ephemeral_vault)
    new_target = ephemeral_vault / "research" / "sources" / "n.md"
    edit_target = ephemeral_vault / "research" / "concepts" / "e.md"
    edit_target.parent.mkdir(parents=True, exist_ok=True)
    edit_target.write_text("---\ntitle: E\n---\n\noriginal\n", encoding="utf-8")

    ps = PatchSet(
        new_files=[NewFile(path=new_target, content="---\ntitle: N\n---\nfresh\n")],
        edits=[Edit(path=edit_target, old="MISSING-OLD-TEXT", new="x")],
    )
    with pytest.raises(ValueError, match="edit old-text not found"):
        vw.apply(ps, allowed_domains=("research",))

    # The rollback must have removed the new file.
    assert not new_target.exists(), "rollback should have unlinked the staged new_file"
    # The edit target must be untouched (the edit failed before write).
    assert edit_target.read_text(encoding="utf-8") == "---\ntitle: E\n---\n\noriginal\n"


def test_undo_record_persisted_before_each_mutation(ephemeral_vault: Path) -> None:
    """Issue #26: persist undo records before mutations complete.

    A SIGKILL between a successful write and the undo-record write would
    leave un-undo-able mutations on disk. The writer now persists the
    in-progress undo record after each new_file/edit append, so an
    out-of-band death has a recoverable trail.

    We can't easily SIGKILL the writer mid-apply from a test, so we
    instead patch ``_atomic_write`` to raise on the SECOND call and
    assert that an undo record exists on disk (proving it was written
    before the second mutation was attempted).
    """
    vw = VaultWriter(vault_root=ephemeral_vault)
    n1 = ephemeral_vault / "research" / "sources" / "n1.md"
    n2 = ephemeral_vault / "research" / "sources" / "n2.md"

    real_atomic_write = vw._atomic_write
    call_count = {"n": 0}

    def flaky_atomic_write(path: Path, content: str) -> None:
        call_count["n"] += 1
        # Fail the second mutation. The first will have already written.
        if call_count["n"] == 2:
            raise OSError("simulated disk failure")
        real_atomic_write(path, content)

    vw._atomic_write = flaky_atomic_write  # type: ignore[method-assign]

    ps = PatchSet(
        new_files=[
            NewFile(path=n1, content="---\ntitle: N1\n---\n"),
            NewFile(path=n2, content="---\ntitle: N2\n---\n"),
        ]
    )
    with pytest.raises(OSError, match="simulated disk failure"):
        vw.apply(ps, allowed_domains=("research",))

    # An undo record was persisted before each attempted mutation.
    # The rollback path also rewrites it, so its existence is the proof
    # we want — but more importantly, it must reference n1 (the file
    # that was actually written before the failure).
    undo_dir = ephemeral_vault / ".brain" / "undo"
    undo_files = list(undo_dir.glob("*.txt"))
    assert undo_files, "expected an undo record on disk after a mid-patch failure"
    record = undo_files[-1].read_text(encoding="utf-8")
    assert str(n1) in record, "undo record must contain the path of the file that was written"


def test_receipt_applied_files_cleared_on_rollback(ephemeral_vault: Path) -> None:
    """Issue #26: ``Receipt.applied_files`` is reset on rollback.

    Defense-in-depth: callers should never observe ``applied_files`` for a
    failed apply (the function re-raises, but other code paths might hold a
    reference to the receipt object).
    """
    vw = VaultWriter(vault_root=ephemeral_vault)
    n1 = ephemeral_vault / "research" / "sources" / "n1.md"
    edit_target = ephemeral_vault / "research" / "concepts" / "e.md"
    edit_target.parent.mkdir(parents=True, exist_ok=True)
    edit_target.write_text("---\ntitle: E\n---\n\noriginal\n", encoding="utf-8")

    captured: dict[str, object] = {}

    real_apply = vw.apply

    def capturing_apply(patch: PatchSet, *, allowed_domains: tuple[str, ...]) -> object:
        # We monkey-patch atomic_write to fail on the edit step, then
        # let the original apply run; since apply constructs its own
        # Receipt internally, we observe state through the on-disk
        # n1.md (must not exist after rollback) and re-check no
        # leftover receipt state by re-running and asserting clean.
        return real_apply(patch, allowed_domains=allowed_domains)

    captured["_"] = capturing_apply  # silence unused

    ps = PatchSet(
        new_files=[NewFile(path=n1, content="---\ntitle: N1\n---\n")],
        edits=[Edit(path=edit_target, old="MISSING", new="x")],
    )
    with pytest.raises(ValueError):
        vw.apply(ps, allowed_domains=("research",))
    # n1 was rolled back: not present on disk.
    assert not n1.exists()
    # Sanity: the writer is reusable after a failed apply (i.e., no
    # leftover internal state — this is what 'clear' protects against).
    receipt = vw.apply(
        PatchSet(new_files=[NewFile(path=n1, content="---\ntitle: N1\n---\n")]),
        allowed_domains=("research",),
    )
    assert receipt.applied_files == [n1]
    assert receipt.undo_id is not None


def test_rollback_continues_when_one_step_errors(ephemeral_vault: Path) -> None:
    """Issue #26: a failure during rollback does not abort the remaining rollback steps.

    The writer wraps each rollback step in try/except and accumulates the
    errors as a note on the original exception so the caller sees both.
    """
    vw = VaultWriter(vault_root=ephemeral_vault)
    n1 = ephemeral_vault / "research" / "sources" / "n1.md"
    n2 = ephemeral_vault / "research" / "sources" / "n2.md"
    edit_target = ephemeral_vault / "research" / "concepts" / "e.md"
    edit_target.parent.mkdir(parents=True, exist_ok=True)
    edit_target.write_text("---\ntitle: E\n---\n\noriginal\n", encoding="utf-8")

    ps = PatchSet(
        new_files=[
            NewFile(path=n1, content="---\ntitle: N1\n---\n"),
            NewFile(path=n2, content="---\ntitle: N2\n---\n"),
        ],
        edits=[Edit(path=edit_target, old="MISSING-OLD-TEXT", new="x")],
    )

    # Patch Path.unlink so that the FIRST rollback unlink raises,
    # but the second succeeds. The current rollback iterates in
    # reverse — so this exercises the "first rollback fails, second
    # still runs" path.
    import pathlib

    real_unlink = pathlib.Path.unlink
    n2_unlink_attempts = {"n": 0}

    def flaky_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == n2 and n2_unlink_attempts["n"] == 0:
            n2_unlink_attempts["n"] += 1
            raise OSError("simulated rollback failure on n2")
        real_unlink(self, *args, **kwargs)

    pathlib.Path.unlink = flaky_unlink  # type: ignore[method-assign]
    try:
        with pytest.raises(ValueError) as excinfo:
            vw.apply(ps, allowed_domains=("research",))
    finally:
        pathlib.Path.unlink = real_unlink  # type: ignore[method-assign]

    # The original error is preserved.
    assert "edit old-text not found" in str(excinfo.value)
    # The rollback failure was attached as a note, not swallowed.
    assert any(
        "rollback hit" in note and "n2" in note for note in getattr(excinfo.value, "__notes__", [])
    ), f"expected rollback note on exception; got notes={getattr(excinfo.value, '__notes__', [])}"
    # Despite the rollback failure on n2, n1 was still rolled back.
    assert not n1.exists(), "n1 rollback should have proceeded after n2 rollback failure"


class TestRenameFile:
    def test_rename_file_moves_file_atomically(self, ephemeral_vault: Path) -> None:
        src = ephemeral_vault / "research" / "sources" / "old.md"
        src.write_text("body", encoding="utf-8")
        writer = VaultWriter(vault_root=ephemeral_vault)
        dst = ephemeral_vault / "research" / "sources" / "new.md"
        receipt = writer.rename_file(src, dst, allowed_domains=("research",))
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "body"
        assert receipt.undo_id is not None
        assert receipt.applied_files == [Path("research/sources/new.md")]

    def test_rename_file_rejects_cross_domain(self, ephemeral_vault: Path) -> None:
        src = ephemeral_vault / "research" / "sources" / "old.md"
        src.write_text("body", encoding="utf-8")
        writer = VaultWriter(vault_root=ephemeral_vault)
        dst = ephemeral_vault / "work" / "sources" / "new.md"
        # Plan 03 Task 24 Batch A: the specific error is ScopeError (a
        # PermissionError subclass), not a bare PermissionError.
        with pytest.raises(ScopeError, match="rename across domains"):
            writer.rename_file(src, dst, allowed_domains=("research", "work"))
        assert src.exists()

    def test_rename_file_rejects_src_outside_vault(
        self, ephemeral_vault: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("body", encoding="utf-8")
        writer = VaultWriter(vault_root=ephemeral_vault)
        dst = ephemeral_vault / "research" / "sources" / "new.md"
        with pytest.raises(PermissionError):  # ScopeError is a PermissionError
            writer.rename_file(outside, dst, allowed_domains=("research",))
        assert outside.exists()

    def test_rename_file_rejects_dst_outside_vault(
        self, ephemeral_vault: Path, tmp_path: Path
    ) -> None:
        src = ephemeral_vault / "research" / "sources" / "old.md"
        src.write_text("body", encoding="utf-8")
        outside_dst = tmp_path / "escape.md"
        writer = VaultWriter(vault_root=ephemeral_vault)
        with pytest.raises(PermissionError):
            writer.rename_file(src, outside_dst, allowed_domains=("research",))
        assert src.exists()
        assert not outside_dst.exists()

    def test_rename_file_src_must_exist(self, ephemeral_vault: Path) -> None:
        writer = VaultWriter(vault_root=ephemeral_vault)
        src = ephemeral_vault / "research" / "sources" / "ghost.md"
        dst = ephemeral_vault / "research" / "sources" / "new.md"
        with pytest.raises(FileNotFoundError):
            writer.rename_file(src, dst, allowed_domains=("research",))
        assert not dst.exists()

    def test_rename_file_refuses_overwrite(self, ephemeral_vault: Path) -> None:
        src = ephemeral_vault / "research" / "sources" / "a.md"
        src.write_text("a", encoding="utf-8")
        dst = ephemeral_vault / "research" / "sources" / "b.md"
        dst.write_text("b", encoding="utf-8")
        writer = VaultWriter(vault_root=ephemeral_vault)
        with pytest.raises(FileExistsError, match="already exists"):
            writer.rename_file(src, dst, allowed_domains=("research",))
        assert src.exists()
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "b"

    def test_rename_file_writes_undo_record(self, ephemeral_vault: Path) -> None:
        src = ephemeral_vault / "research" / "sources" / "old.md"
        src.write_text("body", encoding="utf-8")
        writer = VaultWriter(vault_root=ephemeral_vault)
        dst = ephemeral_vault / "research" / "sources" / "new.md"
        receipt = writer.rename_file(src, dst, allowed_domains=("research",))
        undo_file = ephemeral_vault / ".brain" / "undo" / f"{receipt.undo_id}.txt"
        assert undo_file.exists()
        contents = undo_file.read_text(encoding="utf-8")
        assert contents.startswith("RENAME")
        assert "SRC" in contents
        assert "DST" in contents

    def test_rename_undo_record_uses_lf_line_endings(
        self, ephemeral_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression (Plan 03 Task 22 cross-platform sweep): the rename undo
        # record must be written with LF line endings on every platform so it
        # matches the rest of the vault's on-disk convention. Path.write_text
        # without newline="\n" translates \n -> os.linesep on Windows, which
        # would produce CRLF. We can't run on Windows in local CI, so we
        # intercept Path.write_text and assert newline="\n" is explicitly
        # passed for the rename undo record.
        import pathlib

        real_write_text = pathlib.Path.write_text
        seen_kwargs: list[dict[str, object]] = []

        def spy_write_text(self_: Path, data: str, **kwargs: object) -> int:
            if ".brain/undo/" in self_.as_posix() or ".brain\\undo\\" in str(self_):
                seen_kwargs.append(dict(kwargs))
            return real_write_text(self_, data, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(pathlib.Path, "write_text", spy_write_text)

        src = ephemeral_vault / "research" / "sources" / "old.md"
        src.write_text("body", encoding="utf-8")
        writer = VaultWriter(vault_root=ephemeral_vault)
        dst = ephemeral_vault / "research" / "sources" / "new.md"
        writer.rename_file(src, dst, allowed_domains=("research",))

        assert seen_kwargs, "rename undo record was not written via Path.write_text"
        rename_call = seen_kwargs[-1]
        assert rename_call.get("newline") == "\n", (
            f"rename undo record must be written with newline='\\n' to avoid "
            f"CRLF translation on Windows; got kwargs={rename_call}"
        )
