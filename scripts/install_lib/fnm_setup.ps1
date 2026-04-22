# scripts/install_lib/fnm_setup.ps1
#
# Plan 08 Task 8. Install fnm (Fast Node Manager) into the brain install
# tree and use it to install Node 20. The fnm binary and all node
# versions live under ``<install>\tools\fnm\`` — never on the user's
# global PATH.
#
# Usage (dot-sourced):
#
#     . scripts/install_lib/fnm_setup.ps1
#     Install-Fnm -InstallDir <path>
#     Install-Node -InstallDir <path> -NodeVersion 20
#     Activate-FnmEnv -InstallDir <path>
#
# PowerShell 5.1 compatible.

Set-StrictMode -Version Latest


function _Fnm-PlatformSlug {
    <#
    .SYNOPSIS
      Return the fnm release asset slug for the current platform.

      Windows x64   → windows
      Windows ARM64 → arm64 (best-effort; fnm has ARM64 artifact since v1.38)
    #>
    $arch = $env:PROCESSOR_ARCHITECTURE
    # WOW64 runs 32-bit PS on 64-bit OS; consult PROCESSOR_ARCHITEW6432.
    if ($arch -eq "x86" -and $env:PROCESSOR_ARCHITEW6432) {
        $arch = $env:PROCESSOR_ARCHITEW6432
    }

    switch ($arch) {
        "AMD64" { return "windows" }
        "ARM64" { return "arm64" }
        default {
            throw "unsupported Windows arch: $arch (brain supports AMD64 / ARM64)"
        }
    }
}


function Install-Fnm {
    <#
    .SYNOPSIS
      Download the fnm binary and unzip it into <install>\tools\fnm\.

    .DESCRIPTION
      Idempotent — if the binary already exists, skip the download.
      Uses Invoke-WebRequest + Expand-Archive (both PS 5.1 native).
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir
    )

    $fnmRoot = Join-Path $InstallDir "tools\fnm"
    $fnmBin = Join-Path $fnmRoot "fnm.exe"

    if (Test-Path -LiteralPath $fnmBin -PathType Leaf) {
        Write-Host "  fnm already installed at $fnmBin"
        return
    }

    if (-not (Test-Path -LiteralPath $fnmRoot)) {
        New-Item -ItemType Directory -Path $fnmRoot -Force | Out-Null
    }

    $platform = _Fnm-PlatformSlug
    $zipPath = Join-Path $fnmRoot "fnm.zip"
    $url = "https://github.com/Schniz/fnm/releases/latest/download/fnm-$platform.zip"

    Write-Host "  downloading fnm for $platform"
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = `
            [System.Net.ServicePointManager]::SecurityProtocol -bor `
            [System.Net.SecurityProtocolType]::Tls12
    } catch { }

    try {
        Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing `
            -ErrorAction Stop | Out-Null
    } catch {
        throw "failed to download fnm from $url : $($_.Exception.Message)"
    }

    try {
        Expand-Archive -LiteralPath $zipPath -DestinationPath $fnmRoot -Force
    } catch {
        throw "failed to extract fnm archive: $($_.Exception.Message)"
    }

    Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue

    if (-not (Test-Path -LiteralPath $fnmBin -PathType Leaf)) {
        throw "fnm.exe missing after extract at $fnmBin"
    }

    Write-Host "  fnm installed at $fnmBin"
}


function Activate-FnmEnv {
    <#
    .SYNOPSIS
      Prepend fnm + the active Node bin dir to this process's PATH.

    .DESCRIPTION
      Affects the current PowerShell process only. Child processes
      inherit the change; other shells do not.

      Returns the fnm.exe path so callers can invoke it directly.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir
    )

    $fnmRoot = Join-Path $InstallDir "tools\fnm"
    $fnmBin = Join-Path $fnmRoot "fnm.exe"

    $env:FNM_DIR = $fnmRoot

    # Prepend fnm root to PATH for this process.
    if ($env:PATH -notlike "*$fnmRoot*") {
        $env:PATH = "$fnmRoot;$env:PATH"
    }

    # If a default Node has been aliased, prepend its installation bin.
    $nodeBin = Join-Path $fnmRoot "aliases\default\installation"
    if (Test-Path -LiteralPath $nodeBin) {
        if ($env:PATH -notlike "*$nodeBin*") {
            $env:PATH = "$nodeBin;$env:PATH"
        }
    }

    return $fnmBin
}


function Install-Node {
    <#
    .SYNOPSIS
      Install Node at <NodeVersion> via fnm into the install tree.

    .DESCRIPTION
      Idempotent — if the version is already installed, skip. Sets it
      as fnm's default so Activate-FnmEnv picks it up on re-activate.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir,
        [Parameter(Mandatory = $true)][string]$NodeVersion
    )

    $fnmBin = Activate-FnmEnv -InstallDir $InstallDir
    if (-not (Test-Path -LiteralPath $fnmBin -PathType Leaf)) {
        throw "fnm not installed at $fnmBin; call Install-Fnm first"
    }

    # Is this version already present?
    $listing = & $fnmBin list 2>$null
    $alreadyInstalled = $false
    if ($LASTEXITCODE -eq 0 -and $listing) {
        foreach ($line in $listing) {
            if ($line -match "v$NodeVersion(\.|$)") {
                $alreadyInstalled = $true
                break
            }
        }
    }

    if ($alreadyInstalled) {
        Write-Host "  node $NodeVersion already installed"
    } else {
        Write-Host "  installing node $NodeVersion (via fnm)"
        & $fnmBin install $NodeVersion
        if ($LASTEXITCODE -ne 0) {
            throw "fnm failed to install node $NodeVersion (exit $LASTEXITCODE)"
        }
    }

    & $fnmBin default $NodeVersion 2>$null | Out-Null
    & $fnmBin use $NodeVersion 2>$null | Out-Null

    # Re-activate so the newly-aliased default bin dir is on PATH.
    Activate-FnmEnv -InstallDir $InstallDir | Out-Null

    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($null -eq $node) {
        throw "node not on PATH after install — fnm activation failed"
    }

    $nodeVer = & node --version
    Write-Host "  node $nodeVer ready"
}
