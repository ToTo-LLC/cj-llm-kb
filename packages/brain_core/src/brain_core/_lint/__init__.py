"""brain_core local lint rules.

Standalone AST checkers wired into the pre-commit pipeline (NOT ruff
plugins — Astral does not expose a Python plugin API for ruff's custom
rules; the official extension path is to contribute the rule in Rust to
ruff's main repo). Rules in this package match the actionlint hook
shape landed in Plan 16 Task 16: a `local` pre-commit hook that calls
``python -m brain_core._lint.<rule>`` with the staged Python files.

Rules:
    * ``brn001`` — flag ``ctx.config`` reads outside the allowed
      entry-points list (Plan 16 Task 45 / D33).
"""

from __future__ import annotations
