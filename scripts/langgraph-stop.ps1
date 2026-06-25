param(
    [int]$Port = 8124
)

$ErrorActionPreference = "Stop"

$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique

if (-not $pids) {
    Write-Host "No process found on port $Port."
    exit 0
}

foreach ($pid in $pids) {
    Write-Host "Killing process $pid on port $Port"
    Stop-Process -Id $pid -Force
}
Write-Host "Done."
