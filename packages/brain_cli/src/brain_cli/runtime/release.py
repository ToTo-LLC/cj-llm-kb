"""GitHub release metadata + tarball download for ``brain upgrade``.

Plan 08 Task 5. Two small pieces:

* :func:`check_latest_release` queries the GitHub Releases API and
  returns a :class:`ReleaseInfo` iff a newer version is available. Honors
  ``BRAIN_NO_UPDATE_CHECK=1`` as an opt-out (returns ``None``).
* :func:`download_release` streams a tarball to disk and optionally
  verifies a SHA256 digest.

The SHA256 convention is documented in the release-body parser: ship a
line like ``SHA256: <64-hex>`` in the GitHub release description and the
upgrade flow will verify the downloaded artifact against it. Absent that
line, ``check_latest_release`` returns ``sha256=None`` and the caller
must decide whether to proceed unverified (default: warn + continue).
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

_GITHUB_LATEST_URL = "https://api.github.com/repos/ToTo-LLC/cj-llm-kb/releases/latest"

# Matches lines like ``SHA256: abc123...`` (case-insensitive on the label,
# 64-hex payload). Placed as the first match-group so callers don't have
# to juggle named groups.
_SHA256_RE = re.compile(r"(?im)^\s*SHA256\s*:\s*([0-9a-f]{64})\s*$")

# Streaming download chunk size. 64 KB is the usual sweet spot on spinning
# and SSD disks alike — small enough to update progress smoothly, large
# enough to amortize syscall overhead.
_DOWNLOAD_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class ReleaseInfo:
    """What we need to download + verify a release tarball.

    ``version`` is ``tag_name`` with any leading ``v`` stripped — keeps
    comparisons a simple semver string match. ``sha256`` is ``None`` when
    the release body didn't include a hash; callers decide what to do.
    """

    version: str
    tag_name: str
    tarball_url: str
    sha256: str | None
    body: str


class ReleaseError(RuntimeError):
    """Any failure in the release-check or download path.

    We keep this as a single exception type rather than a hierarchy
    because the user-facing behavior is identical across failure modes:
    print the message, exit with status 1, recommend a manual download.
    """


def _strip_leading_v(tag: str) -> str:
    """Return ``tag`` with a single leading ``v`` removed if present."""
    return tag[1:] if tag.startswith("v") else tag


def check_latest_release(
    current_version: str,
    *,
    timeout_s: int = 10,
    url: str = _GITHUB_LATEST_URL,
) -> ReleaseInfo | None:
    """Query the GitHub API and return release info iff a newer version exists.

    Returns ``None`` in three cases:
      1. ``BRAIN_NO_UPDATE_CHECK=1`` is set (user opt-out; non-blocking).
      2. Current version equals the published ``tag_name`` (no update).
      3. The response lacks a tarball asset we can download.

    Raises :class:`ReleaseError` on transport / parse failures so the
    caller can surface a plain-English "couldn't reach GitHub" message.
    Network errors during an opt-in check should not crash the user's
    upgrade attempt — the calling command typically prints the error and
    offers ``--tarball`` as a fallback.
    """
    if os.environ.get("BRAIN_NO_UPDATE_CHECK") == "1":
        return None

    try:
        response = httpx.get(
            url,
            timeout=timeout_s,
            # Set the API version header per GitHub recommendation —
            # keeps us on the stable schema even if v4 ships.
            headers={"Accept": "application/vnd.github+json"},
        )
    except httpx.RequestError as exc:
        raise ReleaseError(f"Could not reach GitHub: {exc}") from exc

    if response.status_code != 200:
        raise ReleaseError(
            f"GitHub returned HTTP {response.status_code} — cannot determine latest release."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ReleaseError(f"Malformed JSON from GitHub: {exc}") from exc

    tag_name = str(payload.get("tag_name", "")).strip()
    if not tag_name:
        raise ReleaseError("GitHub response missing tag_name field.")

    latest_version = _strip_leading_v(tag_name)
    if latest_version == current_version or tag_name == current_version:
        # Already up to date — return None instead of raising so callers
        # can do ``if info: upgrade() else: print("up to date")``.
        return None

    assets = payload.get("assets") or []
    if not isinstance(assets, list):
        raise ReleaseError("GitHub response: assets field is not a list.")

    # Prefer a tarball asset; fall back to the repo tarball URL if one is
    # exposed. Most of our releases will ship a pre-built ``.tar.gz``.
    tarball_url: str | None = None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        if name.endswith(".tar.gz"):
            tarball_url = str(asset.get("browser_download_url", "")) or None
            if tarball_url:
                break

    if tarball_url is None:
        # Fall back to the auto-generated tarball URL if present.
        fallback = payload.get("tarball_url")
        if isinstance(fallback, str) and fallback:
            tarball_url = fallback

    if tarball_url is None:
        raise ReleaseError(f"Release {tag_name} has no .tar.gz asset to download.")

    body = str(payload.get("body") or "")
    match = _SHA256_RE.search(body)
    sha256 = match.group(1).lower() if match else None

    return ReleaseInfo(
        version=latest_version,
        tag_name=tag_name,
        tarball_url=tarball_url,
        sha256=sha256,
        body=body,
    )


def download_release(
    url: str,
    dest: Path,
    *,
    expected_sha256: str | None = None,
    timeout_s: int = 120,
    progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Stream a release tarball to ``dest``, verifying SHA256 if given.

    ``progress`` is an optional callback ``(bytes_so_far, total_or_None)``
    — a no-op by default. We pass it through so a future TTY progress
    bar can plug in without changing this signature. ``total`` is
    ``None`` when the server doesn't send Content-Length.

    On SHA mismatch we delete the partial file and raise
    :class:`ReleaseError` — never leave a half-good artifact on disk
    that a second attempt might mistake for a valid cache hit.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    hasher = hashlib.sha256() if expected_sha256 is not None else None
    downloaded = 0

    try:
        # Stream mode so we don't pull the full tarball into memory
        # before writing — tarballs can reach 100s of MB.
        with httpx.stream(
            "GET",
            url,
            timeout=timeout_s,
            follow_redirects=True,
        ) as response:
            if response.status_code != 200:
                raise ReleaseError(f"Download returned HTTP {response.status_code}: {url}")

            total_header = response.headers.get("content-length")
            try:
                total: int | None = int(total_header) if total_header else None
            except ValueError:
                total = None

            with dest.open("wb") as fh:
                for chunk in response.iter_bytes(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    if hasher is not None:
                        hasher.update(chunk)
                    downloaded += len(chunk)
                    if progress is not None:
                        progress(downloaded, total)
    except httpx.RequestError as exc:
        # Partial file is now invalid — clean it up before re-raising.
        if dest.exists():
            with contextlib.suppress(OSError):
                dest.unlink()
        raise ReleaseError(f"Download failed: {exc}") from exc

    if hasher is not None and expected_sha256 is not None:
        actual = hasher.hexdigest()
        if actual.lower() != expected_sha256.lower():
            # Bad hash — ditch the file so retrying doesn't short-circuit.
            with contextlib.suppress(OSError):
                dest.unlink()
            raise ReleaseError(
                f"SHA256 mismatch on downloaded tarball: expected {expected_sha256}, got {actual}."
            )

    return dest
