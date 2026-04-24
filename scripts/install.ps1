# scripts/install.ps1 — Plan 08 Task 8
#
# One-command installer for brain on Windows 11 (Windows 10 build
# 19041+ also supported). End state on a fresh box:
#
#   1. ``uv`` on PATH (installed if missing).
#   2. App tree at %LOCALAPPDATA%\brain\ populated from the release
#      tarball, with ``uv sync`` run and the static UI built.
#   3. Shim at %LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd which is
#      on the default user PATH.
#   4. Start Menu entry (brain.lnk) so the user can launch from the
#      Start button or pin to the taskbar.
#   5. ``brain doctor`` reports PASS (or prints next-action on any FAIL).
#
# Re-running this script is safe: existing installs are moved aside to
# ``<install>-prev-<timestamp>\`` before a fresh extract. On failure we
# try to roll the previous install back into place.
#
# Usage:
#
#     irm <url>/install.ps1 | iex
#     pwsh -ExecutionPolicy Bypass -File scripts\install.ps1
#     $env:BRAIN_RELEASE_URL = "file:///C:/tmp/brain.tar.gz"; .\install.ps1
#
# Exit codes:
#     0 — success
#     1 — recoverable failure (network, disk, hash mismatch)
#     2 — prerequisite failure (unsupported OS/arch, missing tool)
#
# PowerShell 5.1 compatible (ships in Windows 10+). No PS 7-only
# syntax (no ??, no ternary ? :, no pipeline-parallel). Tested against
# both Windows PowerShell 5.1 and PowerShell 7.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"


# ---------------------------------------------------------------------------
# 0. Script location + helper loading
# ---------------------------------------------------------------------------

$ScriptPath = $MyInvocation.MyCommand.Path
if (-not $ScriptPath) {
    # Fallback when piped through iex.
    $ScriptPath = $PSCommandPath
}
if ($ScriptPath) {
    $ScriptDir = Split-Path -Parent $ScriptPath
} else {
    $ScriptDir = (Get-Location).Path
}
$LibDir = Join-Path $ScriptDir "install_lib"

# Defaults used by BOTH the bootstrap branch and the main flow.
# Duplicated below in the defaults section — keep in sync. These must
# sit above the bootstrap because the bootstrap fires before we source
# install_lib/*.ps1 (which is the reason we're bootstrapping at all).
$BrainDefaultReleaseUrl = "https://github.com/ToTo-LLC/cj-llm-kb/releases/download/v0.1.0/brain-0.1.0.tar.gz"
$BrainDefaultReleaseSha256 = "657f9feaab04fc2a54fe9089b226ae7d118a6c523cc6c03b72dbaba829592c1a"

# Track any bootstrap staging dir so we can clean it up on exit.
$script:BootstrapStaging = ""

