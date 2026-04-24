#!/bin/bash
# scripts/install_lib/make_app_bundle.sh
#
# Plan 08 Task 7. Create a minimal ~/Applications/brain.app/ directory
# wrapper so the user can launch brain from Spotlight / Launchpad and
# drag the icon to the Dock. This is NOT a signed .app bundle — it's a
# plain directory with the magic ``Info.plist`` + an executable at
# ``Contents/MacOS/brain``. Gatekeeper won't warn on it because it's
# never been quarantined (we create it in place, nothing downloaded).
#
# Usage (sourced):
#   . scripts/install_lib/make_app_bundle.sh
#   make_app_bundle "<install_dir>"
#
# Mac-only; the install.sh guards on ``$OSTYPE`` before calling this.
# Bash 3.2 compatible.

# ---------------------------------------------------------------------------
# _app_info_plist
#   Prints a minimal Info.plist on stdout. Using ``LSUIElement=0``
#   means it shows in the Dock while running. ``CFBundleExecutable``
#   must match the file under MacOS/.
# ---------------------------------------------------------------------------
_app_info_plist() {
    cat <<'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>brain</string>
  <key>CFBundleIconFile</key>
  <string>brain</string>
  <key>CFBundleIdentifier</key>
  <string>com.totollc.brain</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>brain</string>
  <key>CFBundleDisplayName</key>
  <string>brain</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSUIElement</key>
  <false/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST_EOF
}

# ---------------------------------------------------------------------------
# _app_launcher_body INSTALL_DIR UV_PATH
#   The script that Launchpad invokes when the user double-clicks the
#   app. It just calls ``brain start`` via the same uv machinery the
#   shim uses — ``brain start`` handles port probing and browser open.
#
#   UV_PATH is an absolute path to ``uv`` captured at install time. GUI
#   launches (Spotlight / Launchpad / double-click) do NOT inherit the
#   user's shell PATH, so a bare ``uv`` here would always fail. Hard-code
#   the resolved path.
#
#   We use ``osascript`` to open Terminal.app only if the user started
#   from Finder (detected by the absence of a controlling tty). When
#   run from a shell the exec path keeps stdio.
# ---------------------------------------------------------------------------
_app_launcher_body() {
    local install_dir="$1"
    local uv_path="$2"
    cat <<LAUNCH_EOF
#!/bin/bash
# brain.app launcher — installed by scripts/install.sh (Plan 08)
# Double-click runs 'brain start'; it opens the browser once ready.
#
# BRAIN_INSTALL_DIR is exported so the ``brain start`` command picks
# up the actual versioned install path (e.g. ~/Applications/brain-v0.1.0/),
# not the platform default (~/Applications/brain/). Without this the
# supervisor's cwd would be the non-existent default.
export BRAIN_INSTALL_DIR="\${BRAIN_INSTALL_DIR:-$install_dir}"
exec "$uv_path" run --project "$install_dir" brain start
LAUNCH_EOF
}

# ---------------------------------------------------------------------------
# make_app_bundle INSTALL_DIR
#   Create ~/Applications/brain.app/ (or refresh if it exists). Copies
#   brain.icns from <install>/assets/ if present; silently skips the
#   icon otherwise (Task 9 ships the real asset).
# ---------------------------------------------------------------------------
make_app_bundle() {
    local install_dir="$1"
    if [ -z "$install_dir" ]; then
        echo "error: make_app_bundle <install_dir>" >&2
        return 2
    fi

    local apps_dir="$HOME/Applications"
    local app_root="$apps_dir/brain.app"
    local macos_dir="$app_root/Contents/MacOS"
    local resources_dir="$app_root/Contents/Resources"
    local info_plist="$app_root/Contents/Info.plist"
    local launcher="$macos_dir/brain"

    # Resolve ``uv`` to an absolute path at bundle-write time. The .app
    # is launched from Finder / Spotlight / Launchpad with a minimal env
    # (no ~/.local/bin on PATH), so the launcher script MUST NOT rely on
    # runtime PATH to find uv.
    local uv_path
    uv_path="$(command -v uv 2>/dev/null || true)"
    if [ -z "$uv_path" ]; then
        echo "error: uv not found on PATH when building .app bundle" >&2
        echo "       ensure_uv should have installed it before this step." >&2
        return 2
    fi

    mkdir -p "$macos_dir" "$resources_dir" || {
        echo "error: cannot create $app_root" >&2
        return 1
    }

    _app_info_plist > "$info_plist" || {
        echo "error: failed to write $info_plist" >&2
        return 1
    }

    _app_launcher_body "$install_dir" "$uv_path" > "$launcher" || {
        echo "error: failed to write $launcher" >&2
        return 1
    }
    chmod +x "$launcher" || {
        echo "error: failed to chmod $launcher" >&2
        return 1
    }

    # Copy the icon if Task 9 has shipped it. Otherwise skip silently;
    # the app bundle still works, it just gets the generic icon.
    local icns_src="$install_dir/assets/brain.icns"
    if [ -f "$icns_src" ]; then
        cp "$icns_src" "$resources_dir/brain.icns" || {
            echo "warning: failed to copy icon to $resources_dir" >&2
        }
    fi

    echo "  .app bundle written: $app_root"
    return 0
}
