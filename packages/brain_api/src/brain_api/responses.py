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
            "Heterogeneous across errors; typed detail models land in Task 16."
        ),
    )
