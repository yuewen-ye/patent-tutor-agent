$src = "T:\Study\Learn\Multi-Agent\OCR-RAG\milvus_lite.db"
$dest = "T:\Study\Learn\Multi-Agent\patent-tutor-agent\backend\app\rag\data\milvus_lite.db"

$srcLock = Join-Path $src "LOCK"
if (Test-Path $srcLock) {
    Remove-Item $srcLock -Force
    Write-Host "[1] OCR-RAG LOCK 已删除"
} else {
    Write-Host "[1] OCR-RAG 无 LOCK 文件"
}

Write-Host "[2] 删除 patent 旧数据库..."
if (Test-Path $dest) {
    Remove-Item -Recurse -Force $dest
    Write-Host "  已删除"
}

Write-Host "[3] 复制数据库..."
Copy-Item -Recurse $src $dest
$count = (Get-ChildItem $dest -Recurse -File).Count
Write-Host "  复制完成，共 $count 个文件"

$destLock = Join-Path $dest "LOCK"
if (Test-Path $destLock) {
    Remove-Item $destLock -Force
    Write-Host "[4] 已排除 LOCK 文件"
} else {
    Write-Host "[4] 无 LOCK 文件"
}

Write-Host "[5] 设置只读..."
Get-ChildItem -Path $dest -Recurse -File | Set-ItemProperty -Name IsReadOnly -Value $true
$readOnly = (Get-ChildItem -Path $dest -Recurse -File | Where-Object { $_.IsReadOnly -eq $true }).Count
Write-Host "  $readOnly 个文件已设为只读"

Write-Host ""
Write-Host "全部完成。"
