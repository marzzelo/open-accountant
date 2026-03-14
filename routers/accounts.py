"""
routers/accounts.py — Account CRUD + balance + movements + history.
"""
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from database import get_db, balance_delta, compute_filtered_balance, DEBIT_NORMAL
from models import AccountIn, AccountUpdate, AccountOut, MovementOut, MonthlyBar

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _current_year_range() -> tuple[str, str]:
    y = datetime.now().year
    return (f"{y}-01-01 00:00:00", f"{y}-12-31 23:59:59")


def _last_3_movements(conn, account_id: int, from_dt: str, to_dt: str) -> list[MovementOut]:
    rows = conn.execute(
        """
        SELECT t.id, t.date, t.description, t.amount,
               t.debit_account, t.credit_account,
               da.name AS debit_name, ca.name AS credit_name
        FROM transactions t
        JOIN accounts da ON t.debit_account  = da.id
        JOIN accounts ca ON t.credit_account = ca.id
        WHERE (t.debit_account = ? OR t.credit_account = ?)
          AND t.date BETWEEN ? AND ?
        ORDER BY t.date DESC, t.id DESC
        LIMIT 3
        """,
        (account_id, account_id, from_dt, to_dt),
    ).fetchall()

    out = []
    for r in rows:
        if r["debit_account"] == account_id:
            role, counterpart = "debit", r["credit_name"]
        else:
            role, counterpart = "credit", r["debit_name"]
        out.append(MovementOut(
            id=r["id"], date=r["date"], description=r["description"],
            amount=r["amount"], role=role, counterpart=counterpart,
        ))
    return out


def _monthly_history(conn, account_id: int, type_id: int) -> list[MonthlyBar]:
    """Last 12 calendar months — net change per month."""
    rows = conn.execute(
        """
        SELECT strftime('%Y-%m', date) AS month,
               COALESCE(SUM(CASE WHEN debit_account  = ? THEN amount ELSE 0 END), 0) AS deb,
               COALESCE(SUM(CASE WHEN credit_account = ? THEN amount ELSE 0 END), 0) AS cred
        FROM transactions
        WHERE (debit_account = ? OR credit_account = ?)
          AND date >= date('now', '-11 months', 'start of month')
        GROUP BY month
        ORDER BY month
        """,
        (account_id, account_id, account_id, account_id),
    ).fetchall()

    result = []
    for r in rows:
        if type_id in DEBIT_NORMAL:
            net = r["deb"] - r["cred"]
        else:
            net = r["cred"] - r["deb"]
        result.append(MonthlyBar(month=r["month"], net=net))
    return result


def _build_account_out(
    conn, row, from_dt: str, to_dt: str, filtered: bool
) -> AccountOut:
    account_id = row["id"]
    type_id    = row["type_id"]

    balance = (
        compute_filtered_balance(conn, account_id, type_id, row["initial_balance"], from_dt, to_dt)
        if filtered
        else row["balance"]
    )

    movements = _last_3_movements(conn, account_id, from_dt, to_dt)
    history   = _monthly_history(conn, account_id, type_id)

    return AccountOut(
        id=account_id,
        name=row["name"],
        type_id=type_id,
        type_name=row["type_name"],
        subtype_id=row["subtype_id"],
        subtype_name=row["subtype_name"],
        description=row["description"],
        initial_balance=row["initial_balance"],
        balance=balance,
        last_movements=movements,
        monthly_history=history,
    )


_ACCOUNT_SELECT = """
    SELECT a.*, t.name AS type_name,
           s.name AS subtype_name
    FROM accounts a
    JOIN types t    ON a.type_id    = t.id
    LEFT JOIN subtypes s ON a.subtype_id = s.id
"""

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
):
    # Default filter: current calendar year
    if from_date and to_date:
        from_dt, to_dt = from_date + " 00:00:00", to_date + " 23:59:59"
        filtered = True
    else:
        from_dt, to_dt = _current_year_range()
        filtered = False  # use stored balance for speed

    with get_db() as conn:
        rows = conn.execute(_ACCOUNT_SELECT + " ORDER BY a.type_id, a.name").fetchall()
        return [_build_account_out(conn, r, from_dt, to_dt, filtered) for r in rows]


@router.get("/accounts/{account_id}", response_model=AccountOut)
def get_account(
    account_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
):
    if from_date and to_date:
        from_dt, to_dt, filtered = from_date + " 00:00:00", to_date + " 23:59:59", True
    else:
        from_dt, to_dt = _current_year_range()
        filtered = False

    with get_db() as conn:
        row = conn.execute(
            _ACCOUNT_SELECT + " WHERE a.id = ?", (account_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Account not found")
        return _build_account_out(conn, row, from_dt, to_dt, filtered)


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(data: AccountIn):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM types WHERE id = ?", (data.type_id,)).fetchone():
            raise HTTPException(400, f"Type {data.type_id} does not exist")
        if data.subtype_id:
            st = conn.execute(
                "SELECT type_id FROM subtypes WHERE id = ?", (data.subtype_id,)
            ).fetchone()
            if not st:
                raise HTTPException(400, "Subtype not found")
            if st["type_id"] != data.type_id:
                raise HTTPException(400, "Subtype does not belong to the selected type")
        try:
            cur = conn.execute(
                """INSERT INTO accounts
                   (name, type_id, subtype_id, description, initial_balance, balance, properties)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (data.name.strip(), data.type_id, data.subtype_id,
                 data.description, data.initial_balance, data.initial_balance,
                 data.properties),
            )
            aid = cur.lastrowid
        except Exception as e:
            raise HTTPException(409, f"Account name already exists: {e}")

        row = conn.execute(_ACCOUNT_SELECT + " WHERE a.id = ?", (aid,)).fetchone()
        from_dt, to_dt = _current_year_range()
        return _build_account_out(conn, row, from_dt, to_dt, False)


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, data: AccountUpdate):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Account not found")

        name            = data.name.strip()          if data.name is not None            else row["name"]
        subtype_id      = data.subtype_id             if data.subtype_id is not None      else row["subtype_id"]
        description     = data.description            if data.description is not None     else row["description"]
        properties      = data.properties             if data.properties is not None      else row["properties"]
        initial_balance = data.initial_balance        if data.initial_balance is not None else row["initial_balance"]

        # Recalculate cumulative balance if initial_balance changed
        if data.initial_balance is not None:
            delta_init = data.initial_balance - row["initial_balance"]
            new_balance = row["balance"] + delta_init
        else:
            new_balance = row["balance"]

        conn.execute(
            """UPDATE accounts
               SET name=?, subtype_id=?, description=?, properties=?,
                   initial_balance=?, balance=?,
                   updated_at=datetime('now')
               WHERE id=?""",
            (name, subtype_id, description, properties,
             initial_balance, new_balance, account_id),
        )
        row = conn.execute(_ACCOUNT_SELECT + " WHERE a.id = ?", (account_id,)).fetchone()
        from_dt, to_dt = _current_year_range()
        return _build_account_out(conn, row, from_dt, to_dt, False)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone():
            raise HTTPException(404, "Account not found")
        tx_count = conn.execute(
            """SELECT COUNT(*) FROM transactions
               WHERE debit_account = ? OR credit_account = ?""",
            (account_id, account_id),
        ).fetchone()[0]
        if tx_count:
            raise HTTPException(
                409, f"Cannot delete: account has {tx_count} transaction(s). Delete transactions first."
            )
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
