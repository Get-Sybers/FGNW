[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$requireDc = ($env:AD_WAIT_REQUIRE_DC -eq 'true')
try {
    $services = @('NTDS', 'DNS', 'Netlogon')
    if ($requireDc) { $services += 'kdc' }
    foreach ($s in $services) {
        $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
        if (-not $svc -or $svc.Status -ne 'Running') { throw "$s not running" }
    }
    $null = Get-ADDomain -ErrorAction Stop
    if ($requireDc) {
        $null = Get-ADDomainController -Identity $env:COMPUTERNAME -ErrorAction Stop
        $shares = (Get-SmbShare -ErrorAction SilentlyContinue).Name
        if ($shares -notcontains 'SYSVOL' -or $shares -notcontains 'NETLOGON') {
            throw 'SYSVOL/NETLOGON not shared yet'
        }
    }
    exit 0
} catch {
    Write-Error $_
    exit 1
}
