# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project is intended to follow Semantic Versioning.

## [Unreleased]

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