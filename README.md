[Leer este README en Español](README-ES.md)

# Open Accountant

> Personal double-entry accounting that runs locally, stays fast, and remains under your control.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Release](https://img.shields.io/github/v/release/marzzelo/open-accountant?display_name=tag)](https://github.com/marzzelo/open-accountant/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Open Accountant is a browser-based personal accounting application built with FastAPI, SQLite, vanilla JavaScript, Tailwind CSS, and Chart.js. It is designed for self-hosted use on your own machine or local network, with data stored locally in SQLite books and no required cloud services.

The project has been developed in large part with AI assistance, especially through the OpenClaw agent system. Contributors are welcome to use the same workflow as long as every change is reviewed carefully and explained clearly.

---

## Features

| Area | Details |
| --- | --- |
| Double-entry accounting | Every transaction debits one account and credits another, so books remain balanced by construction |
| Multi-book management | Create, activate, rename, back up, import, and delete independent accounting books stored as separate SQLite files |
| Kanban board | Visual board for assets, liabilities, equity, income, and expenses with drag-and-drop and long-press transfer workflows |
| Smart transaction entry | Transaction forms support amount expressions, source/destination prefill, reusable shortcuts, pinned frequent flows, and direct balance-targeting mode |
| Currency-aware posting | Record entries in ARS or USD using official buy, official sell, blue buy, blue sell, or card rates |
| FX traceability | Transactions store booked amount, original amount, original currency, FX rate, and FX source for later audit in reports |
| Financial classification | Accounts can be classified with liquidity, liability-term, and essential/discretionary expense properties from the account form |
| Resilient liquidity logic | Current ratio, quick ratio, runway, and projection health work even if subtype labels were renamed or deleted, because the backend normalizes and infers account properties |
| Reports | Balance Sheet, General Journal, General Ledger, and Transactions views with drill-down, sorting, CSV export, and PDF export |
| Report filters | Balance view can hide account rows, show or hide zero-balance sections, and filter by accounting type |
| Statistics dashboard | KPI cards, monthly cash-flow analysis, expense and income breakdowns, asset composition, top-account concentration, and net-worth evolution |
| Projections | Regression-based projections for income, expenses, savings, assets, and liabilities, plus user-defined scheduled series |
| Projection health summary | Current, baseline-end, scenario-end, and delta-end health cards for net worth, liquidity ratios, and runway |
| Settings and preferences | Runtime language switching, finance-rate management, automatic Bluelytics fetch, per-book UI preferences, masked .env editing, and optional FX sound effects |
| Responsive UI | Desktop toolbar, mobile drawer, FAB actions, bottom-sheet modals, and screen-aware layouts |
| Offline and private | Data lives locally in SQLite files under data/ and can be used without external services |
| About integrity check | The About panel is backed by HMAC-sealed metadata and shows a tamper warning if integrity verification fails |

### Interface preview

<p align="center">
  <img src="docs/images/board.png" alt="Open Accountant board view" width="70%">
</p>
<p align="center"><em>Main board with accounts grouped by accounting class for quick navigation.</em></p>

<p align="center">
  <img src="docs/images/stats.png" alt="Open Accountant statistics view" width="70%">
</p>
<p align="center"><em>Statistics dashboard with KPI cards, cash-flow trends, and financial-health charts.</em></p>

---

## Requirements

- Python 3.10+
- pip
- A modern web browser such as Chrome, Firefox, Safari, or Edge

---

## Installation

### Linux / macOS

```bash
git clone https://github.com/marzzelo/open-accountant.git
cd open-accountant
bash install.sh
```

Optional flags:

```bash
bash install.sh --host 0.0.0.0 --port 5001
bash install.sh --force-db
```

### Windows

```bat
git clone https://github.com/marzzelo/open-accountant.git
cd open-accountant
install.bat
```

### Manual installation

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/seed_demo.py
.venv/bin/python main.py
```

Then open http://127.0.0.1:5001/ in your browser.

### Docker

```bash
docker build -t open-accountant:local .
docker run --rm -p 5001:5001 -v open-accountant-data:/app/data open-accountant:local
```

Published container images can be distributed through GHCR as:

`ghcr.io/marzzelo/open-accountant`

---

## Running

```bash
bash start.sh
.venv/bin/python main.py
.venv\Scripts\python main.py
```

The development server starts with hot reload enabled for Python code.

## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

The repository includes unit tests, API smoke tests, and a GitHub Actions workflow that runs them on pushes and pull requests.

---

## Usage

### First run

After installation, a demo book named Home is created with seeded accounts and anonymized sample transactions so you can explore the UI immediately.

### Managing books

- Create new books from Settings -> Books
- Optionally seed a new book with basic accounts
- Activate a different current book without restarting the browser UI
- Rename books from the settings panel
- Download SQL backups per book
- Import a SQL dump into a new book
- Keep transactions, accounts, and user preferences isolated per book

### Accounts and financial classification

Accounts support the usual accounting structure of type, subtype, description, and initial balance, plus a normalized properties payload used by analytics and projections.

- Asset accounts can be tagged as quick, current, or non-current
- Liability accounts can be tagged as current or long-term
- Expense accounts can be tagged as essential or discretionary
- If you leave those selectors on automatic, the backend infers a reasonable classification from account and subtype names
- Ratios and runway continue to work even if users rename or delete subtype labels, because classification is stored at the account level and normalized server-side

<p align="center">
  <img src="docs/images/subtypes.png" alt="Open Accountant subtype management" width="70%">
</p>
<p align="center"><em>Subtype management helps keep the chart of accounts organized while giving reports and liquidity logic stable labels to work from.</em></p>

### Entering transactions

- Create transactions from the board, toolbar, or account cards
- Choose ARS or one of the supported USD rate modes: USD buy, USD sell, blue buy, blue sell, or card
- Override the exchange rate manually before saving if needed
- Keep the original foreign-currency amount alongside the booked ARS amount
- Store the FX source used for the conversion so reports can show where the rate came from
- Use force-balance mode to enter a transaction whose goal is to bring either the debit or credit account to a target balance
- Enter simple arithmetic expressions in the amount field when that is more convenient than calculating externally

<p align="center">
  <img src="docs/images/transaction_dialog.png" alt="Open Accountant transaction dialog" width="70%">
</p>
<p align="center"><em>The transaction dialog supports currency mode selection, manual dates, free-form descriptions, and direct balance-adjustment mode.</em></p>

### Board workflows and shortcuts

- Long-press one card on mobile to mark it as the credit source, then tap another card to open a prefilled transfer
- Drag one card onto another on desktop to open the same transfer flow
- Cancel a pending source selection by tapping the selected origin again
- Reuse recent transaction patterns from the Common transactions panel
- Pin frequently used flows so they stay at the top

<p align="center">
  <img src="docs/images/board2.png" alt="Open Accountant board with common transactions" width="70%">
</p>
<p align="center"><em>The board combines reusable common transactions with live account cards so routine transfers can be launched with minimal input.</em></p>

<p align="center">
  <img src="docs/images/transaction_effects.png" alt="Open Accountant drag-and-drop transfer effects" width="70%">
</p>
<p align="center"><em>Drag-and-drop interactions visually emphasize the origin and destination accounts during a transfer, with optional FX feedback effects.</em></p>

### Reports and audit trail

Open Accountant includes four report-oriented views: Balance Sheet, General Journal, General Ledger, and Transactions.

- Journal, Ledger, and Transactions support ascending or descending date review
- The Balance Sheet can hide account lines, keep only subtype totals, and include or exclude zero-balance groups
- The Balance Sheet can also filter visible data by accounting type
- Clicking accounts in balance sections can drill into the related ledger
- Transaction detail modals show booked amount, original amount, currency, FX rate, FX source, date, and description
- CSV and PDF exports preserve the active report context and include FX fields where relevant

<p align="center">
  <img src="docs/images/balance.png" alt="Open Accountant balance sheet" width="70%">
</p>
<p align="center"><em>The Balance Sheet rolls accounts into accounting classes and subtotals while keeping period filters and zero-balance visibility under your control.</em></p>

<p align="center">
  <img src="docs/images/journal.png" alt="Open Accountant general journal" width="70%">
</p>
<p align="center"><em>The General Journal lists postings chronologically and keeps CSV, PDF, detail, edit, and delete actions close to each row.</em></p>

<p align="center">
  <img src="docs/images/ledger.png" alt="Open Accountant general ledger" width="70%">
</p>
<p align="center"><em>The General Ledger focuses on one account at a time, showing counterpart entries, running balance, and export actions.</em></p>

### Statistics dashboard

The statistics view goes beyond basic charts and now summarizes overall financial health.

- KPI cards for total income, total expense, net result, average monthly net, and savings rate
- Volatility and negative-month indicators for cash-flow quality
- Net worth, debt ratio, current ratio, quick ratio, and liquidity runway
- Current assets, quick assets, current liabilities, and essential-expense basis for liquidity interpretation
- Monthly cash-flow chart with rolling trend context
- Income and expense breakdowns by subtype
- Asset composition and top-account concentration
- Net-worth evolution across the selected period

<p align="center">
  <img src="docs/images/stats1.png" alt="Open Accountant statistics summary" width="70%">
</p>
<p align="center"><em>The statistics header summarizes income, expenses, savings rate, liquidity, and concentration before you drill into the monthly trend.</em></p>

<p align="center">
  <img src="docs/images/stats2.png" alt="Open Accountant statistics breakdowns" width="70%">
</p>
<p align="center"><em>Breakdowns by category, asset composition, and top-account concentration make it easier to spot structural dependencies in the book.</em></p>

### Financial projections

Open the Projections view to estimate future states from historical behavior plus planned series.

- Choose a horizon from 1 to 10 years
- Choose a history window from 3 to 24 months
- Run regression-based projections for income, expenses, savings, assets, and liabilities
- Fill sparse historical months using regression so missing months do not collapse the trend
- Add scheduled future series for income or expense installments
- Edit or delete those series from the same screen
- Compare baseline projections against scenario projections that include scheduled series
- Review health summary cards for current state, end-of-baseline, end-of-scenario, and scenario delta
- See projected changes in net worth, current ratio, quick ratio, and liquidity runway

### Settings, preferences, and automation

Settings are split into Configuration and Env tabs.

- Configure host, port, app name, and language at runtime
- Manage finance rates manually from the UI
- Fetch the latest official and blue USD rates from Bluelytics and automatically derive the card rate
- Store runtime settings in the main database (`oacc_settings` on PostgreSQL, `settings` on SQLite fallback)
- Migrate legacy finance preferences automatically into the global finance config on startup
- Store report preferences such as hidden-account and zero-balance toggles globally for the active dataset
- Persist report sort directions and other UI preferences
- Edit the root .env file from the UI
- Mask sensitive environment values and preserve hidden secrets unless explicitly changed
- Enable optional FX drag-and-drop sounds

<p align="center">
  <img src="docs/images/config.png" alt="Open Accountant settings and finance configuration" width="70%">
</p>
<p align="center"><em>Settings centralize bind address, finance rates, language, and optional FX sound effects in one panel.</em></p>

### Migration to PostgreSQL

- Set `DATABASE_URL` to a PostgreSQL database to use shared-hosting mode
- The app stores all application tables with the `oacc_` prefix to coexist with other systems
- Use `scripts/migrate_sqlite_to_postgres.py` as the independent one-off migration path from legacy SQLite data
- If `DATABASE_URL` is omitted, the app falls back to a single local SQLite database at `data/open_accountant.db`

### About and integrity

The About view exposes project metadata, version, source link, and author information. The metadata is verified with an HMAC-based integrity check, and the UI shows a warning if that verification fails.

---

## LAN / Remote Access

Set the bind address to a network-visible host such as 0.0.0.0 if you want to reach the app from another device on your LAN. Once the server is running, open it from another device using:

`http://<your-local-ip>:5001/`

For secure remote access, Tailscale works well because the app is just an HTTP service on your own machine.

---

## OpenClaw Integration

Open Accountant can be launched and managed by the OpenClaw AI agent framework.

### Start via OpenClaw

Add this to your OpenClaw HEARTBEAT.md or invoke it via chat:

```text
Start Open Accountant at ~/apps/accountant/start.sh
```

### Launcher tile

If you use the OpenClaw Memory Dashboard plugin, add Open Accountant to launcher.html:

```html
<a href="http://localhost:5001/" target="_blank" class="card">
  <span class="icon">💰</span>
  <span class="label">Open Accountant</span>
</a>
```

### Agent skill

You can also build an OpenClaw skill to query balances, register transactions, or produce reports through natural language.

---

## Configuration Reference

Runtime settings are stored in the main database. On PostgreSQL they live in `oacc_settings`; on the SQLite fallback they live in `data/open_accountant.db` under `settings`.

| Key | Default | Description |
| --- | --- | --- |
| `[general] host` | `0.0.0.0` | Server bind address |
| `[general] port` | `5001` | HTTP port |
| `[app] name` | `Open Accountant` | Display name |
| `[app] language` | `en` | Default UI language |
| `[finance] usd_official_buy_ars` | `0.00` | Official USD buy rate used when posting USD transactions |
| `[finance] usd_official_sell_ars` | `0.00` | Official USD sell rate |
| `[finance] usd_blue_buy_ars` | `0.00` | Blue USD buy rate |
| `[finance] usd_blue_sell_ars` | `0.00` | Blue USD sell rate |
| `[finance] usd_card_ars` | `0.00` | Card USD rate, derived from official sell x 1.30 |
| `[finance] usd_official_last_update` | `` | Last manual or automatic finance update timestamp |

Legacy `config.ini` and `data/app_meta.sqlite3` files are treated as migration sources. New installs use the main application database for settings.

Optional environment variables are read from the project root `.env` file, which can be edited from Settings -> Env. Sensitive keys are masked in the UI.

---

## Internationalization

The UI supports English and Spanish out of the box.

- Switch language at runtime from Settings -> Configuration
- JSON UI translations live in `static/locales/`
- Gettext catalogs live in `locales/{en,es}/LC_MESSAGES/messages.po`

### Adding a new language

```bash
cp static/locales/en.json static/locales/fr.json
python3 i18n_tools.py extract
python3 i18n_tools.py compile
python3 i18n_tools.py stats
```

---

## Data and Privacy

- Business data can run on PostgreSQL via `DATABASE_URL`, or on the local SQLite fallback at `data/open_accountant.db`
- Nothing is sent to an external cloud service by default
- `data/*.db` files are git-ignored
- On PostgreSQL, Open Accountant tables are prefixed with `oacc_`
- The legacy multi-book layout is superseded by a single shared dataset

---

## Contributing

Contributions are welcome.

- Read `CONTRIBUTING.md` for the workflow
- Follow `CODE_OF_CONDUCT.md` in all project spaces
- Use `SECURITY.md` for private vulnerability reporting
- Review release notes in `CHANGELOG.md`

AI-assisted contributions are welcome, but they still need careful review.

### Reporting issues

Please include:

- OS and Python version
- Steps to reproduce
- Expected behavior and actual behavior

---

## Releases and Versioning

Open Accountant is intended to follow Semantic Versioning.

- Release notes live in `CHANGELOG.md`
- Git tags should use the `vX.Y.Z` format
- GitHub Actions can build test artifacts and Docker images
- Tagged releases can publish packaged source assets automatically
- Docker is the primary reproducible packaging format

---

## Project Structure

```text
open-accountant/
├── main.py
├── database.py
├── app_config.py
├── models.py
├── i18n_tools.py
├── requirements.txt
├── requirements-dev.txt
├── config.ini.example
├── docs/
│   └── images/
├── install.sh
├── install.bat
├── start.sh
├── routers/
│   ├── accounts.py
│   ├── books.py
│   ├── projections.py
│   ├── reports.py
│   ├── settings.py
│   ├── subtypes.py
│   ├── transactions.py
│   ├── types.py
│   └── about.py
├── services/
│   ├── accounts_service.py
│   ├── projections_service.py
│   ├── reports_service.py
│   ├── settings_service.py
│   ├── transactions_service.py
│   ├── helpers.py
│   └── about_service.py
├── scripts/
│   └── seed_demo.py
├── static/
│   ├── index.html
│   ├── css/
│   ├── images/
│   ├── locales/
│   │   ├── en.json
│   │   └── es.json
│   └── js/
│       ├── about.js
│       ├── app.js
│       ├── board.js
│       ├── charts.js
│       ├── forms.js
│       ├── fx.js
│       ├── i18n.js
│       ├── projections.js
│       ├── reports.js
│       └── settings.js
├── locales/
│   ├── en/LC_MESSAGES/
│   └── es/LC_MESSAGES/
├── tests/
│   ├── test_api_smoke.py
│   └── test_services_unit.py
└── data/
    └── .gitkeep
```

---

## License

MIT License. See `LICENSE` for details.

## About the Author

<p align="left">
  <img src="docs/images/marzzelo.png" alt="the author" width="30%">
</p>

Marcelo Valdez is an Electronics Engineer and Software Developer focused on data acquisition, instrumentation, signal analysis, APIs, and AI-powered applications. He builds practical software that connects real-world engineering needs with modern development tools, with a strong emphasis on Python, automation, and technical problem-solving. He lives in Cordoba, Argentina.

- GitHub: https://github.com/marzzelo
- LinkedIn: https://www.linkedin.com/in/marcelovaldez/
- Email: zedlavolecram@gmail.com


[Leer esto en español](README-ES.md)

