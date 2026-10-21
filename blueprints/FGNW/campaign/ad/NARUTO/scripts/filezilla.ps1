Start-Process -FilePath c:\filezilla.exe -ArgumentList "/S" -Wait
$directoryPath = "C:\wineremix"
If (-Not (Test-Path -Path $directoryPath)) {
    New-Item -ItemType Directory -Path $directoryPath
}
$content = @"
Ave, César !
J'ai envoyé un messager avec les plans du village. Il aura besoin de rentrer discrètement dans le camp et remettra les plans au commandant du camp.
Le mot de passe pour entrer dans le camp sera le suivant : wUSYIuhhWy!!12OL , il faudra prévenir la sentinelle locale à ce poste pour qu'il puisse s'authentifier sans encombre !!!
J'ai aussi entendu dire que le capitaine Lapsus était passé dans le camp le mois dernier. J'espère qu'il n'a pas laissé de trace !
"@
$filePath = Join-Path -Path $directoryPath -ChildPath "plans.txt"
Set-Content -Path $filePath -Value $content
Write-Output "File 'plans.txt' created successfully at $directoryPath"
net stop "FileZilla-Server"
cp c:\users.xml c:\programdata\filezilla-server\ -force
net start "FileZilla-Server"
