Get-ADUser -Identity "konohamaru.sarutobi" | Set-ADAccountControl -DoesNotRequirePreAuth:$true
