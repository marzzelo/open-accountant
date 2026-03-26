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

### Entering transactions

- Create transactions from the board, toolbar, or account cards
- Choose ARS or one of the supported USD rate modes: USD buy, USD sell, blue buy, blue sell, or card
- Override the exchange rate manually before saving if needed
- Keep the original foreign-currency amount alongside the booked ARS amount
- Store the FX source used for the conversion so reports can show where the rate came from
- Use force-balance mode to enter a transaction whose goal is to bring either the debit or credit account to a target balance
- Enter simple arithmetic expressions in the amount field when that is more convenient than calculating externally

### Board workflows and shortcuts

- Long-press one card on mobile to mark it as the credit source, then tap another card to open a prefilled transfer
- Drag one card onto another on desktop to open the same transfer flow
- Cancel a pending source selection by tapping the selected origin again
- Reuse recent transaction patterns from the Common transactions panel
- Pin frequently used flows so they stay at the top

### Reports and audit trail

Open Accountant includes four report-oriented views: Balance Sheet, General Journal, General Ledger, and Transactions.

- Journal, Ledger, and Transactions support ascending or descending date review
- The Balance Sheet can hide account lines, keep only subtype totals, and include or exclude zero-balance groups
- The Balance Sheet can also filter visible data by accounting type
- Clicking accounts in balance sections can drill into the related ledger
- Transaction detail modals show booked amount, original amount, currency, FX rate, FX source, date, and description
- CSV and PDF exports preserve the active report context and include FX fields where relevant

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

Settings are split into Books, Configuration, and Env tabs.

- Configure host, port, app name, and language at runtime
- Manage finance rates manually from the UI
- Fetch the latest official and blue USD rates from Bluelytics and automatically derive the card rate
- Keep finance settings globally in data/app_meta.sqlite3
- Migrate legacy finance preferences automatically into the global finance config on startup
- Store report preferences such as hidden-account and zero-balance toggles per book
- Persist report sort directions and other UI preferences
- Edit the root .env file from the UI
- Mask sensitive environment values and preserve hidden secrets unless explicitly changed
- Enable optional FX drag-and-drop sounds

### Backup and restore

- Export any book as a SQL dump from Settings -> Books
- Import an existing SQL dump into a new book
- Keep your data portable without relying on a server-side account or vendor service

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

Global application settings are stored in `data/app_meta.sqlite3`.

| Key | Default | Description |
| --- | --- | --- |
| `[general] current_book` | `home` | Active book name mapped to `data/<name>.db` |
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

Legacy `config.ini` files are treated as migration sources. New installs use SQLite-backed app settings instead.

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

- All business data is stored locally in SQLite files under `data/`
- Nothing is sent to an external cloud service by default
- `data/*.db` files are git-ignored
- `data/app_meta.sqlite3` stores global configuration
- Each book stores its own transactions, accounts, projection series, and user preferences

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

*** Add File: c:\Python\Projects\open-accountant\README-ES.md
[Read this README in English](README.md)

# Open Accountant

