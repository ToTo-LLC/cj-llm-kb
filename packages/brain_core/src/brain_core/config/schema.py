"""Typed Config model. Source of truth for all user-configurable behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Domain = Literal["research", "work", "personal"]
ALLOWED_DOMAINS: tuple[Domain, ...] = ("research", "work", "personal")


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["anthropic"] = "anthropic"
    default_model: str = "claude-sonnet-4-6"
    classify_model: str = "claude-haiku-4-5-20251001"
    max_output_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_usd: float = Field(default=5.0, ge=0.0)
    monthly_usd: float = Field(default=80.0, ge=0.0)
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)


class AutonomousConfig(BaseModel):
    """Per-category auto-apply flags for staged PatchSets.

    Every flag defaults to ``False`` — out-of-the-box brain stages every
    LLM-authored vault mutation for human approval (CLAUDE.md principle #3).
    Flipping a flag to ``True`` opts that category into auto-apply via
    :func:`brain_core.autonomy.should_auto_apply`. The category keys mirror
    :class:`brain_core.vault.types.PatchCategory` values 1:1.
    """

    model_config = ConfigDict(extra="forbid")
    ingest: bool = False
    entities: bool = False
    concepts: bool = False
    index_rewrites: bool = False
    draft: bool = False


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vault_path: Path = Field(default_factory=lambda: Path.home() / "Documents" / "brain")
    active_domain: Domain = "research"
    autonomous_mode: bool = False
    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    autonomous: AutonomousConfig = Field(default_factory=AutonomousConfig)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    log_llm_payloads: bool = False

    @field_validator("active_domain")
    @classmethod
    def _check_domain(cls, v: str) -> str:
        if v not in ALLOWED_DOMAINS:
            raise ValueError(f"active_domain must be one of {ALLOWED_DOMAINS}, got {v!r}")
        return v
