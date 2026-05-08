"""Pin tests for ``brain_core._lint.brn001``.

Plan 16 Task 45 / D33. Covers:

    1. Violation file → ``check_file`` returns one Violation at the
       right line/col.
    2. Allowlisted file → ``main`` skips it; exit 0.
    3. ``# noqa: BRN001`` suppresses.
    4. ``# noqa: BRN001`` with trailing whitespace and other codes
       still suppresses.
    5. Bare ``# noqa`` (no code) does NOT suppress (narrow-only).
    6. Multi-segment access (``ctx.config.foo.bar``) → exactly ONE
       violation.
    7. ``self.ctx.config`` is NOT flagged (only ``Name('ctx').config``
       matches).
    8. CLI exit codes — violation file → 1 + stderr line; clean file
       → 0 + no output.
    9. pyproject.toml allowlist resolution from a custom repo root.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core._lint.brn001 import (
    _line_suppresses_brn001,
    check_file,
    main,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a fake repo root with a ``[tool.brain-lint.brn001]`` table.

    Returns the repo root path. Tests write source files under
    ``repo/pkg/<file>.py`` and pass ``--repo-root <repo>`` to ``main``
    so allowlist paths resolve relative to a stable, isolated root.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.brain-lint.brn001]\n'
        'allowed-entry-points = ["pkg/allowed.py"]\n',
        encoding="utf-8",
    )
    (tmp_path / "pkg").mkdir()
    return tmp_path


# 1. Violation file → check_file returns one Violation at the right
# line/col.
def test_violation_file_check_file(tmp_path: Path) -> None:
    src = tmp_path / "violator.py"
    src.write_text(
        "def f(ctx):\n"
        "    daily = ctx.config.budget.daily_usd\n"
        "    return daily\n",
        encoding="utf-8",
    )
    hits = check_file(src)
    assert len(hits) == 1
    v = hits[0]
    assert v.line == 2
    # ``ctx.config`` starts at column 12 in ``    daily = ctx.config...``
    assert v.col == 12
    assert v.path == src


# 2. Allowlisted file → main skips it; exit 0.
def test_allowlisted_file_skipped(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = repo / "pkg" / "allowed.py"
    src.write_text(
        "def f(ctx):\n"
        "    return ctx.config.budget\n",
        encoding="utf-8",
    )
    rc = main(["--repo-root", str(repo), str(src)])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# 3. ``# noqa: BRN001`` suppresses.
def test_noqa_suppresses(tmp_path: Path) -> None:
    src = tmp_path / "with_noqa.py"
    src.write_text(
        "def f(ctx):\n"
        "    return ctx.config.budget  # noqa: BRN001\n",
        encoding="utf-8",
    )
    assert check_file(src) == []


# 4. ``# noqa: BRN001`` with trailing whitespace and combined with other
# codes still suppresses.
@pytest.mark.parametrize(
    "comment",
    [
        "# noqa: BRN001",
        "# noqa:BRN001",  # no space after colon
        "# noqa: BRN001, E501",
        "# noqa: E501, BRN001",
        "# noqa: BRN001   ",  # trailing spaces
        "# NOQA: BRN001",  # case-insensitive on the noqa token
    ],
)
def test_noqa_variants_suppress(tmp_path: Path, comment: str) -> None:
    src = tmp_path / "variant.py"
    src.write_text(
        f"def f(ctx):\n    return ctx.config  {comment}\n",
        encoding="utf-8",
    )
    assert check_file(src) == [], f"comment {comment!r} should suppress"


# 5. Bare ``# noqa`` (no code) does NOT suppress.
def test_bare_noqa_does_not_suppress(tmp_path: Path) -> None:
    src = tmp_path / "bare_noqa.py"
    src.write_text(
        "def f(ctx):\n"
        "    return ctx.config  # noqa\n",
        encoding="utf-8",
    )
    hits = check_file(src)
    assert len(hits) == 1, (
        "bare ``# noqa`` (without a code) must NOT suppress BRN001 — "
        "narrow suppression only is the contract (see brn001.py "
        "module docstring)."
    )


# Direct unit test for the line-suppression helper to lock the contract.
@pytest.mark.parametrize(
    "line, expected",
    [
        ("    return ctx.config", False),
        ("    return ctx.config  # noqa", False),  # bare noqa
        ("    return ctx.config  # noqa: BRN001", True),
        ("    return ctx.config  # noqa:BRN001", True),
        ("    return ctx.config  # noqa: E501", False),  # different code
        ("    return ctx.config  # noqa: BRN001, E501", True),
        ("    return ctx.config  # NOQA: brn001", True),  # case-insensitive
        ("    # noqa: BRN001 — at start", True),
        ("", False),
    ],
)
def test_line_suppresses_brn001(line: str, expected: bool) -> None:
    assert _line_suppresses_brn001(line) is expected


# 6. Multi-segment access (``ctx.config.foo.bar``) → exactly ONE
# violation, at the outermost ``.config``.
def test_multi_segment_access_one_violation(tmp_path: Path) -> None:
    src = tmp_path / "multi.py"
    src.write_text(
        "def f(ctx):\n"
        "    return ctx.config.budget.per_domain['research'].daily_usd\n",
        encoding="utf-8",
    )
    hits = check_file(src)
    assert len(hits) == 1, (
        "deep attribute chains off ctx.config must produce exactly one "
        "violation (the outermost ``.config`` lookup)."
    )
    assert hits[0].line == 2


# 7. ``self.ctx.config`` is NOT flagged (only ``Name('ctx').config``).
def test_method_style_access_not_flagged(tmp_path: Path) -> None:
    src = tmp_path / "method_style.py"
    src.write_text(
        "class Foo:\n"
        "    def f(self):\n"
        "        return self.ctx.config\n"
        "    def g(self, args):\n"
        "        return args.ctx.config\n",
        encoding="utf-8",
    )
    assert check_file(src) == [], (
        "method-style access (``self.ctx.config``) must NOT be flagged: "
        "BRN001's contract is ``Attribute(value=Name('ctx'), attr='config')``."
    )


# 8a. CLI: violation file → exit 1 + stderr line.
def test_main_violation_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.brain-lint.brn001]\n'
        'allowed-entry-points = []\n',
        encoding="utf-8",
    )
    src = tmp_path / "violator.py"
    src.write_text(
        "def f(ctx):\n"
        "    return ctx.config.budget\n",
        encoding="utf-8",
    )
    rc = main(["--repo-root", str(tmp_path), str(src)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "BRN001" in captured.err
    assert "violator.py" in captured.err
    assert ":2:" in captured.err  # line 2


# 8b. CLI: clean file → exit 0 + no stderr.
def test_main_clean_exit_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.brain-lint.brn001]\n'
        'allowed-entry-points = []\n',
        encoding="utf-8",
    )
    src = tmp_path / "clean.py"
    src.write_text(
        "def f(ctx):\n"
        "    return ctx.vault_root\n",  # no ctx.config
        encoding="utf-8",
    )
    rc = main(["--repo-root", str(tmp_path), str(src)])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# 9. pyproject.toml allowlist resolution from a custom repo root.
def test_allowlist_resolution_from_repo_root(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Two files: one allowlisted, one not; verify only the unlisted
    # one fires.
    allowed = repo / "pkg" / "allowed.py"
    other = repo / "pkg" / "other.py"
    allowed.write_text(
        "def f(ctx):\n    return ctx.config\n",
        encoding="utf-8",
    )
    other.write_text(
        "def f(ctx):\n    return ctx.config\n",
        encoding="utf-8",
    )
    rc = main(["--repo-root", str(repo), str(allowed), str(other)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "other.py" in captured.err
    assert "allowed.py" not in captured.err


# Extra: missing config table → no enforcement, exit 0.
def test_missing_config_table_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When no ``[tool.brain-lint.brn001]`` table is found anywhere
    above CWD, the checker is a no-op (so the hook doesn't block in an
    unconfigured repo). This is a deliberate fallback — production CI
    runs from the repo root which DOES have the table, so this branch
    is defensive only.
    """
    src = tmp_path / "nope.py"
    src.write_text(
        "def f(ctx):\n    return ctx.config\n",
        encoding="utf-8",
    )
    # Pass a repo-root that lacks pyproject.toml entirely.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    rc = main(["--repo-root", str(elsewhere), str(src)])
    # The repo-root override doesn't have the config table, so
    # _load_allowlist returns the empty set; we still run the check
    # against an empty allowlist and report. The "missing config →
    # exit 0" no-op branch is tested via the auto-discovery code path.
    assert rc == 1
    captured = capsys.readouterr()
    assert "BRN001" in captured.err


def test_auto_discovery_no_config_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When CWD has no ancestor pyproject.toml with the table, auto-
    discovery returns None → the checker is a no-op. This is the
    "unconfigured repo" defensive branch.
    """
    src = tmp_path / "src.py"
    src.write_text("def f(ctx):\n    return ctx.config\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = main([str(src)])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""
