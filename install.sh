#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Open Accountant — Linux / macOS installer
# Usage:  bash install.sh [--port 5001] [--host 127.0.0.1] [--force-db]
# ─────────────────────────────────────────────────────────────────────────────
set -e

PYTHON=""
PYTHON_VERSION=""
VENV_DIR=".venv"
VENV_PYTHON=""
HOST="127.0.0.1"
PORT="5001"
FORCE_DB=0

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)    HOST="$2";  shift 2 ;;
        --port)    PORT="$2";  shift 2 ;;
        --force-db) FORCE_DB=1; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m  •\033[0m $*"; }
ok()    { echo -e "\033[1;32m  ✓\033[0m $*"; }
warn()  { echo -e "\033[1;33m  ⚠\033[0m $*"; }
die()   { echo -e "\033[1;31m  ✗\033[0m $*"; exit 1; }

find_python() {
    local candidate
    local version

    while IFS= read -r candidate; do
        [[ -z "$candidate" ]] && continue
        command -v "$candidate" &>/dev/null || continue

        version=$("$candidate" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null) || continue
        "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null || continue

        if [[ -z "$PYTHON_VERSION" ]] || [[ "$(printf '%s\n%s\n' "$PYTHON_VERSION" "$version" | sort -V | tail -n1)" == "$version" && "$version" != "$PYTHON_VERSION" ]]; then
            PYTHON="$candidate"
            PYTHON_VERSION="$version"
        fi
    done < <(
        {
            printf '%s\n' python3 python
            compgen -c python 2>/dev/null || true
        } | grep -E '^python([0-9]+([.][0-9]+)*)?$' | awk '!seen[$0]++'
    )

    [[ -n "$PYTHON" ]]
}

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Open Accountant — Installer        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── 1. Find Python 3.10+ ──────────────────────────────────────────────────────
info "Checking Python version…"
find_python || die "Python 3.10+ is required. Please install it and re-run."
ok "Found $PYTHON ($PYTHON_VERSION)"

# ── 2. Create or reuse virtual environment ───────────────────────────────────
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    info "Creating virtual environment in $VENV_DIR…"
    "$PYTHON" -m venv "$VENV_DIR" || die "Failed to create virtual environment in $VENV_DIR."
    ok "Virtual environment created"
else
    warn "$VENV_DIR already exists — reusing"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
[[ -x "$VENV_PYTHON" ]] || die "Virtual environment is missing $VENV_PYTHON."

# ── 3. Install Python dependencies ────────────────────────────────────────────
info "Installing Python dependencies in $VENV_DIR…"
"$VENV_PYTHON" -m pip install --upgrade pip --quiet || die "pip upgrade failed inside $VENV_DIR."
"$VENV_PYTHON" -m pip install -r requirements.txt --quiet || die "pip install failed inside $VENV_DIR."
ok "Dependencies installed"

# ── 4. Initialize SQLite app settings ────────────────────────────────────────
info "Initializing SQLite app settings…"
"$VENV_PYTHON" -c "import app_config; app_config.load(); app_config.set_value('general', 'host', '$HOST'); app_config.set_value('general', 'port', '$PORT')" \
    || die "Failed to initialize SQLite app settings."
ok "SQLite app settings ready (host=$HOST, port=$PORT)"

# ── 5. Create .env if missing ─────────────────────────────────────────────────
if [[ ! -f .env && -f .env.example ]]; then
    info "Creating .env from template…"
    cp .env.example .env
    ok ".env created"
fi

# ── 6. Ensure data/ directory ─────────────────────────────────────────────────
mkdir -p data
info "data/ directory ready"

# ── 7. Seed demo database ─────────────────────────────────────────────────────
DB_PATH="data/home.db"
if [[ ! -f "$DB_PATH" || "$FORCE_DB" -eq 1 ]]; then
    info "Creating demo database…"
    FORCE_FLAG=""
    [[ "$FORCE_DB" -eq 1 ]] && FORCE_FLAG="--force"
    "$VENV_PYTHON" scripts/seed_demo.py --db "$DB_PATH" $FORCE_FLAG
    ok "Demo database ready: $DB_PATH"
else
    warn "$DB_PATH already exists — skipping seed (use --force-db to reset)"
fi

# ── 8. Compile i18n .mo files ─────────────────────────────────────────────────
if "$VENV_PYTHON" -c "import babel" 2>/dev/null; then
    info "Compiling translation catalogs…"
    "$VENV_PYTHON" i18n_tools.py extract --quiet 2>/dev/null || true
    "$VENV_PYTHON" i18n_tools.py compile --quiet 2>/dev/null || true
    ok "Translations compiled"
fi

# ── 9. Make start script executable ───────────────────────────────────────────
chmod +x start.sh 2>/dev/null && ok "start.sh is executable" || true

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Installation complete! 🎉          ║"
echo "  ╠══════════════════════════════════════╣"
echo "  ║   Run:  bash start.sh               ║"
echo "  ║   Venv: .venv                       ║"
echo "  ║   Open: http://$HOST:$PORT/          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
