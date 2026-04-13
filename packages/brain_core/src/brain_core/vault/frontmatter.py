"""YAML frontmatter parse + serialize. Stable key order for diff-friendliness."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import yaml


class FrontmatterError(ValueError):
    """Raised for any frontmatter parsing failure."""


_FENCE = "---"


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split frontmatter from body. Raises if no frontmatter or malformed."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        raise FrontmatterError("missing frontmatter fence at top of file")

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == _FENCE:
            end_idx = i
            break
    if end_idx is None:
        raise FrontmatterError("unterminated frontmatter - no closing ---")

    yaml_src = "".join(lines[1:end_idx])
    try:
        loaded = yaml.safe_load(yaml_src)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML in frontmatter: {exc}") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    data = cast(dict[str, Any], loaded)

    body = "".join(lines[end_idx + 1 :])
    if body.startswith("\n"):
        body = body[1:]
    return data, body


def serialize_with_frontmatter(data: Mapping[str, Any], *, body: str) -> str:
    """Serialize a note with frontmatter. Key order is preserved from the input mapping."""
    yaml_text = yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True).rstrip("\n")
    return f"{_FENCE}\n{yaml_text}\n{_FENCE}\n\n{body}"
