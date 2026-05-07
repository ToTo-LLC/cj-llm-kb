"""Layered config resolution: defaults → config.json → env → CLI overrides.

Plan 11 D7: the file-read step is a fallback chain rather than a hard
failure. When the primary ``config.json`` is missing or unparseable the
loader falls back to ``config.json.bak`` (the writer's atomic-rename
backup, see :mod:`brain_core.config.writer`); when both are missing /
unparseable the loader falls back to ``Config()`` defaults. Every
fallback step emits a structured ``config_load_fallback`` warning so a
later ``brain doctor`` run can surface the corruption without bricking
startup.

Environment and CLI overlays are applied on top of whichever layer
succeeded — the fallback only governs the file-read base layer.

Plan 16 Task 34 / D28 step 2 of 3 adds :func:`resolve_config`: a
single-process cache layer over :func:`load_config`. Successive calls
return the SAME ``Config`` instance until the on-disk
``config_version`` integer (peeked via :func:`_peek_config_version`,
which only re-parses the JSON head) advances. ``load_config`` itself
remains stateless — every caller that wants caching goes through
``resolve_config``. Production callers (``brain_api`` lifespan,
``brain_cli`` chat command) currently still call ``load_config``
directly; T34.5 (separate task) will migrate them.

The cache is single-process. Cross-process hot-reload (file-watcher +
SIGHUP) is T35's job; this module deliberately does not stat the file
on every call beyond the cheap version peek.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog

from brain_core.config.schema import Config

logger = structlog.get_logger(__name__)

ENV_MAP: dict[str, str] = {
    "BRAIN_VAULT": "vault_path",
    "BRAIN_ACTIVE_DOMAIN": "active_domain",
    "BRAIN_AUTONOMOUS": "autonomous_mode",
    "BRAIN_WEB_PORT": "web_port",
    "BRAIN_LOG_LLM_PAYLOADS": "log_llm_payloads",
}

# Plan 16 Task 34: single-process cache for ``resolve_config``.
# Keyed by the resolved (absolute) path of the ``config_file`` argument
# so two different vault roots (one process holding both Configs in
# flight, e.g. test fixtures) get independent cache entries. Each
# entry's value is the cached ``Config`` plus the on-disk
# ``config_version`` we last observed for this path; on every call we
# peek the disk version and short-circuit when it matches.
#
# Env / CLI overrides are intentionally NOT in the cache key. Production
# never mutates env or CLI args mid-process, and a caller that does
# want a fresh read can pass ``force_reload=True``. Including them
# would double the cache miss rate without buying anything real.
_cached: dict[Path, tuple[Config, int]] = {}


# Plan 16 Task 38 / T37 §3: legacy ``AutonomousConfig`` flag names. The
# pre-T38 shape was a flat BaseModel with these five booleans; the new
# shape is ``dict[str, AutonomyCategoryFlags]`` where each value holds
# the (renamed / reshaped) per-domain flags. The migration helper below
# detects the flat shape by checking whether every key in the
# ``autonomous`` payload is one of these names AND every value is a bool.
_LEGACY_AUTONOMOUS_KEYS: frozenset[str] = frozenset(
    {"ingest", "entities", "concepts", "index_rewrites", "draft"}
)


def _migrate_legacy_autonomous(raw: dict[str, Any]) -> dict[str, Any]:
    """Rewrite the pre-T38 flat ``autonomous`` shape into the per-domain nested shape.

    Plan 16 Task 38 / T37 §3 — IDEMPOTENT migration helper. Three accepted
    input shapes for ``raw["autonomous"]``:

      1. **Already nested** (post-migration / fresh install):
         ``{slug: {flag: bool, ...}, ...}`` — passes through unchanged.
      2. **Flat AutonomousConfig** (the real existing on-disk shape):
         five-key dict ``{"ingest": bool, "entities": bool, "concepts":
         bool, "index_rewrites": bool, "draft": bool}`` — expanded per
         the mapping table below for every slug in ``raw["domains"]``.
      3. **Bare bool** (defensive — a hand-edited legacy config that
         never shipped): ``True`` ⇒ all-True for every slug; ``False``
         ⇒ empty dict.

    Mapping table for shape (2) → (1) (USER-LOCKED, T37 §3 D-1/D-2/D-3):

      * ``ingest=True``  ⇒ ``new_files=True, index_entries=True`` per slug.
        Preserves prior intent ("auto-apply ingest patches") under the new
        member-field gate; an INGEST patch is typically ``new_files`` +
        ``index_entries``, so mapping to only one would break ingest
        auto-apply for half the patches.
      * ``entities=True`` ⇒ DROPPED (no flag is set). D-2 = CONSERVATIVE
        choice locked by the user: silently granting edit-autonomy to a
        domain that didn't previously have it (the alternative aggressive
        mapping was ``{new_files=True, edits=True}``) is a scope-guard-
        adjacent capability change. Instead the helper emits a
        ``logger.warning`` with event ``"legacy_autonomy_entities_dropped"``
        so a future ``brain doctor`` / Settings UI surface can prompt the
        user to re-enable specific categories.
      * ``concepts=True`` ⇒ ``concepts=True`` per slug (1:1 by name).
      * ``index_rewrites=True`` ⇒ ``index_entries=True`` per slug (D-3
        rename — the new shape's Literal uses the PatchSet member-field
        name, the old category-bucket name normalizes away).
      * ``draft=True`` ⇒ ``draft=True`` per slug (1:1 by name).
      * Multiple True flags compose with logical OR per cell.
      * ``False`` flags are no-ops; they leave the per-slug entry's other
        flags at the default ``False``.

    The function returns ``raw`` (mutated in place when a migration ran;
    untouched otherwise). ``raw`` without an ``autonomous`` key passes
    through unchanged — Pydantic's ``Field(default_factory=dict)`` lands
    the empty-dict default at ``Config.model_validate`` time.

    Stable warning event contract (downstream tools may rely on this):
      * ``event="legacy_autonomy_entities_dropped"``
      * ``domains: list[str]`` — the slug list that the dropped flag
        WOULD have applied to.
    """
    if "autonomous" not in raw:
        # Pre-Plan-07 ``config.json`` (no autonomous field at all). The
        # Pydantic default lands at construction time.
        return raw

    autonomous = raw["autonomous"]

    # Shape (3): bare bool. Defensive — never shipped, but cheap to
    # handle correctly so a hand-edited legacy config doesn't blow up.
    if isinstance(autonomous, bool):
        domains_list: list[str] = list(raw.get("domains", []))
        if autonomous:
            raw["autonomous"] = {
                slug: {
                    "new_files": True,
                    "edits": True,
                    "index_entries": True,
                    "concepts": True,
                    "draft": True,
                }
                for slug in domains_list
            }
        else:
            raw["autonomous"] = {}
        return raw

    if not isinstance(autonomous, dict):
        # Anything else (string, int, list, ...) — leave it alone so the
        # downstream ``Config(**data)`` raises a canonical Pydantic
        # ``ValidationError``. Coercing here would mask a genuinely
        # corrupt config.
        return raw

    # Distinguish shape (1) from shape (2). Shape (2) is uniquely
    # identified by EVERY key being one of the legacy flag names AND
    # EVERY value being a bool — no slug-keyed entries can match because
    # the slug regex (Plan 10 D2) forbids keys like "ingest" only by
    # accident; the value-type check is what disambiguates a slug
    # called "ingest" pointing at a dict from the legacy ``ingest: true``.
    is_flat_legacy = bool(autonomous) and all(
        key in _LEGACY_AUTONOMOUS_KEYS and isinstance(value, bool)
        for key, value in autonomous.items()
    )

    if not is_flat_legacy:
        # Shape (1): already nested, OR an empty dict (which is also a
        # valid post-migration shape). Leave it alone.
        return raw

    # Shape (2): expand per the mapping table.
    domains_list = list(raw.get("domains", []))

    if autonomous.get("entities") is True:
        # D-2 = CONSERVATIVE: the entities flag silently drops on
        # migration. Emit a structured warning so the change is
        # observable. The event name is stable contract — downstream
        # tooling may grep ``legacy_autonomy_entities_dropped`` to surface
        # the migration via brain doctor / Settings UI.
        logger.warning(
            "legacy_autonomy_entities_dropped",
            domains=domains_list,
        )

    new_autonomous: dict[str, dict[str, bool]] = {}
    for slug in domains_list:
        flags: dict[str, bool] = {
            "new_files": False,
            "edits": False,
            "index_entries": False,
            "concepts": False,
            "draft": False,
        }
        if autonomous.get("ingest") is True:
            flags["new_files"] = True
            flags["index_entries"] = True
        # ``entities=True`` is intentionally not mapped (D-2 conservative).
        if autonomous.get("concepts") is True:
            flags["concepts"] = True
        if autonomous.get("index_rewrites") is True:
            flags["index_entries"] = True
        if autonomous.get("draft") is True:
            flags["draft"] = True
        new_autonomous[slug] = flags

    raw["autonomous"] = new_autonomous
    return raw


def load_config(
    *,
    config_file: Path | None,
    env: Mapping[str, str],
    cli_overrides: Mapping[str, Any],
) -> Config:
    """Build a Config by merging layers; later layers override earlier ones.

    File-read fallback chain (Plan 11 D7):
      1. ``config_file`` — the caller-supplied primary path.
      2. ``<parent>/<name>.bak`` — the writer's rotation backup.
      3. ``Config()`` defaults.

    Each step that fails (missing file or parse error) logs a
    ``config_load_fallback`` warning and proceeds to the next step.
    """
    data: dict[str, Any] = {}

    if config_file is not None:
        loaded = _try_read_config_file(config_file)
        if loaded is None:
            # Plan 11 D7: ``.bak`` lookup uses ``path.name + ".bak"`` so the
            # extension is preserved. ``path.stem`` would drop ``.json`` and
            # produce ``config.bak`` — that is NOT what the writer creates.
            backup = config_file.parent / f"{config_file.name}.bak"
            loaded = _try_read_config_file(backup)
        if loaded is not None:
            # Plan 16 Task 38 / T37 §3: the pre-T38 flat ``AutonomousConfig``
            # shape (five booleans ``ingest`` / ``entities`` / ``concepts`` /
            # ``index_rewrites`` / ``draft``) on disk gets rewritten to the
            # new per-domain nested ``dict[str, AutonomyCategoryFlags]``
            # shape BEFORE ``Config(**data)`` so any user with an existing
            # ``config.json`` keeps working across the schema bump. The
            # migration is idempotent — re-running on the new shape is a
            # no-op — so a hot-reload cycle (Plan 16 Task 35) doesn't
            # corrupt state. ``env`` and ``cli_overrides`` deliberately
            # don't get the migration call: those layers don't carry an
            # ``autonomous`` key today, and if they ever did the migration
            # would correctly no-op (already-nested or absent).
            loaded = _migrate_legacy_autonomous(loaded)
            data.update(loaded)

    for env_key, field in ENV_MAP.items():
        if env_key in env:
            data[field] = _coerce(field, env[env_key])

    data.update(cli_overrides)
    return Config(**data)


def _try_read_config_file(path: Path) -> dict[str, Any] | None:
    """Read and parse a config JSON file, or return ``None`` and warn.

    Returns the parsed JSON object on success. Returns ``None`` and emits
    a ``config_load_fallback`` structlog warning on either of:
      * file does not exist (``reason="missing"``)
      * file exists but read fails on permissions / I/O (``reason="io_error"``)
      * file read succeeds but JSON parse fails or top-level value is not
        an object (``reason="parse_error"``)

    Warning event contract (stable; downstream consumers may rely on this):
      * ``event="config_load_fallback"``
      * ``attempted: str`` — string form of the path that was tried.
      * ``reason: str`` — one of ``"missing"``, ``"io_error"``, ``"parse_error"``.
      * ``error: str`` — present on ``"io_error"`` and ``"parse_error"``;
        contains the underlying exception message for triage.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="missing",
        )
        return None
    except OSError as exc:
        # Permission errors / unreadable file — distinct from "missing" so
        # ``brain doctor`` can tell "file does not exist (normal first run)"
        # from "file exists but I cannot read it (genuinely wrong)".
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="io_error",
            error=str(exc),
        )
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="parse_error",
            error=str(exc),
        )
        return None

    if not isinstance(parsed, dict):
        # JSON parsed cleanly but the top-level wasn't an object — treat
        # as a parse error from the loader's perspective. ``Config(**data)``
        # would otherwise fail with a less actionable message.
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="parse_error",
            error=f"top-level JSON value is {type(parsed).__name__}, expected object",
        )
        return None

    return parsed


