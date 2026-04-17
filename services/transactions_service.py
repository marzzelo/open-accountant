"""Transaction service functions."""

from datetime import datetime
from typing import Optional

import app_config

from models import TransactionIn, TransactionOut, TransactionUpdate

from services.errors import NotFoundError, ValidationError
from services.helpers import require_row
from services import tags_service

TX_SELECT = """
    SELECT t.*,
           da.name    AS debit_name,  da.type_id AS debit_type_id,
           ca.name    AS credit_name, ca.type_id AS credit_type_id
    FROM transactions t
    JOIN accounts da ON t.debit_account  = da.id
    JOIN accounts ca ON t.credit_account = ca.id
"""


def row_to_out(row, tags=None) -> TransactionOut:
    payload = dict(row)
    payload["tags"] = tags or []
    return TransactionOut(**payload)


def _rows_to_out(conn, rows) -> list[TransactionOut]:
    tag_map = tags_service.get_transaction_tags_map(conn, [row["id"] for row in rows])
    return [row_to_out(row, tag_map.get(row["id"], [])) for row in rows]


FX_SOURCE_CONFIG = {
    "USD_CARD": "usd_card_ars",
    "USD_BUY": "usd_official_buy_ars",
    "USD_SELL": "usd_official_sell_ars",
    "BLUE_BUY": "usd_blue_buy_ars",
    "BLUE_SELL": "usd_blue_sell_ars",
}

SUPPORTED_ORIGINAL_CURRENCIES = {"ARS", "USD"}


def _round_amount(value: float) -> float:
    return round(float(value), 2)


