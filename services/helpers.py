"""Shared helper utilities for the backend service layer."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from services.errors import NotFoundError


ASSET_LIQUIDITY_VALUES = {"quick", "current", "non_current"}
LIABILITY_TERM_VALUES = {"current", "long_term"}
EXPENSE_PROFILE_VALUES = {"essential", "discretionary"}

_QUICK_ASSET_HINTS = (
    "cash",
    "bank",
    "wallet",
    "checking",
    "savings",
    "mercado pago",
    "digital wallet",
)
_NON_CURRENT_ASSET_HINTS = (
    "fixed asset",
    "investment",
    "investments",
    "property",
    "vehicle",
    "equipment",
    "house",
    "land",
)
_LONG_TERM_LIABILITY_HINTS = (
    "long-term",
    "long term",
    "mortgage",
    "loan",
    "debt",
)
_ESSENTIAL_EXPENSE_HINTS = (
    "groc",
    "food",
    "housing",
    "rent",
    "mortgage",
    "utilit",
    "transport",
    "tax",
    "insurance",
    "health",
    "medical",
    "education",
    "current expenses",
)
_DISCRETIONARY_EXPENSE_HINTS = (
    "entertain",
    "travel",
    "vacation",
    "gift",
    "hobby",
    "luxury",
    "stream",
)


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


def parse_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _hint_text(name: str, subtype_name: str | None = None) -> str:
    return f"{name or ''} {subtype_name or ''}".strip().lower()


def infer_asset_liquidity(name: str, subtype_name: str | None = None) -> str:
    text = _hint_text(name, subtype_name)
    if any(token in text for token in _QUICK_ASSET_HINTS):
        return "quick"
    if any(token in text for token in _NON_CURRENT_ASSET_HINTS):
        return "non_current"
    return "current"


def infer_liability_term(name: str, subtype_name: str | None = None) -> str:
    text = _hint_text(name, subtype_name)
    if any(token in text for token in _LONG_TERM_LIABILITY_HINTS):
        return "long_term"
    return "current"


def infer_expense_profile(name: str, subtype_name: str | None = None) -> str:
    text = _hint_text(name, subtype_name)
    if any(token in text for token in _DISCRETIONARY_EXPENSE_HINTS):
        return "discretionary"
    if any(token in text for token in _ESSENTIAL_EXPENSE_HINTS):
        return "essential"
    return "discretionary"


def normalize_account_properties(
    raw_properties: Any,
    *,
    type_id: int,
    name: str,
    subtype_name: str | None = None,
) -> dict[str, Any]:
    properties = parse_json_object(raw_properties)
    normalized = dict(properties)

    if type_id == 1:
        liquidity = normalized.get("liquidity_profile")
        if liquidity not in ASSET_LIQUIDITY_VALUES:
            liquidity = infer_asset_liquidity(name, subtype_name)
        normalized["liquidity_profile"] = liquidity
    elif type_id == 2:
        liability_term = normalized.get("liability_term")
        if liability_term not in LIABILITY_TERM_VALUES:
            liability_term = infer_liability_term(name, subtype_name)
        normalized["liability_term"] = liability_term
    elif type_id == 4:
        expense_profile = normalized.get("expense_profile")
        if expense_profile not in EXPENSE_PROFILE_VALUES:
            expense_profile = infer_expense_profile(name, subtype_name)
        normalized["expense_profile"] = expense_profile

    return normalized


def serialize_account_properties(
    raw_properties: Any,
    *,
    type_id: int,
    name: str,
    subtype_name: str | None = None,
) -> str:
    normalized = normalize_account_properties(
        raw_properties,
        type_id=type_id,
        name=name,
        subtype_name=subtype_name,
    )
    return json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))


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
