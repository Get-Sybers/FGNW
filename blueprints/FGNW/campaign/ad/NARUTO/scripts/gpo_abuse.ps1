Install-WindowsFeature -Name GPMC
$gpo_exist = Get-GPO -Name "WillOfFireWallpaper" -erroraction ignore
if ($gpo_exist) {
} else {
    New-GPO -Name "WillOfFireWallpaper" -comment "Change Wallpaper"
    New-GPLink -Name "WillOfFireWallpaper" -Target "DC=konohagakure,DC=fire,DC=ninja"
    Set-GPRegistryValue -Name "WillOfFireWallpaper" -key "HKEY_CURRENT_USER\Control Panel\Colors" -ValueName Background -Type String -Value "100 175 200"
    Set-GPRegistryValue -Name "WillOfFireWallpaper" -key "HKEY_CURRENT_USER\Control Panel\Desktop" -ValueName Wallpaper -Type String -Value ""
    Set-GPRegistryValue -Name "WillOfFireWallpaper" -Key "HKEY_LOCAL_MACHINE\Software\Policies\Microsoft\Windows NT\CurrentVersion\WinLogon" -ValueName SyncForegroundPolicy -Type DWORD -Value 1
    Set-GPPermissions -Name "WillOfFireWallpaper" -PermissionLevel GpoEditDeleteModifySecurity -TargetName "iruka.umino" -TargetType "User"
}
