[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dbPath = Join-Path $repoRoot "backend\app\rag\data\milvus_lite.db"

if (-not (Test-Path -LiteralPath $dbPath)) {
    throw "Milvus Lite database directory was not found: $dbPath"
}

$files = Get-ChildItem -LiteralPath $dbPath -Recurse -File
foreach ($file in $files) {
    if ($file.Extension -eq ".parquet") {
        attrib +r "$($file.FullName)"
    } else {
        attrib -r "$($file.FullName)"
    }
}

Write-Host "Milvus parquet 数据已只读；LOCK 和集合元数据保持可写。"
Write-Host "LOCK 文件不会由此脚本删除，以免影响正在运行的 Milvus Lite 实例。"
