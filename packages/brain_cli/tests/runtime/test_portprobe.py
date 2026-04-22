"""Unit tests for the ``brain start`` port probe helper.

Probing must be POSIX + Windows safe. We test by binding real sockets on
loopback to a known-free port rather than mocking — the Python socket API
is the actual unit under test.
"""

from __future__ import annotations

import socket
from contextlib import closing

import pytest
from brain_cli.runtime import portprobe


def _bind(port: int) -> socket.socket:
    """Bind a TCP socket on loopback to hold a port open for the test duration.

    Caller must close(). Uses SO_REUSEADDR off so ``is_port_free`` sees the
    port as bound (reuseaddr would let both the probe's connect-style check
    AND the real process claim the same port simultaneously on Linux).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s


def test_is_port_free_true_for_unbound_port() -> None:
    """Grab a port the OS picks, release it, then ask the probe — it must
    be free for at least a brief window before another process can grab it."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # s is closed — the port should be free now.
    assert portprobe.is_port_free(port) is True


def test_is_port_free_false_when_bound() -> None:
    """Holding a socket on a port must make the probe report the port busy."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        assert portprobe.is_port_free(port) is False


def test_find_free_port_returns_in_range() -> None:
    """With a wide-open range the probe must return the first free port."""
    # Pick a high private-range window unlikely to collide with real services.
    start, end = 54_000, 54_010
    port = portprobe.find_free_port(start=start, end=end)
    assert start <= port <= end


def test_find_free_port_skips_busy_ports() -> None:
    """When the first port is bound, the probe must move to the next free one."""
    start, end = 54_100, 54_105
    held = _bind(start)
    try:
        port = portprobe.find_free_port(start=start, end=end)
        # Must not return the held port; must be in range.
        assert port != start
        assert start < port <= end
    finally:
        held.close()


def test_find_free_port_raises_when_range_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """If every port in the range is busy, the probe must raise a clear error."""
    # Monkeypatch the internal check so we don't have to actually bind 14 sockets.
    monkeypatch.setattr(portprobe, "is_port_free", lambda _port: False)
    with pytest.raises(portprobe.NoFreePortError) as exc_info:
        portprobe.find_free_port(start=4317, end=4330)
    # Error message must name the range so users know what to free up.
    assert "4317" in str(exc_info.value)
    assert "4330" in str(exc_info.value)
