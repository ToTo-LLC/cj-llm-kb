"""Pin tests for the shared response envelopes — Plan 20 T1.3 + T1.4.

Every tool dispatch in brain_api flows through
:class:`brain_api.responses.ToolResponse` (success envelope) and
:class:`brain_api.responses.ErrorResponse` (4xx/5xx envelope). The SPA
consumes both shapes across every tool-dispatch call site
(``apps/brain_web/src/lib/api/*.ts``). Drift on either envelope is a
fleet-wide TS narrow break, so these pins close the Plan 19 T1
audit-OK-but-unpinned gap for the two foundational shared envelopes.

Pattern mirrors the canonical Plan 19 T2 precedent at
``test_endpoint_upload_shape.py`` — strict-equality key-set pin plus
per-field type+required pins for each single-typed field.

Note the two heterogeneous fields:

* ``ToolResponse.data: dict[str, Any] | None``
* ``ErrorResponse.detail: dict[str, Any] | None``

Their dict shape is *intentionally* heterogeneous (per-tool data
payloads + per-error detail bodies — see the ``responses.py`` module
docstring and the ``RateLimitDetail`` / ``ValidationDetail``
documentation-only models). Pinning the dict type annotation would
lock out that intentional variation, so the pin here only asserts the
field defaults to ``None`` (``not field.is_required()``).

If you need to widen / narrow either envelope, audit every tool-call
site and TS narrow in lockstep before updating these pins.
"""

from __future__ import annotations

from brain_api.responses import ErrorResponse, ToolResponse


# --------------------------------------------------------------------------
# ToolResponse — Plan 20 T1.3
# --------------------------------------------------------------------------


def test_tool_response_field_set() -> None:
    """``ToolResponse`` emits exactly ``{text, data}``.

    Pin against accidental widening / narrowing. See the module
    docstring for the rationale + lockstep TS sites.
    """
    assert set(ToolResponse.model_fields.keys()) == {"text", "data"}


def test_tool_response_text_is_non_nullable_str() -> None:
    """``text`` is a required, non-nullable ``str``.

    Every tool dispatch produces a human-readable summary; the TS narrow
    can safely declare ``text: string``.
    """
    field = ToolResponse.model_fields["text"]
    assert field.annotation is str
    assert field.is_required()


def test_tool_response_data_defaults_to_none() -> None:
    """``data`` defaults to ``None``.

    SKIP type-annotation pin: ``data: dict[str, Any] | None`` is
    intentionally heterogeneous per the module docstring — each tool
    embeds its own structured payload. Pinning the dict annotation
    would lock out that per-tool variation. We only pin that the field
    is non-required so a tool with nothing structural to say can omit
    it without breaking the envelope contract.
    """
    field = ToolResponse.model_fields["data"]
    assert not field.is_required()


# --------------------------------------------------------------------------
# ErrorResponse — Plan 20 T1.4
# --------------------------------------------------------------------------


def test_error_response_field_set() -> None:
    """``ErrorResponse`` emits exactly ``{error, message, detail}``.

    Pin against accidental widening / narrowing. See the module
    docstring for the rationale + lockstep TS sites.
    """
    assert set(ErrorResponse.model_fields.keys()) == {"error", "message", "detail"}


def test_error_response_error_is_non_nullable_str() -> None:
    """``error`` is a required, non-nullable ``str`` (machine-readable code)."""
    field = ErrorResponse.model_fields["error"]
    assert field.annotation is str
    assert field.is_required()


def test_error_response_message_is_non_nullable_str() -> None:
    """``message`` is a required, non-nullable ``str`` (plain-English copy)."""
    field = ErrorResponse.model_fields["message"]
    assert field.annotation is str
    assert field.is_required()


def test_error_response_detail_defaults_to_none() -> None:
    """``detail`` defaults to ``None``.

    SKIP type-annotation pin: ``detail: dict[str, Any] | None`` is
    intentionally heterogeneous per the module docstring — each error
    code embeds its own detail shape (see ``RateLimitDetail`` and
    ``ValidationDetail`` documentation-only models). Pinning the dict
    annotation would lock out that per-error variation. We only pin
    that the field is non-required so an error with nothing extra to
    say can omit it without breaking the envelope contract.
    """
    field = ErrorResponse.model_fields["detail"]
    assert not field.is_required()
