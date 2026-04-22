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
physical file AND doesn't begin with a reserved prefix, return an
``index.html`` so the SPA can resolve the route on the client. Reserved
prefixes (``/api``, ``/ws``, ``/_next``, ``/healthz``) never get the fallback.

## Dynamic-segment placeholder routing (Plan 08 Task 2)

Next.js app-router static export only emits HTML for paths listed in
``generateStaticParams``. Pages like ``/chat/[thread_id]/`` pre-render one
placeholder (``/chat/_/index.html``) so the chunk is built; real thread ids
are unknown at build time. The generic "serve root index.html" fallback
would put the client router into its 404 state because the initial route
match is ``/``, not ``/chat/[thread_id]``.

The fix: when a 404 would fire for a path matching a known dynamic-segment
pattern (``/chat/<x>/``, ``/browse/<x>/...``, ``/settings/<x>/``), serve the
corresponding ``_``-placeholder HTML so the client runtime mounts the right
route component. That component reads the real id via ``useParams()`` and
the URL stays unchanged in the browser.
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

# Dynamic-segment → placeholder map. Static export's ``generateStaticParams``
# pre-renders one placeholder HTML per dynamic pattern; this dict records
# which placeholder to serve when the live URL matches the pattern but wasn't
# pre-rendered. Keep in sync with the Next.js page files under
# ``apps/brain_web/src/app/**/[...]/page.tsx``.
_DYNAMIC_PLACEHOLDERS: dict[str, str] = {
    # /chat/<thread_id>/...  -> /chat/_/index.html
    "chat": "chat/_/index.html",
    # /browse/<...path>/...  -> /browse/_/index.html
    "browse": "browse/_/index.html",
}

# Pre-rendered tabs under /settings/<tab>/ are enumerated by
# ``generateStaticParams``. Unknown tabs fall through to /settings/general/.
_SETTINGS_FALLBACK = "settings/general/index.html"


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
      ``/healthz``): 404. The caller's typo / misconfigured proxy stays a
      visible failure.
    * If the first segment matches a known dynamic-segment pattern
      (``chat``, ``browse``), serve the corresponding pre-rendered
      ``_``-placeholder so the client runtime mounts the right route
      component and ``useParams()`` sees the real URL.
    * If the first segment is ``settings``, serve ``settings/general/``
      (unknown tabs fall through to General; ``<SettingsScreen />`` handles
      tab normalisation client-side).
    * Otherwise (a bare client-only route like ``/about/``): serve the root
      ``index.html`` so the React Router can resolve it.

    ## Why we override get_response AND watch for ``html=True`` 404s

    Starlette's ``StaticFiles(html=True)`` auto-serves ``<mount_dir>/404.html``
    when a file is missing (see ``staticfiles.py`` lines ~147-152). That
    means we can't simply ``try: super().get_response()`` and catch
    ``HTTPException`` — the base class returns a 200-shaped FileResponse
    with status_code=404 carrying the Next.js built-in 404 page, and no
    exception is raised. We detect both cases: the 404 HTTPException (when
    there's no ``404.html``) AND the 404-status FileResponse, and funnel
    both through the same SPA-fallback decision tree.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return self._spa_fallback(path, raise_on_miss=True)

        # Starlette with html=True converts missing files into a 404
        # FileResponse serving 404.html. Intercept that so we can send the
        # caller to the right SPA placeholder instead of Next.js's static
        # 404 page.
        if response.status_code == 404:
            fallback = self._spa_fallback(path, raise_on_miss=False)
            if fallback is not None:
                return fallback
        return response

    def _spa_fallback(self, path: str, *, raise_on_miss: bool) -> Response | None:
        """Pick the best SPA fallback HTML for a given client-route path.

        Args:
            path: Mount-relative path (no leading slash).
            raise_on_miss: When True, raise ``HTTPException(404)`` if no
                fallback applies. When False, return ``None`` so the caller
                can return the original 404 response unchanged.
        """
        first_segment = path.split("/", 1)[0] if path else ""
        if first_segment in _RESERVED_PREFIXES:
            if raise_on_miss:
                raise HTTPException(status_code=404)
            return None

        out_root = Path(str(self.directory))
        chosen: Path | None = None

        if first_segment in _DYNAMIC_PLACEHOLDERS:
            candidate = out_root / _DYNAMIC_PLACEHOLDERS[first_segment]
            if candidate.is_file():
                chosen = candidate
        elif first_segment == "settings":
            candidate = out_root / _SETTINGS_FALLBACK
            if candidate.is_file():
                chosen = candidate

        if chosen is None:
            # Generic SPA fallback — serve the repo-root index.html.
            root_index = out_root / "index.html"
            if not root_index.is_file():
                if raise_on_miss:
                    raise HTTPException(status_code=404)
                return None
            chosen = root_index

        return FileResponse(chosen)
