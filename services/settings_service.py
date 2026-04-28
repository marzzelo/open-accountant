"""Settings and preferences service functions."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

import app_config
import app_version
from database import (
    PREFIXED_TABLES,
    get_user_preferences,
    update_user_preferences as save_user_preferences,
)

from services.errors import ExternalServiceError, NotFoundError, ValidationError
from services.helpers import require_locale_file

LOCALES_DIR = Path(__file__).parent.parent / "static" / "locales"
BLUELYTICS_LATEST_URL = "https://api.bluelytics.com.ar/v2/latest"
BLUELYTICS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://bluelytics.com.ar/",
}

BACKUP_FORMAT = "open-accountant-backup-v1"
BACKUP_TABLE_INSERT_ORDER: tuple[str, ...] = (
    "types",
    "subtypes",
    "accounts",
    "tags",
    "transactions",
    "transaction_tags",
    "users",
    "auth_sessions",
    "user_preferences",
    "settings",
    "projection_series",
)
BACKUP_TABLE_DELETE_ORDER: tuple[str, ...] = tuple(reversed(BACKUP_TABLE_INSERT_ORDER))
IDENTITY_TABLES: set[str] = {
    "subtypes",
    "accounts",
    "transactions",
    "tags",
    "users",
    "auth_sessions",
    "projection_series",
}


def get_config() -> dict:
    return app_config.get_all()


def update_config(data: dict[str, dict[str, str]]) -> dict:
    for section, values in data.items():
        for key, value in values.items():
            if app_config.is_legacy_setting(section, key):
                continue
            app_config.set_value(section, key, value)
    return {"ok": True, "config": app_config.get_all()}


def _default_rates_fetcher() -> dict[str, Any]:
    request = Request(BLUELYTICS_LATEST_URL, headers=BLUELYTICS_HEADERS)
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bluelytics_latest_rates(
    fetcher: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fetch_rates = fetcher or _default_rates_fetcher
    try:
        payload = fetch_rates()
    except (TimeoutError, URLError, json.JSONDecodeError, ValueError) as exc:
        raise ExternalServiceError(f"Unable to fetch USD rates: {exc}") from exc

    official = payload.get("oficial") or {}
    blue = payload.get("blue") or {}
    official_buy = official.get("value_buy")
    official_sell = official.get("value_sell")
    blue_buy = blue.get("value_buy")
    blue_sell = blue.get("value_sell")

    missing = [
        name
        for name, value in {
            "oficial.value_buy": official_buy,
            "oficial.value_sell": official_sell,
            "blue.value_buy": blue_buy,
            "blue.value_sell": blue_sell,
        }.items()
        if value is None
    ]
    if missing:
        raise ExternalServiceError(
            f"Bluelytics response missing required fields: {', '.join(missing)}"
        )

    return {
        "official_buy": official_buy,
        "official_sell": official_sell,
        "blue_buy": blue_buy,
        "blue_sell": blue_sell,
        "card": round(float(official_sell) * 1.30, 2),
        "last_update": payload.get("last_update"),
        "source": BLUELYTICS_LATEST_URL,
    }


# Preferences with these keys are stored as global configuration under the
# ``finance`` section of the settings table instead of as user preferences,
# so all users share the same FX rates.
FINANCE_PREFERENCE_TO_CONFIG_KEY: dict[str, str] = {
    "finance_usd_official_buy_ars": "usd_official_buy_ars",
    "finance_usd_official_sell_ars": "usd_official_sell_ars",
    "finance_usd_blue_buy_ars": "usd_blue_buy_ars",
    "finance_usd_blue_sell_ars": "usd_blue_sell_ars",
    "finance_usd_card_ars": "usd_card_ars",
    "finance_usd_rate_last_update": "usd_rate_last_update",
    "finance_usd_rate_source": "usd_rate_source",
}


def get_preferences(conn) -> dict[str, Any]:
    return get_user_preferences(conn)


def update_preferences(conn, data: dict[str, Any]) -> dict:
    finance_updates: dict[str, str] = {}
    remaining: dict[str, Any] = {}
    for key, value in data.items():
        config_key = FINANCE_PREFERENCE_TO_CONFIG_KEY.get(key)
        if config_key is None:
            remaining[key] = value
        elif value is not None:
            finance_updates[config_key] = str(value)

    if finance_updates:
        for config_key, value in finance_updates.items():
            app_config.set_value("finance", config_key, value)

    preferences = save_user_preferences(conn, remaining)
    return {"ok": True, "preferences": preferences}


def get_env() -> list[dict[str, Any]]:
    return app_config.env_for_api()


def update_env(pairs: list[dict[str, str]]) -> dict:
    app_config.write_env(pairs)
    return {"ok": True}


def get_language() -> dict[str, str]:
    return {"language": app_config.current_language()}


def set_language(lang: str, locales_dir: Path = LOCALES_DIR) -> dict:
    normalized, _ = require_locale_file(
        lang,
        locales_dir,
        normalize=True,
        error_message_template="Idioma no soportado: '{lang}'",
        error_cls=ValidationError,
    )
    app_config.set_language(normalized)
    return {"ok": True, "language": normalized}


def get_translations(lang: str, locales_dir: Path = LOCALES_DIR) -> dict[str, Any]:
    _, locale_file = require_locale_file(lang, locales_dir)
    with locale_file.open(encoding="utf-8") as handle:
        return json.load(handle)


def list_languages(locales_dir: Path = LOCALES_DIR) -> list[dict[str, str]]:
    languages = []
    for locale_file in sorted(locales_dir.glob("*.json")):
        try:
            data = json.loads(locale_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        languages.append(
            {
                "code": data.get("_lang", locale_file.stem),
                "name": data.get("_name", locale_file.stem),
            }
        )
    return languages


def _physical_table_name(logical_table: str) -> str:
    return f"oacc_{logical_table}"


def _open_accountant_physical_tables() -> set[str]:
    return {_physical_table_name(name) for name in PREFIXED_TABLES}


def _existing_open_accountant_tables(conn) -> set[str]:
    allowed_tables = _open_accountant_physical_tables()
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
                    AND table_name LIKE ?
                """,
        ("oacc_%",),
    ).fetchall()
    return {row["table_name"] for row in rows if row["table_name"] in allowed_tables}


