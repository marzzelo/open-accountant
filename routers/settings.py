"""routers/settings.py — HTTP adapter for settings and preferences services."""

import json
from typing import Any
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_admin_user
from database import db_dep
from services import settings_service

router = APIRouter()


@router.get("/settings/config")
def get_config():
    return settings_service.get_config()


@router.put("/settings/config")
def update_config(data: dict[str, dict[str, str]]):
    return settings_service.update_config(data)


@router.get("/settings/finance/usd-rates")
@router.get("/settings/finance/usd-official")
def get_finance_usd_rates():
    return settings_service.fetch_bluelytics_latest_rates(
        fetcher=lambda: _fetch_rates_payload()
    )


def _fetch_rates_payload() -> dict[str, Any]:
    request = Request(
        settings_service.BLUELYTICS_LATEST_URL,
        headers=settings_service.BLUELYTICS_HEADERS,
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


@router.get("/settings/preferences")
def get_preferences(conn=Depends(db_dep)):
    return settings_service.get_preferences(conn)


@router.put("/settings/preferences")
def update_preferences(data: dict[str, Any], conn=Depends(db_dep)):
    return settings_service.update_preferences(conn, data)


@router.get("/settings/env")
def get_env():
    return settings_service.get_env()


class EnvPair(BaseModel):
    key: str
    value: str


@router.put("/settings/env")
def update_env(pairs: list[EnvPair]):
    return settings_service.update_env([pair.model_dump() for pair in pairs])


@router.get("/settings/language")
def get_language():
    return settings_service.get_language()


class LangRequest(BaseModel):
    language: str


@router.put("/settings/language")
def set_language(req: LangRequest):
    return settings_service.set_language(req.language)


@router.get("/settings/translations/{lang}")
def get_translations(lang: str):
    return settings_service.get_translations(lang)


@router.get("/settings/languages")
def list_languages():
    return settings_service.list_languages()


@router.get("/settings/backup/export")
def export_backup(
    _current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return settings_service.export_backup(conn)


class RestoreBackupRequest(BaseModel):
    backup: dict[str, Any]


@router.post("/settings/backup/restore")
def restore_backup(
    data: RestoreBackupRequest,
    _current_user: dict = Depends(require_admin_user),
    conn=Depends(db_dep),
):
    return settings_service.restore_backup(conn, data.backup)
