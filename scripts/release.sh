#!/bin/bash
# scripts/release.sh — Plan 09 Task 7
#
# Universal tarball builder for brain releases. Produces:
#
#   release/brain-<version>.tar.gz
#   release/brain-<version>.tar.gz.sha256
#
# The tarball ships Python source + prebuilt ``apps/brain_web/out/`` +
# install scripts + release-relevant docs. install.sh (Plan 08 Task 7)
# consumes it directly — the layout is what that script expects after
# its one-strip-component heuristic.
#
# Contrast with ``scripts/cut-local-tarball.sh``: that one calls
# ``git archive HEAD`` for dev use. This one is release-quality — it
# builds the UI first, applies strict include/exclude discipline, and
# aborts on a dirty tree unless ``--force`` is passed.
#
# Usage:
#   bash scripts/release.sh              # build into ./release/
#   bash scripts/release.sh --force      # allow a dirty working tree
#   bash scripts/release.sh --clean      # remove release/ first
#   bash scripts/release.sh --skip-ui    # assume apps/brain_web/out/ already built
#
# Exit codes:
#   0 — success
#   1 — any failure (dirty tree, build failure, missing artifact, etc.)
#
# Bash 3.2 compatible (macOS /bin/bash). No associative arrays, no
# ``[[ -v ]]``. Quote aggressively.

set -eu

# ---------------------------------------------------------------------------
# 0. Locate repo root + parse flags
# ---------------------------------------------------------------------------

SCRIPT_SOURCE="$0"
if [ -L "$SCRIPT_SOURCE" ]; then
    SCRIPT_SOURCE=$(readlink "$SCRIPT_SOURCE")
fi
SCRIPT_DIR=$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

FORCE=0
CLEAN=0
SKIP_UI=0
for arg in "$@"; do
    case "$arg" in
        --force)    FORCE=1 ;;
        --clean)    CLEAN=1 ;;
        --skip-ui)  SKIP_UI=1 ;;
        -h|--help)
            head -n 35 "$0" | sed -n '3,35p'
            exit 0
            ;;
        *)
            echo "error: unknown flag: $arg" >&2
            echo "usage: bash scripts/release.sh [--force] [--clean] [--skip-ui]" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# 1. TTY-aware colors (match install.sh style)
# ---------------------------------------------------------------------------

if [ -t 1 ]; then
    C_RESET=$(printf '\033[0m')
    C_GREEN=$(printf '\033[32m')
    C_YELLOW=$(printf '\033[33m')
    C_RED=$(printf '\033[31m')
    C_BLUE=$(printf '\033[34m')
    C_BOLD=$(printf '\033[1m')
else
    C_RESET=""
    C_GREEN=""
    C_YELLOW=""
    C_RED=""
    C_BLUE=""
    C_BOLD=""
fi

log_step() {
    echo "${C_BOLD}${C_BLUE}==>${C_RESET}${C_BOLD} $1${C_RESET}"
}
log_info() {
    echo "  $1"
}
log_ok() {
    echo "${C_GREEN}  ok${C_RESET} $1"
}
log_warn() {
    echo "${C_YELLOW}warning:${C_RESET} $1" >&2
}
log_err() {
    echo "${C_RED}error:${C_RESET} $1" >&2
}

# ---------------------------------------------------------------------------
# 2. Check working tree cleanliness
# ---------------------------------------------------------------------------

log_step "Checking working tree"
DIRTY=$(git status --porcelain 2>/dev/null || true)
if [ -n "$DIRTY" ]; then
    if [ "$FORCE" != "1" ]; then
        log_err "working tree is dirty. Commit or stash your changes first."
        log_err "Or re-run with --force to build anyway (NOT recommended for releases)."
        echo "" >&2
        echo "$DIRTY" | sed 's/^/  /' >&2
        exit 1
    else
        log_warn "working tree dirty but --force set; continuing."
    fi
else
    log_ok "working tree clean"
fi

# ---------------------------------------------------------------------------
# 3. Read version from VERSION file
# ---------------------------------------------------------------------------

if [ ! -f "$REPO_ROOT/VERSION" ]; then
    log_err "VERSION file missing at $REPO_ROOT/VERSION"
    exit 1
fi
VERSION=$(head -n 1 "$REPO_ROOT/VERSION" | tr -d '[:space:]')
if [ -z "$VERSION" ]; then
    log_err "VERSION file is empty"
    exit 1
fi
log_info "version: $VERSION"

RELEASE_DIR="$REPO_ROOT/release"
STAGING_PARENT="$RELEASE_DIR/staging-$VERSION"
STAGING_DIR="$STAGING_PARENT/brain-$VERSION"
TARBALL="$RELEASE_DIR/brain-$VERSION.tar.gz"
SHA_FILE="$TARBALL.sha256"

# ---------------------------------------------------------------------------
# 4. --clean: wipe release/ before we start
# ---------------------------------------------------------------------------

if [ "$CLEAN" = "1" ]; then
    log_step "Cleaning release/ (--clean)"
    rm -rf "$RELEASE_DIR"
    log_ok "removed $RELEASE_DIR"