# Bootstrap: when install.ps1 was fetched standalone (``irm ... | iex``
# or ``Invoke-WebRequest -OutFile install.ps1 + pwsh -File``),
# install_lib/ does not live next to the script. Download the tarball,
# extract it to a staging dir, and source helpers from there. The main
# install flow then reuses the same tarball via
# $env:BRAIN_BOOTSTRAP_TARBALL so nothing is downloaded twice.
if (-not (Test-Path -LiteralPath $LibDir -PathType Container)) {
    $_BootstrapUrl = [Environment]::GetEnvironmentVariable("BRAIN_RELEASE_URL", "Process")
    if ([string]::IsNullOrEmpty($_BootstrapUrl)) {
        $_BootstrapUrl = $BrainDefaultReleaseUrl
    }
    $_BootstrapSha = [Environment]::GetEnvironmentVariable("BRAIN_RELEASE_SHA256", "Process")
    if ([string]::IsNullOrEmpty($_BootstrapSha)) {
        if ($_BootstrapUrl -eq $BrainDefaultReleaseUrl) {
            $_BootstrapSha = $BrainDefaultReleaseSha256
        } else {
            $_BootstrapSha = ""
        }
    }

    $_BootstrapStaging = Join-Path ([System.IO.Path]::GetTempPath()) `
        ("brain-bootstrap-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $_BootstrapStaging -Force | Out-Null
    $script:BootstrapStaging = $_BootstrapStaging

    $_BootstrapTarball = Join-Path $_BootstrapStaging "brain.tar.gz"

    Write-Host "==> Bootstrapping install helpers" -ForegroundColor Cyan
    Write-Host "  downloading $_BootstrapUrl"

    try {
        if ($_BootstrapUrl -like "file:///*") {
            $_rawPath = $_BootstrapUrl.Substring("file:///".Length)
            if ($_rawPath -match '^[A-Za-z]:') {
                $_localPath = $_rawPath -replace '/', '\'
            } else {
                $_localPath = "/" + $_rawPath
            }
            if (-not (Test-Path -LiteralPath $_localPath -PathType Leaf)) {
                throw "local tarball not found: $_localPath"
            }
            Copy-Item -LiteralPath $_localPath -Destination $_BootstrapTarball -Force
        } else {
            # Force TLS 1.2 on PS 5.1 where the default may still be
            # SSL3/TLS1.0. This is a no-op on PS 7.
            try {
                [System.Net.ServicePointManager]::SecurityProtocol = `
                    [System.Net.ServicePointManager]::SecurityProtocol -bor `
                    [System.Net.SecurityProtocolType]::Tls12
            } catch { }
            Invoke-WebRequest -Uri $_BootstrapUrl -OutFile $_BootstrapTarball `
                -UseBasicParsing -ErrorAction Stop | Out-Null
        }
    } catch {
        Write-Host "error: bootstrap download failed for $_BootstrapUrl" -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
        Remove-Item -LiteralPath $_BootstrapStaging -Force -Recurse `
            -ErrorAction SilentlyContinue
        exit 1
    }

    if (-not [string]::IsNullOrEmpty($_BootstrapSha)) {
        Write-Host "  verifying SHA256"
        $_actual = (Get-FileHash -LiteralPath $_BootstrapTarball -Algorithm SHA256).Hash.ToLowerInvariant()
        $_expected = $_BootstrapSha.ToLowerInvariant()
        if ($_actual -ne $_expected) {
            Write-Host "error: SHA256 mismatch for $_BootstrapUrl" -ForegroundColor Red
            Write-Host "       expected: $_expected" -ForegroundColor Red
            Write-Host "       actual:   $_actual" -ForegroundColor Red
            Write-Host "       the download may be corrupted or tampered with." -ForegroundColor Red
            Remove-Item -LiteralPath $_BootstrapStaging -Force -Recurse `
                -ErrorAction SilentlyContinue
            exit 1
        }
        Write-Host "  ok (sha256 $_actual)"
    } else {
        Write-Host "  (no SHA256 pin available for bootstrap — skipping verify)"
    }

    # Extract. Requires tar.exe on PATH (Windows 10 build 17063+).
    $_tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -eq $_tar) { $_tar = Get-Command tar -ErrorAction SilentlyContinue }
    if ($null -eq $_tar) {
        Write-Host "error: tar.exe not found on PATH" -ForegroundColor Red
        Write-Host "       brain needs the bsdtar that ships with Windows 10 build 17063+." -ForegroundColor Red
        Remove-Item -LiteralPath $_BootstrapStaging -Force -Recurse `
            -ErrorAction SilentlyContinue
        exit 2
    }

    & $_tar.Source -xzf $_BootstrapTarball -C $_BootstrapStaging
    if ($LASTEXITCODE -ne 0) {
        Write-Host "error: failed to extract bootstrap tarball (exit $LASTEXITCODE)" -ForegroundColor Red
        Remove-Item -LiteralPath $_BootstrapStaging -Force -Recurse `
            -ErrorAction SilentlyContinue
        exit 1
    }

    # Find the single top-level dir (brain-<version>). Fall back to the
    # staging dir itself if the tarball was a bare git-archive dump.
    $_extracted = Get-ChildItem -LiteralPath $_BootstrapStaging -Directory `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($_extracted -and (Test-Path -LiteralPath (Join-Path $_extracted.FullName "scripts\install_lib") -PathType Container)) {
        $LibDir = Join-Path $_extracted.FullName "scripts\install_lib"
    } elseif (Test-Path -LiteralPath (Join-Path $_BootstrapStaging "scripts\install_lib") -PathType Container) {
        $LibDir = Join-Path $_BootstrapStaging "scripts\install_lib"
    } else {
        Write-Host "error: install_lib/ not found in bootstrap tarball" -ForegroundColor Red
        Write-Host "       looked in $_BootstrapStaging" -ForegroundColor Red
        Remove-Item -LiteralPath $_BootstrapStaging -Force -Recurse `
            -ErrorAction SilentlyContinue
        exit 1
    }

    # Let the main install flow reuse this tarball instead of fetching
    # it a second time. Fetch-AndExtract checks for this env var before
    # hitting the network.
    $env:BRAIN_BOOTSTRAP_TARBALL = $_BootstrapTarball
    Write-Host "  bootstrap complete — sourcing helpers"
}

