"""Runtime helpers for the ``brain start / stop / status`` supervisor.

This subpackage owns process-group management (PID files, psutil-backed
liveness + terminate/kill), port probing, the uvicorn spawn shim, and the
browser launcher. Every helper is cross-platform by construction — no
POSIX-only signal constants, no ``shell=True``, no hardcoded slashes.
"""
