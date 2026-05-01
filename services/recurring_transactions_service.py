"""Recurring transaction service functions."""

from calendar import monthrange
from datetime import datetime
from typing import Literal

from models import (
    RecurringTransactionIn,
    RecurringTransactionOut,
    RecurringTransactionPostIn,
    RecurringTransactionPostOut,
    RecurringTransactionUpdate,
    TransactionIn,
    TransactionUpdate,
)
from services import tags_service, transactions_service
from services.errors import NotFoundError, ValidationError
from services.helpers import require_row


FilterName = Literal["all", "enabled", "active"]

RTX_SELECT = """
    SELECT rt.*,
           da.name    AS debit_name,  da.type_id AS debit_type_id,
           ca.name    AS credit_name, ca.type_id AS credit_type_id
    FROM recurring_transactions rt
    JOIN accounts da ON rt.debit_account  = da.id
    JOIN accounts ca ON rt.credit_account = ca.id
"""


def _current_period(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return current.strftime("%Y-%m")


def _effective_alert_date(alert_day: int, now: datetime | None = None) -> str:
    current = now or datetime.now()
    last_day = monthrange(current.year, current.month)[1]
    day = min(alert_day, last_day)
    return current.replace(day=day).date().isoformat()


def _is_active(row, now: datetime | None = None) -> bool:
    current = now or datetime.now()
    if not bool(row["enabled"]) or not bool(row["alert_active"]):
        return False
    effective_day = int(_effective_alert_date(row["alert_day"], current)[-2:])
    already_posted = row["last_posted_period"] == current.strftime("%Y-%m")
    return current.day >= effective_day and not already_posted


def _replace_recurring_tags(conn, recurring_id: int, tag_ids: list[int] | None) -> None:
    conn.execute(
        "DELETE FROM recurring_transaction_tags WHERE recurring_transaction_id = ?",
        (recurring_id,),
    )
    if not tag_ids:
        return
    unique_ids = []
    seen = set()
    for tag_id in tag_ids:
        normalized = int(tag_id)
        if normalized not in seen:
            seen.add(normalized)
            unique_ids.append(normalized)

    for tag_id in unique_ids:
        require_row(
            conn,
            "SELECT id FROM tags WHERE id = ?",
            (tag_id,),
            f"Tag {tag_id} not found",
            NotFoundError,
        )
    conn.executemany(
        """INSERT INTO recurring_transaction_tags (recurring_transaction_id, tag_id)
           VALUES (?, ?)""",
        [(recurring_id, tag_id) for tag_id in unique_ids],
    )


def _get_recurring_tags_map(conn, recurring_ids: list[int]) -> dict[int, list[dict]]:
    if not recurring_ids:
        return {}
    placeholders = ",".join("?" for _ in recurring_ids)
    rows = conn.execute(
        f"""
        SELECT rtt.recurring_transaction_id, t.id, t.name, t.color
        FROM recurring_transaction_tags rtt
        JOIN tags t ON t.id = rtt.tag_id
        WHERE rtt.recurring_transaction_id IN ({placeholders})
        ORDER BY LOWER(t.name), t.name
        """,
        recurring_ids,
    ).fetchall()
    tag_map: dict[int, list[dict]] = {}
    for row in rows:
        tag_map.setdefault(row["recurring_transaction_id"], []).append(
            {"id": row["id"], "name": row["name"], "color": row["color"]}
        )
    return tag_map


def _row_to_out(row, tags=None, now: datetime | None = None) -> RecurringTransactionOut:
    payload = dict(row)
    payload["alert_active"] = bool(payload["alert_active"])
    payload["enabled"] = bool(payload["enabled"])
    payload["is_active"] = _is_active(row, now)
    payload["effective_alert_date"] = _effective_alert_date(payload["alert_day"], now)
    payload["tags"] = tags or []
    return RecurringTransactionOut(**payload)


def _rows_to_out(conn, rows, now: datetime | None = None) -> list[RecurringTransactionOut]:
    tag_map = _get_recurring_tags_map(conn, [row["id"] for row in rows])
    return [_row_to_out(row, tag_map.get(row["id"], []), now) for row in rows]


def _validate_accounts(conn, debit_account: int, credit_account: int) -> None:
    if debit_account == credit_account:
        raise ValidationError("Debit and credit accounts must be different")
    require_row(
        conn,
        "SELECT id FROM accounts WHERE id = ?",
        (debit_account,),
        f"Debit account {debit_account} not found",
        NotFoundError,
    )
    require_row(
        conn,
        "SELECT id FROM accounts WHERE id = ?",
        (credit_account,),
        f"Credit account {credit_account} not found",
        NotFoundError,
    )


def list_recurring_transactions(
    conn,
    filter_name: FilterName = "all",
    now: datetime | None = None,
) -> list[RecurringTransactionOut]:
    if filter_name not in {"all", "enabled", "active"}:
        raise ValidationError("Invalid recurring transaction filter")

    where = "WHERE rt.enabled = ?" if filter_name == "enabled" else ""
    params = [True] if filter_name == "enabled" else []
    rows = conn.execute(
        f"{RTX_SELECT} {where} ORDER BY rt.alert_day, rt.id",
        params,
    ).fetchall()
    if filter_name == "active":
        rows = [row for row in rows if _is_active(row, now)]
    return _rows_to_out(conn, rows, now)


def active_count(conn, now: datetime | None = None) -> dict:
    count = len(list_recurring_transactions(conn, "active", now))
    return {"count": count}


def get_recurring_transaction(
    conn, recurring_id: int, now: datetime | None = None
) -> RecurringTransactionOut:
    row = require_row(
        conn,
        RTX_SELECT + " WHERE rt.id = ?",
        (recurring_id,),
        "Recurring transaction not found",
        NotFoundError,
    )
    return _rows_to_out(conn, [row], now)[0]


def create_recurring_transaction(
    conn, data: RecurringTransactionIn
) -> RecurringTransactionOut:
    _validate_accounts(conn, data.debit_account, data.credit_account)
    monetary = transactions_service._monetary_from_create(
        TransactionIn(
            debit_account=data.debit_account,
            credit_account=data.credit_account,
            tag_ids=data.tag_ids,
            amount=data.amount,
            original_amount=data.original_amount,
            original_currency=data.original_currency,
            fx_rate=data.fx_rate,
            fx_source=data.fx_source,
            description=data.description,
        )
    )
    row = conn.execute(
        """INSERT INTO recurring_transactions (
               debit_account, credit_account, amount, original_amount, original_currency,
               fx_rate, fx_source, description, alert_day, alert_active, enabled
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.alert_day,
            data.alert_active,
            data.enabled,
        ),
    )
    recurring_id = row.fetchone()["id"]
    _replace_recurring_tags(conn, recurring_id, data.tag_ids)
    return get_recurring_transaction(conn, recurring_id)


def update_recurring_transaction(
    conn, recurring_id: int, data: RecurringTransactionUpdate
) -> RecurringTransactionOut:
    old = require_row(
        conn,
        "SELECT * FROM recurring_transactions WHERE id = ?",
        (recurring_id,),
        "Recurring transaction not found",
        NotFoundError,
    )
    new_debit = data.debit_account if data.debit_account is not None else old["debit_account"]
    new_credit = (
        data.credit_account if data.credit_account is not None else old["credit_account"]
    )
    _validate_accounts(conn, new_debit, new_credit)
    monetary = transactions_service._monetary_from_update(
        TransactionUpdate(
            amount=data.amount,
            original_amount=data.original_amount,
            original_currency=data.original_currency,
            fx_rate=data.fx_rate,
            fx_source=data.fx_source,
        ),
        old,
    )
    conn.execute(
        """UPDATE recurring_transactions
           SET debit_account = ?, credit_account = ?, amount = ?, original_amount = ?,
               original_currency = ?, fx_rate = ?, fx_source = ?, description = ?,
               alert_day = ?, alert_active = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (
            new_debit,
            new_credit,
            monetary["amount"],
            monetary["original_amount"],
            monetary["original_currency"],
            monetary["fx_rate"],
            monetary["fx_source"],
            data.description if data.description is not None else old["description"],
            data.alert_day if data.alert_day is not None else old["alert_day"],
            data.alert_active if data.alert_active is not None else old["alert_active"],
            data.enabled if data.enabled is not None else old["enabled"],
            recurring_id,
        ),
    )
    if data.tag_ids is not None:
        _replace_recurring_tags(conn, recurring_id, data.tag_ids)
    return get_recurring_transaction(conn, recurring_id)


def delete_recurring_transaction(conn, recurring_id: int) -> None:
    require_row(
        conn,
        "SELECT id FROM recurring_transactions WHERE id = ?",
        (recurring_id,),
        "Recurring transaction not found",
        NotFoundError,
    )
    conn.execute("DELETE FROM recurring_transactions WHERE id = ?", (recurring_id,))


def mark_recurring_transaction_done(
    conn, recurring_id: int
) -> RecurringTransactionOut:
    require_row(
        conn,
        "SELECT id FROM recurring_transactions WHERE id = ?",
        (recurring_id,),
        "Recurring transaction not found",
        NotFoundError,
    )
    conn.execute(
        """UPDATE recurring_transactions
           SET last_posted_period = ?, last_posted_at = CURRENT_TIMESTAMP,
               last_transaction_id = NULL, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (_current_period(), recurring_id),
    )
    return get_recurring_transaction(conn, recurring_id)


def post_recurring_transaction(
    conn, recurring_id: int, data: RecurringTransactionPostIn
) -> RecurringTransactionPostOut:
    recurring = require_row(
        conn,
        "SELECT * FROM recurring_transactions WHERE id = ?",
        (recurring_id,),
        "Recurring transaction not found",
        NotFoundError,
    )
    tag_ids = [
        row["tag_id"]
        for row in conn.execute(
            """SELECT tag_id FROM recurring_transaction_tags
               WHERE recurring_transaction_id = ?
               ORDER BY tag_id""",
            (recurring_id,),
        ).fetchall()
    ]
    tx = transactions_service.create_transaction(
        conn,
        TransactionIn(
            debit_account=recurring["debit_account"],
            credit_account=recurring["credit_account"],
            tag_ids=tag_ids,
            amount=data.amount,
            original_amount=(
                data.original_amount
                if data.original_amount is not None
                else recurring["original_amount"]
            ),
            original_currency=(
                data.original_currency
                if data.original_currency is not None
                else recurring["original_currency"]
            ),
            fx_rate=data.fx_rate if data.fx_rate is not None else recurring["fx_rate"],
            fx_source=(
                data.fx_source if data.fx_source is not None else recurring["fx_source"]
            ),
            description=(
                data.description
                if data.description is not None
                else recurring["description"]
            ),
            date=data.date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.execute(
        """UPDATE recurring_transactions
           SET last_posted_period = ?, last_posted_at = CURRENT_TIMESTAMP,
               last_transaction_id = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (_current_period(), tx.id, recurring_id),
    )
    return RecurringTransactionPostOut(
        recurring=get_recurring_transaction(conn, recurring_id),
        transaction=tx,
    )
