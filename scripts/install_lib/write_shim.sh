#!/bin/bash
# scripts/install_lib/write_shim.sh
#
# Plan 08 Task 7. Write the ``brain`` shim at ~/.local/bin/brain and
# make sure ~/.local/bin/ is on the user's PATH. The shim is a tiny
# bash wrapper around ``uv run --project <install> brain "$@"`` — no
# state, no magic, easy to remove.
#
# Usage (sourced):
#   . scripts/install_lib/write_shim.sh
#   write_mac_shim "<install_dir>"
#
# Bash 3.2 compatible.

# ---------------------------------------------------------------------------
# _shim_body INSTALL_DIR UV_PATH
#   Print the shim script body to stdout. Uses ``exec`` so signals
#   (Ctrl+C) propagate cleanly and the shim doesn't linger as a
#   parent process.
#
#   UV_PATH is an absolute path to ``uv`` captured at install time so the
#   shim does not depend on the invoking shell having ``~/.local/bin`` on
#   PATH (launchd / Spotlight / .app double-click / bash subshell without
#   rc files — these all break a bare ``uv`` lookup).
# ---------------------------------------------------------------------------
_shim_body() {
    local install_dir="$1"
    local uv_path="$2"
    cat <<SHIM_EOF
#!/bin/bash
# brain — installed by scripts/install.sh (Plan 08)
# Edit is safe; re-run install.sh to regenerate.
exec "$uv_path" run --project "$install_dir" brain "\$@"
SHIM_EOF
}

# ---------------------------------------------------------------------------
# _ensure_path_hint SHELL_RC
#   Append a PATH-prepend line to SHELL_RC if it isn't there already.
#   Returns 0 if already present or appended; 1 on write error.
#   Prints one of three status lines so the top-level script can
#   decide whether to tell the user to reopen their terminal.
# ---------------------------------------------------------------------------
_ensure_path_hint() {
    local rc="$1"
    local hint='export PATH="$HOME/.local/bin:$PATH"'
    local marker='# added by brain installer (plan 08)'

    if [ ! -f "$rc" ]; then
        # Don't touch non-existent rc files for shells the user doesn't use.
        return 2
    fi

    if grep -q "$marker" "$rc" 2>/dev/null; then
        return 0
    fi

    # Also accept any pre-existing line that prepends ~/.local/bin.
    if grep -q '\.local/bin' "$rc" 2>/dev/null; then
        return 0
    fi

    {
        echo ""
        echo "$marker"
        echo "$hint"
    } >> "$rc" || return 1

    return 3  # "appended — user must reopen shell"
}

# ---------------------------------------------------------------------------
# write_mac_shim INSTALL_DIR
#   Creates ~/.local/bin/brain + ensures PATH. Emits clear status
#   messages about each step.
# ---------------------------------------------------------------------------
write_mac_shim() {
    local install_dir="$1"
    if [ -z "$install_dir" ]; then
        echo "error: write_mac_shim <install_dir>" >&2
        return 2
    fi

    local bin_dir="$HOME/.local/bin"
    local shim="$bin_dir/brain"

    # Resolve ``uv`` to an absolute path at shim-write time. install.sh's
    # ensure_uv runs before this function + guarantees uv is on PATH, so
    # a failure here is a genuine bug (not a user-facing condition) — but
    # we still emit a plain-English error rather than silently falling
    # back to bare ``uv``.
    local uv_path
    uv_path="$(command -v uv 2>/dev/null || true)"
    if [ -z "$uv_path" ]; then
        echo "error: uv not found on PATH when writing shim" >&2
        echo "       ensure_uv should have installed it before this step." >&2
        echo "       try: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
        return 2
    fi

    mkdir -p "$bin_dir" || {
        echo "error: cannot create $bin_dir" >&2
        return 1
    }

    _shim_body "$install_dir" "$uv_path" > "$shim" || {
        echo "error: failed to write $shim" >&2
        return 1
    }
    chmod +x "$shim" || {
        echo "error: failed to chmod $shim" >&2
        return 1
    }
    echo "  shim written: $shim"

    # Check whether the PATH already includes ~/.local/bin — use a
    # portable case match rather than a regex.
    case ":$PATH:" in
        *":$bin_dir:"*)
            echo "  \$HOME/.local/bin is already on PATH"
            return 0
            ;;
    esac

    # Touch the common rc files in priority order. Only write to
    # files that already exist so we don't accidentally spawn new
    # shell configs.
    local appended=0
    local any_rc=0
    local rc
    for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
        if [ -f "$rc" ]; then
            any_rc=1
            _ensure_path_hint "$rc"
            local rc_status=$?
            if [ $rc_status -eq 3 ]; then
                echo "  PATH edit applied to $rc"
                appended=1
            elif [ $rc_status -eq 0 ]; then
                echo "  PATH entry already present in $rc"
            fi
        fi
    done

    if [ $any_rc -eq 0 ]; then
        # User has no rc files — create ~/.zshrc since zsh is the
        # default on modern Macs.
        local rc="$HOME/.zshrc"
        {
            echo "# created by brain installer (plan 08)"
            echo '# added by brain installer (plan 08)'
            echo 'export PATH="$HOME/.local/bin:$PATH"'
        } > "$rc" || {
            echo "error: failed to create $rc" >&2
            return 1
        }
        echo "  created $rc with PATH entry"
        appended=1
    fi

    if [ $appended -eq 1 ]; then
        echo ""
        echo "  note: reopen your terminal (or run 'source ~/.zshrc')"
        echo "        for the 'brain' command to be on PATH."
    fi

    return 0
}
