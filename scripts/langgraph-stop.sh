#!/usr/bin/env bash
# Stop LangGraph Studio dev server(s) on port 8124.
set -euo pipefail

port="${1:-8124}"

pids=$(lsof -ti ":$port" 2>/dev/null || true)

if [[ -z "$pids" ]]; then
  echo "No process found on port $port."
  exit 0
fi

echo "Killing process(es) on port $port: $pids"
kill -9 $pids
echo "Done."