fi

mkdir -p "$RELEASE_DIR"
# Always start with a fresh staging tree for this version.
rm -rf "$STAGING_PARENT"
mkdir -p "$STAGING_DIR"

# ---------------------------------------------------------------------------
# 5. Build the web UI
# ---------------------------------------------------------------------------

if [ "$SKIP_UI" = "1" ]; then
    log_step "Skipping UI build (--skip-ui)"
    if [ ! -f "$REPO_ROOT/apps/brain_web/out/index.html" ]; then
        log_err "--skip-ui set but apps/brain_web/out/index.html is missing"
        log_err "   run the UI build first: pnpm -F brain_web build"
        exit 1
    fi
    log_ok "existing UI bundle found at apps/brain_web/out/"
else
    log_step "Building web UI (pnpm -F brain_web install && build)"
    if ! command -v pnpm >/dev/null 2>&1; then
        log_err "pnpm not found on PATH"
        log_err "   install with: corepack enable && corepack prepare pnpm@9 --activate"
        exit 1
    fi
    if ! (cd "$REPO_ROOT" && pnpm -F brain_web install --frozen-lockfile); then
        log_err "pnpm install failed"
        exit 1
    fi
    if ! (cd "$REPO_ROOT" && pnpm -F brain_web build); then
        log_err "pnpm build failed"
        exit 1
    fi
    if [ ! -f "$REPO_ROOT/apps/brain_web/out/index.html" ]; then
        log_err "UI build completed but apps/brain_web/out/index.html is missing"
        exit 1
    fi
    log_ok "UI built at apps/brain_web/out/"
fi

# ---------------------------------------------------------------------------
# 6. Seed staging from ``git archive HEAD`` — respects .gitattributes +
#    .gitignore. This gets all tracked files; we sweep excludes in #7
#    and supplement with the prebuilt UI in #8.
# ---------------------------------------------------------------------------

log_step "Seeding staging dir from git archive HEAD"
# Pipe into tar -x to extract directly (bash 3.2-safe pipeline).
(cd "$REPO_ROOT" && git archive --format=tar HEAD) | tar -xf - -C "$STAGING_DIR"
log_ok "staging seeded at $STAGING_DIR"

# ---------------------------------------------------------------------------
# 7. Explicit exclude sweep — defense in depth against anything the
#    git archive pulled that we don't want shipped.
#
# Decisions:
#   - docs/superpowers/  → internal design spec; exclude.
#   - docs/design/       → design assets + deltas; internal; exclude.
#   - docs/testing/      → exclude receipts + screenshots + VM host instructions,
#                          but KEEP docs/testing/manual-qa.md (ship users want
#                          to run the QA sweep on their install).
#   - tasks/             → plan docs + lessons; internal.
#   - .claude/           → personal agent config.
#   - .brain/            → user runtime state; shouldn't be in HEAD anyway.
#   - scripts/tests/     → install-script integration tests; dev-only.
#   - packages/*/tests/  → python unit tests; not needed at runtime.
#   - apps/brain_web/tests/ → frontend tests; not needed at runtime.
#   - node_modules/, __pycache__/, .venv/ → belt + suspenders.
# ---------------------------------------------------------------------------

log_step "Applying exclude sweep"

# Directory excludes — ``-type d`` finds the tree root; rm -rf nukes it.
sweep_dir() {
    local rel="$1"
    local path="$STAGING_DIR/$rel"
    if [ -e "$path" ]; then
        rm -rf "$path"
        log_info "excluded: $rel"
    fi
}

sweep_dir ".claude"
sweep_dir ".brain"
sweep_dir "tasks"
sweep_dir "docs/superpowers"
sweep_dir "docs/design"
sweep_dir "scripts/tests"
sweep_dir "apps/brain_web/tests"
sweep_dir "apps/brain_web/node_modules"
sweep_dir "apps/brain_web/.next"
sweep_dir "apps/brain_web/scripts"
sweep_dir "apps/brain_web/test-results"
sweep_dir "apps/brain_web/playwright-report"
sweep_dir "node_modules"

# Strip brain_web test-runner configs — tests themselves are already
# excluded above; the runner configs are dead weight without them.
for f in "apps/brain_web/playwright.config.ts" "apps/brain_web/vitest.config.ts"; do
    if [ -f "$STAGING_DIR/$f" ]; then
        rm -f "$STAGING_DIR/$f"
        log_info "excluded: $f"
    fi
done

# Strip dev-only scripts — the tarball ships install scripts only.
# Only keep: scripts/install.sh, scripts/install.ps1, scripts/release.sh
# (so downstream users who clone-after-extract can rebuild),
# and the scripts/install_lib/ dir.
if [ -d "$STAGING_DIR/scripts" ]; then
    find "$STAGING_DIR/scripts" -mindepth 1 -maxdepth 1 \
        ! -name "install.sh" \
        ! -name "install.ps1" \
        ! -name "release.sh" \
        ! -name "install_lib" \
        -exec rm -rf {} +
    log_info "excluded: scripts/* (kept install.sh, install.ps1, release.sh, install_lib/)"
