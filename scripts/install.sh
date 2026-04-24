#!/bin/bash
# scripts/install.sh — Plan 08 Task 7
#
# One-command installer for brain on macOS (primary) and Linux
# (best-effort). End state on a fresh Mac:
#
#   1. ``uv`` on PATH (installed if missing).
#   2. App tree at ~/Applications/brain/ populated from the release
#      tarball, with ``uv sync`` run and the static UI built.
#   3. Shim at ~/.local/bin/brain resolving to ``uv run --project ... brain``.
#   4. ~/Applications/brain.app/ directory wrapper so Spotlight / Dock
#      can launch the app.
#   5. ``brain doctor`` reports PASS (or prints next-action on any FAIL).
#
# Re-running this script is safe: existing installs are moved aside to
# ``<install>-prev-<timestamp>/`` before a fresh extract. On failure we
# try to roll the previous install back into place.
#
# Usage:
#   curl -fsSL <url>/install.sh | bash
#   bash scripts/install.sh                     # from a checkout
#   BRAIN_RELEASE_URL=file:///tmp/brain.tar.gz bash scripts/install.sh
#   BRAIN_INSTALL_VERBOSE=1 bash scripts/install.sh      # trace mode
#   BRAIN_INSTALL_FORCE=1 bash scripts/install.sh        # skip confirm
#
# Exit codes:
#   0 — success
#   1 — recoverable failure (network, disk, hash mismatch)
#   2 — prerequisite failure (unsupported OS/arch, missing tool)
#
# Bash 3.2 compatible (macOS /bin/bash). No associative arrays, no
# ``[[ -v ]]``, no ``${var,,}``. Quote aggressively.

set -eu

# ---------------------------------------------------------------------------
# 0. Script location + helper loading
# ---------------------------------------------------------------------------

# Resolve the directory this script lives in (follows one symlink).
SCRIPT_SOURCE="$0"
if [ -L "$SCRIPT_SOURCE" ]; then
    SCRIPT_SOURCE=$(readlink "$SCRIPT_SOURCE")
fi
SCRIPT_DIR=$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)
LIB_DIR="$SCRIPT_DIR/install_lib"

# Defaults used by BOTH the bootstrap path and the main install flow.
# Duplicated here (rather than below) so the bootstrap branch can run
# before install_lib/*.sh gets sourced. The values MUST match the main
# defaults block lower down — they are the same release asset.
BRAIN_DEFAULT_RELEASE_URL="https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/brain-0.1.0.tar.gz"
BRAIN_DEFAULT_RELEASE_SHA256="84e922d9c82b305e052270666e352356745a25cbf387c6151be4f64fe965d24a"

