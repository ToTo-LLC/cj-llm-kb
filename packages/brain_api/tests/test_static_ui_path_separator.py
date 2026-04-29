"""Path-separator regression pins for ``SPAStaticFiles._spa_fallback`` — Plan 15 Task 3.

Background — the bug these tests pin
====================================

Starlette's :class:`starlette.staticfiles.StaticFiles` runs incoming URL
paths through ``os.path.normpath`` inside ``get_path()`` before handing
them to ``get_response()``. On Windows ``os.path`` is ``ntpath``, whose
``normpath`` rewrites forward slashes to backslashes — so the URL
``/chat/abc-123`` arrives at ``_spa_fallback`` as ``"chat\\abc-123"``.

Before the Task 3 fix, ``_spa_fallback`` did
``path.split("/", 1)[0]`` on that backslash-shape value, returning the
whole string ``"chat\\abc-123"`` as the "first segment". That string is
not in ``_DYNAMIC_PLACEHOLDERS``, so the function fell through to root
``index.html`` instead of ``chat/_/index.html``. ChatScreen never
mounted, the composer textbox never rendered, and 2 Playwright tests on
windows-2022 went red.

The fix: a single ``path = path.replace("\\", "/")`` at the top of
``_spa_fallback`` un-does the OS-shape transform that Starlette imposed
on a URL-shaped value.

What this file pins
===================

Three direct unit tests against ``SPAStaticFiles._spa_fallback``. They
build a real ``SPAStaticFiles`` instance against a real fixture vault
directory (no mocks; per lessons.md #343 production-shape rule) and feed
literal path-shapes that simulate what each platform's
``ntpath.normpath`` / ``posixpath.normpath`` would produce. The Mac box
that runs these tests can't reproduce the Windows-shape input naturally
(``posixpath.normpath`` doesn't convert slashes), so we construct the
backslash-shape input directly.

* ``test_windows_shape_path_resolves_dynamic_placeholder`` — load-bearing
  pin; passes ``"chat\\abc-123"`` and asserts the chat-placeholder is
  served. Before the fix this would serve root ``index.html``.
* ``test_unix_shape_path_resolves_dynamic_placeholder`` — Mac/Linux
  regression guard; passes ``"chat/abc-123"`` and asserts the same
  chat-placeholder result.
* ``test_root_index_when_no_dynamic_match`` — pre-existing happy-path;
  passes ``"unknown-route"`` (no slash, no match) and asserts fallback
  to root ``index.html``. Ensures the fix doesn't regress the generic
  fallback.
"""

from __future__ import annotations

import ntpath
from pathlib import Path

import pytest
from brain_api.static_ui import SPAStaticFiles
from starlette.responses import FileResponse, Response

_INDEX_HTML = (
    "<!doctype html>\n"
    "<html><head><title>brain</title></head>"
    '<body><div id="__next">BRAIN_ROOT</div></body></html>\n'
)
_CHAT_PLACEHOLDER_HTML = (
    "<!doctype html>\n"
    "<html><head><title>brain - chat</title></head>"
    '<body><div id="__next">BRAIN_CHAT_PLACEHOLDER</div></body></html>\n'
)


@pytest.fixture
def static_files(tmp_path: Path) -> SPAStaticFiles:
    """Build a real ``SPAStaticFiles`` against a real on-disk ``out/`` dir.

    Mirrors the production-shape contract from ``test_static_ui.py``: a
    miniature ``out/`` with a root ``index.html`` and a
    ``chat/_/index.html`` dynamic-segment placeholder, distinguishable by
    body content so an assertion can tell which file got served.
    """
    root = tmp_path / "out"
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(_INDEX_HTML, encoding="utf-8", newline="\n")

    chat_placeholder_dir = root / "chat" / "_"
    chat_placeholder_dir.mkdir(parents=True, exist_ok=True)
    (chat_placeholder_dir / "index.html").write_text(
        _CHAT_PLACEHOLDER_HTML, encoding="utf-8", newline="\n"
    )

    return SPAStaticFiles(directory=str(root), html=True)


def _read_response_body(response: Response | None) -> str:
    """Read the on-disk file the FileResponse points at.

    Accepts the ``Response | None`` shape that ``_spa_fallback`` returns
    so callers don't have to narrow the type at every call site; the
    runtime ``isinstance`` check below catches any unexpected shape.
    """
    assert response is not None
    assert isinstance(response, FileResponse)
    return Path(response.path).read_text(encoding="utf-8")


def test_windows_shape_path_resolves_dynamic_placeholder(
    static_files: SPAStaticFiles,
) -> None:
    """Backslash-shape input (Starlette+Windows shape) hits the chat placeholder.

    Constructed via :func:`ntpath.normpath` to match exactly what
    Starlette's ``StaticFiles.get_path`` produces on Windows. Before the
    Task 3 fix, this would have served root ``index.html`` — the
    ``BRAIN_ROOT`` body. After the fix it must serve the chat placeholder.
    """
    # ntpath.normpath("chat/abc-123") -> "chat\\abc-123" on every platform,
    # which is exactly the shape Starlette hands us on Windows.
    windows_shape = ntpath.normpath("chat/abc-123")
    assert windows_shape == "chat\\abc-123", (
        f"ntpath.normpath sanity check failed: got {windows_shape!r}"
    )

    response = static_files._spa_fallback(windows_shape, raise_on_miss=True)
    assert response is not None
    body = _read_response_body(response)
    assert "BRAIN_CHAT_PLACEHOLDER" in body, (
        f"Windows-shape path '{windows_shape}' did not resolve to the chat "
        f"placeholder. Body was: {body[:200]!r}"
    )
    assert "BRAIN_ROOT" not in body


def test_unix_shape_path_resolves_dynamic_placeholder(
    static_files: SPAStaticFiles,
) -> None:
    """Forward-slash-shape input (Mac/Linux shape) hits the chat placeholder.

    Pre-existing behavior, retained as a regression guard so the
    Task 3 fix can't accidentally break the Mac/Linux path.
    """
    response = static_files._spa_fallback("chat/abc-123", raise_on_miss=True)
    assert response is not None
    body = _read_response_body(response)
    assert "BRAIN_CHAT_PLACEHOLDER" in body
    assert "BRAIN_ROOT" not in body


def test_root_index_when_no_dynamic_match(static_files: SPAStaticFiles) -> None:
    """Unknown single-segment route falls back to root ``index.html``.

    Pins the generic SPA fallback: paths that don't match a reserved
    prefix, a dynamic placeholder, or ``settings`` should still serve
    the root ``index.html`` so the React Router can resolve them
    client-side.
    """
    response = static_files._spa_fallback("unknown-route", raise_on_miss=True)
    assert response is not None
    body = _read_response_body(response)
    assert "BRAIN_ROOT" in body
    assert "BRAIN_CHAT_PLACEHOLDER" not in body
