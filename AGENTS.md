# Open Accountant Agent Guide

Start with [CLAUDE.md](CLAUDE.md), [README.md](README.md), and [CONTRIBUTING.md](CONTRIBUTING.md). Keep this file focused on repo-specific guidance that is easy to miss during a quick scan.

## Runtime Source Of Truth

- Treat [app_config.py](app_config.py), [database.py](database.py), and the files under [db/](db/) as the source of truth for current runtime behavior.
- The current backend requires PostgreSQL and `DATABASE_URL`; the app fails fast if the variable is missing.
- Some repository docs still describe older SQLite behavior. When docs conflict with code, follow [app_config.py](app_config.py), [database.py](database.py), and [CLAUDE.md](CLAUDE.md).

## Architecture

- Keep the request flow thin: `routers/` -> `services/` -> `db/`.
- Put business rules and validation in `services/`. Keep routers focused on HTTP parsing, response models, and dependency wiring.
- Raise domain errors from [services/errors.py](services/errors.py) and rely on the global exception handlers in [main.py](main.py) instead of per-router error translation.
- The frontend is a vanilla JavaScript SPA rooted in [static/index.html](static/index.html). [static/js/app.js](static/js/app.js) owns bootstrap, shared state, and view switching; feature files extend that flow instead of introducing a framework or router.

## Conventions

- Preserve double-entry accounting invariants when editing accounts, balances, reports, or transaction flows.
- When adding or renaming UI text, update both [static/locales/en.json](static/locales/en.json) and [static/locales/es.json](static/locales/es.json), then run `python i18n_tools.py extract` and `python i18n_tools.py compile`.
- Keep JavaScript aligned with the existing module pattern: `'use strict'`, file-scoped helpers, and `window.*` exports where the current code uses them.
- Keep Python typed where surrounding code is typed, and use 4-space indentation.

## Commands

- Install: `pip install -r requirements.txt -r requirements-dev.txt`
- Run on Windows: `.venv\Scripts\python main.py`
- Run tests: `pytest`
- If a change touches reports, exports, or localized UI, prefer a quick manual verification in addition to automated tests.

## Pointers

- Auth and runtime config: [app_config.py](app_config.py), [auth.py](auth.py), [services/auth_service.py](services/auth_service.py)
- Database translation and schema: [database.py](database.py), [db/connection.py](db/connection.py), [db/dialect.py](db/dialect.py), [db/schema.py](db/schema.py)
- Frontend workflow hotspots: [static/js/forms.js](static/js/forms.js), [static/js/board.js](static/js/board.js), [static/js/reports.js](static/js/reports.js), [static/js/settings.js](static/js/settings.js)

## Imported Claude Cowork project instructions