def _table_columns(conn, physical_table: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = ?
        ORDER BY ordinal_position
        """,
        (physical_table,),
    ).fetchall()
    return [row["column_name"] for row in rows]


def _reset_identity_sequence(conn, physical_table: str) -> None:
    seq_row = conn.execute(
        "SELECT pg_get_serial_sequence(?, 'id') AS seq_name",
        (physical_table,),
    ).fetchone()
    if not seq_row:
        return

    seq_name = seq_row.get("seq_name")
    if not seq_name:
        return

    next_value = conn.execute(
        f'SELECT COALESCE(MAX("id"), 0) + 1 AS next_val FROM "{physical_table}"'
    ).fetchone()["next_val"]
    conn.execute("SELECT setval(?, ?, false)", (seq_name, int(next_value)))


def export_backup(conn) -> dict[str, Any]:
    existing_tables = _existing_open_accountant_tables(conn)
    tables: dict[str, list[dict[str, Any]]] = {}
    row_counts: dict[str, int] = {}

    for logical_table in BACKUP_TABLE_INSERT_ORDER:
        physical_table = _physical_table_name(logical_table)
        if physical_table not in existing_tables:
            continue

        rows = conn.execute(f'SELECT * FROM "{physical_table}"').fetchall()
        payload_rows = [dict(row) for row in rows]
        tables[physical_table] = payload_rows
        row_counts[physical_table] = len(payload_rows)

    return {
        "format": BACKUP_FORMAT,
        "app": "open-accountant",
        "version": app_version.numeric_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
        "row_counts": row_counts,
    }


def restore_backup(conn, backup: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(backup, dict):
        raise ValidationError("El respaldo debe ser un objeto JSON válido.")

    if backup.get("format") != BACKUP_FORMAT:
        raise ValidationError("Formato de respaldo no soportado.")

    tables_payload = backup.get("tables")
    if not isinstance(tables_payload, dict) or not tables_payload:
        raise ValidationError("El respaldo no contiene tablas para recuperar.")

    allowed_tables = _open_accountant_physical_tables()
    invalid_tables = sorted(
        table_name
        for table_name in tables_payload.keys()
        if table_name not in allowed_tables
    )
    if invalid_tables:
        raise ValidationError(
            "El respaldo contiene tablas no permitidas: " + ", ".join(invalid_tables)
        )

    existing_tables = _existing_open_accountant_tables(conn)
    requested_tables = set(tables_payload.keys())
    target_tables = requested_tables & existing_tables
    if not target_tables:
        raise ValidationError(
            "No se encontraron tablas compatibles de Open Accountant para recuperar."
        )

    normalized_rows: dict[str, list[dict[str, Any]]] = {}
    for table_name in target_tables:
        rows = tables_payload.get(table_name)
        if not isinstance(rows, list):
            raise ValidationError(
                f"La tabla '{table_name}' debe contener una lista de filas."
            )
        for row in rows:
            if not isinstance(row, dict):
                raise ValidationError(
                    f"La tabla '{table_name}' contiene una fila con formato inválido."
                )
        normalized_rows[table_name] = rows

    for logical_table in BACKUP_TABLE_DELETE_ORDER:
        physical_table = _physical_table_name(logical_table)
        if physical_table in target_tables:
            conn.execute(f'DELETE FROM "{physical_table}"')

    restored_counts: dict[str, int] = {}
    for logical_table in BACKUP_TABLE_INSERT_ORDER:
        physical_table = _physical_table_name(logical_table)
        if physical_table not in target_tables:
            continue

        table_rows = normalized_rows.get(physical_table, [])
        table_columns = _table_columns(conn, physical_table)
        restored = 0

        for row in table_rows:
            insert_columns = [column for column in table_columns if column in row]
            if not insert_columns:
                continue

            placeholders = ", ".join("?" for _ in insert_columns)
            quoted_columns = ", ".join(f'"{column}"' for column in insert_columns)
            values = tuple(row[column] for column in insert_columns)
            conn.execute(
                f'INSERT INTO "{physical_table}" ({quoted_columns}) VALUES ({placeholders})',
                values,
            )
            restored += 1

        restored_counts[physical_table] = restored

        if logical_table in IDENTITY_TABLES and "id" in table_columns:
            _reset_identity_sequence(conn, physical_table)

    return {
        "ok": True,
        "restored_tables": sorted(target_tables),
        "restored_row_counts": restored_counts,
        "restored_total_rows": sum(restored_counts.values()),
    }
