$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'C:\ludus')) {
    New-Item -ItemType Directory -Path 'C:\ludus' | Out-Null
}
Start-Transcript -Path C:\ludus\setup-log.txt -Append
Write-Output '=== remove-appx-sysprep-blockers: disabling EdgeUpdate services ==='
foreach ($svc in @('edgeupdate', 'edgeupdatem')) {
    if (Get-Service -Name $svc -ErrorAction SilentlyContinue) {
        Stop-Service  -Name $svc -Force        -ErrorAction SilentlyContinue
        Set-Service   -Name $svc -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Output ("Disabled service: {0}" -f $svc)
    } else {
        Write-Output ("Service not present (ok): {0}" -f $svc)
    }
}
$regPath = 'HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate'
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
New-ItemProperty -Path $regPath -Name 'UpdateDefault' -Value 0 -PropertyType DWord -Force | Out-Null
Write-Output 'Set EdgeUpdate policy UpdateDefault=0.'
Write-Output '=== remove-appx-sysprep-blockers: state before removal ==='
function Get-Blockers {
    $provisionedNames = @(Get-AppxProvisionedPackage -Online | ForEach-Object { $_.DisplayName })
    @(
        Get-AppxPackage -AllUsers |
            Where-Object {
                -not $_.IsFramework -and
                -not $_.NonRemovable -and
                $provisionedNames -notcontains $_.Name
            }
    )
}
$blockers = Get-Blockers
if ($blockers.Count -eq 0) {
    Write-Output 'No AppX package is installed-but-not-provisioned - nothing to remove.'
} else {
    $blockers | ForEach-Object { Write-Output ("blocker: {0}" -f $_.PackageFullName) }
}
foreach ($package in $blockers) {
    Write-Output ("Removing per-user AppX package {0}" -f $package.PackageFullName)
    try {
        Remove-AppxPackage -Package $package.PackageFullName -AllUsers -ErrorAction Stop
    } catch {
        Write-Output ("  WARN: removal reported: {0}" -f $_.Exception.Message)
    }
}
$remaining = Get-Blockers
if ($remaining.Count -gt 0) {
    $remaining | ForEach-Object { Write-Output ("BLOCKER REMAINS: {0}" -f $_.PackageFullName) }
    Write-Output 'FATAL: at least one AppX package is still installed-but-not-provisioned; sysprep would fail at deploy time.'
    Stop-Transcript
    exit 1
}
Write-Output 'Verified: no AppX package is installed-but-not-provisioned.'
Write-Output '=== remove-appx-sysprep-blockers: done ==='
Stop-Transcript
exit 0
