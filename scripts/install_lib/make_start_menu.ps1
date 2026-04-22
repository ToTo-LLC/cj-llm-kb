# scripts/install_lib/make_start_menu.ps1
#
# Plan 08 Task 8. Create a Start Menu shortcut (brain.lnk) so the user
# can launch "brain" from the Start menu or pin it to the taskbar.
# Optionally also drop a shortcut on the Desktop.
#
# Usage (dot-sourced):
#
#     . scripts/install_lib/make_start_menu.ps1
#     New-StartMenuEntry -InstallDir <path>
#     New-DesktopShortcut -InstallDir <path>
#
# PowerShell 5.1 compatible. Uses the WScript.Shell COM object — the
# native Windows pattern for producing .lnk files without admin.

Set-StrictMode -Version Latest


function _Test-ComAvailable {
    <#
    .SYNOPSIS
      Return $true if New-Object -ComObject is usable here.

    .DESCRIPTION
      Real Windows PowerShell + PowerShell 7 on Windows support COM.
      PowerShell 7 on Mac/Linux does not — ``New-Object -ComObject``
      throws "A parameter cannot be found that matches parameter name
      'ComObject'". We detect the capability rather than sniffing the
      platform so opt-in CI flows stay honest.
    #>
    try {
        $cmd = Get-Command New-Object -ErrorAction Stop
        # The -ComObject parameter only exists on the Windows build.
        if ($cmd.Parameters.ContainsKey("ComObject")) {
            return $true
        }
    } catch { }
    return $false
}


function _New-Shortcut {
    <#
    .SYNOPSIS
      Create a .lnk file at LnkPath pointing at Target with optional
      arguments + icon.

    .DESCRIPTION
      Uses the WScript.Shell COM object on real Windows. On non-Windows
      (opt-in CI only) writes a stub text file at the same path so test
      harnesses can assert the creation codepath ran; Windows installs
      always get a real .lnk.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$LnkPath,
        [Parameter(Mandatory = $true)][string]$Target,
        [string]$Arguments = "",
        [string]$IconPath = "",
        [string]$WorkingDirectory = "",
        [string]$Description = "brain — LLM-maintained second brain"
    )

    $parent = Split-Path -Parent $LnkPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    if (-not (_Test-ComAvailable)) {
        # Non-Windows opt-in path. Drop a descriptive stub so the test
        # harness can verify the codepath executed end-to-end.
        $stub = @"
brain shortcut stub (COM unavailable on this host)
TargetPath: $Target
Arguments: $Arguments
WorkingDirectory: $WorkingDirectory
IconLocation: $IconPath
Description: $Description
"@
        Set-Content -LiteralPath $LnkPath -Value $stub -Encoding ASCII -Force
        return
    }

    $ws = New-Object -ComObject WScript.Shell
    try {
        $shortcut = $ws.CreateShortcut($LnkPath)
        $shortcut.TargetPath = $Target
        if ($Arguments) { $shortcut.Arguments = $Arguments }
        if ($WorkingDirectory) { $shortcut.WorkingDirectory = $WorkingDirectory }
        if ($Description) { $shortcut.Description = $Description }
        if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
            $shortcut.IconLocation = $IconPath
        }
        $shortcut.Save()
    } finally {
        # Release the COM object — avoid leaking a handle.
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ws) | Out-Null
    }
}


function _Resolve-IconPath {
    <#
    .SYNOPSIS
      Return the install's brain.ico if Task 9 has shipped one, else
      an empty string (the shortcut will fall back to Windows' default).
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir
    )
    $icon = Join-Path $InstallDir "assets\brain.ico"
    if (Test-Path -LiteralPath $icon -PathType Leaf) {
        return $icon
    }
    return ""
}


function New-StartMenuEntry {
    <#
    .SYNOPSIS
      Create brain.lnk in the user's Start Menu\Programs folder.

    .DESCRIPTION
      The shortcut runs ``brain start`` via the shim that Write-Shim
      placed in %LOCALAPPDATA%\Microsoft\WindowsApps\. Using the shim
      means the shortcut survives install-dir moves without rewriting.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir
    )

    if (-not $env:APPDATA) {
        throw "APPDATA not set — can't locate Start Menu"
    }
    $startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    $lnkPath = Join-Path $startMenuDir "brain.lnk"

    # Target is the shim — absolute path to brain.cmd.
    $shim = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\brain.cmd"
    if (-not (Test-Path -LiteralPath $shim -PathType Leaf)) {
        throw "shim missing at $shim — run Write-Shim first"
    }

    $icon = _Resolve-IconPath -InstallDir $InstallDir

    _New-Shortcut `
        -LnkPath $lnkPath `
        -Target $shim `
        -Arguments "start" `
        -IconPath $icon `
        -WorkingDirectory $InstallDir `
        -Description "brain — open the web UI"

    Write-Host "  Start Menu entry: $lnkPath"
}


function New-DesktopShortcut {
    <#
    .SYNOPSIS
      Drop a brain.lnk shortcut on the user's Desktop.

    .DESCRIPTION
      Optional — callers decide whether to invoke (e.g. after prompting
      the user). Uses the same shim target as the Start Menu entry so
      double-click runs ``brain start``.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir
    )

    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop -or -not (Test-Path -LiteralPath $desktop)) {
        Write-Host "  Desktop folder not found — skipping desktop shortcut"
        return
    }

    $lnkPath = Join-Path $desktop "brain.lnk"
    $shim = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\brain.cmd"
    if (-not (Test-Path -LiteralPath $shim -PathType Leaf)) {
        throw "shim missing at $shim — run Write-Shim first"
    }

    $icon = _Resolve-IconPath -InstallDir $InstallDir

    _New-Shortcut `
        -LnkPath $lnkPath `
        -Target $shim `
        -Arguments "start" `
        -IconPath $icon `
        -WorkingDirectory $InstallDir `
        -Description "brain — open the web UI"

    Write-Host "  Desktop shortcut: $lnkPath"
}
