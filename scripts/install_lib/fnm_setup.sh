#!/bin/bash
# scripts/install_lib/fnm_setup.sh
#
# Plan 08 Task 7. Install fnm (Fast Node Manager) into the brain install
# tree and use it to install Node 20. The fnm binary and all node
# versions live under ``<install>/tools/fnm/`` — never on the user's
# global PATH.
#
# Usage (sourced):
#   . scripts/install_lib/fnm_setup.sh
#   install_fnm "<install_dir>"
#   install_node "<install_dir>" "20"
#   activate_fnm_env "<install_dir>"    # exports PATH + FNM_DIR for build
#
# Bash 3.2 compatible.

# ---------------------------------------------------------------------------
# _fnm_detect_platform
#   Prints the platform slug fnm's release assets use. Exits non-zero
#   with a helpful message when unsupported.
#
#   darwin + arm64  → macos-arm64
#   darwin + x86_64 → macos-x64
#   linux  + x86_64 → linux-x64
#   linux  + aarch64 → linux-arm64
# ---------------------------------------------------------------------------
_fnm_detect_platform() {
    local os arch
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)

    case "$os" in
        darwin)
            case "$arch" in
                arm64)   echo "macos-arm64" ;;
                x86_64)  echo "macos-x64" ;;
                *)
                    echo "error: unsupported Mac arch: $arch" >&2
                    return 2
                    ;;
            esac
            ;;
        linux)
            case "$arch" in
                x86_64)  echo "linux-x64" ;;
                aarch64) echo "linux-arm64" ;;
                *)
                    echo "error: unsupported Linux arch: $arch" >&2
                    return 2
                    ;;
            esac
            ;;
        *)
            echo "error: unsupported OS: $os" >&2
            return 2
            ;;
    esac
}

# ---------------------------------------------------------------------------
# install_fnm INSTALL_DIR
#   Download the fnm binary for this platform and unzip it into
#   <install>/tools/fnm/. Idempotent — if the binary already exists,
#   skip the download.
# ---------------------------------------------------------------------------
install_fnm() {
    local install_dir="$1"
    if [ -z "$install_dir" ]; then
        echo "error: install_fnm <install_dir>" >&2
        return 2
    fi

    local fnm_root="$install_dir/tools/fnm"
    local fnm_bin="$fnm_root/fnm"

    if [ -x "$fnm_bin" ]; then
        echo "  fnm already installed at $fnm_bin"
        return 0
    fi

    mkdir -p "$fnm_root"

    local platform
    platform=$(_fnm_detect_platform) || return $?

    # We pin to "latest" — GitHub redirects to the current release
    # asset. For reproducible builds we could pin a version, but this
    # is the documented install pattern and avoids a quarterly
    # maintenance task.
    local url="https://github.com/Schniz/fnm/releases/latest/download/fnm-$platform.zip"
    local zip_path="$fnm_root/fnm.zip"

    echo "  downloading fnm for $platform"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$zip_path" || {
            echo "error: failed to download fnm from $url" >&2
            return 1
        }
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$zip_path" "$url" || {
            echo "error: failed to download fnm from $url" >&2
            return 1
        }
    else
        echo "error: need curl or wget to download fnm" >&2
        return 1
    fi

    # macOS ships unzip; Debian/Ubuntu do too. If it's missing, give a
    # clean fix-hint rather than a noisy traceback.
    if ! command -v unzip >/dev/null 2>&1; then
        echo "error: 'unzip' not found — install it to continue" >&2
        echo "       Mac:   brew install unzip   (if somehow missing)" >&2
        echo "       Linux: sudo apt-get install unzip" >&2
        return 1
    fi

    unzip -q -o "$zip_path" -d "$fnm_root" || {
        echo "error: failed to extract fnm archive" >&2
        return 1
    }
    rm -f "$zip_path"

    chmod +x "$fnm_bin" 2>/dev/null || true

    if [ ! -x "$fnm_bin" ]; then
        echo "error: fnm binary missing after extract at $fnm_bin" >&2
        return 1
    fi

    echo "  fnm installed at $fnm_bin"
    return 0
}

# ---------------------------------------------------------------------------
# activate_fnm_env INSTALL_DIR
#   Export PATH + FNM_DIR for this shell only. Callers who spawn
#   subprocesses inherit; other shells do not. Build uses this; runtime
#   never does.
# ---------------------------------------------------------------------------
activate_fnm_env() {
    local install_dir="$1"
    if [ -z "$install_dir" ]; then
        echo "error: activate_fnm_env <install_dir>" >&2
        return 2
    fi

    FNM_DIR="$install_dir/tools/fnm"
    export FNM_DIR
    # Put fnm on PATH so ``fnm exec`` etc. resolve.
    PATH="$FNM_DIR:$PATH"
    export PATH
    # Also ensure the active node version's bin dir is on PATH when
    # one is selected later.
    if [ -d "$FNM_DIR/aliases/default/bin" ]; then
        PATH="$FNM_DIR/aliases/default/bin:$PATH"
        export PATH
    fi
}

# ---------------------------------------------------------------------------
# install_node INSTALL_DIR VERSION
#   Use fnm to install Node at VERSION into the install tree and set
#   it as the default. Idempotent — skips the download if the version
#   is already present.
# ---------------------------------------------------------------------------
install_node() {
    local install_dir="$1"
    local version="$2"
    if [ -z "$install_dir" ] || [ -z "$version" ]; then
        echo "error: install_node <install_dir> <version>" >&2
        return 2
    fi

    activate_fnm_env "$install_dir"

    local fnm_bin="$install_dir/tools/fnm/fnm"
    if [ ! -x "$fnm_bin" ]; then
        echo "error: fnm not installed at $fnm_bin; call install_fnm first" >&2
        return 1
    fi

    # Check: is this version already installed?
    if "$fnm_bin" list 2>/dev/null | grep -q "v$version"; then
        echo "  node $version already installed"
    else
        echo "  installing node $version (via fnm)"
        if ! "$fnm_bin" install "$version" >/dev/null 2>&1; then
            # Surface the real error on retry so users can diagnose.
            "$fnm_bin" install "$version" || {
                echo "error: fnm failed to install node $version" >&2
                return 1
            }
        fi
    fi

    # Set as default so activate_fnm_env picks up the bin dir on re-activate.
    "$fnm_bin" default "$version" >/dev/null 2>&1 || true
    "$fnm_bin" use "$version" >/dev/null 2>&1 || true

    # Re-activate to pick up the newly-aliased default bin dir.
    activate_fnm_env "$install_dir"

    if ! command -v node >/dev/null 2>&1; then
        echo "error: node not on PATH after install — fnm activation failed" >&2
        return 1
    fi

    local node_version
    node_version=$(node --version)
    echo "  node $node_version ready"
    return 0
}
