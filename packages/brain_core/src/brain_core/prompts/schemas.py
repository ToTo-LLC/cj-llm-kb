"""Output schemas per prompt. Tasks 14-16 extend this module."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from brain_core.vault.types import PatchSet

SCHEMAS: dict[str, type[BaseModel]] = {}


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    entities: list[str]
    concepts: list[str]
    open_questions: list[str]


class ClassifyOutput(BaseModel):
    source_type: Literal["text", "url", "pdf", "email", "transcript", "tweet"]
    domain: Literal["research", "work", "personal"]
    confidence: float = Field(ge=0.0, le=1.0)


SCHEMAS["SummarizeOutput"] = SummarizeOutput
SCHEMAS["IntegrateOutput"] = PatchSet
SCHEMAS["ClassifyOutput"] = ClassifyOutput
