$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'C:\ludus')) {
    New-Item -ItemType Directory -Path 'C:\ludus' | Out-Null
}
Start-Transcript -Path C:\ludus\setup-log.txt -Append
Write-Output '=== remove-appx-sysprep-blockers: disabling the Edge updater (services, scheduled tasks, policy) ==='
# The updater is not only the two services: the MicrosoftEdgeUpdateTaskMachineCore /
# MicrosoftEdgeUpdateTaskMachineUA scheduled tasks launch MicrosoftEdgeUpdate.exe
# directly, so with the services disabled it still runs on a clone, installs a
# newer Edge, and Edge's installer registers the Microsoft.MicrosoftEdge.Stable
# sparse package for the logged-on user - which the next sysprep fails on
# ("installed for a user, but not provisioned for all users", 0x80073cf2).
# All three doors are closed here: services, tasks, and the update policy for
# both the default and the Stable-channel app id.
Get-Process -Name 'MicrosoftEdgeUpdate' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
foreach ($svc in @('edgeupdate', 'edgeupdatem')) {
    if (Get-Service -Name $svc -ErrorAction SilentlyContinue) {
        Stop-Service  -Name $svc -Force        -ErrorAction SilentlyContinue
        Set-Service   -Name $svc -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Output ("Disabled service: {0}" -f $svc)
    } else {
        Write-Output ("Service not present (ok): {0}" -f $svc)
    }
}
$updateTasks = @(Get-ScheduledTask -TaskName 'MicrosoftEdgeUpdate*' -ErrorAction SilentlyContinue)
if ($updateTasks.Count -eq 0) {
    Write-Output 'No EdgeUpdate scheduled task present (ok).'
}
foreach ($task in $updateTasks) {
    $task | Stop-ScheduledTask -ErrorAction SilentlyContinue
    $task | Disable-ScheduledTask | Out-Null
    Write-Output ("Disabled scheduled task: {0}" -f $task.TaskName)
}
$regPath = 'HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate'
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
New-ItemProperty -Path $regPath -Name 'UpdateDefault' -Value 0 -PropertyType DWord -Force | Out-Null
# {56EB18F8-B008-4CBD-B6D2-8C97FE7E9062} is the Edge Stable channel app id.
New-ItemProperty -Path $regPath -Name 'Update{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}' -Value 0 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $regPath -Name 'AutoUpdateCheckPeriodMinutes' -Value 0 -PropertyType DWord -Force | Out-Null
Write-Output 'Set EdgeUpdate policy: UpdateDefault=0, Update{Stable}=0, AutoUpdateCheckPeriodMinutes=0.'
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
