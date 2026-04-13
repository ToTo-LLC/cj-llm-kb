from __future__ import annotations

import pytest

from brain_core.vault.frontmatter import (
    FrontmatterError,
    parse_frontmatter,
    serialize_with_frontmatter,
)


def test_parse_roundtrip() -> None:
    content = (
        "---\n"
        "title: Example\n"
        "domain: research\n"
        "tags:\n"
        "  - foo\n"
        "  - bar\n"
        "---\n"
        "\n"
        "Body text here.\n"
    )
    data, body = parse_frontmatter(content)
    assert data == {"title": "Example", "domain": "research", "tags": ["foo", "bar"]}
    assert body == "Body text here.\n"


def test_parse_no_frontmatter_raises() -> None:
    with pytest.raises(FrontmatterError, match="missing"):
        parse_frontmatter("Just body, no frontmatter.\n")


def test_parse_unterminated_raises() -> None:
    with pytest.raises(FrontmatterError, match="unterminated"):
        parse_frontmatter("---\ntitle: x\nno-close-marker\n")


def test_parse_invalid_yaml_raises() -> None:
    with pytest.raises(FrontmatterError, match="invalid YAML"):
        parse_frontmatter("---\n: : bad\n---\nbody\n")


def test_serialize_produces_parseable_output() -> None:
    out = serialize_with_frontmatter(
        {"title": "X", "domain": "work"},
        body="Hello.\n",
    )
    data, body = parse_frontmatter(out)
    assert data["title"] == "X"
    assert data["domain"] == "work"
    assert body == "Hello.\n"


def test_serialize_preserves_key_order_stable() -> None:
    out = serialize_with_frontmatter(
        {"title": "a", "domain": "b", "type": "c"}, body=""
    )
    assert out.splitlines()[:5] == ["---", "title: a", "domain: b", "type: c", "---"]
