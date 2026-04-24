"""Typed Config model. Source of truth for all user-configurable behavior."""

from __future__ import annotations

from datetime import datetime
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
    # Plan 07 Task 4: ephemeral budget override. ``override_until`` is a UTC
    # timestamp; while ``now() < override_until`` the effective daily cap is
    # ``daily_usd + override_delta_usd``. Both fields are read-only on the
    # config object for now (Plan 07 Task 5 wires real persistence) — the
    # ``brain_budget_override`` tool sets them in-process via Pydantic
    # ``model_copy`` or settings-shim.
    override_until: datetime | None = None
    override_delta_usd: float = Field(default=0.0, ge=0.0)


class URLHandlerConfig(BaseModel):
    """Tunables for the URL source handler (issue #23).

    Surfaced via the Settings UI / ``brain_config_set`` so a user on a slow
    network can raise the timeout, or a user on a flaky one can lower it
    (and surface an error sooner).
    """

    model_config = ConfigDict(extra="forbid")
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Per-request timeout for the URL fetch step (httpx).",
    )


class TweetHandlerConfig(BaseModel):
    """Tunables for the Tweet source handler (issue #23).

    The tweet syndication endpoint is unauthenticated and can be slow or
    flaky; expose timeout so users can tune.
    """

    model_config = ConfigDict(extra="forbid")
    timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        description="Per-request timeout for the syndication endpoint fetch.",
    )


class PDFHandlerConfig(BaseModel):
    """Tunables for the PDF source handler (issue #23).

    ``min_chars`` is the threshold below which extracted PDF text is treated
    as a "scanned PDF" (image-only) and rejected with a clear error. Lower
    the value if you have legitimately short PDFs you want ingested; raise
    it to be more aggressive about catching scans.
    """

    model_config = ConfigDict(extra="forbid")
    min_chars: int = Field(
        default=200,
        ge=0,
        description=(
            "Minimum extractable character count below which a PDF is treated "
            "as scanned/image-only and rejected. 0 disables the check."
        ),
    )


class HandlersConfig(BaseModel):
    """Aggregate config for source handlers (issue #23).

    Each handler with user-tunable behavior gets a sub-config here. Adding a
    new handler with tunables means: add a sub-config model, add a field
    here, plumb the override into the handler's constructor in
    :func:`brain_core.ingest.dispatcher._default_handlers`, and add the
    nested key paths (``handlers.<name>.<field>``) to ``_SETTABLE_KEYS`` in
    :mod:`brain_core.tools.config_set`.
    """

    model_config = ConfigDict(extra="forbid")
    url: URLHandlerConfig = Field(default_factory=URLHandlerConfig)
    tweet: TweetHandlerConfig = Field(default_factory=TweetHandlerConfig)
    pdf: PDFHandlerConfig = Field(default_factory=PDFHandlerConfig)


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
    handlers: HandlersConfig = Field(default_factory=HandlersConfig)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    log_llm_payloads: bool = False

    @field_validator("active_domain")
    @classmethod
    def _check_domain(cls, v: str) -> str:
        if v not in ALLOWED_DOMAINS:
            raise ValueError(f"active_domain must be one of {ALLOWED_DOMAINS}, got {v!r}")
        return v
