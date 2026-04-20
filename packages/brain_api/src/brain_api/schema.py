"""Build Pydantic models from each tool's JSON-Schema subset — Plan 05 Task 11.

Called at app startup (see ``brain_api.app._lifespan``). The JSON-Schema subset
we support covers every current ``brain_core.tools.*`` ``INPUT_SCHEMA``; richer
JSON-Schema features (``minimum``/``maximum``/``enum``/``pattern``/nested
objects) can be added incrementally as tools require them and will be tracked
as Plan 05 Task 25 deferral.

Why this exists (rather than a third-party library):
- ``datamodel-code-generator`` is a heavy CLI tool that wants subprocess calls.
- ``jsonschema`` validates but returns no Pydantic model, so FastAPI's OpenAPI
  introspection at ``/docs`` sees an opaque ``dict[str, Any]``.

``pydantic.create_model`` produces real Pydantic ``BaseModel`` subclasses that
FastAPI introspects for ``/docs`` and that ``Model.model_validate(body)`` can
reject at the dispatcher edge.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, create_model

# Map JSON-Schema primitive types to Python types. ``array`` and ``object``
# are handled specially in ``_python_type_for`` so we emit ``list[Any]`` and
# ``dict[str, Any]`` rather than the bare generics (which Pydantic treats
# as ``list`` / ``dict`` of unknown shape).
_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class UnsupportedSchemaError(ValueError):
    """Raised at boot if a tool's INPUT_SCHEMA uses features we haven't mapped yet.

    Fails loud at lifespan startup rather than at request time — a malformed
    tool schema should block the app from accepting any traffic, not surface
    as an obscure 500 on the first call to that tool.
    """


def _python_type_for(prop_schema: dict[str, Any]) -> Any:
    """Map a JSON-Schema property dict to a Python type annotation.

    Returns ``typing.Any`` for unknown or absent types — permissive by design
    so tool authors can prototype ``{}``-typed fields (``config_set``'s
    ``value`` is the canonical example) without waiting for the builder to
    catch up with a new JSON-Schema feature.
    """
    js_type = prop_schema.get("type")
    if js_type is None:
        # ``{}`` (no type key) — e.g. ``config_set``'s ``value`` which may be
        # any JSON value; the handler validates at apply time.
        return Any
    if isinstance(js_type, list):
        # Unions like ``["string", "null"]`` — just accept any value rather
        # than building a ``Union[...]`` alias.
        return Any
    if js_type == "array":
        return list[Any]
    if js_type == "object":
        return dict[str, Any]
    return _TYPE_MAP.get(js_type, Any)


def build_model_from_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model from a JSON-Schema object description.

    Args:
        name: Model class name (e.g. the tool NAME) — used as the Pydantic
            class name suffix and surfaces in OpenAPI + error messages.
        schema: Dict shaped like
            ``{"type": "object", "properties": {...}, "required": [...]}``.

    Returns:
        A Pydantic ``BaseModel`` subclass suitable for
        ``Model.model_validate(body)`` at the dispatcher edge.

    Raises:
        UnsupportedSchemaError: if the top-level ``type`` isn't ``"object"``.
            Every brain tool's ``INPUT_SCHEMA`` is currently an object, so a
            non-object top level almost certainly indicates a tool-side bug
            worth halting boot over.
    """
    if schema.get("type") != "object":
        raise UnsupportedSchemaError(
            f"tool {name!r} INPUT_SCHEMA top-level type must be 'object', "
            f"got {schema.get('type')!r}"
        )

    properties: dict[str, Any] = schema.get("properties", {})
    required: set[str] = set(schema.get("required", []))

    fields: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        py_type = _python_type_for(prop_schema)
        description = prop_schema.get("description")
        if prop_name in required:
            fields[prop_name] = (py_type, Field(..., description=description))
        else:
            # Optional fields are ``T | None`` with default ``None`` so
            # ``model_dump(exclude_none=True)`` strips them for handlers.
            fields[prop_name] = (py_type | None, Field(default=None, description=description))

    return create_model(f"{name}_Input", __base__=BaseModel, **fields)
