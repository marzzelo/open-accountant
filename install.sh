#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Open Accountant — Linux / macOS installer
# Usage:  bash install.sh [--port 5001] [--host 127.0.0.1] [--force-db]
# ─────────────────────────────────────────────────────────────────────────────
set -e

PYTHON=""
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

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Open Accountant — Installer        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── 1. Find Python 3.10+ ──────────────────────────────────────────────────────
info "Checking Python version…"
for candidate in python3 python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        VER=$("$candidate" -c 'import sys; print(sys.version_info[:2])')
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            ok "Found $PYTHON ($("$candidate" --version 2>&1))"
            break
        fi
    fi
done
[[ -z "$PYTHON" ]] && die "Python 3.10+ is required. Please install it and re-run."

# ── 2. Install Python dependencies ────────────────────────────────────────────
info "Installing Python dependencies…"
"$PYTHON" -m pip install -r requirements.txt --quiet \
    || "$PYTHON" -m pip install -r requirements.txt --quiet --break-system-packages \
    || die "pip install failed. Try: pip install -r requirements.txt manually."
ok "Dependencies installed"

# ── 3. Create config.ini ──────────────────────────────────────────────────────
if [[ ! -f config.ini ]]; then
    info "Creating config.ini from template…"
    cp config.ini.example config.ini
    sed -i "s/^host = .*/host = $HOST/"   config.ini
    sed -i "s/^port = .*/port = $PORT/"   config.ini
    ok "config.ini created (host=$HOST, port=$PORT)"
else
    warn "config.ini already exists — skipping"
fi

# ── 4. Create .env if missing ─────────────────────────────────────────────────
if [[ ! -f .env && -f .env.example ]]; then
    info "Creating .env from template…"
    cp .env.example .env
    ok ".env created"
fi

# ── 5. Ensure data/ directory ─────────────────────────────────────────────────
mkdir -p data
info "data/ directory ready"

# ── 6. Seed demo database ─────────────────────────────────────────────────────
DB_PATH="data/home.db"
if [[ ! -f "$DB_PATH" || "$FORCE_DB" -eq 1 ]]; then
    info "Creating demo database…"
    FORCE_FLAG=""
    [[ "$FORCE_DB" -eq 1 ]] && FORCE_FLAG="--force"
    "$PYTHON" scripts/seed_demo.py --db "$DB_PATH" $FORCE_FLAG
    ok "Demo database ready: $DB_PATH"
else
    warn "$DB_PATH already exists — skipping seed (use --force-db to reset)"
fi

# ── 7. Compile i18n .mo files ─────────────────────────────────────────────────
if "$PYTHON" -c "import babel" 2>/dev/null; then
    info "Compiling translation catalogs…"
    "$PYTHON" i18n_tools.py extract --quiet 2>/dev/null || true
    "$PYTHON" i18n_tools.py compile --quiet 2>/dev/null || true
    ok "Translations compiled"
fi

# ── 8. Make start script executable ───────────────────────────────────────────
chmod +x start.sh 2>/dev/null && ok "start.sh is executable" || true

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Installation complete! 🎉          ║"
echo "  ╠══════════════════════════════════════╣"
echo "  ║   Run:  bash start.sh               ║"
echo "  ║   Open: http://$HOST:$PORT/          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
