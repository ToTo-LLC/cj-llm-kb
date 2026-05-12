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
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    provider: Literal["anthropic"] = "anthropic"
    default_model: str = "claude-sonnet-4-6"
    classify_model: str = "claude-haiku-4-5-20251001"
    max_output_tokens: int = 4096
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)


class RateLimitOverride(BaseModel):
    """Per-domain rate-limit override (Plan 16 Task 30 / D27 step 1 of 3).

    Schema-only landing: the field exists and round-trips, but no runtime
    enforcement is wired yet (Task 31 lands the AnthropicProvider
    leaky-bucket enforcement; Task 32 lands the Settings UI).

    A ``None`` ``requests_per_minute`` means "no override; the provider
    bypasses rate-limit gating for this domain". A positive integer caps
    the per-minute request rate for spend attributed to this domain. Zero
    and negative values are rejected because the way to disable a limit
    is to pass ``None`` (or omit the field), and a non-positive cap would
    either silently match no traffic or break the leaky-bucket
    arithmetic downstream once Task 31 lands.

    ``extra="forbid"`` matches every other config sub-model so a typo in
    ``config.json`` (e.g. ``rpm`` instead of ``requests_per_minute``)
    surfaces at load time instead of being silently dropped.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    requests_per_minute: int | None = None

    @field_validator("requests_per_minute")
    @classmethod
    def _validate_positive(cls, v: int | None) -> int | None:
        # ``None`` means "no override" and is the documented way to clear
        # a limit; only reject zero / negative integers. Pydantic v2
        # dispatches ``None`` to validators by default for ``Optional``
        # fields, hence the explicit guard.
        if v is not None and v <= 0:
            raise ValueError(
                "requests_per_minute must be positive (use None / omit to disable)"
            )
        return v


class ProviderConfig(BaseModel):
    """Per-LLM-provider config (Plan 16 Task 30 / D27 step 1 of 3).

    Lives under :attr:`Config.providers` keyed by provider name (e.g.
    ``"anthropic"``). The provider name itself is intentionally NOT a
    field on this model — it's the dict key on the parent map, so a
    typo in ``config.json`` collides with no real provider rather than
    silently overriding the active one.

    Schema-only landing: the per-domain rate-limit map exists and
    round-trips. T31 wires AnthropicProvider to read this map before
    each ``client.messages.create(...)`` call; T32 surfaces the value
    via Settings → Domains.

    ``extra="forbid"`` is consistent with every other config sub-model.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    # Plan 16 Task 30 / D27 step 1 of 3: per-domain rate-limit overrides.
    # Keys are domain slugs; values are :class:`RateLimitOverride`.
    # Default ``{}`` so legacy configs that lack the field still load
    # (backward compat). No cross-field "key must be in
    # ``Config.domains``" check yet — that lands with Task 31 alongside
    # enforcement; landing it now would require the validator to reach
    # across into the parent ``Config``, which Pydantic v2 doesn't
    # expose at the sub-model layer cleanly.
    rate_limit_per_domain: dict[str, RateLimitOverride] = Field(
        default_factory=dict
    )


