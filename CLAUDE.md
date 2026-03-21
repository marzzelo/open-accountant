# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Open Accountant** is a browser-based personal double-entry accounting application.
- **Backend**: FastAPI (Python 3.10+) with SQLite (WAL mode)
- **Frontend**: Vanilla JavaScript + Tailwind CSS (SPA, no framework)
- **Default port**: 5001

## Commands

### Setup
```bash
bash install.sh           # Linux/macOS installer (creates .venv, seeds demo data)
pip install -r requirements.txt -r requirements-dev.txt  # Manual dev install
python scripts/seed_demo.py  # Regenerate demo database
```

### Run
```bash
bash start.sh             # Recommended (auto-finds Python 3.10+)
.venv/bin/python main.py  # Direct run with hot-reload
```

### Test
```bash
pytest                    # Run all tests
pytest tests/test_api_smoke.py          # API integration tests only
pytest tests/test_services_unit.py      # Unit tests only
pytest -k "test_accounts"               # Run tests matching a pattern
```

### Docker
```bash
docker build -t open-accountant:local .
docker run --rm -p 5001:5001 -v open-accountant-data:/app/data open-accountant:local
```

## Architecture

### Request Flow
```
HTTP Request → routers/ (FastAPI handlers)
                  → services/ (business logic, validation)
                      → database.py (SQLite queries)
                          → data/<book>.db (per-book SQLite files)
```

### Key Files
- [main.py](main.py) — App entry point, router registration, lifespan hooks
- [database.py](database.py) — SQLite schema, migrations, balance helpers, `get_db()` context manager
- [models.py](models.py) — Pydantic v2 request/response schemas
- [app_config.py](app_config.py) — Config hierarchy: env vars → `app_meta.sqlite3` → legacy `config.ini` → hardcoded defaults
- [services/errors.py](services/errors.py) — Custom exceptions (`ValidationError`, `NotFoundError`, `ConflictError`)

### Multi-Book System
Each accounting book is a separate SQLite file in `data/` (e.g., `data/home.db`). Global settings are in `data/app_meta.sqlite3`. The active book is tracked in app config.

### Double-Entry Accounting Logic
Every transaction debits one account and credits another. Balance calculation uses account type:
- **Debit-normal** (Asset type_id=1, Expense type_id=4): `balance = initial + debit_total - credit_total`
- **Credit-normal** (Liability, Income, Equity): `balance = initial - debit_total + credit_total`

### Database Schema
```
types → subtypes → accounts → transactions
                 → user_preferences (key-value JSON store, per-book)
```

### Frontend SPA
No client-side router. View switching is manual (`showView(name)`), toggling `display: none/block`. Translation via `t()` in [static/js/i18n.js](static/js/i18n.js). Locale files at [static/locales/](static/locales/) (en/es).

Key JS files:
- [static/js/app.js](static/js/app.js) — Bootstrap, filter state, view switching
- [static/js/forms.js](static/js/forms.js) — Account/transaction modals, FX conversion
- [static/js/board.js](static/js/board.js) — Kanban board with drag-drop transfers
- [static/js/reports.js](static/js/reports.js) — Balance sheet, journal, ledger, stats
- [static/js/settings.js](static/js/settings.js) — Settings panel, book management

### Currency Support
Transactions store `original_amount`, `original_currency`, `fx_rate`, `fx_source` for USD/ARS dual-currency support. Rates are configurable in Settings → Finance.

## Testing Conventions
- Tests use `conftest.py` fixtures with isolated `tmp_path` directories — no shared state between tests
- `monkeypatch` redirects config paths to temp dirs
- `TestClient` (FastAPI) for HTTP-level integration tests
- CI runs on PR/push to main via GitHub Actions
