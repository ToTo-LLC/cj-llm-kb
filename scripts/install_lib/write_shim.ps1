# scripts/install_lib/write_shim.ps1
#
# Plan 08 Task 8. Write the ``brain.cmd`` shim at
# %LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd. That directory has
# been on the default user PATH since Windows 10 build 1709 (Fall
# Creators Update, October 2017), so we usually don't need to mutate
# the user's PATH ourselves.
#
# Usage (dot-sourced):
#
#     . scripts/install_lib/write_shim.ps1
#     Write-Shim -InstallDir <path>
#
# PowerShell 5.1 compatible.

Set-StrictMode -Version Latest


function _Get-WindowsAppsDir {
    <#
    .SYNOPSIS
      Return the WindowsApps shim directory.
    #>
    if (-not $env:LOCALAPPDATA) {
        throw "LOCALAPPDATA not set — is this a user-mode shell?"
    }
    return (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps")
}


function _Resolve-UvPath {
    <#
    .SYNOPSIS
      Return the absolute path to ``uv.exe`` (or ``uv``) on this host.

    .DESCRIPTION
      install.ps1's Ensure-Uv runs before Write-Shim + guarantees uv is
      on PATH. We resolve it here so the generated shim doesn't have to
      rely on runtime PATH — that matters for Start Menu / taskbar
      launches + anywhere cmd.exe starts with a minimal env (scheduled
      tasks, services, Windows Terminal profiles, etc).
    #>
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        throw "uv not found on PATH when writing shim — ensure_uv should have installed it before this step."
    }
    return $cmd.Source
}


function _Shim-Body {
    <#
    .SYNOPSIS
      Produce the .cmd shim body for a given install dir.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir,
        [Parameter(Mandatory = $true)][string]$UvPath
    )

    # Escape ampersands + percents correctly for cmd.exe. The install
    # dir rarely contains either, but quote defensively.
    #
    # BRAIN_INSTALL_DIR is set so ``brain start`` / ``brain doctor`` /
    # ``brain upgrade`` pick up the actual versioned install path
    # (e.g. %LOCALAPPDATA%\brain-v0.1.0\), not the platform default
    # (%LOCALAPPDATA%\brain\). Without this the commands look in the
    # wrong dir and the supervisor's cwd is non-existent.
    $body = @"
@echo off
REM brain.cmd — installed by scripts\install.ps1 (Plan 08)
REM Edit is safe; re-run install.ps1 to regenerate.
if not defined BRAIN_INSTALL_DIR set "BRAIN_INSTALL_DIR=$InstallDir"
"$UvPath" run --project "$InstallDir" brain %*
"@
    return $body
}


function _Ensure-WindowsAppsOnPath {
    <#
    .SYNOPSIS
      Verify %LOCALAPPDATA%\Microsoft\WindowsApps is on the User PATH.

    .DESCRIPTION
      On Windows 10 1709+ this is the default state. On older builds
      (or if the user cleaned their PATH manually) we add it.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$WindowsAppsDir
    )

    # User PATH (not the process PATH — we want a persistent change).
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $userPath) { $userPath = "" }

    $segments = @()
    foreach ($seg in $userPath.Split(';')) {
        if (-not [string]::IsNullOrWhiteSpace($seg)) {
            $segments += $seg
        }
    }

    foreach ($seg in $segments) {
        # Case-insensitive comparison on Windows file paths.
        if ($seg.TrimEnd('\') -ieq $WindowsAppsDir.TrimEnd('\')) {
            return  # already present — nothing to do
        }
    }

    # Not present — append.
    $newSegments = $segments + $WindowsAppsDir
    $newPath = [string]::Join(';', $newSegments)
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")

    Write-Host "  added $WindowsAppsDir to User PATH"
    Write-Host "  note: reopen your terminal for the 'brain' command to be on PATH."
}


function Write-Shim {
    <#
    .SYNOPSIS
      Write %LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd +
      ensure that directory is on PATH.

    .DESCRIPTION
      WindowsApps is a UAC-free user-writable location on PATH since
      Windows 10 1709. We overwrite any existing shim so re-installs
      always point at the latest install dir.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir
    )

    $winAppsDir = _Get-WindowsAppsDir
    if (-not (Test-Path -LiteralPath $winAppsDir)) {
        New-Item -ItemType Directory -Path $winAppsDir -Force | Out-Null
    }

    $shimPath = Join-Path $winAppsDir "brain.cmd"
    $uvPath = _Resolve-UvPath
    $body = _Shim-Body -InstallDir $InstallDir -UvPath $uvPath

    # -Encoding ASCII keeps cmd.exe happy (no BOM, no UTF-16).
    Set-Content -LiteralPath $shimPath -Value $body -Encoding ASCII -Force

    Write-Host "  shim written: $shimPath"

    _Ensure-WindowsAppsOnPath -WindowsAppsDir $winAppsDir
}
