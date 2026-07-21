$dbPath = "T:\Study\Learn\Multi-Agent\patent-tutor-agent\backend\app\rag\data\milvus_lite.db"

Get-ChildItem -Path $dbPath -Recurse -File | Set-ItemProperty -Name IsReadOnly -Value $true

Write-Host "设置完成，验证结果："
$files = Get-ChildItem -Path $dbPath -Recurse -File
$readOnly = ($files | Where-Object { $_.IsReadOnly -eq $true }).Count
$writable = ($files | Where-Object { $_.IsReadOnly -eq $false }).Count
Write-Host "  总文件数: $($files.Count)"
Write-Host "  只读文件: $readOnly"
Write-Host "  可写文件: $writable"

$lockFile = Join-Path $dbPath "LOCK"
if (Test-Path $lockFile) {
    Write-Host ""
    Write-Host "警告：检测到 LOCK 文件（上次异常退出残留），建议删除后再使用"
}