def _resolve_fx_rate(fx_source: str) -> float:
    config_key = FX_SOURCE_CONFIG.get(fx_source)
    if not config_key:
        raise ValidationError(f"Unsupported fx_source: {fx_source}")

    try:
        rate = float(app_config.get("finance", config_key, "0"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid configured FX rate for {fx_source}") from exc

    if rate <= 0:
        raise ValidationError(f"Missing configured FX rate for {fx_source}")
    return rate


def _normalize_currency(currency: Optional[str]) -> str:
    return (currency or "ARS").strip().upper()


def _monetary_from_create(data: TransactionIn) -> dict:
    if (
        data.original_amount is None
        and data.original_currency is None
        and data.fx_rate is None
        and data.fx_source is None
    ):
        if data.amount is None:
            raise ValidationError("amount is required")
        amount = _round_amount(data.amount)
        return {
            "amount": amount,
            "original_amount": amount,
            "original_currency": "ARS",
            "fx_rate": 1.0,
            "fx_source": None,
        }

    raw_original_amount = (
        data.original_amount if data.original_amount is not None else data.amount
    )
    if raw_original_amount is None:
        raise ValidationError("Either amount or original_amount is required")
    original_amount = _round_amount(raw_original_amount)
    original_currency = _normalize_currency(data.original_currency)
    if original_currency not in SUPPORTED_ORIGINAL_CURRENCIES:
        raise ValidationError(f"Unsupported original_currency: {original_currency}")

    if original_currency == "ARS":
        return {
            "amount": original_amount,
            "original_amount": original_amount,
            "original_currency": "ARS",
            "fx_rate": 1.0,
            "fx_source": None,
        }

    fx_source = (data.fx_source or "").strip().upper()
    if not fx_source:
        raise ValidationError("fx_source is required for non-ARS transactions")
    fx_rate = (
        _round_amount(data.fx_rate)
        if data.fx_rate is not None
        else _resolve_fx_rate(fx_source)
    )
    return {
        "amount": _round_amount(original_amount * fx_rate),
        "original_amount": original_amount,
        "original_currency": original_currency,
        "fx_rate": fx_rate,
        "fx_source": fx_source,
    }


def _monetary_from_update(data: TransactionUpdate, old) -> dict:
    if (
        data.amount is None
        and data.original_amount is None
        and data.original_currency is None
        and data.fx_rate is None
        and data.fx_source is None
    ):
        return {
            "amount": old["amount"],
            "original_amount": old["original_amount"],
            "original_currency": old["original_currency"],
            "fx_rate": old["fx_rate"],
            "fx_source": old["fx_source"],
        }

    if (
        data.original_amount is None
        and data.original_currency is None
        and data.fx_rate is None
        and data.fx_source is None
    ):
        if data.amount is None:
            raise ValidationError("amount is required")
        amount = _round_amount(data.amount)
        return {
            "amount": amount,
            "original_amount": amount,
            "original_currency": "ARS",
            "fx_rate": 1.0,
            "fx_source": None,
        }

    original_amount = _round_amount(
        data.original_amount
        if data.original_amount is not None
        else old["original_amount"]
    )
    original_currency = _normalize_currency(
        data.original_currency
        if data.original_currency is not None
        else old["original_currency"]
    )
    if original_currency not in SUPPORTED_ORIGINAL_CURRENCIES:
        raise ValidationError(f"Unsupported original_currency: {original_currency}")

    if original_currency == "ARS":
        return {
            "amount": original_amount,
            "original_amount": original_amount,
            "original_currency": "ARS",
            "fx_rate": 1.0,
            "fx_source": None,
        }

    next_fx_source = (
        (data.fx_source if data.fx_source is not None else old["fx_source"] or "")
        .strip()
        .upper()
    )
    if not next_fx_source:
        raise ValidationError("fx_source is required for non-ARS transactions")
    fx_rate = (
        _round_amount(data.fx_rate)
        if data.fx_rate is not None
        else _resolve_fx_rate(next_fx_source)
    )
    return {
        "amount": _round_amount(original_amount * fx_rate),
        "original_amount": original_amount,
        "original_currency": original_currency,
        "fx_rate": fx_rate,
        "fx_source": next_fx_source,
    }


def list_transactions(
    conn,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    account_id: Optional[int] = None,
    tag_ids: Optional[list[int]] = None,
    limit: int = 500,
    offset: int = 0,
) -> list[TransactionOut]:
    conditions = []
    params: list = []

    if from_date:
        conditions.append("t.date >= ?")
        params.append(from_date + " 00:00:00")
    if to_date:
        conditions.append("t.date <= ?")
        params.append(to_date + " 23:59:59")
    if account_id:
        conditions.append("(t.debit_account = ? OR t.credit_account = ?)")
        params += [account_id, account_id]
    tag_condition, tag_params = tags_service.build_transaction_tag_filter("t", tag_ids)
    if tag_condition:
        conditions.append(tag_condition)
        params += tag_params

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]
    rows = conn.execute(
        f"{TX_SELECT} {where} ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return _rows_to_out(conn, rows)


def get_transaction(conn, tx_id: int) -> TransactionOut:
    row = require_row(
        conn,
        TX_SELECT + " WHERE t.id = ?",
        (tx_id,),
        "Transaction not found",
        NotFoundError,
    )
    return _rows_to_out(conn, [row])[0]


def create_transaction(conn, data: TransactionIn) -> TransactionOut:
    if data.debit_account == data.credit_account:
        raise ValidationError("Debit and credit accounts must be different")

    tx_date = data.date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    require_row(
        conn,
        "SELECT id FROM accounts WHERE id = ?",
        (data.debit_account,),
        f"Debit account {data.debit_account} not found",
        NotFoundError,
    )
    require_row(
        conn,
        "SELECT id FROM accounts WHERE id = ?",
        (data.credit_account,),
        f"Credit account {data.credit_account} not found",
        NotFoundError,
    )

    monetary = _monetary_from_create(data)

    row = conn.execute(
        """INSERT INTO transactions
           (debit_account, credit_account, amount, original_amount, original_currency,
            fx_rate, fx_source, description, date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           RETURNING id""",
        (
            data.debit_account,
            data.credit_account,
            monetary["amount"],
            monetary["original_amount"],
            monetary["original_currency"],
            monetary["fx_rate"],
            monetary["fx_source"],
            data.description,
            tx_date,
        ),
    )
    tx_id = row.fetchone()["id"]
    tags_service.replace_transaction_tags(conn, tx_id, data.tag_ids)
    return get_transaction(conn, tx_id)


def update_transaction(conn, tx_id: int, data: TransactionUpdate) -> TransactionOut:
    old = require_row(
        conn,
        "SELECT * FROM transactions WHERE id = ?",
        (tx_id,),
        "Transaction not found",
        NotFoundError,
    )

    new_debit_account = (
        data.debit_account if data.debit_account is not None else old["debit_account"]
    )
    new_credit_account = (
        data.credit_account
        if data.credit_account is not None
        else old["credit_account"]
    )
    if new_debit_account == new_credit_account:
        raise ValidationError("Debit and credit accounts must be different")

    require_row(
        conn,
        "SELECT id FROM accounts WHERE id = ?",
        (new_debit_account,),
        f"Debit account {new_debit_account} not found",
        NotFoundError,
    )
    require_row(
        conn,
        "SELECT id FROM accounts WHERE id = ?",
        (new_credit_account,),
        f"Credit account {new_credit_account} not found",
        NotFoundError,
    )

    monetary = _monetary_from_update(data, old)
    new_desc = data.description if data.description is not None else old["description"]
    new_date = data.date if data.date is not None else old["date"]

    conn.execute(
        """UPDATE transactions
           SET debit_account = ?, credit_account = ?, amount = ?, original_amount = ?,
               original_currency = ?, fx_rate = ?, fx_source = ?, description = ?, date = ?
           WHERE id = ?""",
        (
            new_debit_account,
            new_credit_account,
            monetary["amount"],
            monetary["original_amount"],
            monetary["original_currency"],
            monetary["fx_rate"],
            monetary["fx_source"],
            new_desc,
            new_date,
            tx_id,
        ),
    )
    if data.tag_ids is not None:
        tags_service.replace_transaction_tags(conn, tx_id, data.tag_ids)
    return get_transaction(conn, tx_id)


def delete_transaction(conn, tx_id: int):
    require_row(
        conn,
        "SELECT * FROM transactions WHERE id = ?",
        (tx_id,),
        "Transaction not found",
        NotFoundError,
    )
    conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
