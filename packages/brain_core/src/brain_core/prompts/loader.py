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


def _split_sections(body: str, *, name: str) -> dict[str, str]:
    """Return a mapping of section heading -> trimmed content.

    Raises :class:`PromptError` if the same heading appears more than once.
    """
    parts = _SECTION_RE.split(body)
    # parts[0] is text before the first heading (usually empty).
    # After that: [heading, content, heading, content, ...]
    sections: dict[str, str] = {}
    it = iter(parts[1:])
    for heading in it:
        content = next(it, "")
        heading_stripped = heading.strip()
        if heading_stripped in sections:
            raise PromptError(
                f"Duplicate section {heading_stripped!r} in prompt {name!r}. "
                "Prompt bodies must contain '## System' and '## User Template' exactly once."
            )
        sections[heading_stripped] = content.strip()
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

        Raises :class:`PromptError` if a placeholder is missing, positional,
        or the format string is malformed.
        """
        try:
            return self.user_template.format(**kwargs)
        except (KeyError, IndexError, ValueError) as exc:
            raise PromptError(
                f"Prompt {self.name!r} render() failed: missing or malformed placeholder ({exc})"
            ) from exc


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
        keys, non-string frontmatter values, frontmatter name mismatch,
        missing or empty body sections, duplicate sections, or unknown schema
        (strict mode).
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

    fm_name = fm["name"]
    fm_schema = fm["output_schema"]

    # --- Validate frontmatter values are strings -----------------------------
    if not isinstance(fm_name, str):
        raise PromptError(
            f"Prompt {name!r}: frontmatter 'name' must be a string, got {type(fm_name).__name__}."
        )
    if not isinstance(fm_schema, str):
        raise PromptError(
            f"Prompt {name!r}: frontmatter 'output_schema' must be a string, "
            f"got {type(fm_schema).__name__}."
        )

    # --- Validate frontmatter name matches the filename stem -----------------
    if fm_name != name:
        raise PromptError(
            f"Prompt {name!r}: frontmatter 'name' is {fm_name!r}; it must match the filename stem."
        )

    output_schema_name: str = fm_schema

    # --- Resolve schema class -------------------------------------------------
    output_schema: type[BaseModel] | None = SCHEMAS.get(output_schema_name)
    if output_schema is None and not allow_unregistered_schema:
        raise PromptError(
            f"unknown schema '{output_schema_name}' in '{prompt_path}'. "
            "Register it in brain_core.prompts.schemas.SCHEMAS before loading."
        )

    # --- Split body into sections --------------------------------------------
    sections = _split_sections(body, name=name)

    system = sections.get(_SYSTEM_HEADER)
    if system is None:
        raise PromptError(f"prompt file '{prompt_path}' is missing required section: '## System'")
    if not system:
        raise PromptError(f"Prompt {name!r}: '## System' section is empty.")

    user_template = sections.get(_USER_TEMPLATE_HEADER)
    if user_template is None:
        raise PromptError(
            f"prompt file '{prompt_path}' is missing required section: '## User Template'"
        )
    if not user_template:
        raise PromptError(f"Prompt {name!r}: '## User Template' section is empty.")

    return Prompt(
        name=fm_name,
        system=system,
        user_template=user_template,
        output_schema_name=output_schema_name,
        output_schema=output_schema,
    )
