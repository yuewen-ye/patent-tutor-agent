$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONUTF8 = "1"

if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path $repoRoot ".uv-cache"
}

if (-not $env:UV_PYTHON_INSTALL_DIR) {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot ".uv-python"
}

uv run langgraph dev --no-browser --host 127.0.0.1 --port 8124
