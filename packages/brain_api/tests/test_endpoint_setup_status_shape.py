"""Pin test for ``SetupStatusResponse`` field shape — Plan 20 T1.1.

The browser's first handshake (``GET /api/setup-status``) drives the
setup wizard / chat redirect decision in
``apps/brain_web/src/lib/setup-status.ts`` (and its consumers in the
shell + wizard routes). If anyone adds/removes/renames a field on
:class:`brain_api.endpoints.setup_status.SetupStatusResponse` without
also updating the TS narrow + consumer call sites, the SPA silently
drifts (Plan 18 T1-class shape — empty / missing field rendered as
``undefined``). This pin closes the Plan 19 T1 audit-OK-but-unpinned
gap for the setup-status response model.

Pattern mirrors the canonical Plan 19 T2 precedent at
``test_endpoint_upload_shape.py`` — one strict-equality key-set pin
plus one per-field type+required pin for each single-typed primitive.

If you need to widen / narrow this response body, update the TS narrow
+ every consumer call site in lockstep, then update this pin.
"""

from __future__ import annotations

from brain_api.endpoints.setup_status import SetupStatusResponse


def test_setup_status_response_field_set() -> None:
    """``SetupStatusResponse`` emits exactly the 4 documented fields.

    Pin against accidental widening / narrowing. See the module
    docstring for the rationale + lockstep TS sites.
    """
    assert set(SetupStatusResponse.model_fields.keys()) == {
        "has_token",
        "is_first_run",
        "vault_exists",
        "vault_path",
    }


def test_setup_status_response_has_token_is_non_nullable_bool() -> None:
    """``has_token`` is a required, non-nullable ``bool``."""
    field = SetupStatusResponse.model_fields["has_token"]
    assert field.annotation is bool
    assert field.is_required()


def test_setup_status_response_is_first_run_is_non_nullable_bool() -> None:
    """``is_first_run`` is a required, non-nullable ``bool``."""
    field = SetupStatusResponse.model_fields["is_first_run"]
    assert field.annotation is bool
    assert field.is_required()


def test_setup_status_response_vault_exists_is_non_nullable_bool() -> None:
    """``vault_exists`` is a required, non-nullable ``bool``."""
    field = SetupStatusResponse.model_fields["vault_exists"]
    assert field.annotation is bool
    assert field.is_required()


def test_setup_status_response_vault_path_is_non_nullable_str() -> None:
    """``vault_path`` is a required, non-nullable ``str``.

    The endpoint emits ``str(vault_root)`` (never None) so the TS-side
    narrow can safely declare ``vault_path: string``.
    """
    field = SetupStatusResponse.model_fields["vault_path"]
    assert field.annotation is str
    assert field.is_required()