def _coerce(field: str, raw: str) -> Any:
    if field in {"web_port"}:
        return int(raw)
    if field in {"autonomous_mode", "log_llm_payloads"}:
        return raw.lower() in {"1", "true", "yes", "on"}
    if field == "vault_path":
        return Path(raw).expanduser()
    return raw


def _peek_config_version(path: Path) -> int | None:
    """Return the on-disk ``config_version`` integer, or ``None``.

    Used by :func:`resolve_config` to detect a stale in-memory cache
    without re-parsing the entire config file. The function is the
    cheap path: every ``resolve_config`` call goes through this, but
    only cache misses fall through to a full :func:`load_config`.

    Returns ``None`` for any of:
      * the file does not exist (first run, fresh vault)
      * the file is unreadable (permissions, transient I/O error)
      * the JSON parse fails or the top-level value is not an object
      * the ``config_version`` field is absent (legacy pre-T34 config)

    A ``None`` return is the loader's "version unknown — keep cached
    object" signal. Callers that genuinely need a re-read pass
    ``force_reload=True``; treating a transient I/O failure as a hard
    re-load would thrash the in-memory state on a flaky disk.

    Raises :class:`TypeError` if ``config_version`` IS present but is
    not an integer. Per CLAUDE.md "fail loud on unexpected state":
    silently coercing corrupted disk state to ``None`` would mask a
    real bug (someone wrote a string into the version field). The
    caller is expected to either repair the file or pass
    ``force_reload=True`` and accept whatever ``Config(**data)``
    decides about the bad payload.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    version = parsed.get("config_version")
    if version is None:
        return None
    if not isinstance(version, int) or isinstance(version, bool):
        # ``isinstance(True, int)`` is ``True`` in Python (bool subclasses
        # int). We refuse booleans here because writing ``true`` to the
        # version field is unambiguously corrupted disk state, not a
        # legitimate version of "1".
        raise TypeError(
            f"config_version in {path} is {type(version).__name__}, expected int"
        )
    return version


def resolve_config(
    *,
    config_file: Path | None,
    env: Mapping[str, str],
    cli_overrides: Mapping[str, Any],
    force_reload: bool = False,
) -> Config:
    """Return a cached :class:`Config`, re-loading when the disk version advances.

    Plan 16 Task 34 / D28 step 2 of 3: the single-process cache layer
    over :func:`load_config`. Each call:

    1. If ``force_reload`` — re-load via :func:`load_config`, refresh
       the cache entry for this ``config_file`` path, return.
    2. If no cache entry for this ``config_file`` path — same.
    3. Otherwise peek the on-disk ``config_version`` via
       :func:`_peek_config_version`. If it differs from the cached
       version (or the peek raises a real corruption error like a
       non-int field — propagated to the caller), re-load and refresh.
       If the peek returns ``None`` ("version unknown"), keep the
       cached object — a transient read failure should not blow the
       in-memory state.

    The cache key is the resolved ``Path`` of ``config_file`` (or a
    sentinel for ``None``). Env and CLI overrides are NOT in the key —
    production never changes them at runtime; callers that need a
    fresh read pass ``force_reload=True``.

    The returned ``Config`` is the same object across consecutive
    calls until the disk version advances — callers may rely on
    object identity, but must NOT mutate the returned object outside
    of :func:`brain_core.config.writer.save_config` (which does the
    in-place version bump and re-key under the cache lock implicitly
    via the next ``resolve_config`` call's version peek).
    """
    # Normalize the cache key. ``config_file=None`` is a valid call
    # (no on-disk source — defaults + env + CLI only) and gets its
    # own slot via a sentinel. ``Path.resolve()`` collapses
    # ``../foo`` and symlinks so two callers reaching the same
    # canonical file share one cache entry.
    cache_key: Path = (
        Path("__defaults_only__") if config_file is None else config_file.resolve()
    )

    cached_entry = _cached.get(cache_key)

    if force_reload or cached_entry is None:
        cfg = load_config(
            config_file=config_file,
            env=env,
            cli_overrides=cli_overrides,
        )
        _cached[cache_key] = (cfg, cfg.config_version)
        return cfg

    cached_cfg, cached_version = cached_entry

    # ``config_file=None`` has no disk to peek; the cache always hits
    # until ``force_reload``. Production never uses this path
    # (callers always supply a config file); it exists for tests and
    # ergonomic call sites.
    if config_file is None:
        return cached_cfg

    on_disk_version = _peek_config_version(config_file)
    if on_disk_version is None:
        # Version unknown (file missing / unreadable / no version
        # field). Keep the cached object — see docstring.
        return cached_cfg

    if on_disk_version == cached_version:
        return cached_cfg

    cfg = load_config(
        config_file=config_file,
        env=env,
        cli_overrides=cli_overrides,
    )
    _cached[cache_key] = (cfg, cfg.config_version)
    return cfg


def _reset_cache_for_tests() -> None:
    """Clear the single-process resolve cache.

    Mirrors :func:`brain_core.llm.providers.anthropic._reset_buckets_for_tests`
    in shape: a leading underscore signals "test-only escape hatch",
    and the function is a no-arg clear so test fixtures can call it
    from an autouse fixture without threading state through.
    """
    _cached.clear()


def invalidate_cache_for(config_file: Path | None) -> None:
    """Drop the cached :class:`Config` for ``config_file``.

    Plan 16 Task 35 / D28 step 3 of 3: the production-callable
    invalidation entry. :class:`brain_core.config.hot_reload.ConfigWatcher`
    invokes this from its filesystem-event callback so long-running
    consumers (brain_api request handlers, brain_mcp tool dispatchers)
    holding a ``Config`` reference between :func:`resolve_config`
    calls see the new disk state on their NEXT call without waiting
    for T34's lazy-peek path to fire.

    The next :func:`resolve_config` for this path will fall through
    to the cache-miss branch and re-load from disk. T34's peek
    remains the safety net — if a watchdog event is dropped (rare,
    but FSEvents has been observed to coalesce events under load),
    the next ``resolve_config`` peek catches it.

    ``None`` argument is a deliberate no-op rather than a key error:
    the watcher's ``on_change`` does not always know the
    canonicalized path that maps to the cache key, and the symmetric
    case (one watcher per config file) means there is at most one
    relevant entry to drop. Callers wanting a global flush use
    :func:`invalidate_all_caches`.

    Mirrors :func:`_reset_cache_for_tests` in shape — both converge
    on the same module-level ``_cached`` dict — but the public name
    + production semantics keep the test escape hatch and the
    production invalidation API distinct.
    """
    if config_file is None:
        return
    cache_key = config_file.resolve()
    _cached.pop(cache_key, None)


def invalidate_all_caches() -> None:
    """Drop every cached :class:`Config`.

    The no-arg sibling of :func:`invalidate_cache_for`. Used when the
    watcher's event payload doesn't carry the full path or when a
    test fixture wants a hard reset without coupling to a specific
    cache-key shape. Equivalent to :func:`_reset_cache_for_tests` but
    public — call this from production code; call the underscore
    variant from test fixtures so the intent is legible at a glance.
    """
    _cached.clear()
