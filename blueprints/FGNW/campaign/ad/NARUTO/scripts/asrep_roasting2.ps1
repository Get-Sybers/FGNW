Get-ADUser -Identity "sai" | Set-ADAccountControl -DoesNotRequirePreAuth:$true
