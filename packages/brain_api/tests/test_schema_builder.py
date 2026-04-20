"""Tests for brain_api.schema.build_model_from_schema — Plan 05 Task 11.

The builder translates the JSON-Schema subset used by every
``brain_core.tools.*`` ``INPUT_SCHEMA`` into a real Pydantic model so the
dispatcher can validate request bodies (and FastAPI's OpenAPI introspection
"just works"). These tests pin the subset we promise to support.
"""

from __future__ import annotations

import pytest
from brain_api.schema import build_model_from_schema
from pydantic import BaseModel, ValidationError


def test_simple_required_string() -> None:
    """A ``required: [name]`` string field is present + non-null on the model."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    model_cls = build_model_from_schema("T", schema)
    assert issubclass(model_cls, BaseModel)

    instance = model_cls(name="hi")
    # ``create_model``-built classes have dynamic attributes mypy can't see.
    assert instance.name == "hi"  # type: ignore[attr-defined]

    with pytest.raises(ValidationError):
        model_cls()  # missing required


def test_optional_string_defaults_none() -> None:
    """A non-required field defaults to None on the model."""
    schema = {
        "type": "object",
        "properties": {"hint": {"type": "string"}},
    }
    model_cls = build_model_from_schema("T", schema)
    instance = model_cls()
    assert instance.hint is None  # type: ignore[attr-defined]


def test_integer_type_coerced() -> None:
    """An integer field rejects strings that don't parse as ints."""
    schema = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
    }
    model_cls = build_model_from_schema("T", schema)
    with pytest.raises(ValidationError):
        model_cls(limit="not-an-int")
    assert model_cls(limit=5).limit == 5  # type: ignore[attr-defined]


def test_array_type_accepts_list() -> None:
    """An array field accepts a Python list untouched."""
    schema = {
        "type": "object",
        "properties": {"domains": {"type": "array"}},
    }
    model_cls = build_model_from_schema("T", schema)
    assert model_cls(domains=["a", "b"]).domains == ["a", "b"]  # type: ignore[attr-defined]


def test_builds_models_for_every_real_tool_schema() -> None:
    """Sanity — every registered tool's INPUT_SCHEMA builds without raising.

    If this test ever fails, a new tool has added a JSON-Schema feature the
    builder doesn't support yet. Extend ``_python_type_for`` (or raise
    ``UnsupportedSchemaError`` intentionally to gate the rollout).
    """
    from brain_core.tools import list_tools

    for module in list_tools():
        model_cls = build_model_from_schema(module.NAME, module.INPUT_SCHEMA)
        assert issubclass(model_cls, BaseModel), f"{module.NAME} failed to build"
