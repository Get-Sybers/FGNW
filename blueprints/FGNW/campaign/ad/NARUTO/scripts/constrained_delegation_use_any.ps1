Set-ADUser -Identity "gaara" -ServicePrincipalNames @{Add='CIFS/suna-dc1.sunagakure.wind.ninja'}
Get-ADUser -Identity "gaara" | Set-ADAccountControl -TrustedToAuthForDelegation $true
Set-ADUser -Identity "gaara" -Add @{'msDS-AllowedToDelegateTo'=@('CIFS/sunagakure.wind.ninja','CIFS/sunagakure')}
Add-ADGroupMember -Identity 'Protected Users' -Members gaara
