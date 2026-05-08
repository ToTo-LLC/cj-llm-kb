"""BRN001 — flag ``ctx.config`` reads outside the allowed entry-points list.

Plan 16 Task 45 / D33. Ruff does not support pure-Python custom rules
(Astral's plugin path is Rust-only, verified 2026-05), so this rule
lands as a standalone AST checker wired into pre-commit, matching the
actionlint hook shape (Plan 16 Task 16).

Semantic goal
-------------
Enforce that the live :class:`brain_core.config.schema.Config` is read
centrally (at the tool entry-point boundary) and threaded through the
system, not picked up ad-hoc inside random helpers. The check fires on
any ``Attribute(value=Name("ctx"), attr="config")`` AST node — i.e.
syntactic ``ctx.config`` lookups where ``ctx`` is a bare Name — unless
the containing file is on the allowlist or the line carries the
``# noqa: BRN001`` suppression.

Usage (CLI)
-----------
::

    python -m brain_core._lint.brn001 <files...>

Returns exit ``0`` on clean, exit ``1`` on violation. Each violation
prints ``<file>:<line>:<col>: BRN001 ctx.config read outside allowed
entry points`` on stderr and the offending line text indented for
context.

Configuration
-------------
The allowlist lives in the repo root ``pyproject.toml`` under
``[tool.brain-lint.brn001]``::

    [tool.brain-lint.brn001]
    allowed-entry-points = [
        "packages/brain_core/src/brain_core/tools/config_get.py",
        ...
    ]

Paths in the allowlist are repo-relative POSIX strings. The checker
compares against the file's path resolved relative to the repo root
(the directory containing the ``pyproject.toml`` that holds the
allowlist).

Suppression
-----------
A trailing ``# noqa: BRN001`` (or ``# noqa:BRN001`` — no space) on the
violating line suppresses the report. A bare ``# noqa`` (without the
code) does NOT suppress — narrow suppression only, by design, so that
new rules added later cannot be silently muted by stale broad pragmas.

Scope decisions
---------------
* **Only ``Name("ctx").config``** is flagged. Method-style access
  (``self.ctx.config``, ``args.ctx.config``) is not flagged because
  the ``Attribute.value`` is itself an ``Attribute`` (or other) node,
  not a bare ``Name``. This matches the codebase: tool-context reads
  are written ``ctx.config`` by convention; deeper nesting is rare and
  if it does occur, route the case back through the engineer.
* **Multi-segment access** (``ctx.config.budget.daily_usd``) produces
  exactly ONE violation, at the outermost ``.config`` node. The
  children (``.budget``, ``.daily_usd``) are accessed against the
  ``Config`` instance returned by ``ctx.config``, not against ``ctx``,
  so the AST does not match them and no double-counting occurs.
* **Read or write** — ``ctx.config = X`` is also reported (still
  ``Attribute(value=Name("ctx"), attr="config")``). That is the right
  default: assigning to ``ctx.config`` outside the lifecycle wiring
  point is just as suspect as reading.
"""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    """A single BRN001 violation in a single file."""

    path: Path
    line: int
    col: int
    source_line: str

    def format(self) -> str:
        """Render the violation as a ``<file>:<line>:<col>: BRN001 …`` string."""
        # Print path as POSIX-style for cross-platform consistency. The
        # CLI's stderr is a developer-facing hint, not a parsed format.
        rel = self.path.as_posix()
        return (
            f"{rel}:{self.line}:{self.col}: BRN001 ctx.config read outside "
            f"allowed entry points\n    {self.source_line.strip()}"
        )


class _CtxConfigVisitor(ast.NodeVisitor):
    """Visit AST nodes; record ``Attribute(value=Name('ctx'), attr='config')`` reads.

    Suppression is line-based and uses the original source text (not
    ``ast.get_source_segment``) because the AST does not preserve
    trailing comments — they belong to whitespace/tokenizer concerns
    that ``ast`` discards. Reading ``self._lines[lineno-1]`` is the
    canonical way to get "the source line" for line-anchored pragmas.
    """

    def __init__(self, source_text: str) -> None:
        self._lines = source_text.splitlines()
        self.hits: list[tuple[int, int, str]] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "ctx"
            and node.attr == "config"
        ):
            line_text = (
                self._lines[node.lineno - 1]
                if 0 <= node.lineno - 1 < len(self._lines)
                else ""
            )
            if not _line_suppresses_brn001(line_text):
                self.hits.append((node.lineno, node.col_offset, line_text))
        self.generic_visit(node)


