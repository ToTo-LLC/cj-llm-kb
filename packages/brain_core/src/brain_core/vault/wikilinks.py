"""Wikilink extraction and resolution. Obsidian-compatible [[target]] syntax."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

# Matches [[target]] or [[target|alias]] — captures the target portion only.
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


@dataclass(frozen=True)
class Resolved:
    target: str
    path: Path


@dataclass(frozen=True)
class BrokenLink:
    target: str


Resolution: TypeAlias = Resolved | BrokenLink


def extract_wikilinks(body: str) -> list[str]:
    """Return all wikilink targets in body, skipping fenced code blocks."""
    stripped = _CODE_FENCE.sub("", body)
    return [m.group(1).strip() for m in _WIKILINK.finditer(stripped)]


def resolve_wikilinks(
    targets: list[str],
    *,
    vault_root: Path,
    active_domain: str,
) -> dict[str, Resolution]:
    """Resolve each target to a concrete .md path, preferring the active domain on collision."""
    out: dict[str, Resolution] = {}
    for target in targets:
        filename = f"{target}.md"
        matches: list[Path] = list((vault_root / active_domain).rglob(filename))
        if not matches:
            for domain_dir in vault_root.iterdir():
                if not domain_dir.is_dir() or domain_dir.name.startswith("."):
                    continue
                if domain_dir.name == active_domain:
                    continue
                matches.extend(domain_dir.rglob(filename))
        if matches:
            out[target] = Resolved(target=target, path=matches[0])
        else:
            out[target] = BrokenLink(target=target)
    return out