# Bootstrap: when install.sh was fetched standalone (``curl ... | bash``
# or ``curl -o install.sh && bash install.sh``), install_lib/ does not
# live next to the script. We download the tarball, extract it to a
# staging dir, and source helpers from there. The main install flow
# then reuses the same tarball via BRAIN_BOOTSTRAP_TARBALL so nothing
# is downloaded twice.
if [ ! -d "$LIB_DIR" ]; then
    BOOTSTRAP_URL="${BRAIN_RELEASE_URL:-$BRAIN_DEFAULT_RELEASE_URL}"
    if [ -n "${BRAIN_RELEASE_SHA256:-}" ]; then
        BOOTSTRAP_SHA256="$BRAIN_RELEASE_SHA256"
    elif [ "$BOOTSTRAP_URL" = "$BRAIN_DEFAULT_RELEASE_URL" ]; then
        BOOTSTRAP_SHA256="$BRAIN_DEFAULT_RELEASE_SHA256"
    else
        BOOTSTRAP_SHA256=""
    fi

    BOOTSTRAP_STAGING=$(mktemp -d 2>/dev/null || mktemp -d -t brain-bootstrap)
    # Clean up the staging dir on *any* exit — the main install flow
    # will copy the tarball out (or fail), and either way we don't need
    # the staging dir after main() returns. A later trap overrides this
    # with the rollback logic; we want both to run, so the later trap
    # chains in the staging cleanup.
    BRAIN_BOOTSTRAP_STAGING="$BOOTSTRAP_STAGING"
    export BRAIN_BOOTSTRAP_STAGING

    BOOTSTRAP_TARBALL="$BOOTSTRAP_STAGING/brain.tar.gz"

    echo "==> Bootstrapping install helpers"
    echo "  downloading $BOOTSTRAP_URL"

    case "$BOOTSTRAP_URL" in
        file://*)
            _src="${BOOTSTRAP_URL#file://}"
            if [ ! -f "$_src" ]; then
                echo "error: local tarball not found: $_src" >&2
                rm -rf "$BOOTSTRAP_STAGING"
                exit 1
            fi
            cp "$_src" "$BOOTSTRAP_TARBALL" || {
                echo "error: failed to copy local tarball" >&2
                rm -rf "$BOOTSTRAP_STAGING"
                exit 1
            }
            ;;
        *)
            if command -v curl >/dev/null 2>&1; then
                if ! curl -fsSL "$BOOTSTRAP_URL" -o "$BOOTSTRAP_TARBALL"; then
                    echo "error: download failed for $BOOTSTRAP_URL" >&2
                    echo "       check your network connection and retry." >&2
                    rm -rf "$BOOTSTRAP_STAGING"
                    exit 1
                fi
            elif command -v wget >/dev/null 2>&1; then
                if ! wget -q -O "$BOOTSTRAP_TARBALL" "$BOOTSTRAP_URL"; then
                    echo "error: download failed for $BOOTSTRAP_URL" >&2
                    rm -rf "$BOOTSTRAP_STAGING"
                    exit 1
                fi
            else
                echo "error: need curl or wget for bootstrap download" >&2
                echo "       Mac: xcode-select --install" >&2
                echo "       Linux: install curl via your package manager" >&2
                rm -rf "$BOOTSTRAP_STAGING"
                exit 2
            fi
            ;;
    esac

    if [ -n "$BOOTSTRAP_SHA256" ]; then
        echo "  verifying SHA256"
        if command -v shasum >/dev/null 2>&1; then
            _actual=$(shasum -a 256 "$BOOTSTRAP_TARBALL" | awk '{print $1}')
        elif command -v sha256sum >/dev/null 2>&1; then
            _actual=$(sha256sum "$BOOTSTRAP_TARBALL" | awk '{print $1}')
        else
            echo "error: no SHA256 tool found (need shasum or sha256sum)" >&2
            rm -rf "$BOOTSTRAP_STAGING"
            exit 1
        fi
        _expected_lc=$(printf '%s' "$BOOTSTRAP_SHA256" | tr '[:upper:]' '[:lower:]')
        _actual_lc=$(printf '%s' "$_actual" | tr '[:upper:]' '[:lower:]')
        if [ "$_expected_lc" != "$_actual_lc" ]; then
            echo "error: SHA256 mismatch for $BOOTSTRAP_URL" >&2
            echo "       expected: $_expected_lc" >&2
            echo "       actual:   $_actual_lc" >&2
            echo "       the download may be corrupted or tampered with." >&2
            rm -rf "$BOOTSTRAP_STAGING"
            exit 1
        fi
        echo "  ok (sha256 $_actual_lc)"
    else
        echo "  (no SHA256 pin available for bootstrap — skipping verify)"
    fi

    # Extract into the staging dir. We don't reuse fetch_tarball.sh's
    # extract helper because we can't source it yet (that's the whole
    # reason we're here). The standard-shape tarball has a single
    # top-level directory named brain-<version>/.
    if ! tar -xzf "$BOOTSTRAP_TARBALL" -C "$BOOTSTRAP_STAGING"; then
        echo "error: failed to extract bootstrap tarball" >&2
        rm -rf "$BOOTSTRAP_STAGING"
        exit 1
    fi

    # Find the single top-level dir (brain-<version>). If the tarball
    # was a bare ``git archive HEAD`` dump the helpers sit directly
    # under $BOOTSTRAP_STAGING/scripts/install_lib — handle both.
    EXTRACTED_DIR=$(find "$BOOTSTRAP_STAGING" -mindepth 1 -maxdepth 1 -type d \
        -not -name 'brain.tar.gz' 2>/dev/null | head -1)
    if [ -n "$EXTRACTED_DIR" ] && [ -d "$EXTRACTED_DIR/scripts/install_lib" ]; then
        LIB_DIR="$EXTRACTED_DIR/scripts/install_lib"
    elif [ -d "$BOOTSTRAP_STAGING/scripts/install_lib" ]; then
        # Bare tarball (no top-level prefix).
        EXTRACTED_DIR="$BOOTSTRAP_STAGING"
        LIB_DIR="$BOOTSTRAP_STAGING/scripts/install_lib"
    else
        echo "error: install_lib/ not found in bootstrap tarball" >&2
        echo "       looked in $BOOTSTRAP_STAGING" >&2
        rm -rf "$BOOTSTRAP_STAGING"
        exit 1
    fi

    # Let the main install flow reuse this tarball instead of downloading
    # it a second time. fetch_and_extract checks for this env var before
    # hitting the network.
    BRAIN_BOOTSTRAP_TARBALL="$BOOTSTRAP_TARBALL"
    export BRAIN_BOOTSTRAP_TARBALL
    echo "  bootstrap complete — sourcing helpers"
