# sasori-verify.ps1 — build sasori and run the verify subcommand on Windows.
#
# Usage:
#   .\scripts\sasori-verify.ps1 [-Deep] [hostname1] [hostname2] ...
#
# Required env vars (set beforehand or they will be reported as missing):
#   PVE_HOST         Proxmox base URL   e.g. https://pve01:8006
#   PVE_USER         API token user     e.g. emulator@pve
#   PVE_TOKEN_ID     token ID           (the part after the !)
#   PVE_SECRET       token secret
#   RANGE_NUMBER     Ludus range number (integer)
#
# Optional env vars:
#   PVE_NODE             Proxmox node name (default: pve)
#   PVE_INSECURE         1 to skip TLS verification
#   PERSONA_TIMELINES    path to persona-timelines.yml (skip if passing hostnames)
#   PERSONA_OVERRIDES    path to persona-overrides.yml
#
# Example — check two specific VMs with the deep exec test:
#   $env:PVE_HOST='https://pve01:8006'
#   $env:PVE_USER='emulator@pve'
#   $env:PVE_TOKEN_ID='verify-token'
#   $env:PVE_SECRET='xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
#   $env:RANGE_NUMBER='10'
#   .\scripts\sasori-verify.ps1 -Deep konoha-ws1 konoha-ws2

[CmdletBinding()]
param(
    [switch]$Deep,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Hostnames
)

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$SasoriDir  = Split-Path -Parent $ScriptDir

# ── Required env vars ────────────────────────────────────────────────────────
$required = @('PVE_HOST', 'PVE_USER', 'PVE_TOKEN_ID', 'PVE_SECRET', 'RANGE_NUMBER')
$missing  = $required | Where-Object { -not [Environment]::GetEnvironmentVariable($_) }
if ($missing) {
    Write-Error ("Missing required env vars: {0}`nSet them before running this script." -f ($missing -join ', '))
    exit 1
}

# ── Build ────────────────────────────────────────────────────────────────────
$BinPath = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "sasori-$([System.Guid]::NewGuid().ToString('N')).exe")

Write-Host "Building sasori..."
Push-Location $SasoriDir
try {
    $env:CGO_ENABLED = '0'
    & go build -trimpath -ldflags '-s -w' -o $BinPath ./cmd/sasori
    if ($LASTEXITCODE -ne 0) {
        Write-Error "go build failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
Write-Host "Build OK.`n"

# ── Run verify ───────────────────────────────────────────────────────────────
$verifyArgs = @('verify')
if ($Deep)      { $verifyArgs += '--deep' }
if ($Hostnames) { $verifyArgs += $Hostnames }

try {
    & $BinPath @verifyArgs
    $ExitCode = $LASTEXITCODE
} finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $BinPath
}
exit $ExitCode