> Contabilidad personal de partida doble que corre en forma local, responde rapido y permanece bajo tu control.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Release](https://img.shields.io/github/v/release/marzzelo/open-accountant?display_name=tag)](https://github.com/marzzelo/open-accountant/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Open Accountant es una aplicacion de contabilidad personal basada en navegador, construida con FastAPI, SQLite, JavaScript vanilla, Tailwind CSS y Chart.js. Esta pensada para autoalojarse en tu propia maquina o red local, con los datos guardados localmente en libros SQLite y sin depender de servicios en la nube.

El proyecto fue desarrollado en gran parte con ayuda de IA, especialmente mediante el sistema de agentes OpenClaw. Los contribuyentes tambien pueden usar ese flujo, siempre que cada cambio se revise con cuidado y se explique con claridad.

---

## Caracteristicas

| Area | Detalles |
| --- | --- |
| Contabilidad de partida doble | Cada transaccion debita una cuenta y acredita otra, por lo que los libros quedan balanceados por construccion |
| Gestion multi-libro | Crea, activa, renombra, respalda, importa y elimina libros independientes guardados como archivos SQLite separados |
| Tablero Kanban | Vista visual para activos, pasivos, patrimonio, ingresos y gastos con flujos de transferencia por arrastre y pulsacion prolongada |
| Carga inteligente de transacciones | Los formularios aceptan expresiones en el importe, precarga de origen y destino, atajos reutilizables, flujos fijados y modo de saldo objetivo |
| Registro con monedas | Permite cargar movimientos en ARS o USD usando cotizacion oficial compra, oficial venta, blue compra, blue venta o tarjeta |
| Trazabilidad cambiaria | Las transacciones guardan monto contabilizado, monto original, moneda original, tasa FX y fuente de cotizacion para auditoria posterior |
| Clasificacion financiera | Las cuentas pueden clasificarse por liquidez, plazo del pasivo y gasto esencial o discrecional desde el formulario de cuentas |
| Logica de liquidez robusta | Ratio corriente, prueba acida, runway y salud de proyecciones siguen funcionando aunque se renombren o eliminen subtipos, porque el backend normaliza e infiere propiedades |
| Reportes | Balance General, Libro Diario, Libro Mayor y vista de Transacciones con drill-down, ordenamiento y exportacion CSV y PDF |
| Filtros de reportes | El Balance puede ocultar cuentas, mostrar u ocultar secciones en cero y filtrar por tipo contable |
| Panel estadistico | Tarjetas KPI, analisis de flujo mensual, desgloses de ingresos y gastos, composicion de activos, concentracion por cuentas y evolucion patrimonial |
| Proyecciones | Proyecciones por regresion para ingresos, gastos, ahorro, activos y pasivos, mas series programadas definidas por el usuario |
| Resumen de salud proyectada | Tarjetas con estado actual, final base, final con escenario y delta final para patrimonio, ratios de liquidez y runway |
| Configuracion y preferencias | Cambio de idioma en tiempo real, gestion de cotizaciones, fetch automatico desde Bluelytics, preferencias por libro, edicion enmascarada de .env y sonidos FX opcionales |
| UI responsive | Barra de herramientas de escritorio, menu movil, FAB, modales tipo bottom-sheet y layouts adaptativos |
| Offline y privado | Los datos viven localmente en archivos SQLite dentro de data/ y pueden usarse sin servicios externos |
| Verificacion de integridad | El panel About usa metadatos sellados con HMAC y muestra una alerta si falla la verificacion |

### Vista previa de la interfaz

<p align="center">
  <img src="docs/images/board.png" alt="Vista de tablero de Open Accountant" width="70%">
</p>
<p align="center"><em>Tablero principal con cuentas agrupadas por clase contable para una navegacion rapida.</em></p>

<p align="center">
  <img src="docs/images/stats.png" alt="Vista estadistica de Open Accountant" width="70%">
</p>
<p align="center"><em>Dashboard estadistico con KPI, tendencias de flujo y graficos de salud financiera.</em></p>

---

## Requisitos

- Python 3.10+
- pip
- Un navegador moderno como Chrome, Firefox, Safari o Edge

---

## Instalacion

### Linux / macOS

```bash
git clone https://github.com/marzzelo/open-accountant.git
cd open-accountant
bash install.sh
```

Flags opcionales:

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

### Instalacion manual

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/seed_demo.py
.venv/bin/python main.py
```

Luego abre http://127.0.0.1:5001/ en tu navegador.

### Docker

```bash
docker build -t open-accountant:local .
docker run --rm -p 5001:5001 -v open-accountant-data:/app/data open-accountant:local
```

Las imagenes tambien pueden distribuirse via GHCR como:

`ghcr.io/marzzelo/open-accountant`

---

## Ejecucion

```bash
bash start.sh
.venv/bin/python main.py
.venv\Scripts\python main.py
```

El servidor de desarrollo se inicia con recarga en caliente para el codigo Python.

## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

El repositorio incluye tests unitarios, smoke tests de API y un workflow de GitHub Actions que los ejecuta en pushes y pull requests.

---

## Uso

### Primera ejecucion

Despues de instalar, se crea un libro demo llamado Home con cuentas sembradas y transacciones anonimizadas para que puedas explorar la interfaz de inmediato.

### Gestion de libros

- Crea nuevos libros desde Settings -> Books
- Opcionalmente inicia un libro nuevo con cuentas basicas
- Activa otro libro actual sin reiniciar la interfaz del navegador
- Renombra libros desde el panel de configuracion
- Descarga backups SQL por libro
- Importa un volcado SQL en un libro nuevo
- Mantiene transacciones, cuentas y preferencias de usuario aisladas por libro

### Cuentas y clasificacion financiera

Las cuentas soportan la estructura habitual de tipo, subtipo, descripcion y saldo inicial, mas un payload normalizado de propiedades usado por analitica y proyecciones.

- Las cuentas de activo pueden marcarse como liquidez inmediata, corriente o no corriente
- Las cuentas de pasivo pueden marcarse como corriente o de largo plazo
- Las cuentas de gasto pueden marcarse como esenciales o discrecionales
- Si dejas esos selectores en automatico, el backend infiere una clasificacion razonable a partir del nombre de la cuenta y del subtipo
- Los ratios y el runway siguen funcionando aunque el usuario renombre o elimine etiquetas de subtipos, porque la clasificacion se guarda a nivel cuenta y se normaliza del lado servidor

### Carga de transacciones

- Crea transacciones desde el tablero, la barra superior o las tarjetas de cuenta
- Elige ARS o alguno de los modos USD soportados: compra, venta, blue compra, blue venta o tarjeta
- Sobrescribe manualmente la tasa de cambio antes de guardar si lo necesitas
- Conserva el monto original en moneda extranjera junto al monto contabilizado en ARS
- Guarda la fuente FX usada para que los reportes muestren de donde salio la cotizacion
- Usa el modo de saldo forzado para registrar una transaccion cuyo objetivo sea llevar la cuenta debitada o acreditada a un saldo determinado
- Ingresa expresiones aritmeticas simples en el campo de importe cuando te resulte mas practico que calcular afuera

### Flujos del tablero y atajos

- Haz pulsacion prolongada sobre una tarjeta en mobile para marcarla como cuenta origen de credito y luego toca otra tarjeta para abrir una transferencia precargada
- Arrastra una tarjeta sobre otra en desktop para abrir el mismo flujo de transferencia
- Cancela una seleccion de origen tocando nuevamente la tarjeta ya seleccionada
- Reutiliza patrones recientes desde el panel Common transactions
- Fija los flujos mas usados para mantenerlos arriba

### Reportes y auditoria

Open Accountant incluye cuatro vistas orientadas a reportes: Balance General, Libro Diario, Libro Mayor y Transacciones.

- Diario, Mayor y Transacciones soportan orden ascendente o descendente por fecha
- El Balance puede ocultar lineas de cuentas, dejar solo los subtotales y mostrar u ocultar grupos con saldo cero
- El Balance tambien puede filtrar la informacion visible por tipo contable
- Al hacer clic sobre cuentas del balance puedes abrir el mayor relacionado
- Los modales de detalle de transaccion muestran monto contabilizado, monto original, moneda, tasa FX, fuente FX, fecha y descripcion
- Las exportaciones CSV y PDF preservan el contexto activo del reporte e incluyen campos FX cuando corresponde

### Dashboard estadistico

La vista de estadisticas va mas alla de los graficos basicos y resume la salud financiera general.

- Tarjetas KPI para ingresos totales, gastos totales, resultado neto, neto mensual promedio y tasa de ahorro
- Indicadores de volatilidad y cantidad de meses negativos para evaluar calidad del flujo
- Patrimonio neto, ratio de deuda, ratio corriente, prueba acida y runway de liquidez
- Activos corrientes, activos rapidos, pasivos corrientes y base de gasto esencial para interpretar liquidez
- Grafico de flujo mensual con contexto de tendencia movil
- Desgloses de ingresos y gastos por subtipo
- Composicion de activos y concentracion por cuentas principales
- Evolucion patrimonial a lo largo del periodo seleccionado

### Proyecciones financieras

Abre la vista Projections para estimar estados futuros a partir del comportamiento historico y de series planificadas.

- Elige un horizonte de 1 a 10 anos
- Elige una ventana historica de 3 a 24 meses
- Ejecuta proyecciones por regresion para ingresos, gastos, ahorro, activos y pasivos
- Rellena meses historicos dispersos usando regresion para que los faltantes no deformen la tendencia
- Agrega series futuras programadas para cuotas, bonos o gastos previstos
- Edita o elimina esas series desde la misma pantalla
- Compara proyecciones base contra escenarios que incluyen series programadas
- Revisa tarjetas de salud para el estado actual, el final del caso base, el final con escenario y el delta del escenario
- Observa cambios proyectados en patrimonio neto, ratio corriente, prueba acida y runway de liquidez

### Configuracion, preferencias y automatizacion

Settings se divide en pestañas de Books, Configuration y Env.

- Configura host, puerto, nombre de la app e idioma en tiempo real
- Gestiona las cotizaciones financieras manualmente desde la UI
- Trae la ultima cotizacion oficial y blue desde Bluelytics y deriva automaticamente la cotizacion tarjeta
- Guarda la configuracion financiera global en data/app_meta.sqlite3
- Migra automaticamente preferencias financieras legacy hacia la configuracion global al iniciar
- Guarda por libro preferencias como ocultar cuentas o mostrar saldos cero
- Persiste direcciones de orden en reportes y otras preferencias visuales
- Edita el archivo raiz .env desde la UI
- Enmascara variables sensibles y conserva secretos ocultos salvo que se modifiquen explicitamente
- Habilita efectos de sonido FX opcionales para arrastre y transiciones

### Backup y restauracion

- Exporta cualquier libro como volcado SQL desde Settings -> Books
- Importa un volcado SQL existente en un libro nuevo
- Mantiene tus datos portables sin depender de cuentas de usuario o servicios del proveedor

### About e integridad

La vista About expone metadatos del proyecto, version, enlace al codigo fuente e informacion del autor. Esos metadatos se verifican con un control de integridad basado en HMAC, y la interfaz muestra una advertencia si falla esa verificacion.

---

## Acceso por LAN / remoto

Configura la direccion de enlace a un host visible en la red, como 0.0.0.0, si quieres acceder desde otro dispositivo en tu LAN. Con el servidor en marcha, abre desde otro dispositivo:

`http://<tu-ip-local>:5001/`

Para acceso remoto seguro, Tailscale funciona muy bien porque la app no es mas que un servicio HTTP ejecutandose en tu propia maquina.

---

## Integracion con OpenClaw

Open Accountant puede iniciarse y gestionarse desde el framework de agentes OpenClaw.

### Inicio via OpenClaw

Agrega esto a HEARTBEAT.md de OpenClaw o invocalo por chat:

```text
Start Open Accountant at ~/apps/accountant/start.sh
```

### Tile del launcher

Si usas el plugin OpenClaw Memory Dashboard, agrega Open Accountant a launcher.html:

```html
<a href="http://localhost:5001/" target="_blank" class="card">
  <span class="icon">💰</span>
  <span class="label">Open Accountant</span>
</a>
```

### Skill del agente

Tambien puedes construir una skill de OpenClaw para consultar saldos, registrar transacciones o producir reportes con lenguaje natural.

---

## Referencia de configuracion

La configuracion global de la aplicacion se almacena en `data/app_meta.sqlite3`.

| Key | Default | Descripcion |
| --- | --- | --- |
| `[general] current_book` | `home` | Nombre del libro activo mapeado a `data/<name>.db` |
| `[general] host` | `0.0.0.0` | Direccion de enlace del servidor |
| `[general] port` | `5001` | Puerto HTTP |
| `[app] name` | `Open Accountant` | Nombre visible de la aplicacion |
| `[app] language` | `en` | Idioma de la interfaz por defecto |
| `[finance] usd_official_buy_ars` | `0.00` | Cotizacion oficial compra usada al registrar transacciones en USD |
| `[finance] usd_official_sell_ars` | `0.00` | Cotizacion oficial venta |
| `[finance] usd_blue_buy_ars` | `0.00` | Cotizacion blue compra |
| `[finance] usd_blue_sell_ars` | `0.00` | Cotizacion blue venta |
| `[finance] usd_card_ars` | `0.00` | Cotizacion tarjeta, derivada de oficial venta x 1.30 |
| `[finance] usd_official_last_update` | `` | Marca temporal de la ultima actualizacion financiera manual o automatica |

Los archivos legacy `config.ini` se tratan solo como fuentes de migracion. Las instalaciones nuevas usan configuracion respaldada por SQLite.

Las variables de entorno opcionales se leen desde el archivo raiz `.env`, que puede editarse desde Settings -> Env. Las claves sensibles se muestran enmascaradas en la UI.

---

## Internacionalizacion

La interfaz soporta ingles y espanol de forma nativa.

- Cambia el idioma en tiempo real desde Settings -> Configuration
- Las traducciones JSON viven en `static/locales/`
- Los catalogos Gettext viven en `locales/{en,es}/LC_MESSAGES/messages.po`

### Agregar un nuevo idioma

```bash
cp static/locales/en.json static/locales/fr.json
python3 i18n_tools.py extract
python3 i18n_tools.py compile
python3 i18n_tools.py stats
```

---

## Datos y privacidad

- Toda la informacion de negocio se guarda localmente en archivos SQLite dentro de `data/`
- Por defecto no se envia nada a servicios cloud externos
- Los archivos `data/*.db` estan ignorados por git
- `data/app_meta.sqlite3` guarda la configuracion global
- Cada libro guarda sus propias transacciones, cuentas, series de proyeccion y preferencias de usuario

---

## Contribuir

Las contribuciones son bienvenidas.

- Lee `CONTRIBUTING.md` para el flujo de trabajo
- Sigue `CODE_OF_CONDUCT.md` en todos los espacios del proyecto
- Usa `SECURITY.md` para reportar vulnerabilidades en privado
- Revisa `CHANGELOG.md` para notas de version

Las contribuciones asistidas por IA son bienvenidas, pero siguen requiriendo revision cuidadosa.

### Reporte de issues

Incluye por favor:

- OS y version de Python
- Pasos para reproducir
- Comportamiento esperado y comportamiento real

---

## Releases y versionado

Open Accountant busca seguir Semantic Versioning.

- Las notas de version viven en `CHANGELOG.md`
- Los tags git deben usar el formato `vX.Y.Z`
- GitHub Actions puede construir artefactos de test e imagenes Docker
- Los releases etiquetados pueden publicar assets empaquetados automaticamente
- Docker es el formato principal para despliegues reproducibles

---

## Estructura del proyecto

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

## Licencia

Licencia MIT. Ve `LICENSE` para mas detalles.

## Sobre el autor

<p align="left">
  <img src="docs/images/marzzelo.png" alt="autor" width="30%">
</p>

Marcelo Valdez es Ingeniero Electronico y Desarrollador de Software, enfocado en adquisicion de datos, instrumentacion, analisis de senales, APIs y aplicaciones impulsadas por IA. Construye software practico que conecta necesidades reales de ingenieria con herramientas modernas de desarrollo, con fuerte enfasis en Python, automatizacion y resolucion tecnica de problemas. Vive en Cordoba, Argentina.

- GitHub: https://github.com/marzzelo
- LinkedIn: https://www.linkedin.com/in/marcelovaldez/
- Email: zedlavolecram@gmail.com