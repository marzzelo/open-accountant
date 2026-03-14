#!/usr/bin/env bash
# Open Accountant — Quick-start script
# Run from the project root directory.
set -e

PYTHON="${PYTHON:-}"

find_python() {
    local candidate
    local version=""

    while IFS= read -r candidate; do
        [[ -z "$candidate" ]] && continue
        command -v "$candidate" &>/dev/null || continue
        "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null || continue

        local candidate_version
        candidate_version=$("$candidate" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null) || continue
        if [[ -z "$version" ]] || [[ "$(printf '%s\n%s\n' "$version" "$candidate_version" | sort -V | tail -n1)" == "$candidate_version" && "$candidate_version" != "$version" ]]; then
            PYTHON="$candidate"
            version="$candidate_version"
        fi
    done < <(
        {
            printf '%s\n' python3 python
            compgen -c python 2>/dev/null || true
        } | grep -E '^python([0-9]+([.][0-9]+)*)?$' | awk '!seen[$0]++'
    )

    [[ -n "$PYTHON" ]]
}

if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
elif [[ -z "$PYTHON" ]]; then
    find_python || {
        echo "Python 3.10+ not found. Run bash install.sh first."
        exit 1
    }
fi

echo "Starting Open Accountant with $PYTHON…"
exec "$PYTHON" main.py
