"""
app_config.py — application settings and environment management.

Handles:
  - runtime environment loading from .env
  - DATABASE_URL resolution
  - app settings stored in the main database
  - legacy config.ini and app_meta.sqlite3 migration
"""

import configparser
import json
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config.ini"
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"
DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_SQLITE_DB_NAME = "open_accountant.db"

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

LEGACY_SETTING_KEYS: dict[str, set[str]] = {
    "general": {"current_book"},
}

_DEFAULTS: dict[str, dict[str, str]] = {
    "general": {
        "host": "0.0.0.0",
        "port": "5001",
    },
    "app": {
        "name": "Open Accountant",
        "language": "en",
    },
    "finance": FINANCE_DEFAULTS,
}

_SENSITIVE = {"secret", "password", "token", "key", "pass", "api_key"}

AUTH_ENABLED_ENV = "AUTH_ENABLED"
AUTH_BOOTSTRAP_ADMIN_USERNAME_ENV = "AUTH_BOOTSTRAP_ADMIN_USERNAME"
AUTH_BOOTSTRAP_ADMIN_PASSWORD_ENV = "AUTH_BOOTSTRAP_ADMIN_PASSWORD"
AUTH_SESSION_DAYS_DEFAULT_ENV = "AUTH_SESSION_DAYS_DEFAULT"
AUTH_SESSION_DAYS_REMEMBER_ME_ENV = "AUTH_SESSION_DAYS_REMEMBER_ME"
AUTH_COOKIE_SECURE_ENV = "AUTH_COOKIE_SECURE"
AUTH_COOKIE_NAME_ENV = "AUTH_COOKIE_NAME"


def get_db_path() -> Path:
    return DATA_DIR / DEFAULT_SQLITE_DB_NAME


def _legacy_meta_db_path() -> Path:
    return DATA_DIR / "app_meta.sqlite3"


def _default_sqlite_url() -> str:
    return f"sqlite:///{get_db_path().resolve().as_posix()}"


def _load_env_file() -> dict[str, str]:
    values = read_env()
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def load():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _load_env_file()

    from database import init_db

    init_db()
    _migrate_legacy_config()
    _migrate_legacy_meta_settings()
    _ensure_defaults()
    _migrate_legacy_finance_preferences()
    _bootstrap_auth_admin_if_needed()


def database_url() -> str:
    return os.environ.get(DATABASE_URL_ENV, "").strip() or _default_sqlite_url()


