"""Tests for brain_core.prompts.loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.prompts.loader import PromptError, load_prompt
from brain_core.prompts.schemas import SCHEMAS
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Helper to write a prompt file inline
# ---------------------------------------------------------------------------


def _write_prompt(tmp_path: Path, filename: str, content: str) -> None:
    (tmp_path / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — Happy path: load echo.md from fixture dir
# ---------------------------------------------------------------------------


def test_load_echo_happy_path(prompts_fixture_dir: Path) -> None:
    prompt = load_prompt(
        "echo",
        search_dir=prompts_fixture_dir,
        allow_unregistered_schema=True,
    )
    assert prompt.name == "echo"
    assert prompt.output_schema_name == "EchoOutput"
    assert prompt.output_schema is None  # not registered
    assert "You are a concise assistant" in prompt.system
    assert "{text}" in prompt.user_template
    rendered = prompt.render(text="hello")
    assert rendered == "Please echo: hello"


# ---------------------------------------------------------------------------
# Test 2 — Missing frontmatter key raises PromptError
# ---------------------------------------------------------------------------


def test_missing_frontmatter_key_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "bad.md",
        "---\nname: bad\n---\n\n## System\n\nHello.\n\n## User Template\n\nHi {name}\n",
    )
    with pytest.raises(PromptError, match="output_schema"):
        load_prompt("bad", search_dir=tmp_path)


# ---------------------------------------------------------------------------
# Test 3 — Unknown schema strict mode raises PromptError
# ---------------------------------------------------------------------------


def test_unknown_schema_strict_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "strict.md",
        "---\nname: strict\noutput_schema: NotASchema\n---\n\n## System\n\nHello.\n\n## User Template\n\nHi {name}\n",
    )
    with pytest.raises(PromptError, match="unknown schema"):
        load_prompt("strict", search_dir=tmp_path, allow_unregistered_schema=False)


# ---------------------------------------------------------------------------
# Test 4 — Unknown schema permissive mode returns Prompt with output_schema=None
# ---------------------------------------------------------------------------


def test_unknown_schema_permissive(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "permissive.md",
        "---\nname: permissive\noutput_schema: NotASchema\n---\n\n## System\n\nHello.\n\n## User Template\n\nHi {name}\n",
    )
    prompt = load_prompt("permissive", search_dir=tmp_path, allow_unregistered_schema=True)
    assert prompt.output_schema is None
    assert prompt.output_schema_name == "NotASchema"


# ---------------------------------------------------------------------------
# Test 5 — Missing sections raises PromptError
# ---------------------------------------------------------------------------


def test_missing_system_section_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "nosys.md",
        "---\nname: nosys\noutput_schema: Foo\n---\n\n## User Template\n\nHi {name}\n",
    )
    with pytest.raises(PromptError, match="## System"):
        load_prompt("nosys", search_dir=tmp_path, allow_unregistered_schema=True)


def test_missing_user_template_section_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "notpl.md",
        "---\nname: notpl\noutput_schema: Foo\n---\n\n## System\n\nHello.\n",
    )
    with pytest.raises(PromptError, match="## User Template"):
        load_prompt("notpl", search_dir=tmp_path, allow_unregistered_schema=True)


# ---------------------------------------------------------------------------
# Test 6 — render() with missing placeholder raises PromptError (Fix 1 + Fix 6)
# ---------------------------------------------------------------------------


def test_render_missing_placeholder_raises(prompts_fixture_dir: Path) -> None:
    prompt = load_prompt(
        "echo",
        search_dir=prompts_fixture_dir,
        allow_unregistered_schema=True,
    )
    with pytest.raises(PromptError, match=r"missing or malformed placeholder"):
        prompt.render()  # missing required 'text' kwarg


# ---------------------------------------------------------------------------
# Test 7 — Registered schema is resolved at load time
# ---------------------------------------------------------------------------


def test_registered_schema_resolved(tmp_path: Path) -> None:
    class DummySchema(BaseModel):
        result: str

    SCHEMAS["DummySchema"] = DummySchema
    try:
        _write_prompt(
            tmp_path,
            "dummy.md",
            "---\nname: dummy\noutput_schema: DummySchema\n---\n\n## System\n\nHello.\n\n## User Template\n\nHi {name}\n",
        )
        prompt = load_prompt("dummy", search_dir=tmp_path)
        assert prompt.output_schema is DummySchema
        assert prompt.output_schema_name == "DummySchema"
    finally:
        SCHEMAS.pop("DummySchema", None)


# ---------------------------------------------------------------------------
# Fix 1 — render() wraps IndexError (positional placeholder) in PromptError
# ---------------------------------------------------------------------------


def test_render_positional_placeholder_raises_prompt_error(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "positional.md",
        "---\nname: positional\noutput_schema: Foo\n---\n\n## System\n\nHello.\n\n## User Template\n\npositional {0}\n",
    )
    prompt = load_prompt("positional", search_dir=tmp_path, allow_unregistered_schema=True)
    with pytest.raises(PromptError, match=r"missing or malformed placeholder"):
        prompt.render()  # no positional args supplied


# ---------------------------------------------------------------------------
# Fix 1 — render() wraps ValueError (malformed template) in PromptError
# ---------------------------------------------------------------------------


def test_render_malformed_template_raises_prompt_error(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "malformed.md",
        "---\nname: malformed\noutput_schema: Foo\n---\n\n## System\n\nHello.\n\n## User Template\n\nbad {\n",
    )
    prompt = load_prompt("malformed", search_dir=tmp_path, allow_unregistered_schema=True)
    with pytest.raises(PromptError, match=r"missing or malformed placeholder"):
        prompt.render()


# ---------------------------------------------------------------------------
# Fix 2 — Duplicate section header raises PromptError
# ---------------------------------------------------------------------------


def test_duplicate_section_header_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "dupsec.md",
        (
            "---\nname: dupsec\noutput_schema: Foo\n---\n\n"
            "## System\n\nFirst system.\n\n"
            "## User Template\n\nHi {name}\n\n"
            "## System\n\nDuplicate system.\n"
        ),
    )
    with pytest.raises(PromptError, match=r"[Dd]uplicate section"):
        load_prompt("dupsec", search_dir=tmp_path, allow_unregistered_schema=True)


# ---------------------------------------------------------------------------
# Fix 3 — Frontmatter name must match filename stem
# ---------------------------------------------------------------------------


def test_frontmatter_name_must_match_filename(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "foo.md",
        "---\nname: bar\noutput_schema: Foo\n---\n\n## System\n\nHello.\n\n## User Template\n\nHi {name}\n",
    )
    with pytest.raises(PromptError, match=r"frontmatter 'name'"):
        load_prompt("foo", search_dir=tmp_path, allow_unregistered_schema=True)


# ---------------------------------------------------------------------------
# Fix 4 — Empty ## System section raises PromptError
# ---------------------------------------------------------------------------


def test_empty_system_section_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "emptysys.md",
        "---\nname: emptysys\noutput_schema: Foo\n---\n\n## System\n\n## User Template\n\nHi {name}\n",
    )
    with pytest.raises(PromptError, match=r"'## System' section is empty"):
        load_prompt("emptysys", search_dir=tmp_path, allow_unregistered_schema=True)


# ---------------------------------------------------------------------------
# Fix 4 — Empty ## User Template section raises PromptError
# ---------------------------------------------------------------------------


def test_empty_user_template_section_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "emptytpl.md",
        "---\nname: emptytpl\noutput_schema: Foo\n---\n\n## System\n\nHello.\n\n## User Template\n",
    )
    with pytest.raises(PromptError, match=r"'## User Template' section is empty"):
        load_prompt("emptytpl", search_dir=tmp_path, allow_unregistered_schema=True)


# ---------------------------------------------------------------------------
# Fix 5 — Non-string frontmatter 'name' raises PromptError
# ---------------------------------------------------------------------------


def test_non_string_frontmatter_value_raises(tmp_path: Path) -> None:
    _write_prompt(
        tmp_path,
        "intname.md",
        "---\nname: 123\noutput_schema: Foo\n---\n\n## System\n\nHello.\n\n## User Template\n\nHi {x}\n",
    )
    with pytest.raises(PromptError, match=r"frontmatter 'name' must be a string"):
        load_prompt("intname", search_dir=tmp_path, allow_unregistered_schema=True)
