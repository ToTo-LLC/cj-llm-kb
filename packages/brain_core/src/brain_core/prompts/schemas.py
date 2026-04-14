"""Output schemas per prompt. Tasks 14-16 extend this module."""

from __future__ import annotations

from pydantic import BaseModel

SCHEMAS: dict[str, type[BaseModel]] = {}
