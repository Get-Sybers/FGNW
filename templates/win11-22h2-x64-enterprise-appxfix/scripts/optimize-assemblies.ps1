function Optimize-Assemblies {
    param (
        [string]$assemblyFilter = "Microsoft.PowerShell.",
        [string]$activity = "Native Image Installation"
    )
    try {
        $ngenPath = [System.IO.Path]::Combine([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory(), "ngen.exe")
        if (-Not (Test-Path $ngenPath)) {
            Write-Host "Ngen.exe not found at $ngenPath. Make sure .NET Framework is installed."
            return
        }
        $assemblies = [AppDomain]::CurrentDomain.GetAssemblies()
        $filteredAssemblies = $assemblies | Where-Object { $_.FullName -ilike "$assemblyFilter*" }
        if ($filteredAssemblies.Count -eq 0) {
            Write-Host "No matching assemblies found for optimization."
            return
        }
        foreach ($assembly in $filteredAssemblies) {
            $name = [System.IO.Path]::GetFileName($assembly.Location)
            Write-Progress -Activity $activity -Status "Optimizing $name"
            Start-Process -FilePath $ngenPath -ArgumentList "install `"$($assembly.Location)`"" -Wait -WindowStyle Hidden
        }
        Write-Host "Optimization complete."
    } catch {
        Write-Host "An error occurred: $_"
    }
}
Optimize-Assemblies -assemblyFilter "Microsoft.PowerShell."
