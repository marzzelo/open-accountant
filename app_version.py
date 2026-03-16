"""
app_version.py — centralized application and release version helpers.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

APP_NAME = "Open Accountant"
DEFAULT_TAG = "v1.2.1"
TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
BASE_DIR = Path(__file__).parent
VERSION_FILE = BASE_DIR / "VERSION"


def _clean_tag(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if TAG_PATTERN.fullmatch(candidate):
        return candidate
    return None


def _tag_from_env() -> str | None:
    return _clean_tag(os.getenv("OPEN_ACCOUNTANT_VERSION"))


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


def full_app_title() -> str:
    return f"{APP_NAME} {release_tag()}"


def version_payload() -> dict[str, str]:
    tag = release_tag()
    return {
        "app_name": APP_NAME,
        "tag": tag,
        "version": tag.removeprefix("v"),
        "full_title": f"{APP_NAME} {tag}",
    }
