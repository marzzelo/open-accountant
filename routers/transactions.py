"""
routers/transactions.py — Transaction CRUD with double-entry balance updates.
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from database import get_db, balance_delta
from models import TransactionIn, TransactionUpdate, TransactionOut

router = APIRouter()


def _row_to_out(row) -> TransactionOut:
    return TransactionOut(
        id=row["id"],
        debit_account=row["debit_account"],
        debit_name=row["debit_name"],
        debit_type_id=row["debit_type_id"],
        credit_account=row["credit_account"],
        credit_name=row["credit_name"],
        credit_type_id=row["credit_type_id"],
        amount=row["amount"],
        description=row["description"],
        date=row["date"],
        created_at=row["created_at"],
    )


_TX_SELECT = """
    SELECT t.*,
           da.name    AS debit_name,  da.type_id AS debit_type_id,
           ca.name    AS credit_name, ca.type_id AS credit_type_id
    FROM transactions t
    JOIN accounts da ON t.debit_account  = da.id
    JOIN accounts ca ON t.credit_account = ca.id
"""


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    from_date:  Optional[str] = Query(None, alias="from"),
    to_date:    Optional[str] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    limit:      int = Query(500, ge=1, le=5000),
    offset:     int = Query(0, ge=0),
):
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

    with get_db() as conn:
        rows = conn.execute(
            f"{_TX_SELECT} {where} ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [_row_to_out(r) for r in rows]


@router.get("/transactions/{tx_id}", response_model=TransactionOut)
def get_transaction(tx_id: int):
    with get_db() as conn:
        row = conn.execute(_TX_SELECT + " WHERE t.id = ?", (tx_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Transaction not found")
    return _row_to_out(row)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionIn):
    if data.debit_account == data.credit_account:
        raise HTTPException(400, "Debit and credit accounts must be different")

    tx_date = data.date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        # Fetch both accounts
        deb_acc = conn.execute(
            "SELECT id, type_id, balance FROM accounts WHERE id = ?", (data.debit_account,)
        ).fetchone()
        cred_acc = conn.execute(
            "SELECT id, type_id, balance FROM accounts WHERE id = ?", (data.credit_account,)
        ).fetchone()

        if not deb_acc:
            raise HTTPException(404, f"Debit account {data.debit_account} not found")
        if not cred_acc:
            raise HTTPException(404, f"Credit account {data.credit_account} not found")

        # Insert transaction
        cur = conn.execute(
            """INSERT INTO transactions
               (debit_account, credit_account, amount, description, date)
               VALUES (?, ?, ?, ?, ?)""",
            (data.debit_account, data.credit_account,
             data.amount, data.description, tx_date),
        )
        tx_id = cur.lastrowid

        # Update balances
        deb_delta  = balance_delta(deb_acc["type_id"],  "debit",  data.amount)
        cred_delta = balance_delta(cred_acc["type_id"], "credit", data.amount)

        conn.execute(
            "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id = ?",
            (deb_delta, data.debit_account),
        )
        conn.execute(
            "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id = ?",
            (cred_delta, data.credit_account),
        )

        row = conn.execute(_TX_SELECT + " WHERE t.id = ?", (tx_id,)).fetchone()
    return _row_to_out(row)


@router.put("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, data: TransactionUpdate):
    """Update amount, description or date. Reverses old balance effect and applies new one."""
    with get_db() as conn:
        old = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        if not old:
            raise HTTPException(404, "Transaction not found")

        deb_acc  = conn.execute("SELECT type_id FROM accounts WHERE id = ?",
                                (old["debit_account"],)).fetchone()
        cred_acc = conn.execute("SELECT type_id FROM accounts WHERE id = ?",
                                (old["credit_account"],)).fetchone()

        # Reverse old balance effect
        old_deb_delta  = balance_delta(deb_acc["type_id"],  "debit",  old["amount"])
        old_cred_delta = balance_delta(cred_acc["type_id"], "credit", old["amount"])
        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now') WHERE id = ?",
            (old_deb_delta, old["debit_account"]),
        )
        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now') WHERE id = ?",
            (old_cred_delta, old["credit_account"]),
        )

        # Apply updates
        new_amount = data.amount if data.amount is not None else old["amount"]
        new_desc   = data.description if data.description is not None else old["description"]
        new_date   = data.date if data.date is not None else old["date"]

        conn.execute(
            "UPDATE transactions SET amount = ?, description = ?, date = ? WHERE id = ?",
            (new_amount, new_desc, new_date, tx_id),
        )

        # Apply new balance effect
        new_deb_delta  = balance_delta(deb_acc["type_id"],  "debit",  new_amount)
        new_cred_delta = balance_delta(cred_acc["type_id"], "credit", new_amount)
        conn.execute(
            "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id = ?",
            (new_deb_delta, old["debit_account"]),
        )
        conn.execute(
            "UPDATE accounts SET balance = balance + ?, updated_at = datetime('now') WHERE id = ?",
            (new_cred_delta, old["credit_account"]),
        )

        row = conn.execute(_TX_SELECT + " WHERE t.id = ?", (tx_id,)).fetchone()
    return _row_to_out(row)


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int):
    """Delete a transaction and reverse its balance effect."""
    with get_db() as conn:
        old = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Transaction not found")

        deb_acc  = conn.execute("SELECT type_id FROM accounts WHERE id = ?",
                                (old["debit_account"],)).fetchone()
        cred_acc = conn.execute("SELECT type_id FROM accounts WHERE id = ?",
                                (old["credit_account"],)).fetchone()

        # Reverse balance
        deb_delta  = balance_delta(deb_acc["type_id"],  "debit",  old["amount"])
        cred_delta = balance_delta(cred_acc["type_id"], "credit", old["amount"])

        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now') WHERE id = ?",
            (deb_delta, old["debit_account"]),
        )
        conn.execute(
            "UPDATE accounts SET balance = balance - ?, updated_at = datetime('now') WHERE id = ?",
            (cred_delta, old["credit_account"]),
        )
        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
