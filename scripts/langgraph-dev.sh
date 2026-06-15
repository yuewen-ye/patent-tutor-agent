#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONUTF8=1
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repo_root/.uv-cache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$repo_root/.uv-python}"

exec uv run langgraph dev --no-browser --host 127.0.0.1 --port 8124
