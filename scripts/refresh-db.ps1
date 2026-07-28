$src = "T:\Study\Learn\Multi-Agent\OCR-RAG\milvus_lite.db"
$dest = "T:\Study\Learn\Multi-Agent\patent-tutor-agent\backend\app\rag\data\milvus_lite.db"

$srcLock = Join-Path $src "LOCK"
if (Test-Path $srcLock) {
    Remove-Item $srcLock -Force
    Write-Host "[1] OCR-RAG LOCK removed"
} else {
    Write-Host "[1] OCR-RAG no LOCK file"
}

Write-Host "[2] Removing old patent database..."
if (Test-Path $dest) {
    Remove-Item -Recurse -Force $dest
    Write-Host "  Done"
}

Write-Host "[3] Copying database..."
Copy-Item -Recurse $src $dest
$count = (Get-ChildItem $dest -Recurse -File).Count
Write-Host "  Copied $count files"

$destLock = Join-Path $dest "LOCK"
if (Test-Path $destLock) {
    Remove-Item $destLock -Force
    Write-Host "[4] LOCK file removed"
} else {
    Write-Host "[4] No LOCK file"
}

# Only protect parquet data files (read-only), keep metadata files writable
# Use attrib command because Set-ItemProperty cannot modify read-only files on Windows
Write-Host "[5] Setting parquet data files read-only..."
$files = Get-ChildItem -Path $dest -Recurse -File
foreach ($f in $files) {
    if ($f.Extension -eq ".parquet") {
        attrib +r "$($f.FullName)"
    } else {
        attrib -r "$($f.FullName)"
    }
}
$parquetRO = ($files | Where-Object { $_.Extension -eq ".parquet" }).Count
$otherRW = ($files | Where-Object { $_.Extension -ne ".parquet" }).Count
Write-Host "  $parquetRO parquet data files set read-only"
Write-Host "  $otherRW metadata/index files kept writable"

Write-Host ""
Write-Host "All done."
