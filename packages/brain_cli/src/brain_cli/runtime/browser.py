"""Cross-platform browser launcher.

stdlib ``webbrowser.open`` handles the common case on Mac + Linux + Windows.
On restricted Windows setups (e.g. Server Core) ``webbrowser`` can fail to
find a handler; we fall back to ``os.startfile`` which delegates to the
Shell's default-association resolver.
"""

from __future__ import annotations

import sys
import webbrowser


def open_browser(url: str) -> bool:
    """Open ``url`` in the user's default browser.

    Returns True on success, False if every strategy fails. Does NOT raise
    — ``brain start`` still considers itself successful if only the
    browser launch misfired (the URL is printed to stdout as a fallback).
    """
    try:
        if webbrowser.open(url):
            return True
    except webbrowser.Error:
        pass

    # Windows fallback: ``os.startfile`` uses the Shell verb "open" which
    # is more robust than webbrowser's spawn heuristic. Only available on
    # Windows — guard with ``sys.platform``.
    if sys.platform == "win32":
        try:
            import os

            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False

    return False
