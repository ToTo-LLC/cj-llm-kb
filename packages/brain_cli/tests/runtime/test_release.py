"""Tests for ``brain_cli.runtime.release`` — Plan 08 Task 5."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import httpx
import pytest
from brain_cli.runtime import release
from brain_cli.runtime.release import (
    ReleaseError,
    check_latest_release,
    download_release,
)


def _mock_httpx_get(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    """Install a stub ``httpx.get`` that returns ``payload`` as a 200 response."""

    class _StubResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return payload

    def _stub_get(_url: str, **_kwargs: object) -> _StubResponse:
        return _StubResponse()

    monkeypatch.setattr(release.httpx, "get", _stub_get)


def test_check_latest_release_returns_release_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: new version available, SHA parsed from body."""
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)
    _mock_httpx_get(
        monkeypatch,
        {
            "tag_name": "v0.2.0",
            "body": ("## What's new\n\n- faster chat\n\nSHA256: " + "a" * 64 + "\n"),
            "assets": [
                {
                    "name": "brain-0.2.0-darwin-arm64.tar.gz",
                    "browser_download_url": ("https://example.com/brain-0.2.0-darwin-arm64.tar.gz"),
                }
            ],
        },
    )

    info = check_latest_release(current_version="0.1.0")

    assert info is not None
    assert info.version == "0.2.0"
    assert info.tag_name == "v0.2.0"
    assert info.tarball_url.endswith(".tar.gz")
    assert info.sha256 == "a" * 64


def test_check_latest_release_same_version_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-update path: current == tag_name (sans v)."""
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)
    _mock_httpx_get(
        monkeypatch,
        {
            "tag_name": "v0.1.0",
            "body": "",
            "assets": [],
        },
    )

    assert check_latest_release(current_version="0.1.0") is None


def test_check_latest_release_opt_out_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``BRAIN_NO_UPDATE_CHECK=1`` should skip the API call entirely."""
    monkeypatch.setenv("BRAIN_NO_UPDATE_CHECK", "1")
    # Any httpx call would raise; we confirm the function never made one.
    sentinel_called = {"hit": False}

    def _boom(*_args: object, **_kwargs: object) -> None:
        sentinel_called["hit"] = True
        raise AssertionError("opt-out failed to short-circuit")

    monkeypatch.setattr(release.httpx, "get", _boom)

    assert check_latest_release(current_version="0.1.0") is None
    assert sentinel_called["hit"] is False


def test_download_release_sha_mismatch_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A bad hash must raise and clean up the partial file."""

    payload_bytes = b"corrupted tarball bytes"
    # Compute the CORRECT sha then pass a WRONG one so we trigger the mismatch.
    bad_expected = "0" * 64

    class _StubStreamContext:
        status_code = 200

        def __init__(self) -> None:
            self.headers: dict[str, str] = {"content-length": str(len(payload_bytes))}

        def __enter__(self) -> _StubStreamContext:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def iter_bytes(self, chunk_size: int = 0) -> list[bytes]:
            _ = chunk_size  # chunk_size is passed as a kwarg by httpx consumers.
            return [payload_bytes]

    def _stub_stream(_method: str, _url: str, **_kwargs: object) -> _StubStreamContext:
        return _StubStreamContext()

    monkeypatch.setattr(release.httpx, "stream", _stub_stream)

    dest = tmp_path / "brain.tar.gz"
    with pytest.raises(ReleaseError, match="SHA256 mismatch"):
        download_release("https://example/test.tar.gz", dest, expected_sha256=bad_expected)

    # Partial file must have been cleaned up.
    assert not dest.exists()

    # Sanity: hashing our payload manually produces something != bad_expected
    assert hashlib.sha256(payload_bytes).hexdigest() != bad_expected


def test_check_latest_release_network_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transport errors surface as ReleaseError, not bare httpx exceptions."""
    monkeypatch.delenv("BRAIN_NO_UPDATE_CHECK", raising=False)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(release.httpx, "get", _raise)

    with pytest.raises(ReleaseError, match="Could not reach GitHub"):
        check_latest_release(current_version="0.1.0")