fi

# shellcheck source=install_lib/fetch_tarball.sh
. "$LIB_DIR/fetch_tarball.sh"
# shellcheck source=install_lib/fnm_setup.sh
. "$LIB_DIR/fnm_setup.sh"
# shellcheck source=install_lib/write_shim.sh
. "$LIB_DIR/write_shim.sh"
# shellcheck source=install_lib/make_app_bundle.sh
. "$LIB_DIR/make_app_bundle.sh"

# ---------------------------------------------------------------------------
# 1. Defaults + environment
# ---------------------------------------------------------------------------

BRAIN_INSTALL_VERBOSE="${BRAIN_INSTALL_VERBOSE:-0}"
if [ "$BRAIN_INSTALL_VERBOSE" = "1" ]; then
    set -x
fi

BRAIN_INSTALL_FORCE="${BRAIN_INSTALL_FORCE:-0}"
# Default tarball URL + pinned SHA256 for the currently-shipping GitHub
# release asset. ``curl -fsSL install.sh | bash`` on a clean machine Just
# Works and is integrity-verified out of the box. Override by exporting
# ``BRAIN_RELEASE_URL`` (e.g. ``file:///tmp/brain-dev.tar.gz``) for
# local/dev installs; the default SHA pin is only used when URL + SHA are
# both left at their defaults.
#
# NOTE: BRAIN_DEFAULT_RELEASE_URL + BRAIN_DEFAULT_RELEASE_SHA256 are set
# at the very top of the file (section 0) so the bootstrap branch can
# use them before install_lib/*.sh is sourced. Keep both in sync.
BRAIN_RELEASE_URL="${BRAIN_RELEASE_URL:-$BRAIN_DEFAULT_RELEASE_URL}"
if [ -z "${BRAIN_RELEASE_SHA256:-}" ] && [ "$BRAIN_RELEASE_URL" = "$BRAIN_DEFAULT_RELEASE_URL" ]; then
    BRAIN_RELEASE_SHA256="$BRAIN_DEFAULT_RELEASE_SHA256"
else
    BRAIN_RELEASE_SHA256="${BRAIN_RELEASE_SHA256:-}"
fi
BRAIN_NODE_VERSION="${BRAIN_NODE_VERSION:-20}"
# Skip the heavy Node-dependent build steps. Useful for tests and for
# offline installs where the tarball already ships a prebuilt UI under
# apps/brain_web/out/.
BRAIN_SKIP_NODE="${BRAIN_SKIP_NODE:-0}"
BRAIN_SKIP_DOCTOR="${BRAIN_SKIP_DOCTOR:-0}"
# Test-only escape hatch. When set, we skip the ``uv sync`` step — used
# by scripts/tests/ so integration tests can run offline in seconds.
# Not documented to end users; release builds never set it.
BRAIN_SKIP_UV_SYNC="${BRAIN_SKIP_UV_SYNC:-0}"

# ---------------------------------------------------------------------------
# 2. TTY-aware colors
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

# ---------------------------------------------------------------------------
# 3. Logging helpers
# ---------------------------------------------------------------------------

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
# 4. OS + arch detection
# ---------------------------------------------------------------------------