. (Join-Path $LibDir "fetch_tarball.ps1")
. (Join-Path $LibDir "fnm_setup.ps1")
. (Join-Path $LibDir "write_shim.ps1")
. (Join-Path $LibDir "make_start_menu.ps1")


# ---------------------------------------------------------------------------
# 1. Defaults + environment
# ---------------------------------------------------------------------------

function _Get-EnvDefault {
    param([string]$Name, [string]$Default)
    $val = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrEmpty($val)) { return $Default }
    return $val
}

$BrainInstallVerbose = _Get-EnvDefault "BRAIN_INSTALL_VERBOSE" "0"
if ($BrainInstallVerbose -eq "1") {
    $VerbosePreference = "Continue"
}

$BrainInstallForce = _Get-EnvDefault "BRAIN_INSTALL_FORCE" "0"
# Default tarball URL + pinned SHA256 for the currently-shipping GitHub
# release asset. ``irm install.ps1 | iex`` on a clean machine Just Works
# and is integrity-verified out of the box. Override by setting
# $env:BRAIN_RELEASE_URL (e.g. "file:///C:/tmp/brain-dev.tar.gz") for
# local/dev installs; the default SHA pin is only used when URL + SHA are
# both left at their defaults.
#
# NOTE: $BrainDefaultReleaseUrl + $BrainDefaultReleaseSha256 are set at
# the very top of the file (section 0) so the bootstrap branch can use
# them before install_lib/*.ps1 is sourced. Keep both in sync.
$BrainReleaseUrl = _Get-EnvDefault "BRAIN_RELEASE_URL" $BrainDefaultReleaseUrl
$BrainReleaseSha256Raw = _Get-EnvDefault "BRAIN_RELEASE_SHA256" ""
if ([string]::IsNullOrEmpty($BrainReleaseSha256Raw) -and ($BrainReleaseUrl -eq $BrainDefaultReleaseUrl)) {
    $BrainReleaseSha256 = $BrainDefaultReleaseSha256
} else {
    $BrainReleaseSha256 = $BrainReleaseSha256Raw
}
$BrainNodeVersion = _Get-EnvDefault "BRAIN_NODE_VERSION" "20"

# Skip the heavy Node build step (offline + test mode).
$BrainSkipNode = _Get-EnvDefault "BRAIN_SKIP_NODE" "0"
$BrainSkipDoctor = _Get-EnvDefault "BRAIN_SKIP_DOCTOR" "0"
# Test-only escape hatch. Keeps integration tests running offline in seconds.
$BrainSkipUvSync = _Get-EnvDefault "BRAIN_SKIP_UV_SYNC" "0"
# Test-only: skip the optional Desktop shortcut prompt.
$BrainSkipDesktop = _Get-EnvDefault "BRAIN_SKIP_DESKTOP" "1"


# ---------------------------------------------------------------------------
# 2. Logging helpers
# ---------------------------------------------------------------------------

function Log-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}
function Log-Info {
    param([string]$Message)
    Write-Host "  $Message"
}
function Log-Ok {
    param([string]$Message)
    Write-Host "  ok " -ForegroundColor Green -NoNewline
    Write-Host $Message
}
function Log-Warn {
    param([string]$Message)
    Write-Host "warning: $Message" -ForegroundColor Yellow
}
function Log-Err {
    param([string]$Message)
    Write-Host "error: $Message" -ForegroundColor Red
}


# ---------------------------------------------------------------------------
# 3. OS + arch detection
# ---------------------------------------------------------------------------

