"""brain_repair_config — diagnostic re-run of the config-load fallback chain.

Plan 16 Task 33 / D28 step 1 of 3. The Settings → General "Repair config"
button opens :class:`apps/brain_web/src/components/dialogs/repair-config-dialog.tsx`
which calls this tool to:

  1. Re-read ``<vault>/.brain/config.json`` from disk (bypassing the
     :func:`brain_core.config.loader.resolve_config` cache).
  2. Validate via :class:`brain_core.config.schema.Config`.
  3. Fall back to ``config.json.bak`` if the primary fails (read or validate).
  4. Fall back to :class:`Config` defaults if both prior layers fail.
  5. Diff the recovered config against the live ``ctx.config`` and report
     whether a re-apply (write to disk) is needed.

Mirrors :func:`brain_core.config.loader.load_config`'s file-read fallback
(see ``loader.py`` for the canonical chain) — but where ``load_config`` is
silent about which layer succeeded, this tool surfaces a per-step result
list so the UI can render a ``brain doctor``-shaped panel.

This tool is **read-only**. The Re-apply button calls the sibling
:mod:`brain_core.tools.repair_config_apply` tool (Option 1: two tools, two
responsibilities — mirrors the ``backup_create`` / ``backup_restore`` split).

Step rows are shaped::

    {"step": "read_primary", "status": "success" | "warning" | "error", "message": "..."}

Status semantics:

  * ``success`` — step ran cleanly.
  * ``warning`` — step ran but produced a fallback (e.g. primary missing on
    a fresh vault — normal, not an error).
  * ``error`` — step attempted and failed (e.g. parse error, schema reject).

Steps that did NOT run (because earlier steps already succeeded) are NOT in
the rows list — keeps the UI compact and matches the "actually attempted"
mental model of ``brain doctor``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from brain_core.config.schema import Config
from brain_core.tools._errors import raise_if_no_config
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_repair_config"
DESCRIPTION = (
    "Re-run the config-load fallback chain (config.json -> .bak -> defaults) "
    "and return per-step results. Read-only diagnostic; pair with "
    "brain_repair_config_apply to write the repaired config to disk."
)
INPUT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


def _try_read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read + parse a JSON object file. Returns ``(payload, error_message)``.

    Mirrors :func:`brain_core.config.loader._try_read_config_file`'s
    exception handling shape but returns the error message back to the
    caller so the per-step result row can render it. The original loader
    helper logs through structlog instead of returning — we re-implement
    locally rather than calling it because the contract here is "surface
    the error to the UI", not "log it to brain doctor".

    Tuple discriminator:
      * ``(payload, None)`` — read + parsed cleanly to a dict.
      * ``(None, "missing")`` — file does not exist (sentinel string).
      * ``(None, "io_error: ...")`` / ``(None, "parse_error: ...")`` —
        read or parse failed; the error message is the second element.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        return None, f"io_error: {exc}"

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"parse_error: {exc}"

    if not isinstance(parsed, dict):
        return None, (
            f"parse_error: top-level JSON value is {type(parsed).__name__}, "
            "expected object"
        )

    return parsed, None


def _try_validate_config(payload: dict[str, Any]) -> tuple[Config | None, str | None]:
    """Run ``Config(**payload)`` and report success / structured failure.

    Returns ``(config, None)`` on success or ``(None, message)`` on
    Pydantic validation failure. ``Config()`` with no kwargs is the
    schema-defaults fallback elsewhere in this module — that path
    cannot fail and so does not go through this helper.
    """
    try:
        return Config(**payload), None
    except (ValueError, TypeError) as exc:
        # Pydantic v2 ValidationError subclasses ValueError; ``Config(**bad)``
        # also raises TypeError when the payload's keys collide with
        # @model_validator hooks. Both are treated identically here —
        # surface the message as the per-step ``error`` row.
        return None, f"schema_error: {exc}"


def _configs_equal(a: Config, b: Config) -> bool:
    """Deep-compare two Configs via ``model_dump()``.

    Object-identity comparison would always be False here (the loader
    constructs a fresh instance every time), so we go through
    ``model_dump`` for a structural check. Plan 16 D28 step 1 of 3
    spec calls for ``persisted_dict()`` deep-equal — using the persisted
    shape ensures we don't false-positive on ``vault_path`` or any other
    chicken-and-egg field that's deliberately not round-tripped.
    """
    return a.persisted_dict() == b.persisted_dict()


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    """Re-run the fallback chain and report per-step results.

    The ``arguments`` dict is unused (the tool always re-reads the live
    vault root); kept in the signature for ToolContext shape parity.

    Raises :class:`RuntimeError` when ``ctx.config`` is None — the brain_api
    lifespan is responsible for threading the loaded Config through the
    ``ToolContext``. A None config here means a lifecycle violation, not a
    fallback case (matches ``brain_config_get``'s contract).
    """
    raise_if_no_config(ctx, NAME)

    primary_path = ctx.vault_root / ".brain" / "config.json"
    backup_path = ctx.vault_root / ".brain" / "config.json.bak"

    steps: list[dict[str, str]] = []
    repaired: Config | None = None

    # Step 1: read primary.
    primary_payload, primary_read_err = _try_read_json_object(primary_path)
    if primary_payload is not None:
        steps.append(
            {"step": "read_primary", "status": "success", "message": "Read OK"}
        )
        # Step 2: validate primary.
        primary_cfg, primary_validate_err = _try_validate_config(primary_payload)
        if primary_cfg is not None:
            steps.append(
                {
                    "step": "validate_primary",
                    "status": "success",
                    "message": "Schema valid",
                }
            )
            repaired = primary_cfg
        else:
            # Validation failed — record error, fall through to backup.
            steps.append(
                {
                    "step": "validate_primary",
                    "status": "error",
                    "message": primary_validate_err or "Schema validation failed",
                }
            )
    elif primary_read_err == "missing":
        # Missing primary on first run is not an error — surface as a warning.
        steps.append(
            {
                "step": "read_primary",
                "status": "warning",
                "message": "config.json not found; falling back to backup or defaults",
            }
        )
    else:
        # I/O or parse error — actual failure.
        steps.append(
            {
                "step": "read_primary",
                "status": "error",
                "message": primary_read_err or "Read failed",
            }
        )

    # Step 3 / 4: backup, only if primary did not produce a Config.
    if repaired is None:
        backup_payload, backup_read_err = _try_read_json_object(backup_path)
        if backup_payload is not None:
            steps.append(
                {
                    "step": "read_backup",
                    "status": "success",
                    "message": "Read OK from .bak",
                }
            )
            backup_cfg, backup_validate_err = _try_validate_config(backup_payload)
            if backup_cfg is not None:
                steps.append(
                    {
                        "step": "validate_backup",
                        "status": "success",
                        "message": "Restored from backup",
                    }
                )
                repaired = backup_cfg
            else:
                steps.append(
                    {
                        "step": "validate_backup",
                        "status": "error",
                        "message": backup_validate_err or "Schema validation failed",
                    }
                )
        elif backup_read_err == "missing":
            # No backup file is an expected condition (no prior write yet);
            # logged as error here because we genuinely needed it and it's
            # absent — the next step is the defaults fallback.
            steps.append(
                {
                    "step": "read_backup",
                    "status": "error",
                    "message": ".bak not found",
                }
            )
        else:
            steps.append(
                {
                    "step": "read_backup",
                    "status": "error",
                    "message": backup_read_err or "Read failed",
                }
            )

    # Step 5: defaults fallback. ``Config()`` cannot fail.
    if repaired is None:
        repaired = Config()
        steps.append(
            {
                "step": "apply_defaults",
                "status": "success",
                "message": "Using built-in defaults",
            }
        )

    repair_changes_pending = not _configs_equal(repaired, ctx.config)

    # Build a one-line text summary for chat / LLM surfaces.
    final_step = steps[-1]["step"]
    summary = (
        f"repair: {len(steps)} step(s); recovered from {final_step}; "
        f"changes_pending={repair_changes_pending}"
    )

    return ToolResult(
        text=summary,
        data={
            "steps": steps,
            "repair_changes_pending": repair_changes_pending,
            "repaired_config": repaired.persisted_dict(),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