detect_os_arch() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    case "$OS" in
        darwin)
            PLATFORM_NAME="mac"
            case "$ARCH" in
                arm64)  PLATFORM_SLUG="darwin-arm64" ;;
                x86_64) PLATFORM_SLUG="darwin-x86_64" ;;
                *)
                    log_err "unsupported Mac arch: $ARCH"
                    exit 2
                    ;;
            esac
            ;;
        linux)
            PLATFORM_NAME="linux"
            case "$ARCH" in
                x86_64)  PLATFORM_SLUG="linux-x86_64" ;;
                aarch64) PLATFORM_SLUG="linux-aarch64" ;;
                *)
                    log_err "unsupported Linux arch: $ARCH"
                    exit 2
                    ;;
            esac
            log_warn "Linux install is best-effort."
            log_warn "Please file issues if anything breaks:"
            log_warn "  https://github.com/ToTo-LLC/cj-llm-kb/issues"
            ;;
        *)
            log_err "unsupported OS: $OS (brain supports macOS 13+ and Linux)"
            exit 2
            ;;
    esac
    export OS ARCH PLATFORM_NAME PLATFORM_SLUG
}

# ---------------------------------------------------------------------------
# 5. uv bootstrap
# ---------------------------------------------------------------------------

ensure_uv() {
    log_step "Checking for uv"
    if command -v uv >/dev/null 2>&1; then
        local uv_version
        uv_version=$(uv --version 2>/dev/null || echo "uv ?")
        log_ok "uv already present ($uv_version)"
        return 0
    fi

    log_info "uv not found; installing from https://astral.sh/uv/install.sh"

    if command -v curl >/dev/null 2>&1; then
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
            log_err "uv installer failed"
            log_err "  try: https://docs.astral.sh/uv/getting-started/installation/"
            exit 1
        fi
    elif command -v wget >/dev/null 2>&1; then
        if ! wget -qO- https://astral.sh/uv/install.sh | sh; then
            log_err "uv installer failed"
            exit 1
        fi
    else
        log_err "need curl or wget to install uv"
        log_err "  Mac: xcode-select --install"
        log_err "  Linux: install curl via your package manager"
        exit 1
    fi

    # uv's installer puts the binary in ~/.local/bin by default; source
    # its env file if present so the rest of this script can see uv.
    if [ -f "$HOME/.local/bin/env" ]; then
        # shellcheck disable=SC1091
        . "$HOME/.local/bin/env"
    fi
    # Also prepend ~/.local/bin just in case.
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) PATH="$HOME/.local/bin:$PATH" ; export PATH ;;
    esac

    if ! command -v uv >/dev/null 2>&1; then
        log_err "uv installed but not on PATH — reopen your terminal and retry"
        exit 1
    fi

    log_ok "uv installed ($(uv --version))"
}

# ---------------------------------------------------------------------------
# 6. Install directory selection
# ---------------------------------------------------------------------------

resolve_install_dir() {
    if [ -n "${BRAIN_INSTALL_DIR:-}" ]; then
        INSTALL_DIR="$BRAIN_INSTALL_DIR"
    elif [ "$PLATFORM_NAME" = "mac" ]; then
        INSTALL_DIR="$HOME/Applications/brain"
    else
        INSTALL_DIR="$HOME/.local/share/brain"
    fi
    export INSTALL_DIR
    log_info "install dir: $INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# 7. Backup existing install
# ---------------------------------------------------------------------------

# Global var — set by backup_existing_install when a backup happens.
BACKUP_DIR=""

backup_existing_install() {
    if [ ! -d "$INSTALL_DIR" ]; then
        return 0
    fi

    # If the dir is empty (e.g. first run aborted mid-extract), just remove it.
    if [ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
        rmdir "$INSTALL_DIR" 2>/dev/null || true
        return 0
    fi

    if [ "$BRAIN_INSTALL_FORCE" != "1" ] && [ -t 0 ]; then
        # Interactive + not forcing: ask.
        echo ""
        echo "  An existing install is present at $INSTALL_DIR"
        echo "  It will be moved to a timestamped backup dir, then a fresh"
        echo "  install will be extracted in its place."
        printf "  Continue? [y/N] "
        local reply
        read -r reply
        case "$reply" in
            y|Y|yes|YES) ;;
            *)
                echo "  cancelled."
                exit 0
                ;;
        esac
    fi

    local ts
    ts=$(date +%Y%m%d-%H%M%S)
    BACKUP_DIR="${INSTALL_DIR}-prev-${ts}"
    log_info "backing up existing install → $BACKUP_DIR"
    mv "$INSTALL_DIR" "$BACKUP_DIR" || {
        log_err "failed to move existing install to $BACKUP_DIR"
        exit 1
    }
    export BACKUP_DIR
}

