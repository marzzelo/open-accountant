#!/usr/bin/env bash
# Open Accountant — Quick-start script
# Run from the project root directory.
set -e

PYTHON="${PYTHON:-python3}"

# Detect Homebrew Python if system Python is outdated (common on macOS/Linux)
for candidate in python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

echo "Starting Open Accountant with $PYTHON…"
exec "$PYTHON" main.py
