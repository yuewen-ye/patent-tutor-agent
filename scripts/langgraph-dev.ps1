$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONUTF8 = "1"

$dotenvPath = Join-Path $repoRoot ".env"
if (Test-Path $dotenvPath) {
    Get-Content -Encoding UTF8 $dotenvPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $key, $value = $line.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim()

        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        if ($key -match "^[A-Za-z_][A-Za-z0-9_]*$" -and -not [Environment]::GetEnvironmentVariable($key)) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

if (-not $env:STUDIO_THIRD_PARTY_LOG_LEVEL) {
    $env:STUDIO_THIRD_PARTY_LOG_LEVEL = "ERROR"
}
if (-not $env:WORKFLOW_LOG_ROOT) {
    $env:WORKFLOW_LOG_ROOT = Join-Path $repoRoot "artifacts"
}

if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path $repoRoot ".uv-cache"
}

if (-not $env:UV_PYTHON_INSTALL_DIR) {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot ".uv-python"
}

$dbPath = Join-Path $repoRoot "backend\app\rag\data\milvus_lite.db"
if (Test-Path $dbPath) {
    $lockFile = Join-Path $dbPath "LOCK"
    if (Test-Path $lockFile) {
        Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
        Write-Host "[init] 已清理残留 LOCK 文件"
    }
    Get-ChildItem -Path $dbPath -Recurse -File | Set-ItemProperty -Name IsReadOnly -Value $true
    $fileCount = (Get-ChildItem -Path $dbPath -Recurse -File).Count
    Write-Host "[init] 数据库已设为只读（$fileCount 个文件）"
} else {
    Write-Host "[init] 数据库目录不存在，跳过只读设置"
}

uv run langgraph dev --no-reload --no-browser --host 127.0.0.1 --port 8124
