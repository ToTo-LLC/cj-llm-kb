"""Port probing for the brain supervisor.

Plan 08 P4a: probe ports 4317..4330 at ``brain start``, write the chosen
port to ``.brain/run/brain.port``, auto-open the browser at that URL.
The probe is a simple bind-to-localhost test — if the bind succeeds we
release the socket and declare the port free.

Note: there's an inherent TOCTOU window between "we saw this port free"
and "uvicorn binds it". In practice the window is microseconds and
uvicorn will fail cleanly with "address in use" if anything slipped in.
We don't try to close the gap with SO_REUSEADDR shenanigans because that
would hide real conflicts from uvicorn.
"""

from __future__ import annotations

import socket


class NoFreePortError(RuntimeError):
    """Raised when every port in the probed range is busy.

    The supervisor surfaces this to the user as a clear "check for rogue
    servers holding 4317-4330" message rather than a traceback.
    """


def is_port_free(port: int) -> bool:
    """Return True iff ``port`` can be bound on 127.0.0.1 right now.

    Cross-platform: ``bind`` + ``OSError`` on busy port works identically
    on Mac, Linux, and Windows. We deliberately do NOT set SO_REUSEADDR
    — that would let us "see" a port that another socket is already
    holding with the same flag, which isn't the "free" we mean here.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return False
    else:
        return True
    finally:
        sock.close()


def find_free_port(start: int = 4317, end: int = 4330) -> int:
    """Return the first free port in ``[start, end]`` (inclusive).

    Raises :class:`NoFreePortError` if every port in the range is busy.
    """
    for port in range(start, end + 1):
        if is_port_free(port):
            return port
    raise NoFreePortError(
        f"no free port in range {start}-{end}; check for another brain "
        "instance or stray servers holding these ports."
    )
