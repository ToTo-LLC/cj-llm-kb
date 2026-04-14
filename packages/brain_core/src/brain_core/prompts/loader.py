"""Prompt `.md` file loader.

Each prompt file has YAML frontmatter + two sections:

    ## System
    <system prompt text>

    ## User Template
    <user template with {placeholder} variables>

The loader reads the file, parses frontmatter, splits sections, and returns
a frozen :class:`Prompt` dataclass.  Template substitution is plain
``str.format``—no Jinja, no extra deps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter

from .schemas import SCHEMAS


class PromptError(ValueError):
    """Raised for any prompt loading or rendering failure."""


# Section headers exactly as they appear in prompt files.
_SYSTEM_HEADER = "## System"
_USER_TEMPLATE_HEADER = "## User Template"

# Regex to split body into named sections delimited by "## Heading" lines.
_SECTION_RE = re.compile(r"^(##\s+\S[^\n]*)", re.MULTILINE)


def _split_sections(body: str) -> dict[str, str]:
    """Return a mapping of section heading -> trimmed content."""
    parts = _SECTION_RE.split(body)
    # parts[0] is text before the first heading (usually empty).
    # After that: [heading, content, heading, content, ...]
    sections: dict[str, str] = {}
    it = iter(parts[1:])
    for heading in it:
        content = next(it, "")
        sections[heading.strip()] = content.strip()
    return sections


@dataclass(frozen=True)
class Prompt:
    """An immutable loaded prompt."""

    name: str
    system: str
    user_template: str
    output_schema_name: str
    output_schema: type[BaseModel] | None

    def render(self, **kwargs: Any) -> str:
        """Substitute ``{placeholders}`` in the user template.

        Raises ``KeyError`` if a required placeholder is missing.
        """
        try:
            return self.user_template.format(**kwargs)
        except KeyError as exc:
            raise KeyError(f"Prompt '{self.name}' render() missing placeholder: {exc}") from exc


def load_prompt(
    name: str,
    *,
    search_dir: Path | None = None,
    allow_unregistered_schema: bool = False,
) -> Prompt:
    """Load a prompt by name from *search_dir* (default: the prompts package dir).

    Parameters
    ----------
    name:
        The stem of the ``.md`` file to load (e.g. ``"summarize"``).
    search_dir:
        Directory to search for ``<name>.md``.  Defaults to the directory
        containing this module — i.e. the real prompts live alongside the code.
    allow_unregistered_schema:
        When ``True``, an ``output_schema`` name that isn't in :data:`SCHEMAS`
        is silently accepted and ``Prompt.output_schema`` is set to ``None``.
        When ``False`` (the default), an unknown schema name raises
        :class:`PromptError`.

    Returns
    -------
    Prompt
        A frozen dataclass with parsed fields and resolved schema class.

    Raises
    ------
    PromptError
        On missing file, malformed frontmatter, missing required frontmatter
        keys, missing body sections, or unknown schema (strict mode).
    """
    if search_dir is None:
        search_dir = Path(__file__).parent

    prompt_path = search_dir / f"{name}.md"
    if not prompt_path.exists():
        raise PromptError(f"prompt file not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8")

    # --- Parse frontmatter ---------------------------------------------------
    try:
        fm, body = parse_frontmatter(content)
    except FrontmatterError as exc:
        raise PromptError(f"invalid frontmatter in '{prompt_path}': {exc}") from exc

    # --- Validate required frontmatter keys ----------------------------------
    for key in ("name", "output_schema"):
        if key not in fm:
            raise PromptError(
                f"prompt file '{prompt_path}' is missing required frontmatter key: '{key}'"
            )

    fm_name: str = fm["name"]
    output_schema_name: str = fm["output_schema"]

    # --- Resolve schema class -------------------------------------------------
    output_schema: type[BaseModel] | None = SCHEMAS.get(output_schema_name)
    if output_schema is None and not allow_unregistered_schema:
        raise PromptError(
            f"unknown schema '{output_schema_name}' in '{prompt_path}'. "
            "Register it in brain_core.prompts.schemas.SCHEMAS before loading."
        )

    # --- Split body into sections --------------------------------------------
    sections = _split_sections(body)

    system = sections.get(_SYSTEM_HEADER)
    if system is None:
        raise PromptError(f"prompt file '{prompt_path}' is missing required section: '## System'")

    user_template = sections.get(_USER_TEMPLATE_HEADER)
    if user_template is None:
        raise PromptError(
            f"prompt file '{prompt_path}' is missing required section: '## User Template'"
        )

    return Prompt(
        name=fm_name,
        system=system,
        user_template=user_template,
        output_schema_name=output_schema_name,
        output_schema=output_schema,
    )
