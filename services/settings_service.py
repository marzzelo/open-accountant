"""Settings and preferences service functions."""

import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

import app_config
from database import (
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


def strip_legacy_finance_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in preferences.items()
        if key not in app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY
    }


def get_config() -> dict:
    return app_config.get_all()


def update_config(data: dict[str, dict[str, str]]) -> dict:
    for section, values in data.items():
        for key, value in values.items():
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


def get_preferences(conn) -> dict[str, Any]:
    preferences = get_user_preferences(conn)
    return strip_legacy_finance_preferences(preferences)


def update_preferences(conn, data: dict[str, Any]) -> dict:
    legacy_finance_values = {
        key: value
        for key, value in data.items()
        if key in app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY
    }
    for preference_key, value in legacy_finance_values.items():
        app_config.set_value(
            "finance",
            app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY[preference_key],
            value,
        )

    filtered_data = {
        key: value for key, value in data.items() if key not in legacy_finance_values
    }
    preferences = save_user_preferences(conn, filtered_data)
    return {"ok": True, "preferences": strip_legacy_finance_preferences(preferences)}


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
