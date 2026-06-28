#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONUTF8=1

dotenv_path="$repo_root/.env"
if [[ -f "$dotenv_path" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi

    if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ && -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < "$dotenv_path"
fi

export STUDIO_THIRD_PARTY_LOG_LEVEL="${STUDIO_THIRD_PARTY_LOG_LEVEL:-ERROR}"
export WORKFLOW_LOG_ROOT="${WORKFLOW_LOG_ROOT:-$repo_root/artifacts}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$repo_root/.uv-cache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$repo_root/.uv-python}"

exec uv run langgraph dev --no-browser --host 127.0.0.1 --port 8124
