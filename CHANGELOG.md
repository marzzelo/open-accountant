# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project is intended to follow Semantic Versioning.

## [Unreleased]

### Added

- **Balance-over-time chart in the General Ledger**: a full-width strip chart (width : height ≈ 10 : 1) sits between the ledger header and the ledger table, plotting the account's daily balance for the last 12 months with vertical dividers on the 1st of each month.
- Clicking the strip opens an enlarged, interactive view of the same chart with **window zoom (drag), pan, and reset** controls; it degrades gracefully to a static chart if the zoom plugin cannot be loaded.
- New API endpoint `GET /api/reports/ledger/{account_id}/balance-series`, which seeds the running balance with every movement before the window so the curve is correct regardless of the global period filter.
- i18n keys for all new UI labels in English and Spanish.

## [2.0.1] - 2026-04-10

### Changed

- Money-like inputs across dialogs, finance settings, and projection trend controls now accept localized non-ambiguous separators and reject ambiguous formats with a validation error.

## [2.0.0] - 2026-04-09

### Changed

- Release baseline advanced to `v2.0.0` for the new major milestone.
- The combined projections chart now marks historical values excluded by the trend range filter with `✕`, matching the UI label.

## [1.4.0] - 2026-03-21

### Added

- **Financial Projections page** (`🔮 Proyecciones`): new dedicated navigation view that forecasts income, expenses, savings, total assets, and total liabilities using ordinary-least-squares linear regression on historical data.
- Configurable **projection horizon** (1, 2, 5, or 10 years) and **history window** (3, 6, 12, or 24 months) with one-click controls.
- **Scheduled series** (projection_series): users can define future income or expense flows with a name, type, start month, duration, and monthly amount. Series are persisted in SQLite and overlaid on top of the regression baseline.
- Horizontally scrollable **series table** with a sticky name column, per-month amounts for active series, and a totals row.
- Five interactive **Chart.js charts** per metric — historical scatter points, dashed regression trend line, and solid filled projection line.
- Accumulated assets and liabilities projections anchored to the real current balance with cumulative cash-flow summation.
- Backward extrapolation of sparse historical months: months without transactions are filled using regression on the months that do have data, preventing zero-filling from distorting the trend.
- New API endpoints: `GET/POST /api/projections/series`, `PUT/DELETE /api/projections/series/{id}`, `GET /api/reports/projections`.
- i18n keys for all new UI labels in English and Spanish.

## [1.3.1] - 2026-03-18

### Added

- Board mobile swipe navigation now cycles across all columns while preserving a selected credit source until the debit account is chosen.
- Board column headers and mobile type tabs now use dedicated image assets instead of emoji icons.
- The Board now shows a persistent in-context hint when a credit account is selected and waiting for the debit account.

### Changed

- Desktop toolbar layout now separates app/book context, centered tool icons, and right-aligned date filters.
- Board mobile tabs were centered and resized to better fit small screens.
- Account balances now retain their negative sign in the UI when the balance is opposite to the account's natural side.

## [1.3.0] - 2026-03-17

### Added

- Persisted multicurrency traceability on transactions with original amount, original currency, FX rate, and FX source fields.
- Journal and ledger actions now include view and edit affordances alongside foreign-currency indicators.
- Transaction detail dialogs now expose the stored FX traceability for each movement.
- API coverage for FX persistence, journal exposure, and transaction update recalculation flows.

### Changed

- Transaction editing now preserves the originally recorded FX ratio while new transactions continue using the current configured rate.
- Journal and ledger layouts were simplified by removing duplicate transaction panels, shrinking large-screen margins, and replacing text actions with icon-only controls.
- Report exports now include FX traceability columns so CSV output stays aligned with the report payloads.

## [1.2.1] - 2026-03-16

### Added

- Report smoke coverage for the statistics and export endpoints.
- Updated documentation screenshots for the board, balance, statistics, and transaction dialog flows.

### Changed

- Report statistics now expose asset composition alongside the existing cash-flow, subtype, and balance evolution series.
- Chart rendering and report aggregation were refined to match the expanded statistics payload.

## [1.2.0] - 2026-03-16

### Added

- Long-press and long-touch board transfers that let you select a credit source card and complete the transfer by tapping a destination card.
- Visual feedback for pending board transfers, including source-card highlighting and confirmation toasts.
- Transaction amount entry in either AR$ or USD, with automatic USD-to-ARS conversion using the configured official buy rate.
- A cash-image drag ghost for board transfers using the new static dollars asset.
- README updates covering the new board workflow, currency-aware transaction entry, and finance configuration.

### Changed

- Board dragging now keeps the ghost centered on the pointer and renders the transfer preview at a larger size.
- Drag ghost rendering was adjusted to avoid the white compositing seam visible on some browsers.

## [1.1.0] - 2026-03-15

### Added

- A collapsible Common Transactions panel on the Board with reusable recent transaction shortcuts.
- PIN / UNPIN support for Common Transactions shortcuts, persisted in the browser for quick access.
- A live status bar for medium and large screens showing Current Assets, Total Assets, Total Liabilities, Net Result, and the current local date/time.
- Refreshed README documentation and interface assets covering the new Board workflow and navigation updates.
- Dedicated community health files for contributing, security, and community conduct.
- GitHub issue templates and a pull request template.
- A pytest-based API smoke test suite for core accounting workflows.
- A GitHub Actions workflow for automated tests and Python compile checks.
- Docker packaging and a GitHub Actions workflow to build and publish container images.
- Publication-oriented documentation updates, including release notes and contributor guidance.

### Changed

- Desktop navigation now uses icon-only toolbar buttons with translated tooltips.
- The mobile drawer now closes consistently for all destinations, including About.
- Board account cards now emphasize account names more strongly for faster scanning.
- Journal, Ledger, and Transactions views now support toggling chronological order ascending or descending.
- The browser tab title now relies on plain text while the favicon carries the app icon.


## [1.0.0] - 2026-03-14

### Added

- Local-first double-entry accounting app built with FastAPI and vanilla JavaScript.
- Multi-book SQLite storage.
- Board view, reports, statistics, CSV export, PDF export, and bilingual UI support.
- Install scripts for Linux, macOS, and Windows.
- OpenClaw-friendly local launch flow.