# ---------------------------------------------------------------------------
# 8. Rollback helper (invoked on failure after backup)
# ---------------------------------------------------------------------------

rollback_install() {
    if [ -z "$BACKUP_DIR" ]; then
        return 0
    fi
    if [ ! -d "$BACKUP_DIR" ]; then
        return 0
    fi
    log_warn "rolling back to previous install at $BACKUP_DIR"
    # If a partial new install exists, nuke it.
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR" 2>/dev/null || true
    fi
    mv "$BACKUP_DIR" "$INSTALL_DIR" || {
        log_err "rollback failed — previous install remains at $BACKUP_DIR"
        return 1
    }
    log_info "rollback complete"
    BACKUP_DIR=""
}

_on_exit() {
    rc=$?
    if [ $rc -ne 0 ]; then
        rollback_install
    fi
    # Clean up the bootstrap staging dir (if any). Safe to rm even on
    # success — the tarball inside has already been copied into the
    # install's temp dir by fetch_and_extract and extracted by now.
    if [ -n "${BRAIN_BOOTSTRAP_STAGING:-}" ] && [ -d "$BRAIN_BOOTSTRAP_STAGING" ]; then
        rm -rf "$BRAIN_BOOTSTRAP_STAGING" 2>/dev/null || true
    fi
    exit $rc
}
trap _on_exit EXIT

# ---------------------------------------------------------------------------
# 9. Tarball fetch + extract
# ---------------------------------------------------------------------------

