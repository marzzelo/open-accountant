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


# ── User preferences ───────────────────────────────────────────────────────────


@router.get("/settings/preferences")
def get_preferences():
    with get_db() as conn:
        return get_user_preferences(conn)


@router.put("/settings/preferences")
def update_preferences(data: dict[str, Any]):
    with get_db() as conn:
        preferences = save_user_preferences(conn, data)
    return {"ok": True, "preferences": preferences}


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