def _line_suppresses_brn001(line: str) -> bool:
    """Return True iff the source line carries a ``# noqa: BRN001`` pragma.

    Honors both ``# noqa: BRN001`` and ``# noqa:BRN001`` (no-space
    variant). Bare ``# noqa`` (no code) is deliberately NOT honored so
    future rules cannot be muted by stale broad pragmas.
    """
    stripped = line.rstrip()
    # Look for ``# noqa: BRN001`` or ``# noqa:BRN001``. The pragma can
    # carry a comma-separated list (``# noqa: BRN001, E501``); honor
    # the case where BRN001 appears anywhere in that list.
    lowered = stripped.lower()
    idx = lowered.find("# noqa")
    if idx == -1:
        return False
    after = stripped[idx + len("# noqa") :]
    # Require a colon after ``# noqa`` for narrow suppression.
    after = after.lstrip()
    if not after.startswith(":"):
        return False
    after = after[1:].lstrip()
    # Split on whitespace and commas; check membership.
    codes = {tok.strip().upper() for tok in after.replace(",", " ").split()}
    return "BRN001" in codes


def check_file(path: Path) -> list[Violation]:
    """Parse ``path`` and return the list of BRN001 violations.

    Files that fail to parse return an empty list — the rule is a
    semantic check, not a syntax checker, and SyntaxErrors are
    surfaced by other tools (ruff, the interpreter itself).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    visitor = _CtxConfigVisitor(text)
    visitor.visit(tree)
    return [
        Violation(path=path, line=ln, col=co, source_line=src)
        for ln, co, src in visitor.hits
    ]


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from ``start`` looking for a ``pyproject.toml`` containing
    a ``[tool.brain-lint.brn001]`` table. Returns the directory holding
    that file, or ``None`` if not found.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        pp = candidate / "pyproject.toml"
        if not pp.is_file():
            continue
        try:
            data = tomllib.loads(pp.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        tool = data.get("tool", {})
        if isinstance(tool, dict) and isinstance(tool.get("brain-lint"), dict):
            brain_lint = tool["brain-lint"]
            if isinstance(brain_lint.get("brn001"), dict):
                return candidate
    return None


def _load_allowlist(repo_root: Path) -> set[str]:
    """Read ``[tool.brain-lint.brn001].allowed-entry-points`` from
    ``<repo_root>/pyproject.toml``. Paths are stored as POSIX strings.
    Missing config returns the empty set.
    """
    pp = repo_root / "pyproject.toml"
    try:
        data = tomllib.loads(pp.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return set()
    brain_lint = tool.get("brain-lint")
    if not isinstance(brain_lint, dict):
        return set()
    rule = brain_lint.get("brn001")
    if not isinstance(rule, dict):
        return set()
    entries = rule.get("allowed-entry-points", [])
    if not isinstance(entries, list):
        return set()
    return {str(e) for e in entries if isinstance(e, str)}


def _is_allowlisted(path: Path, repo_root: Path, allowlist: set[str]) -> bool:
    """True iff ``path`` (resolved) is repo-relative-equal to an
    allowlist entry. Paths in ``allowlist`` are POSIX strings; we
    compare against ``path.resolve().relative_to(repo_root).as_posix()``.
    """
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        # path is not under repo_root — treat as not allowlisted; the
        # caller will still report it. (Most pre-commit invocations
        # pass paths under the repo root, so this branch is
        # defensive.)
        return False
    return rel.as_posix() in allowlist


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point.

    Arguments are file paths (one or more). The checker:
        1. Locates the repo root (nearest ``pyproject.toml`` with a
           ``[tool.brain-lint.brn001]`` table) starting from CWD.
        2. Loads the allowlist.
        3. Skips allowlisted files; runs :func:`check_file` on the
           rest.
        4. Prints each violation to stderr; returns ``0`` on clean,
           ``1`` if any violation was reported.
    """
    parser = argparse.ArgumentParser(
        prog="brn001",
        description="Flag ctx.config reads outside the allowed entry-points list.",
    )
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override the repo root used for allowlist resolution.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root: Path | None = (
        args.repo_root
        if args.repo_root is not None
        else _find_repo_root(Path.cwd())
    )
    if repo_root is None:
        # No allowlist config found — nothing to enforce. Return clean
        # so the hook does not block in an unconfigured repo.
        return 0

    allowlist = _load_allowlist(repo_root)
    any_violation = False
    for raw in args.files:
        path = Path(raw)
        if not path.is_file():
            continue
        if _is_allowlisted(path, repo_root, allowlist):
            continue
        for v in check_file(path):
            print(v.format(), file=sys.stderr)
            any_violation = True
    return 1 if any_violation else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
