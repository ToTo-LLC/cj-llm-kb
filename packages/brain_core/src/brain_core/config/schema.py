"""Typed Config model. Source of truth for all user-configurable behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Domain = Literal["research", "work", "personal"]
ALLOWED_DOMAINS: tuple[Domain, ...] = ("research", "work", "personal")


class LLMConfig(BaseModel):
    provider: Literal["anthropic"] = "anthropic"
    default_model: str = "claude-sonnet-4-6"
    classify_model: str = "claude-haiku-4-5-20251001"
    max_output_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)


class BudgetConfig(BaseModel):
    daily_usd: float = Field(default=5.0, ge=0.0)
    monthly_usd: float = Field(default=80.0, ge=0.0)
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)


class Config(BaseModel):
    vault_path: Path = Field(default_factory=lambda: Path.home() / "Documents" / "brain")
    active_domain: Domain = "research"
    autonomous_mode: bool = False
    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    log_llm_payloads: bool = False

    @field_validator("active_domain")
    @classmethod
    def _check_domain(cls, v: str) -> str:
        if v not in ALLOWED_DOMAINS:
            raise ValueError(f"active_domain must be one of {ALLOWED_DOMAINS}, got {v!r}")
        return v
