"""Pin test for ``UploadResponse`` field shape — Plan 19 T2.

The frontend's ``UploadResult`` TS interface at
``apps/brain_web/src/lib/ingest/upload.ts`` is narrowed to mirror this
backend response_model exactly (``{patch_id: string}``). Two live
consumers — ``apps/brain_web/src/components/inbox/drop-zone.tsx`` and
``apps/brain_web/src/components/shell/app-shell.tsx`` — used to read
``res.domain`` from the upload response, which the backend never
emitted. Plan 18 T1-class shape (silently-empty fields). This pin
fails RED if anyone adds/removes a field on ``UploadResponse`` without
also updating the TS narrow + the consumer sites.

If you need to widen the response body (e.g. emit the classified
``domain`` in T2.B-style follow-up), update the TS interface and both
consumer call sites in lockstep, then update this pin.
"""

from __future__ import annotations

from brain_api.endpoints.upload import UploadResponse


def test_upload_response_field_set() -> None:
    """``UploadResponse`` emits exactly ``{patch_id}``.

    Pin against accidental widening / narrowing. See the module
    docstring for the rationale + lockstep TS sites.
    """
    assert set(UploadResponse.model_fields.keys()) == {"patch_id"}


def test_upload_response_patch_id_is_non_nullable_str() -> None:
    """``patch_id`` is a required, non-nullable ``str``.

    The TS-side narrow declares ``patch_id: string`` (non-null). If the
    backend ever loosens this to ``str | None``, the TS narrow becomes
    too tight and the two consumer call sites (drop-zone, app-shell)
    need to defensively coalesce again.
    """
    field = UploadResponse.model_fields["patch_id"]
    assert field.annotation is str
    assert field.is_required()
