"""Unit tests for :func:`brain_api.static_ui._find_repo_root` — Plan 21 T1.

These pin the walk-up helper's semantics:

* finds a marker at the starting directory;
* honors first-hit-wins when the marker exists at multiple ancestor levels;
* returns ``None`` when the marker is absent from every ancestor up to ``/``;
* accepts both a directory and a file as the starting path (a file means
  "start from this file's parent directory").

We use a unique sentinel name (``BRAIN_TEST_SENTINEL`` / ``UNLIKELY_NAME_BRAIN_TEST_SENTINEL``)
instead of ``.git`` so the test runner's own repository — which has a ``.git``
directory somewhere up the ancestor chain from ``tmp_path`` — cannot
contaminate the assertions.
"""

from __future__ import annotations

from pathlib import Path

from brain_api.static_ui import _find_repo_root

_MARKER = "BRAIN_TEST_SENTINEL"
_ABSENT_MARKER = "UNLIKELY_NAME_BRAIN_TEST_SENTINEL"


def test_find_repo_root_finds_marker_at_start(tmp_path: Path) -> None:
    """Marker at ``tmp_path``; walk-up from a nested file returns ``tmp_path``."""
    (tmp_path / _MARKER).mkdir()
    nested_dir = tmp_path / "subdir"
    nested_dir.mkdir()
    file_path = nested_dir / "file.py"
    file_path.write_text("# placeholder\n", encoding="utf-8")

    result = _find_repo_root(file_path, marker=_MARKER)

    assert result == tmp_path


def test_find_repo_root_finds_marker_at_intermediate_level(tmp_path: Path) -> None:
    """Marker at BOTH ``tmp_path`` and ``tmp_path/subdir`` — first hit wins."""
    (tmp_path / _MARKER).mkdir()
    nested_dir = tmp_path / "subdir"
    nested_dir.mkdir()
    (nested_dir / _MARKER).mkdir()
    deeper_dir = nested_dir / "deeper"
    deeper_dir.mkdir()
    file_path = deeper_dir / "file.py"
    file_path.write_text("# placeholder\n", encoding="utf-8")

    result = _find_repo_root(file_path, marker=_MARKER)

    # Walk-up starts at deeper_dir, then goes to nested_dir — first hit wins.
    assert result == nested_dir


def test_find_repo_root_returns_none_when_marker_absent(tmp_path: Path) -> None:
    """No marker anywhere — walk-up reaches ``/`` and returns ``None``.

    We use an extremely unlikely marker name to keep this deterministic on
    any host filesystem (a stray ``UNLIKELY_NAME_BRAIN_TEST_SENTINEL`` at
    ``/`` would be a real surprise).
    """
    file_path = tmp_path / "file.py"
    file_path.write_text("# placeholder\n", encoding="utf-8")

    result = _find_repo_root(file_path, marker=_ABSENT_MARKER)

    assert result is None


def test_find_repo_root_accepts_starting_path_as_directory(tmp_path: Path) -> None:
    """Passing a directory directly — walk-up starts at the directory itself."""
    (tmp_path / _MARKER).mkdir()

    result = _find_repo_root(tmp_path, marker=_MARKER)

    assert result == tmp_path


def test_find_repo_root_accepts_starting_path_as_file(tmp_path: Path) -> None:
    """Passing a file — walk-up starts at the file's parent directory.

    The file does not need to exist for the parent-derivation to work
    (``Path.parent`` is purely lexical when the path is not a directory).
    """
    fake_file = tmp_path / "fake.py"  # deliberately not created
    (tmp_path / _MARKER).mkdir()

    result = _find_repo_root(fake_file, marker=_MARKER)

    assert result == tmp_path
