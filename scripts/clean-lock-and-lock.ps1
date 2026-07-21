$dest = "T:\Study\Learn\Multi-Agent\patent-tutor-agent\backend\app\rag\data\milvus_lite.db"

Get-ChildItem -Path $dest -Recurse -File | Set-ItemProperty -Name IsReadOnly -Value $false

$lockFile = Join-Path $dest "LOCK"
if (Test-Path $lockFile) {
    Remove-Item $lockFile -Force
    Write-Host "LOCK 文件已删除"
} else {
    Write-Host "LOCK 文件不存在"
}

Get-ChildItem -Path $dest -Recurse -File | Set-ItemProperty -Name IsReadOnly -Value $true
Write-Host "已重新设置只读"
Write-Host "剩余文件数: $((Get-ChildItem $dest -Recurse -File).Count)"
