# 💰 Open Accountant

> **Personal double-entry accounting — offline, fast, and self-hosted.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Open Accountant is a lightweight, browser-based accounting application built on
**FastAPI** (backend) and **vanilla JavaScript + Tailwind CSS** (frontend).  
It runs entirely on your local machine — no cloud, no subscriptions, no data leaving your network.

---

## ✨ Features

| Feature                     | Details                                                                      |
| --------------------------- | ---------------------------------------------------------------------------- |
| **Double-entry accounting** | Every transaction debits one account and credits another — always balanced   |
| **Multi-book**              | Manage multiple independent accounting books (`.db` files)                   |
| **Kanban board**            | Visual card board with Asset / Expense / Income / Liability & Equity columns |
| **Reports**                 | Balance Sheet, General Journal, General Ledger, Transactions list            |
| **Statistics**              | Bar charts (monthly cash flow), donut charts (by category), top accounts     |
| **CSV / PDF export**        | One-click export for all reports                                             |
| **Internationalization**    | English and Spanish UI — switchable at runtime                               |
| **LAN / Tailscale**         | Configurable bind address; accessible from phone or tablet on your network   |
| **Responsive**              | Mobile-first layout with hamburger drawer, FAB, and bottom-sheet modals      |

### Interface preview

<p align="center">
  <img src="docs/images/board.png" alt="Open Accountant board view" width="70%">
</p>
<p align="center"><em>Main board with accounts grouped by accounting class for quick navigation.</em></p>

<p align="center">
  <img src="docs/images/stats.png" alt="Open Accountant statistics view" width="70%">
</p>
<p align="center"><em>Statistics dashboard with monthly cash flow and category distribution charts.</em></p>

---

## 📋 Requirements

- **Python 3.10+**
- pip (included with Python)
- A modern web browser (Chrome, Firefox, Safari, Edge)

---

## 🚀 Installation

### Linux / macOS

```bash
git clone https://github.com/marzzelo/open-accountant.git
cd open-accountant
bash install.sh
```

Optional flags:

```bash
bash install.sh --host 0.0.0.0 --port 5001   # LAN access
bash install.sh --force-db                    # Reset demo database
```

### Windows

```bat
git clone https://github.com/marzzelo/open-accountant.git
cd open-accountant
install.bat
```

### Manual installation

```bash
# 1. Install dependencies
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 2. Create config
cp config.ini.example config.ini

# 3. Seed demo database
.venv/bin/python scripts/seed_demo.py

# 4. Start
.venv/bin/python main.py
```

Then open **http://127.0.0.1:5001/** in your browser.

---

## ▶️ Running

```bash
bash start.sh                  # Linux / macOS
.venv/bin/python main.py       # Manual run on Linux / macOS
.venv\Scripts\python main.py  # Manual run on Windows
```

The server starts with **hot-reload** enabled — changes to Python files are applied immediately without restarting.

---

## 📖 Usage

### First run

After installation, a demo book named **Home** (`data/home.db`) is created with:

- 19 pre-configured accounts (Assets, Liabilities, Income, Expenses, Equity)
- 34 anonymized example transactions spanning two months

### Creating your own book

1. Open **Settings → Books → + New**
2. Choose a name (e.g., `business`, `personal`)
3. Optionally seed with basic accounts
4. Click **Activate** to switch to it

### Adding transactions

- Click **＋ Account** in the toolbar to create accounts first
- Use the **💸 FAB button** (mobile) or click any account card to register a transaction
- Every transaction specifies a **Credit account** (source) and a **Debit account** (destination)

### Exporting data

- Open any report view (Balance, Journal, Ledger, Transactions)
- Click **CSV** or **PDF** in the top-right of the panel

#### Report examples

<p align="center">
  <img src="docs/images/balance.png" alt="Open Accountant balance sheet report" width="70%">
</p>
<p align="center"><em>Balance Sheet report showing the current state of assets, liabilities, and equity.</em></p>

<p align="center">
  <img src="docs/images/journal.png" alt="Open Accountant journal report" width="70%">
</p>
<p align="center"><em>General Journal view with chronological transaction entries ready to export.</em></p>

<p align="center">
  <img src="docs/images/ledger.png" alt="Open Accountant ledger report" width="70%">
</p>
<p align="center"><em>General Ledger report with account-level movement detail for auditing and review.</em></p>

### Backup & restore

- **Settings → Books → 💾 Backup**: downloads a `.sql` dump
- **Settings → Books → 📥 Import**: restores from a `.sql` dump

---

## 🌐 LAN / Remote Access

To allow access from your phone or another device on the same network:

```ini
# config.ini
[general]
host = 0.0.0.0
port = 5001
```

Then restart the server. Access via `http://<your-local-ip>:5001/`.