function Assert-WindowsSupported {
    <#
    .SYNOPSIS
      Fail with exit code 2 if we're not on a supported Windows build.

      Targets Windows 10 build 19041+ / Windows 11. Older builds miss
      features we rely on (e.g. the default WindowsApps PATH entry, and
      modern tar.exe).

      Also runs under -Skip when BRAIN_INSTALL_PS1_CI=1 so we can
      opt-in on non-Windows dev boxes for test harness purposes.
    #>
    $ciOverride = _Get-EnvDefault "BRAIN_INSTALL_PS1_CI" "0"
    if ($ciOverride -eq "1") {
        Log-Info "BRAIN_INSTALL_PS1_CI=1 — skipping Windows version gate"
        return "ci-override"
    }

    if (-not $IsWindows -and -not $env:OS) {
        # On PS 5.1 $IsWindows doesn't exist; treat $env:OS presence as
        # the signal. On PS 7 both should agree.
        Log-Err "install.ps1 runs on Windows only"
        exit 2
    }
    if ($env:OS -and $env:OS -ne "Windows_NT") {
        Log-Err "install.ps1 requires Windows"
        exit 2
    }

    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        $build = [int]($os.BuildNumber)
        if ($build -lt 19041) {
            Log-Err "Windows build $build is too old (need 19041+ / Win11)"
            Log-Err "  Please update Windows: Settings → Windows Update"
            exit 2
        }
        Log-Info "windows build: $build"
    } catch {
        # CIM can fail inside stripped-down Sandbox / CI. Warn and continue.
        Log-Warn "could not query Windows build number: $($_.Exception.Message)"
    }

    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "x86" -and $env:PROCESSOR_ARCHITEW6432) {
        $arch = $env:PROCESSOR_ARCHITEW6432
    }
    switch ($arch) {
        "AMD64" { return "windows-amd64" }
        "ARM64" { return "windows-arm64" }
        default {
            Log-Err "unsupported Windows arch: $arch"
            exit 2
        }
    }
}


# ---------------------------------------------------------------------------
# 4. uv bootstrap
# ---------------------------------------------------------------------------

function Ensure-Uv {
    Log-Step "Checking for uv"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $uv) {
        $uvVersion = (& uv --version 2>$null)
        if (-not $uvVersion) { $uvVersion = "uv ?" }
        Log-Ok "uv already present ($uvVersion)"
        return
    }

    Log-Info "uv not found; installing from https://astral.sh/uv/install.ps1"

    try {
        [System.Net.ServicePointManager]::SecurityProtocol = `
            [System.Net.ServicePointManager]::SecurityProtocol -bor `
            [System.Net.SecurityProtocolType]::Tls12
    } catch { }

    try {
        $installerScript = Invoke-WebRequest `
            -Uri "https://astral.sh/uv/install.ps1" `
            -UseBasicParsing -ErrorAction Stop
        Invoke-Expression $installerScript.Content
    } catch {
        Log-Err "uv installer failed: $($_.Exception.Message)"
        Log-Err "  try: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }

    # The uv installer drops uv.exe in %USERPROFILE%\.local\bin\ by
    # default. Prepend that path for this session so subsequent steps
    # see uv.
    $uvBin = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path -LiteralPath $uvBin) {
        $env:PATH = "$uvBin;$env:PATH"
    }
    # uv also ships in %LOCALAPPDATA%\Programs\uv\ on some installers.
    $uvAlt = Join-Path $env:LOCALAPPDATA "Programs\uv"
    if (Test-Path -LiteralPath $uvAlt) {
        $env:PATH = "$uvAlt;$env:PATH"
    }

    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -eq $uv) {
        Log-Err "uv installed but not on PATH — reopen your terminal and retry"
        exit 1
    }

    $uvVersion = (& uv --version 2>$null)
    Log-Ok "uv installed ($uvVersion)"
}


# ---------------------------------------------------------------------------
# 5. Install directory selection
# ---------------------------------------------------------------------------

function Resolve-InstallDir {
    $override = _Get-EnvDefault "BRAIN_INSTALL_DIR" ""
    if (-not [string]::IsNullOrEmpty($override)) {
        $script:InstallDir = $override
    } elseif ($env:LOCALAPPDATA) {
        $script:InstallDir = Join-Path $env:LOCALAPPDATA "brain"
    } else {
        throw "LOCALAPPDATA not set — can't choose an install dir"
    }
    Log-Info "install dir: $script:InstallDir"
}