def _env_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_value(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env_value(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def current_language() -> str:
    return get("app", "language", _DEFAULTS["app"]["language"])


def auth_enabled() -> bool:
    return _env_bool(AUTH_ENABLED_ENV, True)


def auth_bootstrap_admin_username() -> str:
    return _env_value(AUTH_BOOTSTRAP_ADMIN_USERNAME_ENV)


def auth_bootstrap_admin_password() -> str:
    return _env_value(AUTH_BOOTSTRAP_ADMIN_PASSWORD_ENV)


def auth_session_days_default() -> int:
    return max(1, _env_int(AUTH_SESSION_DAYS_DEFAULT_ENV, 1))


def auth_session_days_remember_me() -> int:
    return max(1, _env_int(AUTH_SESSION_DAYS_REMEMBER_ME_ENV, 30))


def auth_cookie_secure() -> bool:
    return _env_bool(AUTH_COOKIE_SECURE_ENV, False)


def auth_cookie_name() -> str:
    return _env_value(AUTH_COOKIE_NAME_ENV) or "open_accountant_session"


def set_language(lang: str):
    set_value("app", "language", lang)


def _settings_conn():
    from database import connect_db

    return connect_db()


def is_legacy_setting(section: str, key: str) -> bool:
    return key in LEGACY_SETTING_KEYS.get(section, set())


def _insert_if_missing(section: str, key: str, value: str):
    with _settings_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (section, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(section, key) DO NOTHING
            """,
            (section, key, str(value)),
        )


def _migrate_legacy_config():
    if not CONFIG_PATH.exists():
        return

    parser = configparser.ConfigParser()
    parser.read(CONFIG_PATH)

    for section in parser.sections():
        for key, value in parser.items(section):
            if is_legacy_setting(section, key):
                continue
            _insert_if_missing(section, key, value)


def _migrate_legacy_meta_settings():
    legacy_meta_db_path = _legacy_meta_db_path()
    if not legacy_meta_db_path.exists():
        return

    with sqlite3.connect(str(legacy_meta_db_path)) as legacy_conn:
        table = legacy_conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_settings'"
        ).fetchone()
        if not table:
            return

        rows = legacy_conn.execute(
            "SELECT section, key, value FROM app_settings ORDER BY section, key"
        ).fetchall()

    for section, key, value in rows:
        if is_legacy_setting(section, key):
            continue
        _insert_if_missing(section, key, value)


def _ensure_defaults():
    for section, values in _DEFAULTS.items():
        for key, default in values.items():
            _insert_if_missing(section, key, default)


def _bootstrap_auth_admin_if_needed():
    if not auth_enabled():
        return

    from database import get_db
    from services import auth_service

    with get_db() as conn:
        auth_service.bootstrap_admin_if_needed(conn)


def _legacy_finance_db_candidates() -> list[Path]:
    return [DATA_DIR / "home.db", DATA_DIR / "accountant.db"]


def _finance_setting_is_default(key: str) -> bool:
    default = FINANCE_DEFAULTS.get(key, "")
    current = get("finance", key, default)
    return current == default


def _migrate_legacy_finance_preferences():
    candidates = [path for path in _legacy_finance_db_candidates() if path.exists()]
    if not candidates:
        return

    with sqlite3.connect(str(candidates[0])) as legacy_conn:
        table = legacy_conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_preferences'"
        ).fetchone()
        if not table:
            return

        rows = legacy_conn.execute(
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


def get(section: str, key: str, fallback: str = "") -> str:
    with _settings_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE section = ? AND key = ?",
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
            INSERT INTO settings (section, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(section, key)
            DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (section, key, str(value)),
        )


def get_all() -> dict:
    with _settings_conn() as conn:
        rows = conn.execute(
            "SELECT section, key, value FROM settings ORDER BY section, key"
        ).fetchall()

    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        if is_legacy_setting(row["section"], row["key"]):
            continue
        grouped.setdefault(row["section"], {})[row["key"]] = row["value"]
    return grouped


def server_host() -> str:
    return _env_value("HOST") or get("general", "host", _DEFAULTS["general"]["host"])


def server_port() -> int:
    port_override = _env_value("PORT")
    if port_override:
        try:
            return int(port_override)
        except ValueError:
            pass
    return get_int("general", "port", int(_DEFAULTS["general"]["port"]))


def _is_sensitive(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in _SENSITIVE)


def read_env() -> dict[str, str]:
    result: dict[str, str] = {}
    if not ENV_PATH.exists():
        return result

    with open(ENV_PATH, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def env_for_api() -> list[dict]:
    raw = read_env()
    return [
        {
            "key": key,
            "value": ("••••••••" if _is_sensitive(key) else value),
            "sensitive": _is_sensitive(key),
        }
        for key, value in raw.items()
    ]


def write_env(pairs: list[dict]):
    original = read_env()
    data: dict[str, str] = {}
    for pair in pairs:
        key = pair["key"].strip()
        value = pair["value"]
        if value == "••••••••" and key in original:
            data[key] = original[key]
        else:
            data[key] = value

    lines: list[str] = []
    example_keys: set[str] = set()
    if ENV_EXAMPLE_PATH.exists():
        with open(ENV_EXAMPLE_PATH, encoding="utf-8") as handle:
            for raw_line in handle:
                stripped = raw_line.rstrip()
                if stripped.startswith("#") or not stripped:
                    lines.append(stripped)
                elif "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    example_keys.add(key)
                    lines.append(f"{key}={data.get(key, '')}")

    for key, value in data.items():
        if key not in example_keys:
            lines.append(f"{key}={value}")

    with open(ENV_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    os.environ.update(data)
