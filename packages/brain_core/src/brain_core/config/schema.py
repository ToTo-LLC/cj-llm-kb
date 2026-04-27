"""Typed Config model. Source of truth for all user-configurable behavior.

Plan 10 / issue #21 — domain set is configurable. ``Config.domains`` holds
the user's runtime list of top-level vault domains. The v0.1 ``Domain``
``Literal`` alias remains for one minor version so any external caller
still typing against it compiles through the transition; ``DEFAULT_DOMAINS``
exposes the v0.1 tuple for any caller that needs a default. The legacy
``ALLOWED_DOMAINS`` tuple was dropped in Plan 10 Task 2 — call sites that
need a fallback must import ``DEFAULT_DOMAINS`` (or, preferably, read
``Config.domains`` from the live config).

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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Deprecation alias — kept so external callers typing against ``Domain``
# compile through the Plan 10 transition. The alias becomes a plain
# ``str`` re-export once every internal call site has migrated to
# ``Config.domains`` (filed for the next minor version after Plan 10).
# Plan 10 Task 2 dropped the ``ALLOWED_DOMAINS`` tuple — call sites
# that still need a default fallback should import ``DEFAULT_DOMAINS``
# below, but the preferred path is to read ``Config.domains`` directly.
Domain = Literal["research", "work", "personal"]

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


class DomainOverride(BaseModel):
    """Per-domain LLM/autonomy overrides (Plan 11 D8).

    Every field is ``None`` by default — a missing override means "fall
    back to the global value from :class:`LLMConfig` / :class:`Config`".
    A populated field replaces the global value when the active scope
    matches this override's slug. The bounds on ``temperature`` and
    ``max_output_tokens`` mirror :class:`LLMConfig` 1:1 so a user can't
    write an override that would itself fail global validation.
    """

    model_config = ConfigDict(extra="forbid")
    classify_model: str | None = None
    default_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=1.5)
    max_output_tokens: int | None = Field(default=None, gt=0)
    autonomous_mode: bool | None = None


# Plan 11 D4: persistence whitelist. ``Config.persisted_dict()`` (below)
# uses this set to drive ``model_dump(include=...)`` so the on-disk
# ``config.json`` only carries fields the user is allowed to set.
# ``vault_path`` is deliberately excluded — it's a chicken-and-egg field
# (we need it to find ``config.json`` itself) and is sourced from the
# environment / setup wizard, not the persisted config blob.
_PERSISTED_FIELDS: frozenset[str] = frozenset(
    {
        "domains",
        "active_domain",
        "autonomous_mode",
        "web_port",
        "log_llm_payloads",
        "llm",
        "budget",
        "autonomous",
        "handlers",
        "domain_overrides",
        "privacy_railed",
    }
)


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
    # Plan 11 D11: privacy-rail slug list. ``personal`` is required (the
    # field validator enforces it) so the user can never accidentally
    # un-rail their personal content; additional slugs can be opted in to
    # the rail, but membership is gated against ``self.domains`` by the
    # cross-field model validator below — you cannot rail a slug that
    # doesn't exist as a domain.
    privacy_railed: list[str] = Field(default_factory=lambda: [PRIVACY_RAILED_SLUG])
    # Plan 11 D8: per-domain LLM/autonomy overrides. Keys are domain
    # slugs; values are :class:`DomainOverride` instances. Cross-field
    # validator below enforces that every key is also in ``self.domains``
    # (no orphan overrides for deleted domains).
    domain_overrides: dict[str, DomainOverride] = Field(default_factory=dict)

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

    @field_validator("privacy_railed")
    @classmethod
    def _check_privacy_railed(cls, v: list[str]) -> list[str]:
        # D2 slug rules + D11 personal-required. Single-field rules only
        # — the cross-field "must also be a domain" check is handled by
        # the model validator below (it needs ``self.domains``).
        for slug in v:
            _validate_domain_slug(slug)
        # D2: no duplicates within the rail list.
        seen: set[str] = set()
        for slug in v:
            if slug in seen:
                raise ValueError(
                    f"privacy_railed slug {slug!r} appears more than once in privacy_railed list"
                )
            seen.add(slug)
        # D11: ``personal`` is mandatory in the privacy rail. The user
        # may extend the rail to additional slugs but may NOT remove the
        # ``personal`` rail. Wording mirrors the ``_check_domains`` voice
        # so the Settings UI can surface either error consistently.
        if PRIVACY_RAILED_SLUG not in v:
            raise ValueError(
                f"{PRIVACY_RAILED_SLUG} is required in privacy_railed and may not be removed; "
                "use Settings → Privacy to control which additional domains are railed."
            )
        return v

    @model_validator(mode="after")
    def _check_privacy_railed_subset_of_domains(self) -> Config:
        # D11: every railed slug must also exist as a domain — railing a
        # slug that isn't a domain would silently do nothing on disk and
        # mislead the user about their privacy posture.
        missing = [slug for slug in self.privacy_railed if slug not in self.domains]
        if missing:
            raise ValueError(
                f"privacy_railed entries {missing!r} are not in domains {self.domains!r}; "
                "every railed slug must also be a configured domain."
            )
        return self

    @model_validator(mode="after")
    def _check_domain_overrides_keys_in_domains(self) -> Config:
        # D8: orphan overrides (keys for slugs that aren't in ``domains``)
        # are rejected — silently keeping them would let a deleted domain
        # come back with stale overrides if it were re-added.
        orphans = [slug for slug in self.domain_overrides if slug not in self.domains]
        if orphans:
            raise ValueError(
                f"domain_overrides keys {orphans!r} are not in domains {self.domains!r}; "
                "remove the override or add the domain first."
            )
        return self

    def persisted_dict(self) -> dict[str, Any]:
        """Return only the fields the user is allowed to persist (Plan 11 D4).

        Excludes ``vault_path`` (sourced from the environment / setup
        wizard, not the persisted blob) and any other field not in
        :data:`_PERSISTED_FIELDS`. Use this anywhere ``config.json`` is
        about to hit disk.
        """
        # ``model_dump(include=...)`` typing requires a regular ``set``
        # (or ``dict``), not a ``frozenset``. The module-level constant
        # is kept frozen so external callers can't mutate the canonical
        # whitelist; we materialise a fresh ``set`` per call.
        return self.model_dump(include=set(_PERSISTED_FIELDS))