fetch_and_extract() {
    log_step "Fetching release tarball"

    if [ -z "$BRAIN_RELEASE_URL" ]; then
        # This branch only fires if the caller explicitly blanked
        # ``BRAIN_RELEASE_URL``. The default above points at the real
        # GitHub release asset, so normal ``curl | bash`` never lands here.
        log_err "no release URL configured"
        log_err "  BRAIN_RELEASE_URL was explicitly set empty."
        log_err "  unset it to use the default GitHub release, or"
        log_err "  set BRAIN_RELEASE_URL=file:///path/to/brain-dev.tar.gz"
        log_err "  (cut one with: scripts/cut-local-tarball.sh)"
        exit 1
    fi

    local tmp_dir
    tmp_dir=$(mktemp -d 2>/dev/null || mktemp -d -t brain-install)
    local tarball="$tmp_dir/brain.tar.gz"

    # Bootstrap reuse: when install.sh was curled standalone, section 0
    # already downloaded + verified the tarball. Reuse that file here
    # instead of fetching it a second time. The SHA has already been
    # checked (or explicitly skipped) during bootstrap, so skip verify.
    if [ -n "${BRAIN_BOOTSTRAP_TARBALL:-}" ] && [ -f "$BRAIN_BOOTSTRAP_TARBALL" ]; then
        log_info "reusing tarball downloaded during bootstrap"
        cp "$BRAIN_BOOTSTRAP_TARBALL" "$tarball" || {
            log_err "failed to copy bootstrap tarball"
            rm -rf "$tmp_dir"
            exit 1
        }
    elif [ -n "$BRAIN_RELEASE_SHA256" ]; then
        fetch_tarball "$BRAIN_RELEASE_URL" "$tarball" "$BRAIN_RELEASE_SHA256" || {
            rm -rf "$tmp_dir"
            exit 1
        }
    else
        # No hash pinned — use curl/wget directly, but warn loudly.
        log_warn "BRAIN_RELEASE_SHA256 not set — skipping SHA256 verification."
        log_warn "  (acceptable for local dev tarballs; never skip for release builds.)"
        case "$BRAIN_RELEASE_URL" in
            file://*)
                local src="${BRAIN_RELEASE_URL#file://}"
                if [ ! -f "$src" ]; then
                    log_err "local tarball not found: $src"
                    rm -rf "$tmp_dir"
                    exit 1
                fi
                cp "$src" "$tarball"
                ;;
            *)
                if command -v curl >/dev/null 2>&1; then
                    curl -fsSL "$BRAIN_RELEASE_URL" -o "$tarball" || {
                        log_err "download failed"
                        rm -rf "$tmp_dir"
                        exit 1
                    }
                elif command -v wget >/dev/null 2>&1; then
                    wget -q -O "$tarball" "$BRAIN_RELEASE_URL" || {
                        log_err "download failed"
                        rm -rf "$tmp_dir"
                        exit 1
                    }
                else
                    log_err "no downloader found (need curl or wget)"
                    rm -rf "$tmp_dir"
                    exit 1
                fi
                ;;
        esac
    fi

    log_step "Extracting to $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR" || {
        log_err "cannot create $INSTALL_DIR"
        rm -rf "$tmp_dir"
        exit 1
    }

    # Strip one leading path component only when the tarball has a
    # single shared top-level prefix (e.g. ``brain-v0.1.0/...``). For
    # bare ``git archive HEAD`` output every entry is a sibling of
    # the repo root (``.claude/``, ``packages/``, ``pyproject.toml``,
    # etc.) — no strip.
    #
    # Detection: list all top-level segments, dedup, count. If the
    # count is 1 *and* the segment looks like a directory (not a
    # plain file like ``pyproject.toml``), strip one component.
    local top_segments
    top_segments=$(tar -tzf "$tarball" 2>/dev/null | awk -F/ '{print $1}' | sort -u)
    local top_count
    top_count=$(printf '%s\n' "$top_segments" | grep -c .)
    local strip_args=""
    if [ "$top_count" = "1" ]; then
        # Single top-level entry — is it a directory? (We need the
        # tarball to list it with a trailing slash, which tar does
        # for directory entries.)
        if tar -tzf "$tarball" 2>/dev/null | grep -qE "^${top_segments}/$"; then
            strip_args="--strip-components=1"
        fi
    fi

    # shellcheck disable=SC2086
    tar -xzf "$tarball" -C "$INSTALL_DIR" $strip_args || {
        log_err "failed to extract tarball"
        rm -rf "$tmp_dir"
        exit 1
    }
    rm -rf "$tmp_dir"

    log_ok "extracted"
}

# ---------------------------------------------------------------------------
# 10. Python deps via uv
# ---------------------------------------------------------------------------

run_uv_sync() {
    if [ "$BRAIN_SKIP_UV_SYNC" = "1" ]; then
        log_info "BRAIN_SKIP_UV_SYNC=1 — skipping uv sync (test mode)"
        return 0
    fi

    log_step "Installing Python dependencies (uv sync)"

    # ``--no-dev`` keeps test/lint tooling out of the production install.
    # ``--all-packages`` covers the workspace members.
    if ! (cd "$INSTALL_DIR" && uv sync --all-packages --no-dev); then
        log_err "uv sync failed"
        log_err "  try again with: cd $INSTALL_DIR && uv sync --all-packages --no-dev"
        exit 1
    fi
    log_ok "python deps installed"
}

# ---------------------------------------------------------------------------
# 11. Node + pnpm + UI build
# ---------------------------------------------------------------------------

