"""Static UI mount + out-dir resolver — Plan 08 Task 1.

brain_api serves the Next.js static export (``apps/brain_web/out/``) under
``/`` with SPA-style fallback so client-side routes (``/chat``, ``/chat/<id>``,
``/browse/foo/bar``) all resolve to ``index.html`` and let the React Router
take over post-hydration.

Mount ordering contract (see :func:`brain_api.app.create_app`): every API +
WebSocket router is included BEFORE the static mount. Starlette's routing
table walks routes in insertion order and returns the first match, so
``/api/nonexistent`` is caught by the 404 path inside the routing layer
BEFORE the catch-all static mount ever sees it. If you move the mount
earlier in ``create_app`` you'll start seeing ``index.html`` returned for
unknown API paths — a silent contract break.

Fallback rules (see :class:`SPAStaticFiles`): when the requested path has no
physical file AND doesn't begin with a reserved prefix, return
``index.html`` so the SPA can resolve the route on the client. Reserved
prefixes (``/api``, ``/ws``, ``/_next``, ``/healthz``) never get the fallback:
``/api/*`` + ``/ws/*`` + ``/healthz`` should 404 when not routed; ``/_next/*``
should 404 cleanly so a missing asset surfaces as a real failure rather than
an HTML response that parses as broken JS.
"""

from __future__ import annotations

import os
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Prefixes that MUST NOT receive the SPA fallback. A request to any of these
# that doesn't match a real file stays a 404, so a typo or a stale proxy
# rewrite surfaces visibly instead of masquerading as an HTML page.
_RESERVED_PREFIXES: tuple[str, ...] = ("api", "ws", "_next", "healthz")


def resolve_out_dir() -> Path:
    """Return the directory holding the Next.js static export.

    Lookup order:
    1. ``BRAIN_WEB_OUT_DIR`` — explicit override, used by tests + demos.
    2. ``<BRAIN_INSTALL_DIR>/web/out/`` — Plan 08 install layout (Tasks 7/8).
    3. ``<repo_root>/apps/brain_web/out/`` — dev fallback for ``uv run``
       developers who've run ``pnpm build`` in the repo.

    Raises :class:`RuntimeError` with a plain-English message when none of the
    candidates exist. The error fires at app startup (via
    :func:`brain_api.app.create_app`), so the operator sees the message before
    any request arrives.
    """
    env_override = os.environ.get("BRAIN_WEB_OUT_DIR")
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override))

    install_dir = os.environ.get("BRAIN_INSTALL_DIR")
    if install_dir:
        candidates.append(Path(install_dir) / "web" / "out")

    # Repo dev-fallback: packages/brain_api/src/brain_api/static_ui.py
    # → parents[4] is the repo root.
    here = Path(__file__).resolve()
    repo_root = here.parents[4]
    candidates.append(repo_root / "apps" / "brain_web" / "out")

    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").exists():
            return candidate

    raise RuntimeError(
        "Could not locate the brain_web static export directory. "
        "Searched: "
        + ", ".join(str(c) for c in candidates)
        + ". Set BRAIN_WEB_OUT_DIR to the path containing index.html, or run "
        "`pnpm --dir apps/brain_web build` in the repo."
    )


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that falls back to ``index.html`` for SPA routes.

    On a 404 from the base class, we check the request path:

    * If it starts with a reserved prefix (``/api``, ``/ws``, ``/_next``,
      ``/healthz``): re-raise the 404. The caller's typo / misconfigured proxy
      stays a visible failure.
    * Otherwise (a client-side route like ``/chat/abc-123`` that Next.js
      didn't pre-render, or a missing ``index.html`` in a sub-route): serve
      the root ``index.html`` so the React Router can resolve it.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            # `path` is already stripped of the mount prefix ("/") and has no
            # leading slash — match segments directly.
            first_segment = path.split("/", 1)[0] if path else ""
            if first_segment in _RESERVED_PREFIXES:
                raise
            # SPA fallback: serve the repo-root index.html verbatim.
            index = Path(str(self.directory)) / "index.html"
            if not index.is_file():
                raise
            return FileResponse(index)
