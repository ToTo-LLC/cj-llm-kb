"""Chat WS plumbing for the brain_api backend.

Plan 05 Task 18 introduces typed Pydantic models for every WS event the
server emits and every message the client sends. Task 19 will add a
``SessionRunner`` in this package that bridges ``brain_core.chat`` to the
event stream.
"""
