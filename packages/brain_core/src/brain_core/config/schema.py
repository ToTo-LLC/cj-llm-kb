"""Typed Config model. Source of truth for all user-configurable behavior.

Plan 10 / issue #21 — domain set is configurable. ``Config.domains`` holds
the user's runtime list of top-level vault domains; the v0.1 ``Domain``
``Literal`` and ``ALLOWED_DOMAINS`` tuple are kept as deprecation aliases
so external callers that still import them get a string type and the
default tuple respectively. Plan 10 Task 2 drops ``ALLOWED_DOMAINS`` once
``vault.paths.scope_guard`` reads the live domain set from its caller.

Slug rules (D2 in plan 10):
  * lowercase ASCII
  * regex ``[a-z][a-z0-9_-]{1,30}``
  * may not start with a digit, ``_``, or ``-``
  * may not end with ``_`` or ``-``
  * may not contain path separators (``/``, ``\\``)

Privacy rail (D5): ``personal`` is hardcoded as the privacy-railed slug.
``Config.domains`` MUST contain it; removing it raises a validation
error. Generalizing this to a per-domain flag is filed for Plan 11.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Deprecation aliases — kept so external callers compile through the
# Plan 10 transition. Plan 10 Task 2 drops ``ALLOWED_DOMAINS``; the
# ``Domain`` alias becomes ``str`` once every internal call site has
# migrated to ``Config.domains``. Treat both as read-only legacy.
Domain = Literal["research", "work", "personal"]
ALLOWED_DOMAINS: tuple[Domain, ...] = ("research", "work", "personal")

# Plan 10 D5: ``personal`` is the privacy-railed slug. Hardcoded here so
# the Config validator (and every other call site) can reference one
# canonical name. Renaming this constant in code without also renaming
# the slug on disk would silently disable the privacy rail.
PRIVACY_RAILED_SLUG = "personal"

# Plan 10 D1: default domain set for a fresh vault.
DEFAULT_DOMAINS: tuple[str, ...] = ("research", "work", PRIVACY_RAILED_SLUG)

# Plan 10 D2: slug-validation rule. The pattern enforces:
#   - first char: ASCII lowercase letter (no digit / dash / underscore start)
#   - 2..31 chars total (so the regex max length is 31; matches the
#     ``{1,30}`` suffix because the leading char counts separately)
#   - body: lowercase letters, digits, ``-``, ``_``
# Trailing ``_`` or ``-`` is rejected by a separate post-match check
# below — extending the regex to forbid trailing punctuation works but
# costs readability for no validation gain.
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,30}$")


def _validate_domain_slug(slug: str) -> str:
    """Apply the Plan 10 D2 slug rules. Returns the slug or raises ValueError."""
    if not isinstance(slug, str):
        raise ValueError(f"domain slug must be a string, got {type(slug).__name__}")
    if not slug:
        raise ValueError("domain slug must not be empty")
    if "/" in slug or "\\" in slug:
        raise ValueError(f"domain slug {slug!r} must not contain path separators")
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"domain slug {slug!r} must match [a-z][a-z0-9_-]{{0,30}} "
            "(start with a lowercase letter; 1-31 chars; lowercase / digits / "
            "underscore / hyphen only)"
        )
    if slug.endswith("_") or slug.endswith("-"):
        raise ValueError(
            f"domain slug {slug!r} must not end with '_' or '-' "
            "(reserved for filesystem-tooling separators)"
        )
    return slug


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
    # Plan 10 D1: ``domains`` is the user-configurable list of vault
    # top-level dirs. Order in the list is preserved for UI affordances
    # (Settings → Domains drag-reorder, classify prompt template) but
    # has no semantic meaning on disk. Field validator below enforces
    # D2 slug rules and the D5 ``personal``-required rail.
    domains: list[str] = Field(default_factory=lambda: list(DEFAULT_DOMAINS))
    # Plan 10 D3: ``active_domain`` is widened from the v0.1
    # ``Literal["research","work","personal"]`` to ``str``; the
    # cross-field check (must be in ``domains``) is enforced by the
    # ``model_validator`` below so we can read the live domain set.
    active_domain: str = "research"
    autonomous_mode: bool = False
    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    autonomous: AutonomousConfig = Field(default_factory=AutonomousConfig)
    handlers: HandlersConfig = Field(default_factory=HandlersConfig)
    web_port: int = Field(default=4317, ge=1024, le=65535)
    log_llm_payloads: bool = False

    @field_validator("domains")
    @classmethod
    def _check_domains(cls, v: list[str]) -> list[str]:
        # D1: at least one domain. The ``personal`` rail check below
        # also enforces non-empty as a side effect, but we check
        # length explicitly so the error message is the right one
        # when a user sends ``[]``.
        if not v:
            raise ValueError("domains must contain at least one entry")
        # D2: per-slug rules.
        for slug in v:
            _validate_domain_slug(slug)
        # D2: no duplicates. ``set(v) != len(v)`` would mask which slug
        # collided; iterate so the error message names it.
        seen: set[str] = set()
        for slug in v:
            if slug in seen:
                raise ValueError(f"domain slug {slug!r} appears more than once in domains list")
            seen.add(slug)
        # D5: privacy rail. ``personal`` is hardcoded and may not be
        # removed. The error wording matches the plan-10 spec verbatim
        # so the Settings UI can show it directly.
        if PRIVACY_RAILED_SLUG not in v:
            raise ValueError(
                f"{PRIVACY_RAILED_SLUG} is required and may not be removed; "
                "use Settings → Domains to control its visibility."
            )
        return v

    @model_validator(mode="after")
    def _check_active_domain_in_domains(self) -> Config:
        # D3: ``active_domain`` must be a member of the live ``domains``
        # list. Pydantic field validators can't see other fields cleanly
        # in v2, so we do the cross-field check here.
        if self.active_domain not in self.domains:
            raise ValueError(
                f"active_domain {self.active_domain!r} is not in domains {self.domains!r}"
            )
        return self
