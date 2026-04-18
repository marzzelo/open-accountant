"""
app_version.py — centralized application and release version helpers.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "Open Accountant"
DEFAULT_TAG = "v2.0.1"
TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
BASE_DIR = Path(__file__).parent
VERSION_FILE = BASE_DIR / "VERSION"
HEROKU_RELEASE_VERSION_ENV = "HEROKU_RELEASE_VERSION"
HEROKU_RELEASE_CREATED_AT_ENV = "HEROKU_RELEASE_CREATED_AT"


def _clean_tag(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if TAG_PATTERN.fullmatch(candidate):
        return candidate
    return None


def _tag_from_env() -> str | None:
    return _clean_tag(os.getenv("OPEN_ACCOUNTANT_VERSION"))


def _clean_release_version(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    return candidate or None


def heroku_release_version() -> str | None:
    return _clean_release_version(os.getenv(HEROKU_RELEASE_VERSION_ENV))


def heroku_release_created_at() -> str | None:
    value = os.getenv(HEROKU_RELEASE_CREATED_AT_ENV)
    return value.strip() if value and value.strip() else None


def formatted_release_created_at() -> str | None:
    raw = heroku_release_created_at()
    if not raw:
        return None

    candidate = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return raw

    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(timezone.utc).date().isoformat()


def _tag_from_file() -> str | None:
    if not VERSION_FILE.exists():
        return None
    return _clean_tag(VERSION_FILE.read_text(encoding="utf-8").strip())


def _tag_from_git() -> str | None:
    git_dir = BASE_DIR / ".git"
    if not git_dir.exists():
        return None

    try:
        output = subprocess.run(
            ["git", "tag", "--list", "v*", "--sort=-v:refname"],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    for line in output.stdout.splitlines():
        tag = _clean_tag(line)
        if tag:
            return tag
    return None


def release_tag() -> str:
    return _tag_from_env() or _tag_from_git() or _tag_from_file() or DEFAULT_TAG


def numeric_version() -> str:
    return release_tag().removeprefix("v")


def display_release_version() -> str:
    return heroku_release_version() or release_tag()


def full_app_title() -> str:
    version_label = display_release_version()
    created_at_label = formatted_release_created_at()
    if created_at_label:
        return f"{APP_NAME} {version_label} · {created_at_label}"
    return f"{APP_NAME} {version_label}"


def version_payload() -> dict[str, str | None]:
    tag = release_tag()
    return {
        "app_name": APP_NAME,
        "tag": tag,
        "version": tag.removeprefix("v"),
        "release_version": display_release_version(),
        "release_created_at": heroku_release_created_at(),
        "release_created_at_display": formatted_release_created_at(),
        "full_title": full_app_title(),
    }
