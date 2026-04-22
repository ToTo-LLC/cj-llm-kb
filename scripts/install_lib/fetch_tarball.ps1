# scripts/install_lib/fetch_tarball.ps1
#
# Plan 08 Task 8. Download a release tarball and verify its SHA256 on
# Windows. Mirrors scripts/install_lib/fetch_tarball.sh.
#
# Usage (dot-sourced):
#
#     . scripts/install_lib/fetch_tarball.ps1
#     Fetch-Tarball -Url <url> -DestPath <path> -ExpectedSha256 <sha>
#     Expand-Tarball -TarballPath <path> -DestDir <path>
#
# Supports http(s):// and file:/// URLs. Uses Invoke-WebRequest (Win10+
# has it out of the box; PS 5.1 compatible). SHA256 via Get-FileHash.
# Extraction via tar.exe (bsdtar ships with Windows 10 build 17063+).
#
# PowerShell 5.1 compatible. No PS 7-only syntax (no ??, no ternary,
# no pipeline-parallel).

Set-StrictMode -Version Latest


function Get-FileSha256Hex {
    <#
    .SYNOPSIS
      Compute the SHA256 hex digest (lowercase) of a file.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "file not found: $Path"
    }
    $hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256
    return $hash.Hash.ToLowerInvariant()
}


function Invoke-Download {
    <#
    .SYNOPSIS
      Download a URL to a destination path. Handles http(s):// and
      file:///.

    .DESCRIPTION
      For file:/// URLs we copy directly with Copy-Item — this avoids
      needing any network stack at all (used by the test harness).

      For http(s):// we use Invoke-WebRequest. The -UseBasicParsing
      switch is required on Windows PowerShell 5.1 to avoid the
      InternetExplorer engine dependency.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$DestPath
    )

    $destDir = Split-Path -Parent $DestPath
    if ($destDir -and -not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    # file:/// URLs → plain file copy. Supports both file:///C:/foo and
    # file:///tmp/foo forms.
    if ($Url -like "file:///*") {
        $rawPath = $Url.Substring("file:///".Length)
        # On Windows the result looks like "C:/foo/bar.tar.gz" — needs
        # backslashes for Test-Path. On Unix (opt-in CI) it looks like
        # "tmp/foo" — prepend / back.
        if ($rawPath -match '^[A-Za-z]:') {
            $localPath = $rawPath -replace '/', '\'
        } else {
            $localPath = "/" + $rawPath
        }
        if (-not (Test-Path -LiteralPath $localPath -PathType Leaf)) {
            throw "local tarball not found: $localPath"
        }
        Copy-Item -LiteralPath $localPath -Destination $DestPath -Force
        return
    }

    # Force TLS 1.2 on PS 5.1 where the default may still be SSL3/TLS1.0.
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = `
            [System.Net.ServicePointManager]::SecurityProtocol -bor `
            [System.Net.SecurityProtocolType]::Tls12
    } catch {
        # Older .NET without Tls12 enum — best effort.
    }

    try {
        Invoke-WebRequest -Uri $Url -OutFile $DestPath -UseBasicParsing `
            -ErrorAction Stop | Out-Null
    } catch {
        throw "download failed for $Url : $($_.Exception.Message)"
    }
}


function Fetch-Tarball {
    <#
    .SYNOPSIS
      Download + verify a release tarball.

    .DESCRIPTION
      Top-level entry. Emits a clear error and removes the partial file
      on any hash mismatch so retries start from scratch.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$DestPath,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    Write-Host "  downloading $Url"
    try {
        Invoke-Download -Url $Url -DestPath $DestPath
    } catch {
        if (Test-Path -LiteralPath $DestPath) {
            Remove-Item -LiteralPath $DestPath -Force -ErrorAction SilentlyContinue
        }
        throw "download failed for $Url : $($_.Exception.Message)"
    }

    Write-Host "  verifying SHA256"
    $actual = Get-FileSha256Hex -Path $DestPath
    $expected = $ExpectedSha256.ToLowerInvariant()

    if ($actual -ne $expected) {
        Remove-Item -LiteralPath $DestPath -Force -ErrorAction SilentlyContinue
        throw @"
SHA256 mismatch for $Url
       expected: $expected
       actual:   $actual
       the download may be corrupted or tampered with.
       try again, or report the issue if it persists.
"@
    }

    Write-Host "  ok (sha256 $actual)"
}


function Assert-TarExe {
    <#
    .SYNOPSIS
      Verify tar is available on PATH.

    .DESCRIPTION
      On Windows we prefer ``tar.exe`` (bsdtar, bundled with Windows 10
      build 17063+ at %SystemRoot%\System32\tar.exe). On opt-in non-Windows
      CI we fall back to ``tar``. Returns the full path or throws with
      a clear fix-hint.
    #>
    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -eq $tar) {
        $tar = Get-Command tar -ErrorAction SilentlyContinue
    }
    if ($null -eq $tar) {
        throw @"
tar.exe not found on PATH.
       brain needs the bsdtar that ships with Windows 10 build 17063+
       (April 2018 Update). If you're on an older build, please update
       Windows or install bsdtar/7zip manually.
"@
    }
    return $tar.Source
}


function Expand-Tarball {
    <#
    .SYNOPSIS
      Extract a .tar.gz into a destination directory via tar.exe.

    .DESCRIPTION
      If the tarball has a single shared top-level directory (e.g.
      ``brain-v0.1.0/...``), strip one path component. For a bare
      ``git archive HEAD`` output (every entry is a sibling of the
      repo root) no strip.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$TarballPath,
        [Parameter(Mandatory = $true)][string]$DestDir
    )

    $tar = Assert-TarExe

    if (-not (Test-Path -LiteralPath $TarballPath -PathType Leaf)) {
        throw "tarball not found: $TarballPath"
    }

    if (-not (Test-Path -LiteralPath $DestDir)) {
        New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    }

    # List top-level entries to decide on --strip-components.
    $listing = & $tar -tzf $TarballPath 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "tar.exe failed to list $TarballPath"
    }

    $topSegments = @{}
    foreach ($line in $listing) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $seg = ($line -split '/')[0]
        if (-not [string]::IsNullOrWhiteSpace($seg)) {
            $topSegments[$seg] = $true
        }
    }

    $stripArgs = @()
    if ($topSegments.Count -eq 1) {
        $only = @($topSegments.Keys)[0]
        # Single top-level entry → strip only if it's a directory
        # (tar lists directories with a trailing slash).
        $hasDirEntry = $false
        foreach ($line in $listing) {
            if ($line -eq "$only/") { $hasDirEntry = $true; break }
        }
        if ($hasDirEntry) {
            $stripArgs = @("--strip-components=1")
        }
    }

    $extractArgs = @("-xzf", $TarballPath, "-C", $DestDir) + $stripArgs
    & $tar @extractArgs
    if ($LASTEXITCODE -ne 0) {
        throw "tar.exe failed to extract $TarballPath (exit $LASTEXITCODE)"
    }
}
