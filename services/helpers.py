"""Shared helper utilities for the backend service layer."""

from datetime import datetime
from pathlib import Path
from typing import Any

from services.errors import NotFoundError


def current_year_range() -> tuple[str, str]:
    year = datetime.now().year
    return f"{year}-01-01 00:00:00", f"{year}-12-31 23:59:59"


def resolve_date_range(
    from_date: str | None, to_date: str | None
) -> tuple[str, str, bool]:
    if from_date and to_date:
        return from_date + " 00:00:00", to_date + " 23:59:59", True

    from_dt, to_dt = current_year_range()
    return from_dt, to_dt, False


def require_row(
    conn,
    query: str,
    params: tuple[Any, ...],
    error_message: str,
    error_cls=NotFoundError,
):
    row = conn.execute(query, params).fetchone()
    if not row:
        raise error_cls(error_message)
    return row


def model_from_row(model_cls, row):
    return model_cls(**dict(row))


def normalize_language_code(lang: str) -> str:
    return lang.strip().lower()[:2]


def require_locale_file(
    lang: str,
    locales_dir: Path,
    *,
    normalize: bool = False,
    error_message_template: str = "Idioma '{lang}' no disponible",
    error_cls=NotFoundError,
) -> tuple[str, Path]:
    resolved_lang = normalize_language_code(lang) if normalize else lang
    locale_file = locales_dir / f"{resolved_lang}.json"
    if not locale_file.exists():
        raise error_cls(error_message_template.format(lang=resolved_lang))
    return resolved_lang, locale_file
