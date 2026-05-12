"""Pin test for ``TokenResponse`` field shape — Plan 20 T1.2.

The SPA's ``GET /api/token`` fetch hands the per-run app secret to
same-origin browser code so subsequent writes can attach the
``X-Brain-Token`` header. The TS-side consumer in
``apps/brain_web/src/lib/api/token.ts`` reads ``res.token`` directly;
if the backend ever adds, removes, or renames a field, the TS narrow
silently drifts (Plan 18 T1-class shape). This pin closes the Plan 19
T1 audit-OK-but-unpinned gap for the token response model.

Pattern mirrors the canonical Plan 19 T2 precedent at
``test_endpoint_upload_shape.py`` — strict-equality key-set pin plus
per-field type+required pin.

If you need to widen / narrow this response body, update the TS narrow
+ every consumer call site in lockstep, then update this pin.
"""

from __future__ import annotations

from brain_api.endpoints.token import TokenResponse


def test_token_response_field_set() -> None:
    """``TokenResponse`` emits exactly ``{token}``.

    Pin against accidental widening / narrowing. See the module
    docstring for the rationale + lockstep TS sites.
    """
    assert set(TokenResponse.model_fields.keys()) == {"token"}


def test_token_response_token_is_non_nullable_str() -> None:
    """``token`` is a required, non-nullable ``str``.

    The endpoint raises 503 (``setup_required``) when no token file
    exists on disk — it never emits ``{"token": null}``. The TS narrow
    can therefore safely declare ``token: string``.
    """
    field = TokenResponse.model_fields["token"]
    assert field.annotation is str
    assert field.is_required()
