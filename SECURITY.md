# Security Policy

## Supported Versions

Open Accountant follows semantic versioning for public releases.

Supported runtime baseline:

- Python 3.10 or newer.
- Dependency versions defined in `requirements.txt`.

| Version | Supported |
| ------- | --------- |
| 1.x     | Yes       |
| 0.x     | No        |
| < 1.0   | No        |

## Reporting a Vulnerability

Please report security issues privately.

- Email: zedlavolecram@gmail.com
- Subject suggestion: `Open Accountant security report`

Please include as much detail as you can:

- A clear description of the issue.
- Steps to reproduce it.
- The affected version or branch.
- Impact assessment, if known.
- A suggested fix, if you have one.

Please do not open a public GitHub issue for security vulnerabilities.

## Response Expectations

The project aims to:

- Acknowledge new reports within 72 hours.
- Confirm whether the issue is reproducible.
- Share remediation progress when possible.
- Credit responsible disclosure unless the reporter prefers to stay private.

## Security Notes

- User data is stored locally in SQLite databases under `data/`.
- Sensitive runtime values should live in `.env`, not in committed files.
- Do not share real personal accounting data in bug reports, pull requests, or screenshots.