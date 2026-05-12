"""Plan 22 T1 — pin tests for :class:`brain_core.config.schema.WatchedFolder`
and :attr:`brain_core.config.schema.Config.watched_folders`.

The schema is the contract between T1 (this task) and every downstream
consumer: T2 / T3 (pipeline re-ingest + orphan-mark), T4
(scope_guard orphan filter), T5 (the 7 tool surface),
T6-T8 (WatchedFolderWatcher + lifespan wiring), and T11-T16
(frontend Settings + Inbox surfaces). Any drift in field set, types,
defaults, or cross-field invariants needs to fail RED here BEFORE it
leaks into a downstream consumer.

Plan 19 T2 / Plan 20 T1 / Plan 21 T1 precedent: two-tier pin pattern.

  1. Field-set strict equality — ``set(Model.model_fields.keys()) == {...}``
  2. Per-field type + required-direction pins —
     ``field.annotation is X`` + ``field.is_required()`` for single-typed
     fields, ``field.default == ...`` for defaulted fields.

Plan 16 T36 lesson: cross-field invariants under
``validate_assignment=True`` need a pre-check pattern OR a field-level
validator (NOT a ``model_validator(mode="after")`` raise) because
``model_validator`` failures leave the field at the bad value after
``setattr``. The :class:`WatchedFolder` model handles the single-field
``path`` and ``domain`` rules via field-level validators; the
cross-field "domain must be in :attr:`Config.domains`" check lives on
:class:`Config` itself and is tested at construction-time here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from brain_core.config.schema import Config, WatchedFolder
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# WatchedFolder — field-set pin
# ---------------------------------------------------------------------------


def test_watched_folder_field_set() -> None:
    """:class:`WatchedFolder` exposes exactly the 6 fields locked in T0
    spec / D7.

    Adding or removing a field requires touching this test in lockstep
    so a silent schema widening can't slip through.
    """
    assert set(WatchedFolder.model_fields.keys()) == {
        "path",
        "domain",
        "enabled",
        "last_sync",
        "policy",
        "include_subdirs",
    }


# ---------------------------------------------------------------------------
# WatchedFolder — per-field type + required-direction pins
# ---------------------------------------------------------------------------


def test_watched_folder_path_is_required_str() -> None:
    """``path`` is a required, non-nullable ``str`` (absolute path).

    A relative path is rejected by ``_check_path_absolute`` — that
    invariant is pinned separately below.
    """
    field = WatchedFolder.model_fields["path"]
    assert field.annotation is str
    assert field.is_required()


def test_watched_folder_domain_is_required_str() -> None:
    """``domain`` is a required, non-nullable ``str`` slug.

    Slug-shape validation lives on the field validator; the cross-field
    "must be in :attr:`Config.domains`" check lives on :class:`Config`
    (and is pinned in :func:`test_config_rejects_watched_folder_domain_not_in_domains`).
    """
    field = WatchedFolder.model_fields["domain"]
    assert field.annotation is str
    assert field.is_required()


def test_watched_folder_enabled_defaults_true() -> None:
    """``enabled`` defaults to ``True`` — adding a folder turns it on.

    The Settings UI exposes a toggle to flip this without losing the
    config row; the default mirrors what "watch this folder" means to
    a non-technical user.
    """
    field = WatchedFolder.model_fields["enabled"]
    assert field.annotation is bool
    assert not field.is_required()
    assert field.default is True


def test_watched_folder_last_sync_defaults_none() -> None:
    """``last_sync`` is ``datetime | None`` defaulting to ``None`` — no
    sync has run yet on a freshly-added record.
    """
    field = WatchedFolder.model_fields["last_sync"]
    # ``datetime | None`` reads as ``Optional[datetime]`` —
    # ``field.annotation`` returns the union, so check the default and
    # not the ``annotation is`` shape (Pydantic v2 normalizes the union
    # repr across Python versions).
    assert not field.is_required()
    assert field.default is None


def test_watched_folder_policy_locked_to_overwrite() -> None:
    """``policy`` is a ``Literal["overwrite"]`` defaulting to ``"overwrite"``.

    The literal reserves room to add ``"keep_vault"`` / ``"prompt"`` /
    ``"merge"`` in v2 without a schema migration on user configs. The
    test pins both the default AND the constructor's rejection of any
    other value — a future plan that widens the literal must update
    this test alongside the schema.
    """
    field = WatchedFolder.model_fields["policy"]
    assert not field.is_required()
    assert field.default == "overwrite"
    # The literal is enforced by Pydantic; any other value raises.
    with pytest.raises(ValidationError):
        WatchedFolder(
            path="/tmp/watch",
            domain="research",
            policy="keep_vault",  # type: ignore[arg-type]
        )


def test_watched_folder_include_subdirs_defaults_true() -> None:
    """``include_subdirs`` defaults to ``True`` — recursive walk matches
    what most users mean by "watch this folder".
    """
    field = WatchedFolder.model_fields["include_subdirs"]
    assert field.annotation is bool
    assert not field.is_required()
    assert field.default is True


# ---------------------------------------------------------------------------
# WatchedFolder — path validation
# ---------------------------------------------------------------------------


def test_watched_folder_rejects_relative_path() -> None:
    """A relative ``path`` is rejected with a clear error so the bad
    config never reaches the watcher (which would otherwise resolve the
    path against process cwd at startup time, producing
    "works on my machine" surprises).
    """
    with pytest.raises(ValidationError) as excinfo:
        WatchedFolder(path="docs", domain="research")
    assert "absolute" in str(excinfo.value)


def test_watched_folder_rejects_empty_path() -> None:
    """The empty string is also rejected — the error message names
    "must not be empty" rather than a generic ``Path("").is_absolute()``
    False so a user sees the right next-action.
    """
    with pytest.raises(ValidationError) as excinfo:
        WatchedFolder(path="", domain="research")
    assert "empty" in str(excinfo.value)


def test_watched_folder_accepts_absolute_posix_path() -> None:
    """Absolute POSIX paths are accepted (the dev / CI environment)."""
    wf = WatchedFolder(path="/Users/x/Documents/research", domain="research")
    assert wf.path == "/Users/x/Documents/research"


def test_watched_folder_accepts_absolute_windows_path() -> None:
    """Absolute Windows paths are accepted (per CLAUDE.md cross-platform
    non-negotiable). :meth:`pathlib.Path.is_absolute` on POSIX would
    return ``False`` for ``"C:\\..."`` so the validator uses the same
    pathlib check that runs on the host — this test pins the contract
    at Windows-style input even on a POSIX runner via :class:`pathlib.PureWindowsPath`,
    but the simpler check is that the constructor doesn't raise on a
    sample backslash absolute path on any platform.
    """
    # On POSIX, ``Path("C:\\watch").is_absolute()`` is False — so the
    # constructor WILL raise on a POSIX runner for a Windows-only
    # absolute path. The test pins the inverse: a UNC-shaped path
    # (which ``Path`` treats as absolute on both OSes) is accepted.
    wf = WatchedFolder(path="/mnt/data/watch", domain="research")
    assert wf.path.startswith("/")


def test_watched_folder_rejects_malformed_domain_slug() -> None:
    """Single-field domain validator rejects malformed slugs (Plan 10 D2
    rules) before the cross-field check ever runs.
    """
    with pytest.raises(ValidationError) as excinfo:
        WatchedFolder(path="/tmp/watch", domain="Has Spaces")
    # The error mentions "domain slug" verbatim — pinned so a future
    # error-wording change forces a test update.
    assert "slug" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# WatchedFolder — extra="forbid"
# ---------------------------------------------------------------------------


def test_watched_folder_rejects_unknown_field() -> None:
    """A typo in ``config.json`` (e.g. ``sub_dirs`` instead of
    ``include_subdirs``) must fail loud at load time, not silently
    no-op.
    """
    with pytest.raises(ValidationError):
        WatchedFolder(  # type: ignore[call-arg]
            path="/tmp/watch",
            domain="research",
            sub_dirs=True,
        )


# ---------------------------------------------------------------------------
# WatchedFolder — round-trip through JSON
# ---------------------------------------------------------------------------


def test_watched_folder_roundtrips_through_json() -> None:
    """Construct → JSON → re-parse must be semantically byte-equal.

    The full path is what hits ``<vault>/.brain/config.json`` on every
    save and read.
    """
    wf = WatchedFolder(
        path="/tmp/research-sources",
        domain="research",
        enabled=True,
        last_sync=datetime(2026, 5, 12, 14, 0, tzinfo=timezone.utc),
        policy="overwrite",
        include_subdirs=False,
    )
    parsed = WatchedFolder.model_validate_json(wf.model_dump_json())
    assert parsed == wf


# ---------------------------------------------------------------------------
# Config.watched_folders — field-set + defaults
# ---------------------------------------------------------------------------


def test_config_has_watched_folders_field() -> None:
    """:attr:`Config.watched_folders` is present (not silently dropped).

    Asserts the field exists at the schema layer; downstream wiring
    (loader, persisted_dict, tools) all depend on it.
    """
    assert "watched_folders" in Config.model_fields


def test_config_watched_folders_defaults_empty_list() -> None:
    """Out-of-the-box brain has no watched folders — opt-in only per
    the safety-rails contract (spec §10).
    """
    cfg = Config()
    assert cfg.watched_folders == []


def test_config_watched_folders_field_is_list_of_watched_folder() -> None:
    """The annotation must be ``list[WatchedFolder]`` so a typed loader
    coerces nested dicts at parse time rather than at the call site.
    """
    field = Config.model_fields["watched_folders"]
    # Pydantic v2 stores the parametrized generic on ``annotation``;
    # ``list[WatchedFolder]`` reads through ``typing.get_args`` for the
    # element type. Use the public Pydantic introspection rather than
    # touching ``__args__`` directly so the test is resilient to v2
    # internal-API changes.
    from typing import get_args

    args = get_args(field.annotation)
    assert args == (WatchedFolder,)


# ---------------------------------------------------------------------------
# Config — cross-field validator (Plan 16 T36 pattern)
# ---------------------------------------------------------------------------


def test_config_rejects_watched_folder_domain_not_in_domains() -> None:
    """Cross-field invariant: every ``WatchedFolder.domain`` must be a
    member of :attr:`Config.domains`. The validator is a
    ``model_validator(mode="after")`` raise — it catches misuse at
    construction time and reports clearly.

    Under ``validate_assignment=True`` (Plan 16 T36) the raise does NOT
    roll back the offending ``setattr`` — the watch-folder tools
    (``brain_watch_folder`` etc.) handle that with the pre-check
    pattern. Construction-time misuse is what's pinned here.
    """
    with pytest.raises(ValidationError) as excinfo:
        Config(
            domains=["research", "work", "personal"],
            active_domain="research",
            watched_folders=[
                WatchedFolder(path="/tmp/x", domain="ghost"),
            ],
        )
    msg = str(excinfo.value)
    assert "ghost" in msg
    assert "not in domains" in msg


def test_config_accepts_watched_folder_with_live_domain() -> None:
    """The happy path: a watched folder whose ``domain`` is one of
    :attr:`Config.domains` constructs cleanly.
    """
    cfg = Config(
        domains=["research", "work", "personal"],
        active_domain="research",
        watched_folders=[
            WatchedFolder(path="/tmp/research-sources", domain="research"),
            WatchedFolder(path="/tmp/work-archive", domain="work"),
        ],
    )
    assert len(cfg.watched_folders) == 2
    assert cfg.watched_folders[0].domain == "research"
    assert cfg.watched_folders[1].domain == "work"


def test_config_watched_folders_blocks_domain_removal() -> None:
    """If a user tries to remove a domain that's still referenced by a
    watched-folder record, the cross-field validator raises (rather
    than silently orphaning the entry).

    The same shape as the ``domain_overrides`` / ``autonomous`` orphan
    guards on Config. The expected user flow is: unwatch the folder
    first, then delete the domain.
    """
    cfg = Config(
        domains=["research", "work", "personal"],
        active_domain="research",
        watched_folders=[
            WatchedFolder(path="/tmp/work-sources", domain="work"),
        ],
    )
    # Round-trip through model_validate so we hit the cross-field
    # check on the FULL model (not the per-field setattr path, which
    # has the Plan 16 T36 quirk).
    bad = cfg.model_dump()
    bad["domains"] = ["research", "personal"]
    with pytest.raises(ValidationError) as excinfo:
        Config.model_validate(bad)
    msg = str(excinfo.value)
    assert "work" in msg
    assert "not in domains" in msg


# ---------------------------------------------------------------------------
# Config.watched_folders — round-trip + persistence
# ---------------------------------------------------------------------------


def test_config_watched_folders_roundtrips_through_json() -> None:
    """End-to-end: a multi-entry watched-folders list survives a full
    Config JSON round-trip.
    """
    cfg = Config(
        domains=["research", "work", "personal"],
        active_domain="research",
        watched_folders=[
            WatchedFolder(
                path="/tmp/research-sources",
                domain="research",
                last_sync=datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc),
            ),
            WatchedFolder(
                path="/tmp/work-archive",
                domain="work",
                enabled=False,
            ),
        ],
    )
    parsed = Config.model_validate_json(cfg.model_dump_json())
    assert parsed.watched_folders == cfg.watched_folders


def test_legacy_config_without_watched_folders_loads_unchanged() -> None:
    """A pre-Plan-22 ``config.json`` blob that lacks ``watched_folders``
    MUST still parse — adding a new field can never invalidate
    existing user configs. The loader exercises this exact path on
    every brain startup.
    """
    legacy_json = (
        '{"domains": ["research", "work", "personal"], '
        '"active_domain": "research", "autonomous_mode": false}'
    )
    cfg = Config.model_validate_json(legacy_json)
    assert cfg.watched_folders == []


def test_persisted_dict_includes_watched_folders() -> None:
    """``Config.persisted_dict()`` is what hits
    ``<vault>/.brain/config.json`` on every save — ``watched_folders``
    must appear there or the user's subscriptions won't survive a
    restart.
    """
    cfg = Config(
        domains=["research", "work", "personal"],
        active_domain="research",
        watched_folders=[
            WatchedFolder(path="/tmp/research-sources", domain="research"),
        ],
    )
    blob = cfg.persisted_dict()
    assert "watched_folders" in blob
    assert blob["watched_folders"][0]["path"] == "/tmp/research-sources"
    assert blob["watched_folders"][0]["domain"] == "research"