fi

# docs/testing/ partial — keep only manual-qa.md, drop everything else.
if [ -d "$STAGING_DIR/docs/testing" ]; then
    find "$STAGING_DIR/docs/testing" -mindepth 1 -maxdepth 1 ! -name "manual-qa.md" -exec rm -rf {} +
    log_info "excluded: docs/testing/* (kept manual-qa.md)"
fi

# packages/*/tests/ — remove per-package test trees.
if [ -d "$STAGING_DIR/packages" ]; then
    find "$STAGING_DIR/packages" -mindepth 2 -maxdepth 2 -type d -name "tests" -exec rm -rf {} +
    log_info "excluded: packages/*/tests/"
fi

# Belt + suspenders: strip any __pycache__ / .venv / .DS_Store that leaked in.
find "$STAGING_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING_DIR" -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING_DIR" -name ".DS_Store" -exec rm -f {} + 2>/dev/null || true

# Strip dotfiles at the top-level of staging we don't want shipped
# (keep .gitignore for anyone who might re-init; drop everything else).
for dot in ".gitattributes" ".editorconfig" ".github" ".cursor" ".devcontainer"; do
    sweep_dir "$dot"
done

log_ok "exclude sweep complete"

# ---------------------------------------------------------------------------
# 8. Copy in the prebuilt UI (apps/brain_web/out/ is gitignored, so
#    git archive never sees it).
# ---------------------------------------------------------------------------

log_step "Copying prebuilt UI into staging"
mkdir -p "$STAGING_DIR/apps/brain_web"
# Clean slate in case some stray 'out' sneaked in.
rm -rf "$STAGING_DIR/apps/brain_web/out"
cp -R "$REPO_ROOT/apps/brain_web/out" "$STAGING_DIR/apps/brain_web/out"

if [ ! -f "$STAGING_DIR/apps/brain_web/out/index.html" ]; then
    log_err "UI copy failed — no index.html in staging"
    exit 1
fi
log_ok "UI copied to staging"

# ---------------------------------------------------------------------------
# 9. Pack the tarball
# ---------------------------------------------------------------------------

log_step "Packing tarball"
# Remove any prior tarball + sidecar for this version so the pack is
# deterministic.
rm -f "$TARBALL" "$SHA_FILE"
(cd "$STAGING_PARENT" && tar -czf "$TARBALL" "brain-$VERSION")
log_ok "wrote $TARBALL"

# ---------------------------------------------------------------------------
# 10. SHA256 sidecar (format matches cut-local-tarball.sh + fetch helpers)
# ---------------------------------------------------------------------------

log_step "Computing SHA256 sidecar"
if command -v shasum >/dev/null 2>&1; then
    (cd "$RELEASE_DIR" && shasum -a 256 "brain-$VERSION.tar.gz") > "$SHA_FILE"
elif command -v sha256sum >/dev/null 2>&1; then
    (cd "$RELEASE_DIR" && sha256sum "brain-$VERSION.tar.gz") > "$SHA_FILE"
else
    log_err "no SHA256 tool found (need shasum or sha256sum)"
    exit 1
fi
SHA_VALUE=$(awk '{print $1}' "$SHA_FILE")
log_ok "wrote $SHA_FILE ($SHA_VALUE)"

# ---------------------------------------------------------------------------
# 11. Summary
# ---------------------------------------------------------------------------

# Tarball size — portable (BSD + GNU ``wc -c``).
if command -v du >/dev/null 2>&1; then
    SIZE=$(du -h "$TARBALL" | awk '{print $1}')
else
    SIZE="?"
fi
FILE_COUNT=$(tar -tzf "$TARBALL" | grep -c . || echo "0")

echo ""
echo "${C_GREEN}${C_BOLD}release tarball ready${C_RESET}"
echo ""
echo "  ${C_BOLD}version:${C_RESET}    $VERSION"
echo "  ${C_BOLD}tarball:${C_RESET}    $TARBALL"
echo "  ${C_BOLD}size:${C_RESET}       $SIZE"
echo "  ${C_BOLD}files:${C_RESET}      $FILE_COUNT"
echo "  ${C_BOLD}sha256:${C_RESET}     $SHA_VALUE"
echo ""
echo "  ${C_BOLD}top-level tree (3 levels):${C_RESET}"
# ``find -maxdepth`` is portable. Print relative paths under staging.
(cd "$STAGING_PARENT" && find "brain-$VERSION" -maxdepth 3 -mindepth 1 -type d | sort | sed 's/^/    /')
echo ""
echo "  to install locally from this tarball:"
echo "    BRAIN_RELEASE_URL=\"file://$TARBALL\" \\"
echo "      BRAIN_RELEASE_SHA256=\"$SHA_VALUE\" \\"
echo "      bash scripts/install.sh"
echo ""

# Leave staging in place for inspection unless --clean.
if [ "$CLEAN" = "1" ]; then
    rm -rf "$STAGING_PARENT"
    log_info "removed staging dir (--clean)"
else
    log_info "staging dir left at $STAGING_PARENT (for inspection)"
fi
