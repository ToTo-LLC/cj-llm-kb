"""Typed data models for vault operations. Patches and notes."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PatchCategory(StrEnum):
    """Semantic bucket a :class:`PatchSet` belongs to.

    Used by :func:`brain_core.autonomy.should_auto_apply` to decide whether
    the autonomy gate lets a patch land without human approval. ``OTHER`` is
    the safe default: it NEVER auto-applies, regardless of config flags.
    Every call site that produces a patch we want to consider auto-appliable
    must stamp a non-OTHER category explicitly.
    """

    INGEST = "ingest"
    ENTITIES = "entities"
    CONCEPTS = "concepts"
    INDEX_REWRITES = "index_rewrites"
    DRAFT = "draft"
    OTHER = "other"


class NewFile(BaseModel):
    path: Path
    content: str


class Edit(BaseModel):
    path: Path
    old: str
    new: str


class IndexEntryPatch(BaseModel):
    section: Literal["Sources", "Entities", "Concepts", "Synthesis"]
    line: str  # e.g. "- [[slug]] — summary"
    domain: str


class PatchSet(BaseModel):
    """The typed output of the integrate step. Every LLM vault mutation is a PatchSet."""

    new_files: list[NewFile] = Field(default_factory=list)
    edits: list[Edit] = Field(default_factory=list)
    index_entries: list[IndexEntryPatch] = Field(default_factory=list)
    log_entry: str | None = None
    reason: str = ""
    category: PatchCategory = PatchCategory.OTHER

    def total_size(self) -> int:
        return sum(len(nf.content) for nf in self.new_files) + sum(len(e.new) for e in self.edits)

    def file_count(self) -> int:
        touched = {nf.path for nf in self.new_files} | {e.path for e in self.edits}
        return len(touched)
