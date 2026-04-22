#!/bin/bash
# scripts/cut-local-tarball.sh — Plan 08 Task 7
#
# Build a brain tarball from the current git HEAD + print its SHA256.
# Useful for:
#   1. scripts/tests/test_install_sh.py (consumed via file:// URL).
#   2. Task 10/11 clean-VM dry runs (served via python -m http.server).
#   3. Local "does a fresh install succeed?" smoke tests.
#
# Output: <dest>/brain-dev-<sha>.tar.gz  (+ <dest>/brain-dev-<sha>.tar.gz.sha256)
#
# Usage:
#   scripts/cut-local-tarball.sh              # writes to ./dist/
#   scripts/cut-local-tarball.sh /tmp/brain   # writes to /tmp/brain/
#
# Bash 3.2 compatible.

set -eu

DEST_DIR="${1:-./dist}"
mkdir -p "$DEST_DIR"

# Short git SHA for filename disambiguation.
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "nosha")
TARBALL="$DEST_DIR/brain-dev-$SHA.tar.gz"

echo "==> Cutting tarball from git HEAD ($SHA)"
git archive --format=tar.gz --output "$TARBALL" HEAD

# SHA256 next to the tarball so the installer (or a human) can verify.
if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$TARBALL" | tee "$TARBALL.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$TARBALL" | tee "$TARBALL.sha256"
else
    echo "warning: no SHA256 tool found — skipping hash" >&2
fi

echo ""
echo "tarball: $TARBALL"
echo ""
echo "to install from this tarball:"
echo "  BRAIN_RELEASE_URL=\"file://$(cd "$(dirname "$TARBALL")" && pwd)/$(basename "$TARBALL")\" \\"
echo "    bash scripts/install.sh"
