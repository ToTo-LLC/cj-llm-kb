"""brain_rename_domain — rename a top-level vault domain (atomic via UndoLog).

This tool is the second documented exception to "every vault write goes
through ``VaultWriter.apply``" (Plan 07 pre-flight D2a). Renaming a
domain by definition crosses scope boundaries — the new slug is not yet
in any ``allowed_domains`` tuple — so the PatchSet pathway can't model
it. Instead we run the full sequence under a single undo_id:

  1. Walk ``<vault>/<from>/**/*.md`` and rewrite the ``domain:``
     frontmatter field on each file (atomic per-file write).
  2. Walk every OTHER vault domain's ``**/*.md`` and rewrite any
     wikilinks of the form ``[[<from>/...]]`` to point at the new slug.
  3. ``os.rename(<vault>/<from>, <vault>/<to>)`` — single atomic commit.
  4. Persist a ``KIND\trename_domain`` undo record so
     ``brain_undo_last`` can fully reverse.

Atomicity boundaries:

* Steps 1-2 are file-by-file atomic (write to temp, ``os.replace``) —
  a crash mid-step leaves both ``<from>/`` and any other-domain notes
  in a partially-rewritten state but the folder rename hasn't fired
  yet, so the user can re-run.
* Step 3 is the commit point. After this returns, the new slug is the
  authoritative location.
* Step 4 records what we did so undo can replay.

If step 3 fails, steps 1-2's edits are not auto-reverted (the
in-flight per-file content is still semantically correct — the domain
field merely points at a slug that doesn't exist yet). The simplest
recovery is to re-run with ``rewrite_frontmatter=False``.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brain_core.config.schema import PRIVACY_RAILED_SLUG, _validate_domain_slug
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import (
    FrontmatterError,
    parse_frontmatter,
    serialize_with_frontmatter,
)

NAME = "brain_rename_domain"
DESCRIPTION = (
    "Atomically rename a top-level domain (folder + every domain: frontmatter "
    "field + qualifying wikilinks). Returns an undo_id; brain_undo_last reverses. "
    f"Refuses to rename {PRIVACY_RAILED_SLUG!r} (Plan 10 D5 privacy rail) and "
    "refuses TO a slug already in Config.domains."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {"type": "string"},
        "to": {"type": "string"},
        "rewrite_frontmatter": {"type": "boolean", "default": True},
    },
    "required": ["from", "to"],
}


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _rewrite_domain_field(content: str, from_slug: str, to_slug: str) -> str | None:
    """Return the rewritten content, or None if no change.

    Conservative: only mutates if frontmatter parses cleanly and contains a
    ``domain`` field equal to ``from_slug``. Malformed frontmatter is left
    alone (a destructive heuristic on a malformed file would be worse than
    a no-op).
    """
    try:
        fm, body = parse_frontmatter(content)
    except FrontmatterError:
        return None
    if fm.get("domain") != from_slug:
        return None
    new_fm = dict(fm)
    new_fm["domain"] = to_slug
    return serialize_with_frontmatter(new_fm, body=body)


_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _rewrite_wikilinks(content: str, from_slug: str, to_slug: str) -> tuple[str, int]:
    """Rewrite any ``[[<from_slug>/...]]`` wikilinks to ``[[<to_slug>/...]]``.

    Plain-slug wikilinks ``[[note-name]]`` are left alone — they resolve via
    Obsidian's name-only matcher and do not need a path rewrite. We only
    qualify-rewrite the slash-prefixed form.
    """
    count = 0
    prefix = f"{from_slug}/"
    new_prefix = f"{to_slug}/"

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        target = match.group(1)
        if target.startswith(prefix):
            count += 1
            return f"[[{new_prefix}{target[len(prefix) :]}]]"
        return match.group(0)

    rewritten = _WIKILINK_RE.sub(_sub, content)
    return rewritten, count


def _new_undo_id() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%f")


def _write_rename_domain_undo(
    *,
    undo_dir: Path,
    undo_id: str,
    from_slug: str,
    to_slug: str,
    edits: list[tuple[Path, str]],
) -> None:
    """Persist the rename_domain undo record.

    ``edits`` is a list of ``(absolute_path, prev_content)`` pairs. Paths
    are stored as the original ``<vault>/<from>/...`` absolute path so
    revert can re-create the file at its pre-rename location after
    reversing the folder rename.
    """
    undo_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "KIND\trename_domain",
        f"FROM\t{from_slug}",
        f"TO\t{to_slug}",
    ]
    for path, prev in edits:
        lines.append(f"PATH\t{path}")
        lines.append(f"PREV_LEN\t{len(prev)}")
        lines.append(prev)
        lines.append("END_PREV")
    (undo_dir / f"{undo_id}.txt").write_text("\n".join(lines), encoding="utf-8")


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    from_slug = str(arguments["from"])
    to_slug = str(arguments["to"])
    rewrite_frontmatter = bool(arguments.get("rewrite_frontmatter", True))

    # Plan 10 D5: ``personal`` is the privacy-railed slug. Renaming it
    # would break the structural privacy rail since it's hardcoded by
    # name in scope_guard / Config.domains validation / the classify
    # prompt's privacy rule. Refusal is unconditional.
    if from_slug == PRIVACY_RAILED_SLUG:
        raise PermissionError(
            f"refusing to rename {PRIVACY_RAILED_SLUG!r} — it is the privacy-"
            "railed slug (Plan 10 D5) and is referenced by hardcoded name in "
            "scope_guard, Config validation, and the classify prompt. "
            "Renaming would silently disable the privacy rail."
        )
    if to_slug == PRIVACY_RAILED_SLUG:
        raise PermissionError(
            f"refusing to rename TO {PRIVACY_RAILED_SLUG!r} — that slug is "
            "reserved as the privacy-railed name; pick a different target."
        )

    # Plan 10 D2: slug rules unified with Config.domains validation.
    # ``_validate_domain_slug`` raises ValueError with a slug-specific message.
    _validate_domain_slug(from_slug)
    _validate_domain_slug(to_slug)
    if from_slug == to_slug:
        raise ValueError(f"from and to slugs are identical: {from_slug!r}")

    # Plan 10 Task 5: reject TO if the slug is already configured. The
    # on-disk check below catches the typical case (folder exists), but
    # a slug configured-without-folder (D7) would slip past.
    cfg = ctx.config
    if cfg is not None and to_slug in (getattr(cfg, "domains", None) or []):
        raise FileExistsError(
            f"destination slug {to_slug!r} is already in Config.domains. "
            "Pick a target that's not already configured."
        )

    from_dir = ctx.vault_root / from_slug
    to_dir = ctx.vault_root / to_slug
    if not from_dir.exists() or not from_dir.is_dir():
        raise FileNotFoundError(f"source domain {from_slug!r} does not exist at {from_dir}")
    if to_dir.exists():
        raise FileExistsError(f"destination domain {to_slug!r} already exists at {to_dir}")

    edits_for_undo: list[tuple[Path, str]] = []
    files_updated = 0

    # Step 1: rewrite domain: frontmatter on every file inside <from>/.
    if rewrite_frontmatter:
        for md_path in sorted(from_dir.rglob("*.md")):
            try:
                prev = md_path.read_text(encoding="utf-8")
            except OSError:
                continue
            new_content = _rewrite_domain_field(prev, from_slug, to_slug)
            if new_content is None:
                continue
            edits_for_undo.append((md_path, prev))
            _atomic_write(md_path, new_content)
            files_updated += 1

    # Step 2: rewrite [[<from>/...]] wikilinks in every OTHER domain folder.
    wikilinks_rewritten = 0
    for child in sorted(ctx.vault_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue  # skip .brain etc.
        if child.name == from_slug:
            continue  # already processed in step 1
        for md_path in sorted(child.rglob("*.md")):
            try:
                prev = md_path.read_text(encoding="utf-8")
            except OSError:
                continue
            new_content, n = _rewrite_wikilinks(prev, from_slug, to_slug)
            if n == 0:
                continue
            edits_for_undo.append((md_path, prev))
            _atomic_write(md_path, new_content)
            wikilinks_rewritten += n

    # Step 3: COMMIT — the atomic folder rename.
    os.rename(from_dir, to_dir)

    # Plan 10 Task 5: rewrite ``Config.domains`` in-memory so any
    # ``allowed_domains`` reads from the live config see the new slug
    # immediately. Disk persistence is issue #27 / Plan 07 Task 5.
    if cfg is not None and isinstance(getattr(cfg, "domains", None), list):
        try:
            idx = cfg.domains.index(from_slug)
            cfg.domains[idx] = to_slug
        except ValueError:
            # ``from_slug`` wasn't configured — append the new one so
            # the config reflects what's now on disk.
            cfg.domains.append(to_slug)

    # Step 4: write the single undo record. The absolute paths in
    # edits_for_undo still point under <from>/ (the source-of-truth at
    # write time) — the revert path reverses the folder rename FIRST so
    # those paths resolve again.
    undo_id = _new_undo_id()
    undo_dir = ctx.vault_root / ".brain" / "undo"
    _write_rename_domain_undo(
        undo_dir=undo_dir,
        undo_id=undo_id,
        from_slug=from_slug,
        to_slug=to_slug,
        edits=edits_for_undo,
    )

    return ToolResult(
        text=(
            f"renamed domain {from_slug!r} → {to_slug!r} "
            f"(files_updated={files_updated}, wikilinks_rewritten={wikilinks_rewritten})"
        ),
        data={
            "status": "renamed",
            "from": from_slug,
            "to": to_slug,
            "files_updated": files_updated,
            "wikilinks_rewritten": wikilinks_rewritten,
            "undo_id": undo_id,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