class BudgetOverride(BaseModel):
    """Per-domain budget cap overrides (Plan 16 Task 26 / D26 step 1 of 4).

    Schema-only landing: the field exists and round-trips, but no runtime
    enforcement is wired yet (Task 28 lands enforcement; Task 29 lands the
    Settings UI). Each cap is independent — set one, both, or neither.

    A ``None`` cap means "no domain-level override; fall back to the global
    :class:`BudgetConfig` cap". A positive float overrides the global cap
    for spend attributed to this domain. Zero and negative caps are
    rejected because there's no plausible user intent for them: the way
    to disable a cap is to pass ``None`` (or omit the field), and a
    negative cap would either silently match no spend or, worse, break
    enforcement arithmetic downstream once Task 28 lands.

    ``extra="forbid"`` matches every other config sub-model so a typo in
    ``config.json`` surfaces at load time instead of being silently
    dropped.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    monthly_cap_usd: float | None = None
    daily_cap_usd: float | None = None

    @field_validator("monthly_cap_usd", "daily_cap_usd")
    @classmethod
    def _validate_positive(cls, v: float | None) -> float | None:
        # ``None`` means "no override" and is the documented way to clear
        # a cap; only reject zero / negative numerics. Pydantic v2 dispatches
        # ``None`` to validators by default for ``Optional`` fields, hence
        # the explicit guard.
        if v is not None and v <= 0:
            raise ValueError(
                "budget cap must be positive (use None / omit to disable)"
            )
        return v


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    daily_usd: float = Field(default=5.0, ge=0.0)
    monthly_usd: float = Field(default=80.0, ge=0.0)
    alert_threshold_pct: int = Field(default=80, ge=0, le=100)
    # Plan 07 Task 4: ephemeral budget override. ``override_until`` is a UTC
    # timestamp; while ``now() < override_until`` the effective daily cap is
    # ``daily_usd + override_delta_usd``. Persisted on the Config object and
    # round-tripped to ``<vault>/.brain/config.json`` like every other
    # ``BudgetConfig`` field (Plan 11 Task 4 disk persistence); the
    # ``brain_budget_override`` tool writes them via the standard
    # ``brain_config_set`` allowlist path so a UI surface can wipe them too.
    override_until: datetime | None = None
    override_delta_usd: float = Field(default=0.0, ge=0.0)
    # Plan 16 Task 26 / D26 step 1 of 4: per-domain cap overrides. Keys are
    # domain slugs; values are :class:`BudgetOverride`. Default ``{}`` so
    # legacy configs that lack the field still load (backward compat).
    # No cross-field "key must be in Config.domains" check yet — that
    # arrives with Task 28 alongside enforcement; landing it now would
    # require the validator to reach across into the parent ``Config``,
    # which Pydantic v2 doesn't expose at the sub-model layer cleanly.
    per_domain: dict[str, BudgetOverride] = Field(default_factory=dict)


class URLHandlerConfig(BaseModel):
    """Tunables for the URL source handler (issue #23).

    Surfaced via the Settings UI / ``brain_config_set`` so a user on a slow
    network can raise the timeout, or a user on a flaky one can lower it
    (and surface an error sooner).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
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

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
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

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
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

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    url: URLHandlerConfig = Field(default_factory=URLHandlerConfig)
    tweet: TweetHandlerConfig = Field(default_factory=TweetHandlerConfig)
    pdf: PDFHandlerConfig = Field(default_factory=PDFHandlerConfig)


class AutonomyCategoryFlags(BaseModel):
    """Per-category auto-apply flags for one domain (Plan 16 Task 38 / T37 §1).

    Lives under :attr:`Config.autonomous` keyed by domain slug. The five
    keys are a HYBRID surface — three are :class:`brain_core.vault.types.PatchSet`
    member-field names (``new_files``, ``edits``, ``index_entries``); two
    are :class:`brain_core.vault.types.PatchCategory` values (``concepts``,
    ``draft``). The category selection is intentional: chat-mode autonomy
    ("draft a note for me") is naturally category-shaped, while
    ingest / propose-note autonomy is naturally member-field-shaped (the
    user reasons about "do I trust auto-creating new files?" not "do I
    trust the INGEST bucket?").

    Every flag defaults to ``False`` — out-of-the-box brain stages every
    LLM-authored vault mutation for human approval (CLAUDE.md principle #3).
    The gate (T39 reshapes :func:`brain_core.autonomy.should_auto_apply`)
    treats a missing-domain entry the same as an all-False entry: no key
    in ``Config.autonomous`` for a slug means "stage everything for that
    domain".

    ``extra="forbid"`` rejects unknown category keys at load time so a typo
    in ``config.json`` (e.g. ``new_filez`` instead of ``new_files``) fails
    loud rather than being silently dropped.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    new_files: bool = False
    edits: bool = False
    index_entries: bool = False
    concepts: bool = False
    draft: bool = False


class WatchedFolder(BaseModel):
    """One entry in :attr:`Config.watched_folders` (Plan 22 T1 / spec §5).

    A user-opted-in folder whose contents are mirrored into the vault by
    :class:`brain_core.watch.WatchedFolderWatcher` (T6+). One record per
    watched folder; the watcher reconciles file create / modify / delete
    events into vault note create / update / orphan-mark operations.

    Fields:

    * ``path`` — absolute folder path on disk. Stored as ``str`` (not
      :class:`pathlib.Path`) because the value is treated as an opaque
      identifier in the on-disk config and in :attr:`Frontmatter.watched_folder_id`
      links. The :meth:`_check_path_absolute` validator rejects relative
      paths with a clear message so the error surfaces at config-load time
      rather than later when the watcher tries to walk it.
    * ``domain`` — the vault domain newly-ingested files land in. Must
      be a slug from :attr:`Config.domains`; the cross-field check lives
      on :class:`Config` (not here) because Pydantic v2 sub-models can't
      see the parent's live state cleanly. See :meth:`Config._check_watched_folders_keys_in_domains`.
    * ``enabled`` — default ``True``; toggling to ``False`` makes the
      watcher skip this entry without losing its config row (Settings UI
      affordance per D5 / spec §5).
    * ``last_sync`` — UTC timestamp of the last successful full sync.
      ``None`` until the first sync completes; T2 / T6 update it.
    * ``policy`` — write-collision policy. Locked to ``"overwrite"`` in
      v1 per D1; the :class:`typing.Literal` reserves room to add
      ``"keep_vault"`` / ``"prompt"`` / ``"merge"`` in v2 without a
      schema migration on user configs.
    * ``include_subdirs`` — default ``True``; recursive walk semantics
      match what most users mean by "watch this folder".

    ``extra="forbid"`` matches every other config sub-model so typos in
    ``config.json`` (e.g. ``"pathh"`` or ``"sub_dirs"``) surface at load
    time instead of being silently dropped.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    path: str
    domain: str
    enabled: bool = True
    last_sync: datetime | None = None
    policy: Literal["overwrite"] = "overwrite"
    include_subdirs: bool = True

    @field_validator("path")
    @classmethod
    def _check_path_absolute(cls, v: str) -> str:
        # Field-level validator (not ``model_validator(mode="after")``)
        # so a bad ``path`` raises BEFORE the field is mutated under
        # ``validate_assignment=True`` (CLAUDE.md "What NOT to do" / Plan
        # 16 T36 lesson). Empty-string check first so the error wording
        # is the one a user actually sees instead of a generic
        # ``Path("").is_absolute()`` False.
        if not v:
            raise ValueError("WatchedFolder.path must not be empty")
        if not Path(v).is_absolute():
            raise ValueError(
                f"WatchedFolder.path {v!r} must be absolute "
                "(start with '/' on POSIX, drive letter on Windows)"
            )
        return v

    @field_validator("domain")
    @classmethod
    def _check_domain_slug(cls, v: str) -> str:
        # Single-field rule only — that the slug is well-formed.
        # Cross-field "must be in Config.domains" lives on Config
        # because sub-models can't see the parent state cleanly in
        # Pydantic v2. Mirrors the privacy_railed pattern.
        return _validate_domain_slug(v)


class DomainOverride(BaseModel):
    """Per-domain LLM overrides (Plan 11 D8; Plan 12 D1 dropped the
    autonomy field — autonomy is governed by the per-category flags on
    :class:`AutonomyCategoryFlags`, not a per-domain bool).

    Every field is ``None`` by default — a missing override means "fall
    back to the global value from :class:`LLMConfig`". A populated field
    replaces the global value when the active scope matches this
    override's slug. The bounds on ``temperature`` and
    ``max_output_tokens`` mirror :class:`LLMConfig` 1:1 so a user can't
    write an override that would itself fail global validation.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    classify_model: str | None = None
    default_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=1.5)
    max_output_tokens: int | None = Field(default=None, gt=0)


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
        "cross_domain_warning_acknowledged",
        "providers",
        # Plan 22 T1 / D7: opt-in watched-folder records. Round-trips
        # through ``config.json`` so a watcher restart resumes the
        # subscription set the user configured.
        "watched_folders",
        # Plan 16 Task 34 / D28 step 2 of 3: monotonically-increasing
        # version stamp. Persisted so the loader's single-process cache
        # (``loader.resolve_config``) can detect a stale in-memory
        # snapshot by peeking the on-disk integer without re-parsing
        # the whole config. Bumped in-place by ``save_config`` on every
        # successful write.
        "config_version",
    }
)


class Config(BaseModel):
    # Plan 16 Task 36 / D29 (locked 1.B + 3.A): ``validate_assignment=True``
    # is enabled UNCONDITIONALLY across :class:`Config` and every sub-config.
    # An out-of-range or wrong-type value raises ``ValidationError`` on
    # assignment instead of silently persisting until the next
    # ``load_config`` rejects the file. The accompanying perf benchmark
    # (``tests/config/test_validate_assignment_perf.py``) measures the
    # overhead; the lessons.md Plan 16 entry captures the cost. Per the
    # locked decision, the flag ships regardless of the measured cost —
    # type safety beats a marginal perf delta on a non-hot-path object.
    #
    # Pydantic v2 quirk: ``model_validator(mode="after")`` runs on every
    # ``setattr`` when this flag is set, but a validation failure inside
    # a model_validator does NOT roll back the field mutation (only
    # field-level validators do). Cross-field violations (e.g. setting
    # ``domains=[]`` while ``active_domain="research"``) raise but leave
    # the field at the bad value. The ``persist_config_or_revert``
    # context manager covers this with its snapshot-and-revert path.
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
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
    # Plan 16 Task 38 / T37 §1: per-domain auto-apply flags. Keys are
    # domain slugs; values are :class:`AutonomyCategoryFlags`. Default
    # ``{}`` so a fresh install (and any legacy ``config.json`` that
    # predates this field) lands at all-False evaluation everywhere — the
    # gate (T39 reshapes :func:`brain_core.autonomy.should_auto_apply`)
    # treats a missing slug the same as an explicit all-False entry.
    # Cross-field validator below enforces "every key must be a live
    # domain" (no orphan autonomy entries for deleted slugs).
    #
    # Migration from the pre-T38 flat ``AutonomousConfig`` shape (the
    # five-bool ``ingest`` / ``entities`` / ``concepts`` /
    # ``index_rewrites`` / ``draft`` model) is handled by
    # :func:`brain_core.config.loader._migrate_legacy_autonomous` —
    # called inside ``load_config`` before ``Config(**data)``, so any
    # caller that goes through the loader gets the new shape
    # automatically. The migration is idempotent (re-running on the new
    # shape is a no-op).
    autonomous: dict[str, AutonomyCategoryFlags] = Field(default_factory=dict)
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
    # Plan 11 D8: per-domain LLM overrides. Keys are domain slugs;
    # values are :class:`DomainOverride` instances. Cross-field validator
    # below enforces that every key is also in ``self.domains`` (no
    # orphan overrides for deleted domains). Plan 12 D1 dropped the
    # per-domain ``autonomous_mode`` override field — autonomy is
    # governed by :class:`AutonomyCategoryFlags` per-category flags
    # under :attr:`Config.autonomous` (Plan 16 Task 38 reshaped the field).
    domain_overrides: dict[str, DomainOverride] = Field(default_factory=dict)
    # Plan 12 D8 (spec §4): persistent acknowledgment of the cross-domain
    # confirmation modal. Default ``False`` means the modal fires the
    # next time scope crosses a privacy-railed domain (per the D7
    # trigger: ``len(scope) >= 2 AND any(s in privacy_railed for s in
    # scope)``). Toggling this back to ``False`` via Settings → Domains
    # re-enables the prompt for one more firing.
    cross_domain_warning_acknowledged: bool = Field(default=False)
    # Plan 16 Task 30 / D27 step 1 of 3: per-LLM-provider config map.
    # Keys are provider names (e.g. ``"anthropic"``); values are
    # :class:`ProviderConfig`. Default ``{}`` so legacy configs that
    # lack the field still load (backward compat). T31 wires the
    # AnthropicProvider to read the per-domain rate-limit map from
    # ``self.providers["anthropic"].rate_limit_per_domain`` before
    # each upstream call; T32 surfaces the value via Settings →
    # Domains. The provider-name set is intentionally NOT validated
    # against any Literal — adding a new LLM provider should not
    # require a schema migration of every user's persisted config.
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    # Plan 16 Task 34 / D28 step 2 of 3: monotonically-increasing
    # version counter, bumped in place by ``save_config`` on every
    # successful write. The single-process loader cache
    # (:func:`brain_core.config.loader.resolve_config`) peeks this
    # field on every call to detect a stale in-memory ``Config`` —
    # if the on-disk version exceeds the cached version, the loader
    # re-reads. Default ``0`` so legacy configs that predate this
    # field still load (backward compat); the first ``save_config``
    # call will bump them to ``1``. The value is meaningful only as
    # a strict "did the disk change since I last read it" signal —
    # callers should not interpret the magnitude.
    config_version: int = Field(default=0, ge=0)
    # Plan 22 T1 / D7 / spec §5: opt-in watched-folder records. Empty
    # list by default so a fresh install (and every legacy ``config.json``
    # that predates this field) lands at "no folders watched" — the
    # watcher subsystem is opt-in per the safety-rails contract (no
    # background process touches the user's filesystem without an
    # explicit ``brain_watch_folder`` call). The cross-field validator
    # below enforces "every entry's ``domain`` is a live domain slug"
    # using a snapshot-revert pattern that complies with the Plan 16
    # T36 lesson (``model_validator(mode="after")`` failures leave the
    # field mutated to the bad value under ``validate_assignment=True``
    # — single-field validators like this one DO roll back on raise,
    # which is why we read ``self.domains`` from the post-after-validator
    # state and apply the revert in the model validator itself rather
    # than relying on the raise alone).
    watched_folders: list[WatchedFolder] = Field(default_factory=list)

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

    @model_validator(mode="after")
    def _check_watched_folders_domains_in_domains(self) -> Config:
        # Plan 22 T1 / D7: every ``WatchedFolder.domain`` must be a
        # member of the live ``domains`` list. Mirrors the equivalent
        # ``domain_overrides`` and ``autonomous`` validators. Without
        # this guard, deleting a domain would leave a stale watched-
        # folder entry that silently routes new ingests to a slug that
        # no longer exists. The cross-field check lives here (not on
        # :class:`WatchedFolder`) because Pydantic v2 sub-models can't
        # see the parent's live state cleanly.
        #
        # Pydantic v2 quirk under ``validate_assignment=True`` (Plan 16
        # T36): a raise inside ``model_validator(mode="after")`` does
        # NOT roll back the triggering field mutation. The intended
        # write path for watched-folder mutations is therefore the
        # ``brain_watch_folder`` / ``brain_unwatch_folder`` tools, which
        # apply a pre-check BEFORE ``setattr`` (canonical pattern at
        # :func:`brain_core.tools.config_set._check_active_domain_membership`).
        # This validator catches misuse from direct setattr / load-time
        # construction and reports clearly.
        orphans = sorted(
            {wf.domain for wf in self.watched_folders if wf.domain not in self.domains}
        )
        if orphans:
            raise ValueError(
                f"watched_folders entries reference domains {orphans!r} "
                f"that are not in domains {self.domains!r}; "
                "remove the entry or add the domain first."
            )
        return self

    @model_validator(mode="after")
    def _check_autonomy_keys_in_domains(self) -> Config:
        # Plan 16 Task 38 / T37 §1: orphan autonomy entries (keys for
        # slugs that aren't in ``domains``) are rejected — mirrors the
        # equivalent ``domain_overrides`` validator. Without this guard,
        # deleting a domain would leave a stale autonomy entry that
        # silently comes back if the slug is re-added.
        orphans = [slug for slug in self.autonomous if slug not in self.domains]
        if orphans:
            raise ValueError(
                f"autonomous keys {orphans!r} are not in domains {self.domains!r}; "
                "remove the entry or add the domain first."
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
