# Boots brain_api against a freshly seeded temp vault for Playwright e2e.
#
# Windows counterpart to start-backend-for-e2e.sh. Mirrors its seeding +
# launch behavior so CI parity across macOS + Windows stays tight.
#
# IMPORTANT: ``uv run uvicorn`` replaces the current process on POSIX via
# ``exec``; PowerShell has no direct exec equivalent, so we use
# ``Start-Process -NoNewWindow -Wait`` which achieves the same "run in
# foreground, propagate exit code" semantics Playwright's webServer needs.

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")

# --- vault root --------------------------------------------------------------
if (-not $env:BRAIN_VAULT_ROOT) {
    $suffix = [System.IO.Path]::GetRandomFileName().Replace('.', '')
    $env:BRAIN_VAULT_ROOT = Join-Path $env:TEMP "brain-e2e-vault-$suffix"
}
New-Item -ItemType Directory -Force -Path $env:BRAIN_VAULT_ROOT | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $env:BRAIN_VAULT_ROOT "research\notes") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $env:BRAIN_VAULT_ROOT "work\notes") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $env:BRAIN_VAULT_ROOT ".brain\run") | Out-Null

# Seed one research note + two domain indexes. Write LF-terminated (default
# PowerShell UTF8 writes CRLF; brain_core normalizes but LF on disk is the
# project rule — CLAUDE.md principle #8).
$welcome = @'
---
title: Welcome
---

This is a seeded note for the brain e2e test run.
'@
[System.IO.File]::WriteAllText((Join-Path $env:BRAIN_VAULT_ROOT "research\notes\welcome.md"), ($welcome -replace "`r`n", "`n"))

$researchIndex = @'
# research

- [[welcome]]
'@
[System.IO.File]::WriteAllText((Join-Path $env:BRAIN_VAULT_ROOT "research\index.md"), ($researchIndex -replace "`r`n", "`n"))

$workIndex = @'
# work

_Nothing here yet._
'@
[System.IO.File]::WriteAllText((Join-Path $env:BRAIN_VAULT_ROOT "work\index.md"), ($workIndex -replace "`r`n", "`n"))

# Intentionally no BRAIN.md — see start-backend-for-e2e.sh for rationale.

if (-not $env:BRAIN_ALLOWED_DOMAINS) {
    $env:BRAIN_ALLOWED_DOMAINS = "research,work"
}

# Plan 07 Task 25C: flip FakeLLMProvider's empty-queue fallback from
# "raise RuntimeError" to "return a scripted canned response." See the
# sh sibling for rationale.
if (-not $env:BRAIN_E2E_MODE) {
    $env:BRAIN_E2E_MODE = "1"
}

Write-Host "[e2e-backend] vault=$env:BRAIN_VAULT_ROOT"
Write-Host "[e2e-backend] allowed=$env:BRAIN_ALLOWED_DOMAINS"
Write-Host "[e2e-backend] e2e_mode=$env:BRAIN_E2E_MODE"

# --- launch uvicorn ----------------------------------------------------------
Push-Location $repoRoot
try {
    $uvArgs = @(
        "run", "uvicorn",
        "--factory",
        "--app-dir", "apps/brain_web/scripts",
        "--host", "127.0.0.1",
        "--port", "4317",
        "--log-level", "warning",
        "e2e_backend:build_app"
    )
    & uv @uvArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