For secure remote access, use [Tailscale](https://tailscale.com) — the app works transparently over Tailscale IPs.

---

## 🤖 OpenClaw Integration

Open Accountant can be launched and managed by the [OpenClaw](https://github.com/openclaw/openclaw) AI agent framework.

### Start via OpenClaw

Add to your OpenClaw `HEARTBEAT.md` or invoke via chat:

```
Start Open Accountant at ~/apps/accountant/start.sh
```

### Launcher tile

If you use the OpenClaw Memory Dashboard plugin, add Open Accountant to `launcher.html`:

```html
<a href="http://localhost:5001/" target="_blank" class="card">
  <span class="icon">💰</span>
  <span class="label">Open Accountant</span>
</a>
```

### Agent skill (optional)

You can create a custom OpenClaw skill to query your account balances, register transactions, or generate reports via natural language. See the OpenClaw skill documentation for details.

---

## ⚙️ Configuration Reference

**`config.ini`** (created from `config.ini.example`):

| Key                      | Default           | Description                           |
| ------------------------ | ----------------- | ------------------------------------- |
| `[general] current_book` | `home`            | Active book name (→ `data/<name>.db`) |
| `[general] host`         | `127.0.0.1`       | Bind address                          |
| `[general] port`         | `5001`            | HTTP port                             |
| `[app] name`             | `Open Accountant` | Display name                          |
| `[app] language`         | `en`              | Default language (`en` \| `es`)       |

**`.env`** (optional, for future integrations):

Copy `.env.example` and fill in any optional keys. Sensitive values are masked in the Settings UI.

---

## 🌍 Internationalization

The UI supports **English** and **Spanish** out of the box.

- Switch language at runtime: **Settings → Configuration → 🌐 Language**
- Translation files: `static/locales/en.json`, `static/locales/es.json`
- Gettext catalogs: `locales/{en,es}/LC_MESSAGES/messages.po`

### Adding a new language

```bash
# 1. Copy and translate
cp static/locales/en.json static/locales/fr.json
# Edit fr.json with French translations

# 2. Rebuild .po / .mo files
python3 i18n_tools.py extract
python3 i18n_tools.py compile

# 3. Check coverage
python3 i18n_tools.py stats
```

---

## 🗄️ Data & Privacy

- All data is stored **locally** in SQLite files under `data/`
- Nothing is sent to any external server
- `data/*.db` files are excluded from version control (`.gitignore`)
- `config.ini` is excluded from version control (contains personal settings)

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository and create a feature branch:
   
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. **Keep code clean**: follow existing style (4-space indent, type hints in Python, `'use strict'` in JS)
3. **Translations**: add new UI strings to **both** `en.json` and `es.json`, then rebuild catalogs
4. **No personal data**: never commit `.env`, `config.ini`, or `data/*.db` files
5. **Test manually**: verify the feature works in both English and Spanish
6. Open a **Pull Request** with a clear description of the change

### Reporting issues

Please include:

- OS and Python version
- Steps to reproduce
- Expected vs. actual behavior

---

## 📁 Project Structure

```
open-accountant/
├── main.py                  # FastAPI app entry point
├── database.py              # SQLite schema, seed data, helpers
├── app_config.py            # config.ini reader/writer
├── models.py                # Pydantic models
├── i18n_tools.py            # Babel/gettext utilities
├── requirements.txt
├── config.ini.example       # Config template (safe to commit)
├── .env.example             # Env template (safe to commit)
├── docs/
│   └── images/              # README screenshots
├── install.sh               # Linux/macOS installer
├── install.bat              # Windows installer
├── start.sh                 # Quick-start script
├── routers/
│   ├── accounts.py
│   ├── transactions.py
│   ├── reports.py           # Balance, Journal, Ledger, CSV/PDF
│   ├── types.py
│   ├── subtypes.py
│   ├── books.py             # Multi-book management
│   ├── settings.py          # config.ini + .env API
│   └── about.py             # Developer info (HMAC sealed)
├── scripts/
│   └── seed_demo.py         # Demo database generator
├── static/
│   ├── index.html
│   ├── locales/
│   │   ├── en.json          # English translations
│   │   └── es.json          # Spanish translations
│   └── js/
│       ├── i18n.js          # t() function, language switching
│       ├── app.js           # App bootstrap, filter, view router
│       ├── board.js         # Kanban board
│       ├── forms.js         # Account / transaction modals
│       ├── reports.js       # Report views
│       ├── charts.js        # Chart.js statistics
│       ├── settings.js      # Settings panel
│       └── about.js         # About panel
├── locales/                 # Gettext .po / .mo catalogs
│   ├── en/LC_MESSAGES/
│   └── es/LC_MESSAGES/
└── data/
    └── .gitkeep             # Directory placeholder (DBs are git-ignored)
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with ❤️ and ☕ — contributions welcome.*
