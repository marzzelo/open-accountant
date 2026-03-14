# Contributing to Open Accountant

Thanks for your interest in Open Accountant.

This project is built to stay practical, simple to run, and easy to understand. A large part of its development has been AI-assisted, especially with OpenClaw, and contributors are welcome to use AI tools in their own work too.

The important part is ownership: if you open a pull request, please make sure you understand the change, test it, and explain it clearly.

## Repository

- Main repository: https://github.com/marzzelo/open-accountant
- Main branch: `main`

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a feature branch from `main`.

```bash
git clone https://github.com/<your-user>/open-accountant.git
cd open-accountant
git checkout -b feature/short-description
```

Use the setup instructions in the README for installation and local execution.

## Development Guidelines

- Keep changes focused and easy to review.
- Follow the existing project style.
- Use 4 spaces for Python indentation.
- Keep Python code typed when the surrounding code already uses type hints.
- Use `'use strict'` in JavaScript files.
- Prefer small, readable functions over clever shortcuts.
- Do not commit `config.ini`, `.env`, or anything inside `data/*.db`.

## AI-Assisted Contributions

AI-assisted work is welcome.

- Open Accountant itself was developed in large part with AI tools, especially OpenClaw.
- You may use GitHub Copilot, OpenClaw, ChatGPT, or similar tools when contributing.
- Please review AI-generated code carefully before submitting it.
- If AI support materially shaped the solution, mention it briefly in the pull request description.
- Contributors remain responsible for correctness, safety, licensing, and clarity.

## Translations

If you add or rename UI text:

1. Update both `static/locales/en.json` and `static/locales/es.json`.
2. Rebuild gettext catalogs.
3. Verify the feature manually in English and Spanish.

```bash
python i18n_tools.py extract
python i18n_tools.py compile
python i18n_tools.py stats
```

## Manual Testing

Before opening a pull request:

1. Run the app locally.
2. Test the affected workflow end to end.
3. Check the UI in English and Spanish if text changed.
4. Confirm exports still work if your change touches reports.
5. Run the automated test suite.

```bash
pytest
```

## Pull Request Process

Please include:

- A short summary of the change.
- Why the change is needed.
- Manual test notes.
- Screenshots or screen recordings for UI changes.
- Linked issues, if any.

Maintainer review flow:

1. A maintainer checks scope, clarity, and test coverage.
2. Feedback is handled in the same pull request whenever possible.
3. Changes are merged only after CI passes and the review is resolved.

The project may use labels such as `good first issue` and `help wanted` to highlight beginner-friendly or open tasks.

## Reporting Bugs

Please include:

- Operating system.
- Python version.
- Clear reproduction steps.
- Expected behavior.
- Actual behavior.
- Screenshots, logs, or sample data when useful.

## Community Standards

By participating in this project, you agree to follow the code of conduct in `CODE_OF_CONDUCT.md`.

## Security

Please do not report security issues in public issues. Use the private reporting instructions in `SECURITY.md`.