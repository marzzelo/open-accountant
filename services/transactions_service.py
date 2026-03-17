"""Transaction service functions."""

from datetime import datetime
from typing import Optional

from models import TransactionIn, TransactionOut, TransactionUpdate

from services.errors import NotFoundError, ValidationError
from services.helpers import model_from_row, require_row

TX_SELECT = """
    SELECT t.*,
           da.name    AS debit_name,  da.type_id AS debit_type_id,
           ca.name    AS credit_name, ca.type_id AS credit_type_id
    FROM transactions t
    JOIN accounts da ON t.debit_account  = da.id
    JOIN accounts ca ON t.credit_account = ca.id
"""


def row_to_out(row) -> TransactionOut:
    return model_from_row(TransactionOut, row)


def list_transactions(
    conn,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    account_id: Optional[int] = None,
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

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]
    rows = conn.execute(
        f"{TX_SELECT} {where} ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [row_to_out(row) for row in rows]


def get_transaction(conn, tx_id: int) -> TransactionOut:
    row = require_row(
        conn,
        TX_SELECT + " WHERE t.id = ?",
        (tx_id,),
        "Transaction not found",
        NotFoundError,
    )
    return row_to_out(row)


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

    cur = conn.execute(
        """INSERT INTO transactions
           (debit_account, credit_account, amount, description, date)
           VALUES (?, ?, ?, ?, ?)""",
        (
            data.debit_account,
            data.credit_account,
            data.amount,
            data.description,
            tx_date,
        ),
    )
    return get_transaction(conn, cur.lastrowid)


def update_transaction(conn, tx_id: int, data: TransactionUpdate) -> TransactionOut:
    old = require_row(
        conn,
        "SELECT * FROM transactions WHERE id = ?",
        (tx_id,),
        "Transaction not found",
        NotFoundError,
    )

    new_amount = data.amount if data.amount is not None else old["amount"]
    new_desc = data.description if data.description is not None else old["description"]
    new_date = data.date if data.date is not None else old["date"]

    conn.execute(
        "UPDATE transactions SET amount = ?, description = ?, date = ? WHERE id = ?",
        (new_amount, new_desc, new_date, tx_id),
    )
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
