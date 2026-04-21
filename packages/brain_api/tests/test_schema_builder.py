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


class TestNumericRangeConstraints:
    """Plan 05 Task 25 — ``minimum``/``maximum`` become Pydantic ``ge``/``le``.

    The canonical live example is ``brain_search.top_k``'s
    ``{"type": "integer", "minimum": 1, "maximum": 20}``. Before Task 25 the
    constraints were silently dropped and only the tool handler's runtime
    ``min(..., _MAX_TOP_K)`` clamp enforced them; now the model rejects
    out-of-range values at the dispatcher edge.
    """

    def test_integer_minimum_enforced(self) -> None:
        schema = {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 1}},
            "required": ["n"],
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(n=1).n == 1  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            model_cls(n=0)

    def test_integer_maximum_enforced(self) -> None:
        schema = {
            "type": "object",
            "properties": {"n": {"type": "integer", "maximum": 10}},
            "required": ["n"],
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(n=10).n == 10  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            model_cls(n=11)

    def test_integer_min_and_max_both_enforced(self) -> None:
        schema = {
            "type": "object",
            "properties": {"top_k": {"type": "integer", "minimum": 1, "maximum": 20}},
            "required": ["top_k"],
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(top_k=10).top_k == 10  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            model_cls(top_k=0)
        with pytest.raises(ValidationError):
            model_cls(top_k=21)

    def test_number_constraints_enforced(self) -> None:
        schema = {
            "type": "object",
            "properties": {"threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0}},
            "required": ["threshold"],
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(threshold=0.5).threshold == 0.5  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            model_cls(threshold=-0.1)
        with pytest.raises(ValidationError):
            model_cls(threshold=1.5)

    def test_minimum_on_string_silently_dropped(self) -> None:
        """A typo like ``minimum`` on a string field must not block boot —
        it's silently ignored, because rejecting it would require a schema
        linter the project doesn't ship yet."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string", "minimum": 1}},
            "required": ["name"],
        }
        # Must not raise.
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(name="hi").name == "hi"  # type: ignore[attr-defined]

    def test_brain_search_top_k_rejects_out_of_range(self) -> None:
        """Real-tool regression — the exact schema ``brain_search`` ships.

        Task 11 built a model for this schema but dropped the numeric
        constraints. Task 25 wires them through so the dispatcher rejects
        ``top_k=0`` and ``top_k=21`` before the handler runs.
        """
        from brain_core.tools import search

        model_cls = build_model_from_schema(search.NAME, search.INPUT_SCHEMA)
        # In-range values accepted.
        assert model_cls(query="x", top_k=5).top_k == 5  # type: ignore[attr-defined]
        assert model_cls(query="x", top_k=1).top_k == 1  # type: ignore[attr-defined]
        assert model_cls(query="x", top_k=20).top_k == 20  # type: ignore[attr-defined]
        # Out of range rejected.
        with pytest.raises(ValidationError):
            model_cls(query="x", top_k=0)
        with pytest.raises(ValidationError):
            model_cls(query="x", top_k=21)


class TestEnumConstraints:
    """Plan 05 Task 25 — ``enum`` becomes ``typing.Literal[...]``.

    No current tool uses ``enum``; pinning the builder's behavior now means
    the next tool that adds a mode / status / kind field gets closed-set
    validation for free.
    """

    def test_enum_accepts_listed_value(self) -> None:
        schema = {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["ask", "brainstorm", "draft"]}},
            "required": ["mode"],
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(mode="ask").mode == "ask"  # type: ignore[attr-defined]
        assert model_cls(mode="draft").mode == "draft"  # type: ignore[attr-defined]

    def test_enum_rejects_unlisted_value(self) -> None:
        schema = {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["ask", "brainstorm"]}},
            "required": ["mode"],
        }
        model_cls = build_model_from_schema("T", schema)
        with pytest.raises(ValidationError):
            model_cls(mode="write")

    def test_enum_optional_field_defaults_none(self) -> None:
        """A non-required enum field still permits ``None`` (the default)."""
        schema = {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["a", "b"]}},
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls().mode is None  # type: ignore[attr-defined]
        assert model_cls(mode="a").mode == "a"  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            model_cls(mode="c")

    def test_integer_enum(self) -> None:
        """Enum with integer values — closed set wins over ``type: integer``."""
        schema = {
            "type": "object",
            "properties": {"level": {"type": "integer", "enum": [1, 2, 3]}},
            "required": ["level"],
        }
        model_cls = build_model_from_schema("T", schema)
        assert model_cls(level=2).level == 2  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            model_cls(level=4)