# ---------------------------------------------------------------------------
# 6. Backup existing install
# ---------------------------------------------------------------------------

$script:BackupDir = ""

function Backup-ExistingInstall {
    if (-not (Test-Path -LiteralPath $script:InstallDir)) { return }

    $items = Get-ChildItem -LiteralPath $script:InstallDir -Force -ErrorAction SilentlyContinue
    if ($null -eq $items -or $items.Count -eq 0) {
        # Empty dir (e.g. aborted first run) — just remove.
        Remove-Item -LiteralPath $script:InstallDir -Force -Recurse `
            -ErrorAction SilentlyContinue
        return
    }

    # Interactive + not forcing: ask. Note: when piped through `iex`,
    # stdin may not be a tty; we treat that as "force" to avoid hanging.
    $isInteractive = [Environment]::UserInteractive -and ($Host.Name -ne "Default Host")
    if ($BrainInstallForce -ne "1" -and $isInteractive) {
        Write-Host ""
        Write-Host "  An existing install is present at $script:InstallDir"
        Write-Host "  It will be moved to a timestamped backup dir, then a fresh"
        Write-Host "  install will be extracted in its place."
        $reply = Read-Host "  Continue? [y/N]"
        if ($reply -notmatch '^(y|Y|yes|YES)$') {
            Write-Host "  cancelled."
            exit 0
        }
    }

    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $script:BackupDir = "$($script:InstallDir)-prev-$ts"
    Log-Info "backing up existing install → $script:BackupDir"
    try {
        Move-Item -LiteralPath $script:InstallDir -Destination $script:BackupDir `
            -Force -ErrorAction Stop
    } catch {
        Log-Err "failed to move existing install to $script:BackupDir"
        exit 1
    }
}


function Rollback-Install {
    if ([string]::IsNullOrEmpty($script:BackupDir)) { return }
    if (-not (Test-Path -LiteralPath $script:BackupDir)) { return }

    Log-Warn "rolling back to previous install at $script:BackupDir"
    if (Test-Path -LiteralPath $script:InstallDir) {
        Remove-Item -LiteralPath $script:InstallDir -Force -Recurse `
            -ErrorAction SilentlyContinue
    }
    try {
        Move-Item -LiteralPath $script:BackupDir -Destination $script:InstallDir `
            -Force -ErrorAction Stop
        Log-Info "rollback complete"
        $script:BackupDir = ""
    } catch {
        Log-Err "rollback failed — previous install remains at $script:BackupDir"
    }
}


# ---------------------------------------------------------------------------
# 7. Tarball fetch + extract
# ---------------------------------------------------------------------------

