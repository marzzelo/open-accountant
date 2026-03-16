"""
app_config.py — Application settings and environment management.

Handles:
  - App settings stored in SQLite metadata DB
  - Legacy config.ini migration
  - .env management
  - Book path resolution
  - Legacy DB migration (accountant.db → home.db)
"""

import configparser
import json
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"  # directory that holds *.db files
CONFIG_PATH = BASE_DIR / "config.ini"
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"
APP_META_DB_NAME = "app_meta.sqlite3"
FINANCE_DEFAULTS: dict[str, str] = {
    "usd_official_buy_ars": "0.00",
    "usd_official_sell_ars": "0.00",
    "usd_blue_buy_ars": "0.00",
    "usd_blue_sell_ars": "0.00",
    "usd_card_ars": "0.00",
    "usd_official_last_update": "",
}
FINANCE_PREFERENCE_TO_CONFIG_KEY: dict[str, str] = {
    "finance_usd_official_buy_ars": "usd_official_buy_ars",
    "finance_usd_official_sell_ars": "usd_official_sell_ars",
    "finance_usd_blue_buy_ars": "usd_blue_buy_ars",
    "finance_usd_blue_sell_ars": "usd_blue_sell_ars",
    "finance_usd_card_ars": "usd_card_ars",
    "finance_usd_official_last_update": "usd_official_last_update",
}

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
    "finance": FINANCE_DEFAULTS,
}

_APP_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    section    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (section, key)
);
"""


def _app_meta_db_path() -> Path:
    return DATA_DIR / APP_META_DB_NAME


def _settings_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_app_meta_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def current_language() -> str:
    return get("app", "language", _DEFAULTS["app"]["language"])


def set_language(lang: str):
    set_value("app", "language", lang)


def _init_settings_db():
    with _settings_conn() as conn:
        conn.executescript(_APP_SETTINGS_SCHEMA)


def _migrate_legacy_config():
    if not CONFIG_PATH.exists():
        return

    parser = configparser.ConfigParser()
    parser.read(CONFIG_PATH)

    with _settings_conn() as conn:
        for section in parser.sections():
            for key, value in parser.items(section):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO app_settings (section, key, value)
                    VALUES (?, ?, ?)
                    """,
                    (section, key, value),
                )


def _ensure_defaults():
    with _settings_conn() as conn:
        for section, values in _DEFAULTS.items():
            for key, default in values.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO app_settings (section, key, value)
                    VALUES (?, ?, ?)
                    """,
                    (section, key, default),
                )


def load():
    """Initialise app settings storage and migrate legacy config if present."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _init_settings_db()
    _migrate_legacy_config()
    _ensure_defaults()
    _migrate_legacy_db()
    _migrate_legacy_finance_preferences()


def _migrate_legacy_db():
    """Move data/accountant.db → data/home.db on first run."""
    old = DATA_DIR / "accountant.db"
    new = DATA_DIR / "home.db"
    if old.exists() and not new.exists():
        old.rename(new)
        print("[open-accountant] Migration: accountant.db → home.db")


def _finance_setting_is_default(key: str) -> bool:
    default = FINANCE_DEFAULTS.get(key, "")
    current = get("finance", key, default)
    return current == default


def _migrate_legacy_finance_preferences():
    db_path = get_db_path()
    if not db_path.exists():
        return

    with sqlite3.connect(str(db_path)) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_preferences'"
        ).fetchone()
        if not table:
            return

        rows = conn.execute(
            "SELECT key, value FROM user_preferences WHERE key IN (%s)"
            % ",".join("?" for _ in FINANCE_PREFERENCE_TO_CONFIG_KEY),
            tuple(FINANCE_PREFERENCE_TO_CONFIG_KEY.keys()),
        ).fetchall()

    for preference_key, raw_value in rows:
        config_key = FINANCE_PREFERENCE_TO_CONFIG_KEY.get(preference_key)
        if not config_key or not _finance_setting_is_default(config_key):
            continue
        try:
            parsed_value = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed_value = raw_value
        set_value("finance", config_key, parsed_value)


# ── Config accessors ───────────────────────────────────────────────────────────
def get(section: str, key: str, fallback: str = "") -> str:
    with _settings_conn() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE section = ? AND key = ?",
            (section, key),
        ).fetchone()
    return row["value"] if row else fallback


def get_int(section: str, key: str, fallback: int) -> int:
    try:
        return int(get(section, key, str(fallback)))
    except (TypeError, ValueError):
        return fallback


def set_value(section: str, key: str, value: str):
    with _settings_conn() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (section, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(section, key)
            DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (section, key, str(value)),
        )


def get_all() -> dict:
    """Return all app settings grouped by section."""
    with _settings_conn() as conn:
        rows = conn.execute(
            "SELECT section, key, value FROM app_settings ORDER BY section, key"
        ).fetchall()

    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        grouped.setdefault(row["section"], {})[row["key"]] = row["value"]
    return grouped


def server_host() -> str:
    return get("general", "host", _DEFAULTS["general"]["host"])


def server_port() -> int:
    return get_int("general", "port", int(_DEFAULTS["general"]["port"]))


# ── Book helpers ───────────────────────────────────────────────────────────────
def current_book() -> str:
    return get("general", "current_book", _DEFAULTS["general"]["current_book"])


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
