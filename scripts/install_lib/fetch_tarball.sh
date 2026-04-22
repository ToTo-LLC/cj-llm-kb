#!/bin/bash
# scripts/install_lib/fetch_tarball.sh
#
# Plan 08 Task 7. Download a release tarball and verify its SHA256.
#
# Usage (sourced):
#   . scripts/install_lib/fetch_tarball.sh
#   fetch_tarball "<url>" "<dest_path>" "<expected_sha256>"
#
# Supports http(s):// and file:// URLs. Prefers ``curl``; falls back to
# ``wget`` if curl is not installed. Emits a clear error and returns
# non-zero if neither is available or the SHA256 does not match.
#
# Bash 3.2 compatible (macOS /bin/bash). No arrays, no associative
# arrays, no [[ -v ]]. Everything quoted.

# ---------------------------------------------------------------------------
# _have_cmd NAME
#   Silent check — returns 0 if NAME is on PATH.
# ---------------------------------------------------------------------------
_have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# _sha256_of FILE
#   Compute SHA256 hex digest of FILE. Uses shasum on Mac, sha256sum on
#   Linux. Prints the hex string on stdout. Returns non-zero if neither
#   tool is available.
# ---------------------------------------------------------------------------
_sha256_of() {
    local f="$1"
    if _have_cmd shasum; then
        shasum -a 256 "$f" | awk '{print $1}'
    elif _have_cmd sha256sum; then
        sha256sum "$f" | awk '{print $1}'
    else
        echo "error: no SHA256 tool found (need shasum or sha256sum)" >&2
        return 1
    fi
}

# ---------------------------------------------------------------------------
# _download_url URL DEST
#   Download URL → DEST. curl preferred, wget fallback. Handles file://
#   URLs by copying (both curl and wget can do this, but we special-case
#   for clarity). Returns non-zero on transport error.
# ---------------------------------------------------------------------------
_download_url() {
    local url="$1"
    local dest="$2"

    # file:// → plain cp, so we don't depend on any downloader being
    # present for local/dev flows. This is the path the Python test
    # harness exercises.
    case "$url" in
        file://*)
            local src
            src="${url#file://}"
            if [ ! -f "$src" ]; then
                echo "error: local tarball not found: $src" >&2
                return 1
            fi
            cp "$src" "$dest"
            return $?
            ;;
    esac

    if _have_cmd curl; then
        # -f: fail on HTTP errors, -s: silent, -S: show errors even
        # when silent, -L: follow redirects.
        curl -fsSL "$url" -o "$dest"
        return $?
    fi

    if _have_cmd wget; then
        wget -q -O "$dest" "$url"
        return $?
    fi

    echo "error: no downloader found (install curl or wget)" >&2
    echo "       try: xcode-select --install   (Mac)" >&2
    return 1
}

# ---------------------------------------------------------------------------
# fetch_tarball URL DEST EXPECTED_SHA256
#   Top-level entry. Downloads + verifies. Cleans up a partial file on
#   hash mismatch so retries start fresh.
# ---------------------------------------------------------------------------
fetch_tarball() {
    local url="$1"
    local dest="$2"
    local expected="$3"

    if [ -z "$url" ] || [ -z "$dest" ] || [ -z "$expected" ]; then
        echo "error: fetch_tarball <url> <dest> <expected_sha256>" >&2
        return 2
    fi

    # Make sure destination directory exists before curl writes to it.
    local dest_dir
    dest_dir=$(dirname "$dest")
    mkdir -p "$dest_dir"

    echo "  downloading $url"
    if ! _download_url "$url" "$dest"; then
        echo "error: download failed for $url" >&2
        echo "       check your network connection and retry." >&2
        rm -f "$dest"
        return 1
    fi

    echo "  verifying SHA256"
    local actual
    actual=$(_sha256_of "$dest")
    if [ $? -ne 0 ] || [ -z "$actual" ]; then
        rm -f "$dest"
        return 1
    fi

    # Case-insensitive compare: some SHAs ship uppercase.
    local expected_lc actual_lc
    expected_lc=$(printf '%s' "$expected" | tr '[:upper:]' '[:lower:]')
    actual_lc=$(printf '%s' "$actual" | tr '[:upper:]' '[:lower:]')

    if [ "$expected_lc" != "$actual_lc" ]; then
        echo "error: SHA256 mismatch for $url" >&2
        echo "       expected: $expected_lc" >&2
        echo "       actual:   $actual_lc" >&2
        echo "       the download may be corrupted or tampered with." >&2
        echo "       try again, or report the issue if it persists." >&2
        rm -f "$dest"
        return 1
    fi

    echo "  ok (sha256 $actual_lc)"
    return 0
}
