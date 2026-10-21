Set-ADComputer -Identity "konoha-mail$" -ServicePrincipalNames @{Add='HTTP/konoha-dc1.konohagakure.fire.ninja'}
Set-ADComputer -Identity "konoha-mail$" -Add @{'msDS-AllowedToDelegateTo'=@('HTTP/konoha-dc1.konohagakure.fire.ninja','HTTP/konoha-dc1')}
