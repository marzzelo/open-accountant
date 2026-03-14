"""
app_config.py — Configuration management.

Handles:
  - config.ini  (app settings, current book, host/port…)
  - .env        (sensitive variables)
  - Book path resolution
  - Legacy DB migration (accountant.db → home.db)
"""

import configparser
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"  # directory that holds *.db files
CONFIG_PATH = BASE_DIR / "config.ini"
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"

_cfg = configparser.ConfigParser()

# ── Default values ─────────────────────────────────────────────────────────────
_DEFAULTS: dict[str, dict[str, str]] = {
    "general": {
        "current_book": "home",
        "host": "0.0.0.0",
        "port": "5001",
    },
    "app": {
        "name": "Open Accountant",
        "language": "en",
    },
}


def current_language() -> str:
    return get("app", "language", "en")


def set_language(lang: str):
    set_value("app", "language", lang)


def _ensure_defaults() -> bool:
    changed = False
    for section, values in _DEFAULTS.items():
        if not _cfg.has_section(section):
            _cfg.add_section(section)
            changed = True
        for key, default in values.items():
            if not _cfg.has_option(section, key):
                _cfg.set(section, key, default)
                changed = True
    return changed


def save():
    with open(CONFIG_PATH, "w") as f:
        _cfg.write(f)


def load():
    """Load config.ini from disk; create with defaults if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _cfg.read(CONFIG_PATH)
    if _ensure_defaults():
        save()
    _migrate_legacy_db()


def _migrate_legacy_db():
    """Move data/accountant.db → data/home.db on first run."""
    old = DATA_DIR / "accountant.db"
    new = DATA_DIR / "home.db"
    if old.exists() and not new.exists():
        old.rename(new)
        print("[open-accountant] Migration: accountant.db → home.db")


# ── Config accessors ───────────────────────────────────────────────────────────
def get(section: str, key: str, fallback: str = "") -> str:
    return _cfg.get(section, key, fallback=fallback)


def get_int(section: str, key: str, fallback: int) -> int:
    try:
        return _cfg.getint(section, key, fallback=fallback)
    except ValueError:
        return fallback


def set_value(section: str, key: str, value: str):
    if not _cfg.has_section(section):
        _cfg.add_section(section)
    _cfg.set(section, key, str(value))
    save()


def get_all() -> dict:
    """Return all config.ini sections as nested dict (excluding DEFAULT)."""
    return {s: dict(_cfg[s]) for s in _cfg.sections()}


def server_host() -> str:
    return get("general", "host", _DEFAULTS["general"]["host"])


def server_port() -> int:
    return get_int("general", "port", int(_DEFAULTS["general"]["port"]))


# ── Book helpers ───────────────────────────────────────────────────────────────
def current_book() -> str:
    return get("general", "current_book", "home")


def set_current_book(name: str):
    set_value("general", "current_book", name)


def get_db_path(book: str | None = None) -> Path:
    return DATA_DIR / f"{book or current_book()}.db"


# ── .env helpers ───────────────────────────────────────────────────────────────
_SENSITIVE = {"secret", "password", "token", "key", "pass", "api_key"}


def _is_sensitive(key: str) -> bool:
    k = key.lower()
    return any(kw in k for kw in _SENSITIVE)


def read_env() -> dict[str, str]:
    result: dict[str, str] = {}
    if not ENV_PATH.exists():
        return result
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def env_for_api() -> list[dict]:
    """Return env as list of {key, value, sensitive} — sensitive values masked."""
    raw = read_env()
    return [
        {
            "key": k,
            "value": ("••••••••" if _is_sensitive(k) else v),
            "sensitive": _is_sensitive(k),
        }
        for k, v in raw.items()
    ]


def write_env(pairs: list[dict]):
    """
    Write .env file from list of {key, value} pairs.
    If value == '••••••••', keep the original value for sensitive keys.
    """
    original = read_env()
    data: dict[str, str] = {}
    for p in pairs:
        k, v = p["key"].strip(), p["value"]
        if v == "••••••••" and k in original:
            data[k] = original[k]  # preserve masked values
        else:
            data[k] = v

    lines: list[str] = []
    # Preserve comments from .env.example if it exists
    example_keys: set[str] = set()
    if ENV_EXAMPLE_PATH.exists():
        with open(ENV_EXAMPLE_PATH) as f:
            for line in f:
                stripped = line.rstrip()
                if stripped.startswith("#") or not stripped:
                    lines.append(stripped)
                elif "=" in stripped:
                    k = stripped.split("=", 1)[0].strip()
                    example_keys.add(k)
                    lines.append(f"{k}={data.get(k, '')}")

    # Keys not in example go at the end
    for k, v in data.items():
        if k not in example_keys:
            lines.append(f"{k}={v}")

    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")

    # Reload into os.environ for runtime use
    os.environ.update(data)
