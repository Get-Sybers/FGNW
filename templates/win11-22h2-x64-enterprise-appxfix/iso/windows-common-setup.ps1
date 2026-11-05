$ErrorActionPreference = "Continue"
if (-not (Test-Path "C:\ludus")) {
    New-Item -ItemType Directory -Path "C:\ludus"
}
Start-Transcript -path C:\ludus\setup-log.txt -append
Start-Service -Name 'WinRM' -ErrorAction Stop
if ([System.Environment]::Is64BitOperatingSystem) {
    F:\guest-agent\qemu-ga-x86_64.msi /quiet
}
else {
    F:\guest-agent\qemu-ga-x86.msi /quiet
}
Get-NetAdapter | foreach { Disable-NetAdapterBinding -InterfaceAlias $_.Name -ComponentID ms_tcpip6 }
netsh advfirewall firewall add rule name='ICMP Allow incoming V4 echo request' protocol=icmpv4:8,any dir=in action=allow
netsh interface teredo set state disabled
wmic useraccount where "name='localuser'" set PasswordExpires=FALSE
