[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dbPath = Join-Path $repoRoot "backend\app\rag\data\milvus_lite.db"

if (-not (Test-Path -LiteralPath $dbPath)) {
    throw "Milvus Lite database directory was not found: $dbPath"
}

# Only protect parquet data files (read-only), keep metadata files writable
# Use attrib command because Set-ItemProperty cannot modify read-only files on Windows
$files = Get-ChildItem -LiteralPath $dbPath -Recurse -File
foreach ($f in $files) {
    if ($f.Extension -eq ".parquet") {
        attrib +r "$($f.FullName)"
    } else {
        attrib -r "$($f.FullName)"
    }
}

Write-Host "Done. Verification:"
# Re-read file states after modification
$filesUpdated = Get-ChildItem -Path $dbPath -Recurse -File
$parquetRO = ($filesUpdated | Where-Object { $_.Extension -eq ".parquet" -and $_.IsReadOnly -eq $true }).Count
$parquetRW = ($filesUpdated | Where-Object { $_.Extension -eq ".parquet" -and $_.IsReadOnly -eq $false }).Count
$otherRO = ($filesUpdated | Where-Object { $_.Extension -ne ".parquet" -and $_.IsReadOnly -eq $true }).Count
$otherRW = ($filesUpdated | Where-Object { $_.Extension -ne ".parquet" -and $_.IsReadOnly -eq $false }).Count
Write-Host "  Parquet read-only: $parquetRO"
Write-Host "  Parquet writable:  $parquetRW"
Write-Host "  Other read-only:   $otherRO"
Write-Host "  Other writable:    $otherRW"

$lockFile = Join-Path $dbPath "LOCK"
if (Test-Path $lockFile) {
    attrib -r "$lockFile"
    Write-Host ""
    Write-Host "LOCK file is writable. Stop all Milvus Lite users before deleting it manually."
}