build_web_ui() {
    if [ "$BRAIN_SKIP_NODE" = "1" ]; then
        log_info "BRAIN_SKIP_NODE=1 — skipping Node install + UI build"
        # Still verify a prebuilt UI shipped in the tarball.
        if [ ! -f "$INSTALL_DIR/apps/brain_web/out/index.html" ]; then
            log_warn "no prebuilt UI found at apps/brain_web/out/index.html"
            log_warn "  'brain start' will fail without a UI bundle."
        fi
        return 0
    fi

    # If the tarball already shipped a prebuilt UI, prefer it and skip
    # the expensive Node step entirely. Release tarballs should always
    # include the UI; the git-archive dev tarball does not.
    if [ -f "$INSTALL_DIR/apps/brain_web/out/index.html" ]; then
        log_info "prebuilt UI found in tarball (apps/brain_web/out/index.html); skipping Node"
        return 0
    fi

    log_step "Installing Node $BRAIN_NODE_VERSION via fnm"
    install_fnm "$INSTALL_DIR" || exit 1
    install_node "$INSTALL_DIR" "$BRAIN_NODE_VERSION" || exit 1

    log_step "Enabling pnpm via corepack"
    if ! command -v corepack >/dev/null 2>&1; then
        log_err "corepack not found — comes with Node >=16, something is wrong"
        exit 1
    fi
    corepack enable >/dev/null 2>&1 || {
        log_warn "corepack enable emitted a warning (usually harmless)"
    }
    corepack prepare pnpm@9 --activate >/dev/null 2>&1 || {
        log_err "corepack failed to activate pnpm"
        exit 1
    }
    log_ok "pnpm $(pnpm --version 2>/dev/null || echo '?') ready"

    log_step "Building web UI (pnpm -F brain_web build)"
    if ! (cd "$INSTALL_DIR" && pnpm -F brain_web install --frozen-lockfile=false); then
        log_err "pnpm install failed"
        exit 1
    fi
    if ! (cd "$INSTALL_DIR" && pnpm -F brain_web build); then
        log_err "pnpm build failed"
        exit 1
    fi

    if [ ! -f "$INSTALL_DIR/apps/brain_web/out/index.html" ]; then
        log_err "UI build completed but apps/brain_web/out/index.html is missing"
        exit 1
    fi
    log_ok "UI built"
}

# ---------------------------------------------------------------------------
# 12. Shim + .app bundle
# ---------------------------------------------------------------------------

write_launchers() {
    log_step "Writing CLI shim"
    write_mac_shim "$INSTALL_DIR" || exit 1

    if [ "$PLATFORM_NAME" = "mac" ]; then
        log_step "Creating ~/Applications/brain.app"
        make_app_bundle "$INSTALL_DIR" || exit 1
    else
        log_info "skipping .app bundle (not Mac)"
    fi
}

# ---------------------------------------------------------------------------
# 13. Post-install doctor
# ---------------------------------------------------------------------------

run_doctor() {
    if [ "$BRAIN_SKIP_DOCTOR" = "1" ]; then
        log_info "BRAIN_SKIP_DOCTOR=1 — skipping final brain doctor run"
        return 0
    fi

    log_step "Running brain doctor"
    # Best-effort — if doctor exits non-zero we still print the output
    # so the user can see what's missing. Some checks (token file) are
    # expected to fail pre-setup.
    set +e
    (cd "$INSTALL_DIR" && uv run --project "$INSTALL_DIR" brain doctor)
    local rc=$?
    set -e
    if [ $rc -ne 0 ]; then
        log_warn "brain doctor reported issues (rc=$rc)"
        log_warn "  some FAILs pre-setup are expected (e.g. missing token)."
        log_warn "  run 'brain setup' to finish configuration."
    else
        log_ok "brain doctor green"
    fi
}

# ---------------------------------------------------------------------------
# 14. Main flow
# ---------------------------------------------------------------------------

main() {
    echo "${C_BOLD}brain installer${C_RESET}  ·  $(date '+%Y-%m-%d %H:%M')"
    echo ""

    detect_os_arch
    log_info "platform: $PLATFORM_SLUG"

    ensure_uv
    resolve_install_dir
    backup_existing_install
    fetch_and_extract
    run_uv_sync
    build_web_ui
    write_launchers
    run_doctor

    # Successful path: discard the backup. Keeps ``-prev-`` dirs tidy.
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        log_info "removing backup at $BACKUP_DIR (install succeeded)"
        rm -rf "$BACKUP_DIR" 2>/dev/null || true
        BACKUP_DIR=""
    fi

    echo ""
    echo "${C_GREEN}${C_BOLD}brain installed.${C_RESET}"
    echo "  Run ${C_BOLD}brain start${C_RESET} to launch the setup wizard in your browser."
    echo "  Documentation: https://github.com/ToTo-LLC/cj-llm-kb"
}

main "$@"