function Fetch-AndExtract {
    Log-Step "Fetching release tarball"

    if ([string]::IsNullOrEmpty($BrainReleaseUrl)) {
        # This branch only fires if the caller explicitly blanked
        # $env:BRAIN_RELEASE_URL. The default above points at the real
        # GitHub release asset, so normal ``irm ... | iex`` never lands here.
        Log-Err "no release URL configured"
        Log-Err "  `$env:BRAIN_RELEASE_URL was explicitly set empty."
        Log-Err "  unset it to use the default GitHub release, or"
        Log-Err "  set `$env:BRAIN_RELEASE_URL = 'file:///C:/path/to/brain-dev.tar.gz'"
        Log-Err "  (cut one with: python scripts\cut_local_tarball.py)"
        exit 1
    }

    # Sanity check for tar.exe up front — cheaper failure mode than
    # failing halfway through an extract.
    Assert-TarExe | Out-Null

    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) `
        ("brain-install-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $tarball = Join-Path $tmpDir "brain.tar.gz"

    # Bootstrap reuse: when install.ps1 was curled standalone, section 0
    # already downloaded + verified the tarball. Reuse it instead of
    # fetching it a second time. The SHA has already been checked (or
    # explicitly skipped) during bootstrap, so skip verify.
    $bootstrapTarball = [Environment]::GetEnvironmentVariable(
        "BRAIN_BOOTSTRAP_TARBALL", "Process"
    )
    if (-not [string]::IsNullOrEmpty($bootstrapTarball) -and `
        (Test-Path -LiteralPath $bootstrapTarball -PathType Leaf)) {
        Log-Info "reusing tarball downloaded during bootstrap"
        try {
            Copy-Item -LiteralPath $bootstrapTarball -Destination $tarball -Force
        } catch {
            Log-Err "failed to copy bootstrap tarball: $($_.Exception.Message)"
            Remove-Item -LiteralPath $tmpDir -Force -Recurse -ErrorAction SilentlyContinue
            exit 1
        }
    } else {
        try {
            if (-not [string]::IsNullOrEmpty($BrainReleaseSha256)) {
                Fetch-Tarball -Url $BrainReleaseUrl -DestPath $tarball `
                    -ExpectedSha256 $BrainReleaseSha256
            } else {
                Log-Warn "BRAIN_RELEASE_SHA256 not set — skipping SHA256 verification."
                Log-Warn "  (acceptable for local dev tarballs; never skip for release builds.)"
                Invoke-Download -Url $BrainReleaseUrl -DestPath $tarball
            }
        } catch {
            Log-Err $_.Exception.Message
            Remove-Item -LiteralPath $tmpDir -Force -Recurse -ErrorAction SilentlyContinue
            exit 1
        }
    }

    Log-Step "Extracting to $script:InstallDir"
    if (-not (Test-Path -LiteralPath $script:InstallDir)) {
        try {
            New-Item -ItemType Directory -Path $script:InstallDir -Force | Out-Null
        } catch {
            Log-Err "cannot create $script:InstallDir"
            Remove-Item -LiteralPath $tmpDir -Force -Recurse -ErrorAction SilentlyContinue
            exit 1
        }
    }

    try {
        Expand-Tarball -TarballPath $tarball -DestDir $script:InstallDir
    } catch {
        Log-Err "failed to extract tarball: $($_.Exception.Message)"
        Remove-Item -LiteralPath $tmpDir -Force -Recurse -ErrorAction SilentlyContinue
        exit 1
    }

    Remove-Item -LiteralPath $tmpDir -Force -Recurse -ErrorAction SilentlyContinue

    Log-Ok "extracted"
}


# ---------------------------------------------------------------------------
# 8. Python deps via uv
# ---------------------------------------------------------------------------

function Run-UvSync {
    if ($BrainSkipUvSync -eq "1") {
        Log-Info "BRAIN_SKIP_UV_SYNC=1 — skipping uv sync (test mode)"
        return
    }

    Log-Step "Installing Python dependencies (uv sync)"

    Push-Location $script:InstallDir
    try {
        & uv sync --all-packages --no-dev
        if ($LASTEXITCODE -ne 0) {
            Log-Err "uv sync failed"
            Log-Err "  try again: cd $script:InstallDir; uv sync --all-packages --no-dev"
            exit 1
        }
    } finally {
        Pop-Location
    }
    Log-Ok "python deps installed"
}


# ---------------------------------------------------------------------------
# 9. Node + pnpm + UI build
# ---------------------------------------------------------------------------

function Build-WebUi {
    $indexHtml = Join-Path $script:InstallDir "apps\brain_web\out\index.html"

    if ($BrainSkipNode -eq "1") {
        Log-Info "BRAIN_SKIP_NODE=1 — skipping Node install + UI build"
        if (-not (Test-Path -LiteralPath $indexHtml)) {
            Log-Warn "no prebuilt UI found at apps\brain_web\out\index.html"
            Log-Warn "  'brain start' will fail without a UI bundle."
        }
        return
    }

    # If the tarball shipped a prebuilt UI, prefer it and skip Node entirely.
    if (Test-Path -LiteralPath $indexHtml) {
        Log-Info "prebuilt UI found in tarball (apps\brain_web\out\index.html); skipping Node"
        return
    }

    Log-Step "Installing Node $BrainNodeVersion via fnm"
    Install-Fnm -InstallDir $script:InstallDir
    Install-Node -InstallDir $script:InstallDir -NodeVersion $BrainNodeVersion

    Log-Step "Enabling pnpm via corepack"
    $corepack = Get-Command corepack -ErrorAction SilentlyContinue
    if ($null -eq $corepack) {
        Log-Err "corepack not found — comes with Node >=16, something is wrong"
        exit 1
    }

    & corepack enable 2>$null | Out-Null
    & corepack prepare pnpm@9 --activate 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Log-Err "corepack failed to activate pnpm"
        exit 1
    }

    $pnpmVer = (& pnpm --version 2>$null)
    if (-not $pnpmVer) { $pnpmVer = "?" }
    Log-Ok "pnpm $pnpmVer ready"

    Log-Step "Building web UI (pnpm -F brain_web build)"
    Push-Location $script:InstallDir
    try {
        & pnpm -F brain_web install --frozen-lockfile=false
        if ($LASTEXITCODE -ne 0) {
            Log-Err "pnpm install failed"
            exit 1
        }
        & pnpm -F brain_web build
        if ($LASTEXITCODE -ne 0) {
            Log-Err "pnpm build failed"
            exit 1
        }
    } finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $indexHtml)) {
        Log-Err "UI build completed but apps\brain_web\out\index.html is missing"
        exit 1
    }
    Log-Ok "UI built"
}


# ---------------------------------------------------------------------------
# 10. Shim + Start Menu shortcut
# ---------------------------------------------------------------------------

function Write-Launchers {
    Log-Step "Writing CLI shim"
    Write-Shim -InstallDir $script:InstallDir

    Log-Step "Creating Start Menu entry"
    New-StartMenuEntry -InstallDir $script:InstallDir

    if ($BrainSkipDesktop -ne "1") {
        Log-Step "Creating Desktop shortcut"
        New-DesktopShortcut -InstallDir $script:InstallDir
    }
}


# ---------------------------------------------------------------------------
# 11. Post-install doctor
# ---------------------------------------------------------------------------

function Run-Doctor {
    if ($BrainSkipDoctor -eq "1") {
        Log-Info "BRAIN_SKIP_DOCTOR=1 — skipping final brain doctor run"
        return
    }

    Log-Step "Running brain doctor"
    Push-Location $script:InstallDir
    try {
        & uv run --project $script:InstallDir brain doctor
        $rc = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($rc -ne 0) {
        Log-Warn "brain doctor reported issues (rc=$rc)"
        Log-Warn "  some FAILs pre-setup are expected (e.g. missing token)."
        Log-Warn "  run 'brain setup' to finish configuration."
    } else {
        Log-Ok "brain doctor green"
    }
}


# ---------------------------------------------------------------------------
# 12. Main flow
# ---------------------------------------------------------------------------

function Main {
    Write-Host "brain installer  ·  $(Get-Date -Format 'yyyy-MM-dd HH:mm')" `
        -ForegroundColor White
    Write-Host ""

    $platform = Assert-WindowsSupported
    Log-Info "platform: $platform"

    Ensure-Uv
    Resolve-InstallDir
    Backup-ExistingInstall
    Fetch-AndExtract
    Run-UvSync
    Build-WebUi
    Write-Launchers
    Run-Doctor

    if (-not [string]::IsNullOrEmpty($script:BackupDir) -and `
        (Test-Path -LiteralPath $script:BackupDir)) {
        Log-Info "removing backup at $script:BackupDir (install succeeded)"
        Remove-Item -LiteralPath $script:BackupDir -Force -Recurse `
            -ErrorAction SilentlyContinue
        $script:BackupDir = ""
    }

    Write-Host ""
    Write-Host "brain installed." -ForegroundColor Green
    Write-Host "  Run 'brain start' to launch the setup wizard in your browser."
    Write-Host "  Documentation: https://github.com/ToTo-LLC/cj-llm-kb"
}


function Cleanup-Bootstrap {
    # Clean up the bootstrap staging dir (if any). Safe to remove even on
    # success — Fetch-AndExtract has already copied the tarball into its
    # own temp dir and extracted it by now.
    if (-not [string]::IsNullOrEmpty($script:BootstrapStaging) -and `
        (Test-Path -LiteralPath $script:BootstrapStaging)) {
        Remove-Item -LiteralPath $script:BootstrapStaging -Force -Recurse `
            -ErrorAction SilentlyContinue
        $script:BootstrapStaging = ""
    }
}


try {
    Main
    Cleanup-Bootstrap
    exit 0
} catch {
    Log-Err $_.Exception.Message
    Rollback-Install
    Cleanup-Bootstrap
    exit 1
}
