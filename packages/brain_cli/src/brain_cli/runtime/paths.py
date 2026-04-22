"""Shared path resolution for brain CLI commands.

``default_install_dir`` + ``default_vault_root`` already live in
``brain_cli.runtime.checks``. We re-export them here so new commands
(upgrade, uninstall, backup, etc.) don't have to reach into the checks
module — that module is *doctor* infrastructure, not a public helper
grab-bag. Any future command can import from ``brain_cli.runtime.paths``.

No behavior change vs. the checks-owned originals — this file exists
purely for import hygiene.
"""

from __future__ import annotations

from brain_cli.runtime.checks import default_install_dir, default_vault_root

__all__ = ["default_install_dir", "default_vault_root"]
