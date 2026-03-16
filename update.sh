#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/apps/accountant}"
PORT="${PORT:-5001}"

cd "$PROJECT_DIR"

pid="$(ss -tlnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -n1 || true)"
if [[ -n "$pid" ]]; then
    kill "$pid"
fi

git pull

if [[ -x ".venv/bin/python" ]]; then
    .venv/bin/python -m pip install -r requirements.txt --quiet
else
    pip install -r requirements.txt --quiet
fi

mkdir -p logs
nohup bash start.sh &> logs/server.log &
