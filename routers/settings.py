"""
routers/settings.py — App settings, user preferences, and .env management.

Endpoints:
    GET  /api/settings/config          Read global app settings
    PUT  /api/settings/config          Update global app settings
    GET  /api/settings/preferences     Read user preferences for current book
    PUT  /api/settings/preferences     Update user preferences for current book
    GET  /api/settings/env             Read .env (sensitive values masked)
    PUT  /api/settings/env             Write .env (preserves masked values)
"""

import json
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import app_config
from database import (
    get_db,
    get_user_preferences,
    update_user_preferences as save_user_preferences,
)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

LOCALES_DIR = Path(__file__).parent.parent / "static" / "locales"

router = APIRouter()
BLUELYTICS_LATEST_URL = "https://api.bluelytics.com.ar/v2/latest"
BLUELYTICS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://bluelytics.com.ar/",
}


def _strip_legacy_finance_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in preferences.items()
        if key not in app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY
    }


# ── Config.ini ─────────────────────────────────────────────────────────────────


@router.get("/settings/config")
def get_config():
    return app_config.get_all()


@router.put("/settings/config")
def update_config(data: dict[str, dict[str, str]]):
    for section, values in data.items():
        for key, value in values.items():
            app_config.set_value(section, key, value)
    return {"ok": True, "config": app_config.get_all()}


def _fetch_bluelytics_latest_rates() -> dict[str, Any]:
    try:
        request = Request(BLUELYTICS_LATEST_URL, headers=BLUELYTICS_HEADERS)
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, json.JSONDecodeError) as exc:
        raise HTTPException(502, f"Unable to fetch USD rates: {exc}") from exc

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
        raise HTTPException(
            502,
            f"Bluelytics response missing required fields: {', '.join(missing)}",
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


@router.get("/settings/finance/usd-rates")
@router.get("/settings/finance/usd-official")
def get_finance_usd_rates():
    return _fetch_bluelytics_latest_rates()


# ── User preferences ───────────────────────────────────────────────────────────


@router.get("/settings/preferences")
def get_preferences():
    with get_db() as conn:
        preferences = get_user_preferences(conn)
    return _strip_legacy_finance_preferences(preferences)


@router.put("/settings/preferences")
def update_preferences(data: dict[str, Any]):
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
    with get_db() as conn:
        preferences = save_user_preferences(conn, filtered_data)
    return {"ok": True, "preferences": _strip_legacy_finance_preferences(preferences)}


# ── .env ───────────────────────────────────────────────────────────────────────


@router.get("/settings/env")
def get_env():
    return app_config.env_for_api()


class EnvPair(BaseModel):
    key: str
    value: str


@router.put("/settings/env")
def update_env(pairs: list[EnvPair]):
    app_config.write_env([p.model_dump() for p in pairs])
    return {"ok": True}


# ── Language ────────────────────────────────────────────────────────────────────


@router.get("/settings/language")
def get_language():
    lang = app_config.current_language()
    return {"language": lang}


class LangRequest(BaseModel):
    language: str


@router.put("/settings/language")
def set_language(req: LangRequest):
    lang = req.language.strip().lower()[:2]
    locale_file = LOCALES_DIR / f"{lang}.json"
    if not locale_file.exists():
        raise HTTPException(400, f"Idioma no soportado: '{lang}'")
    app_config.set_language(lang)
    return {"ok": True, "language": lang}


@router.get("/settings/translations/{lang}")
def get_translations(lang: str):
    """Return the JSON translation catalog for the given language."""
    locale_file = LOCALES_DIR / f"{lang}.json"
    if not locale_file.exists():
        raise HTTPException(404, f"Idioma '{lang}' no disponible")
    with open(locale_file, encoding="utf-8") as f:
        return json.load(f)


@router.get("/settings/languages")
def list_languages():
    """Return list of available languages."""
    langs = []
    for f in sorted(LOCALES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            langs.append(
                {"code": data.get("_lang", f.stem), "name": data.get("_name", f.stem)}
            )
        except Exception:
            pass
    return langs
