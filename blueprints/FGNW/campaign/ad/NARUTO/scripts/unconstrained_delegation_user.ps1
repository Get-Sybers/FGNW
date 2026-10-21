Get-ADUser -Identity "sakura.haruno" | Set-ADAccountControl -TrustedForDelegation $true
