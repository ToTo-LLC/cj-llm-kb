"""Response envelope models for brain_api routes.

Task 12 pins the typed response contract for every tool dispatch. FastAPI's
``response_model=ToolResponse`` does two things:

1. Serializes handler output against the model — extra keys are dropped before
   the response is sent, so the contract is enforced at the wire boundary.
2. Drives the ``/docs`` OpenAPI spec — each tool endpoint advertises the
   ``ToolResponse`` schema for 200s and ``ErrorResponse`` for 4xx codes.

``ErrorResponse`` is declared alongside because Task 12 wires it into the
dispatcher's ``responses={}`` kwarg for docs-parity today; Task 15 later uses
the same model body in a project-wide exception handler that flattens the
``{"detail": {...}}`` wrap FastAPI adds to :class:`HTTPException`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    """Envelope for every tool's output: plain text + optional structured data."""

    text: str = Field(description="Human-readable summary for LLM / UI rendering.")
    data: dict[str, Any] | None = Field(
        default=None,
        description="Structured payload. None when the tool has nothing beyond text to say.",
    )


class ErrorResponse(BaseModel):
    """Envelope for error responses.

    Task 12 references this only in OpenAPI metadata (``responses={...}`` on
    the dispatcher); Task 15 wires it into the exception handler so real error
    bodies match this shape at the wire level.
    """

    error: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Plain-English explanation.")
    detail: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional extra context (field-level errors, rate-limit windows, etc.). "
            "Heterogeneous across errors; see RateLimitDetail / ValidationDetail "
            "for the documented shapes."
        ),
    )


class RateLimitDetail(BaseModel):
    """Typed shape of :attr:`ErrorResponse.detail` on 429 responses.

    Documentation-only: the handler in :mod:`brain_api.errors` serializes this
    shape into ``ErrorResponse.detail`` (which stays ``dict[str, Any] | None``
    because :class:`ErrorResponse` is heterogeneous across error codes). The
    model exists so ``/docs`` readers can see the exact fields a rate-limit
    detail carries without having to crack open the handler source.
    """

    bucket: str = Field(description="Which bucket ran out ('patches' or 'tokens').")
    retry_after_seconds: int = Field(
        description="Approximate seconds until enough capacity refills. Matches the Retry-After header.",
    )


class ValidationDetail(BaseModel):
    """Typed shape of :attr:`ErrorResponse.detail` on 400 validation responses.

    Documentation-only — see :class:`RateLimitDetail` for the rationale.
    ``errors`` is Pydantic 2's canonical ``ValidationError.errors()`` list;
    each entry has ``loc`` / ``msg`` / ``type`` / ``input`` / ``url`` keys.
    The entries are rendered as plain dicts (not a nested Pydantic model)
    because the upstream shape is dictated by Pydantic itself.
    """

    errors: list[dict[str, Any]] = Field(
        description="Pydantic ValidationError.errors() list — field-level paths + messages.",
    )
