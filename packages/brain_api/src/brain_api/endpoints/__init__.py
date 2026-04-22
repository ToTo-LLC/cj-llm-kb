"""brain_api endpoint modules added in Plan 08.

These endpoints live beside (and eventually supersede) the earlier ``routes/``
package. They exist so the web UI can boot itself without external help:

* :mod:`brain_api.endpoints.setup_status` — ``GET /api/setup-status`` reports
  which pieces of the fresh-install trifecta (vault dir + token file + BRAIN.md)
  are present, so the frontend knows whether to route to ``/setup``.
* :mod:`brain_api.endpoints.token` — ``GET /api/token`` returns the per-run
  app secret (same-origin only) so the SPA can attach it as ``X-Brain-Token``
  on every subsequent write.
* :mod:`brain_api.endpoints.upload` — ``POST /api/upload`` accepts a multipart
  ``file`` field and dispatches to the in-process ``brain_ingest`` tool
  handler; Plan 08's static UI drops the Next.js proxy that used to sit here.

All three are Origin-gated at the endpoint layer (see
:func:`brain_api.endpoints._origin.require_loopback_origin`). The shared
:class:`brain_api.auth.OriginHostMiddleware` only enforces Origin on state-
changing methods + WebSocket upgrades; the GET endpoints in this package
carry sensitive information (setup state, app secret) that demands a stricter
same-origin contract, so we layer an explicit check on top.
"""
