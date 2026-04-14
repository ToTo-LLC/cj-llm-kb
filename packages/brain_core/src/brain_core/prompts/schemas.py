"""Output schemas per prompt. Tasks 14-16 extend this module."""

from __future__ import annotations

from pydantic import BaseModel

from brain_core.vault.types import PatchSet

SCHEMAS: dict[str, type[BaseModel]] = {}


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    entities: list[str]
    concepts: list[str]
    open_questions: list[str]


SCHEMAS["SummarizeOutput"] = SummarizeOutput
SCHEMAS["IntegrateOutput"] = PatchSet
