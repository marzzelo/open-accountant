"""Account service functions."""

from json import JSONDecodeError
from typing import Optional

from database import (
    DEBIT_NORMAL,
    compute_balance,
    compute_filtered_balance,
    month_bucket_sql,
    recent_months_filter_sql,
)
from models import AccountIn, AccountOut, AccountUpdate, MonthlyBar, MovementOut

from services.errors import ConflictError, NotFoundError, ValidationError
from services.helpers import (
    normalize_account_properties,
    require_row,
    resolve_date_range,
    serialize_account_properties,
    serialize_temporal_value,
)

ACCOUNT_SELECT = """
    SELECT a.*, t.name AS type_name,
           s.name AS subtype_name
    FROM accounts a
    JOIN types t    ON a.type_id    = t.id
    LEFT JOIN subtypes s ON a.subtype_id = s.id
"""


def last_3_movements(
    conn, account_id: int, from_dt: str, to_dt: str
) -> list[MovementOut]:
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
    for row in rows:
        if row["debit_account"] == account_id:
            role, counterpart = "debit", row["credit_name"]
        else:
            role, counterpart = "credit", row["debit_name"]
        out.append(
            MovementOut(
                id=row["id"],
                date=serialize_temporal_value(row["date"]),
                description=row["description"],
                amount=row["amount"],
                role=role,
                counterpart=counterpart,
            )
        )
    return out


def monthly_history(conn, account_id: int, type_id: int) -> list[MonthlyBar]:
    month_expr = month_bucket_sql(conn, "date")
    recent_filter = recent_months_filter_sql(conn, "date", 11)
    rows = conn.execute(
        f"""
        SELECT {month_expr} AS month,
               COALESCE(SUM(CASE WHEN debit_account  = ? THEN amount ELSE 0 END), 0) AS deb,
               COALESCE(SUM(CASE WHEN credit_account = ? THEN amount ELSE 0 END), 0) AS cred
        FROM transactions
        WHERE (debit_account = ? OR credit_account = ?)
          AND {recent_filter}
        GROUP BY month
        ORDER BY month
        """,
        (account_id, account_id, account_id, account_id),
    ).fetchall()

    result = []
    for row in rows:
        if type_id in DEBIT_NORMAL:
            net = row["deb"] - row["cred"]
        else:
            net = row["cred"] - row["deb"]
        result.append(MonthlyBar(month=row["month"], net=net))
    return result


def batch_balances(
    conn, rows, from_dt: str, to_dt: str, filtered: bool
) -> dict[int, float]:
    date_filter = ""
    params: tuple = ()
    if filtered:
        date_filter = " WHERE date BETWEEN ? AND ?"
        params = (from_dt, to_dt)

    totals = conn.execute(
        f"""
        WITH tx_legs AS (
            SELECT debit_account AS account_id,
                   amount AS debit_amount,
                   0 AS credit_amount
            FROM transactions{date_filter}

            UNION ALL

            SELECT credit_account AS account_id,
                   0 AS debit_amount,
                   amount AS credit_amount
            FROM transactions{date_filter}
        )
        SELECT account_id,
               COALESCE(SUM(debit_amount), 0) AS total_debit,
               COALESCE(SUM(credit_amount), 0) AS total_credit
        FROM tx_legs
        GROUP BY account_id
        """,
        params * 2 if filtered else params,
    ).fetchall()

    total_map = {
        row["account_id"]: (row["total_debit"], row["total_credit"]) for row in totals
    }
    balance_map: dict[int, float] = {}
    for row in rows:
        total_debit, total_credit = total_map.get(row["id"], (0.0, 0.0))
        if row["type_id"] in DEBIT_NORMAL:
            balance_map[row["id"]] = row["initial_balance"] + total_debit - total_credit
        else:
            balance_map[row["id"]] = row["initial_balance"] - total_debit + total_credit
    return balance_map


def batch_last_movements(
    conn, from_dt: str, to_dt: str
) -> dict[int, list[MovementOut]]:
    rows = conn.execute(
        """
        WITH movement_legs AS (
            SELECT t.debit_account AS account_id,
                   t.id,
                   t.date,
                   t.description,
                   t.amount,
                   'debit' AS role,
                   ca.name AS counterpart
            FROM transactions t
            JOIN accounts ca ON t.credit_account = ca.id
            WHERE t.date BETWEEN ? AND ?

            UNION ALL

            SELECT t.credit_account AS account_id,
                   t.id,
                   t.date,
                   t.description,
                   t.amount,
                   'credit' AS role,
                   da.name AS counterpart
            FROM transactions t
            JOIN accounts da ON t.debit_account = da.id
            WHERE t.date BETWEEN ? AND ?
        ),
        ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY account_id
                       ORDER BY date DESC, id DESC
                   ) AS rn
            FROM movement_legs
        )
        SELECT account_id, id, date, description, amount, role, counterpart
        FROM ranked
        WHERE rn <= 3
        ORDER BY account_id, date DESC, id DESC
        """,
        (from_dt, to_dt, from_dt, to_dt),
    ).fetchall()

    movement_map: dict[int, list[MovementOut]] = {}
    for row in rows:
        movement_map.setdefault(row["account_id"], []).append(
            MovementOut(
                id=row["id"],
                date=serialize_temporal_value(row["date"]),
                description=row["description"],
                amount=row["amount"],
                role=row["role"],
                counterpart=row["counterpart"],
            )
        )
    return movement_map


def batch_monthly_history(conn, rows) -> dict[int, list[MonthlyBar]]:
    month_expr = month_bucket_sql(conn, "date")
    recent_filter = recent_months_filter_sql(conn, "date", 11)
    totals = conn.execute(
        f"""
        WITH month_legs AS (
            SELECT debit_account AS account_id,
             {month_expr} AS month,
                   amount AS debit_amount,
                   0 AS credit_amount
            FROM transactions
         WHERE {recent_filter}

            UNION ALL

            SELECT credit_account AS account_id,
             {month_expr} AS month,
                   0 AS debit_amount,
                   amount AS credit_amount
            FROM transactions
         WHERE {recent_filter}
        )
        SELECT account_id,
               month,
               COALESCE(SUM(debit_amount), 0) AS deb,
               COALESCE(SUM(credit_amount), 0) AS cred
        FROM month_legs
        GROUP BY account_id, month
        ORDER BY account_id, month
        """
    ).fetchall()

    type_map = {row["id"]: row["type_id"] for row in rows}
    history_map: dict[int, list[MonthlyBar]] = {}
    for row in totals:
        type_id = type_map.get(row["account_id"])
        if type_id is None:
            continue
        net = (
            row["deb"] - row["cred"]
            if type_id in DEBIT_NORMAL
            else row["cred"] - row["deb"]
        )
        history_map.setdefault(row["account_id"], []).append(
            MonthlyBar(month=row["month"], net=net)
        )
    return history_map


def build_account_out(
    conn, row, from_dt: str, to_dt: str, filtered: bool
) -> AccountOut:
    account_id = row["id"]
    type_id = row["type_id"]
    balance = (
        compute_filtered_balance(
            conn, account_id, type_id, row["initial_balance"], from_dt, to_dt
        )
        if filtered
        else compute_balance(conn, account_id, type_id, row["initial_balance"])
    )

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
        properties=normalize_account_properties(
            row["properties"],
            type_id=type_id,
            name=row["name"],
            subtype_name=row["subtype_name"],
        ),
        last_movements=last_3_movements(conn, account_id, from_dt, to_dt),
        monthly_history=monthly_history(conn, account_id, type_id),
    )


def list_accounts(
    conn, from_date: Optional[str] = None, to_date: Optional[str] = None
) -> list[AccountOut]:
    from_dt, to_dt, filtered = resolve_date_range(from_date, to_date)

    rows = conn.execute(ACCOUNT_SELECT + " ORDER BY a.type_id, a.name").fetchall()
    balance_map = batch_balances(conn, rows, from_dt, to_dt, filtered)
    movement_map = batch_last_movements(conn, from_dt, to_dt)
    history_map = batch_monthly_history(conn, rows)

    return [
        AccountOut(
            id=row["id"],
            name=row["name"],
            type_id=row["type_id"],
            type_name=row["type_name"],
            subtype_id=row["subtype_id"],
            subtype_name=row["subtype_name"],
            description=row["description"],
            initial_balance=row["initial_balance"],
            balance=balance_map.get(row["id"], float(row["initial_balance"])),
            properties=normalize_account_properties(
                row["properties"],
                type_id=row["type_id"],
                name=row["name"],
                subtype_name=row["subtype_name"],
            ),
            last_movements=movement_map.get(row["id"], []),
            monthly_history=history_map.get(row["id"], []),
        )
        for row in rows
    ]


def get_account(
    conn,
    account_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> AccountOut:
    from_dt, to_dt, filtered = resolve_date_range(from_date, to_date)
    row = require_row(
        conn,
        ACCOUNT_SELECT + " WHERE a.id = ?",
        (account_id,),
        "Account not found",
        NotFoundError,
    )
    return build_account_out(conn, row, from_dt, to_dt, filtered)


def create_account(conn, data: AccountIn) -> AccountOut:
    require_row(
        conn,
        "SELECT 1 FROM types WHERE id = ?",
        (data.type_id,),
        f"Type {data.type_id} does not exist",
        ValidationError,
    )
    subtype_name = None
    if data.subtype_id:
        subtype = require_row(
            conn,
            "SELECT type_id, name FROM subtypes WHERE id = ?",
            (data.subtype_id,),
            "Subtype not found",
            ValidationError,
        )
        if subtype["type_id"] != data.type_id:
            raise ValidationError("Subtype does not belong to the selected type")
        subtype_name = subtype["name"]

    try:
        properties = serialize_account_properties(
            data.properties,
            type_id=data.type_id,
            name=data.name.strip(),
            subtype_name=subtype_name,
        )
    except (TypeError, ValueError, JSONDecodeError) as exc:
        raise ValidationError("Invalid properties payload") from exc

    try:
        row = conn.execute(
            """INSERT INTO accounts
                     (name, type_id, subtype_id, description, initial_balance, properties)
                     VALUES (?, ?, ?, ?, ?, ?)
                     RETURNING id""",
            (
                data.name.strip(),
                data.type_id,
                data.subtype_id,
                data.description,
                data.initial_balance,
                properties,
            ),
        )
    except Exception as exc:
        raise ConflictError(f"Account name already exists: {exc}") from exc

    return get_account(conn, row.fetchone()["id"])


def update_account(conn, account_id: int, data: AccountUpdate) -> AccountOut:
    row = require_row(
        conn,
        "SELECT * FROM accounts WHERE id = ?",
        (account_id,),
        "Account not found",
        NotFoundError,
    )

    name = data.name.strip() if data.name is not None else row["name"]
    subtype_id = data.subtype_id if data.subtype_id is not None else row["subtype_id"]
    description = (
        data.description if data.description is not None else row["description"]
    )
    initial_balance = (
        data.initial_balance
        if data.initial_balance is not None
        else row["initial_balance"]
    )

    subtype_name = None
    if subtype_id:
        subtype = require_row(
            conn,
            "SELECT type_id, name FROM subtypes WHERE id = ?",
            (subtype_id,),
            "Subtype not found",
            ValidationError,
        )
        if subtype["type_id"] != row["type_id"]:
            raise ValidationError("Subtype does not belong to the selected type")
        subtype_name = subtype["name"]

    raw_properties = (
        data.properties if data.properties is not None else row["properties"]
    )
    try:
        properties = serialize_account_properties(
            raw_properties,
            type_id=row["type_id"],
            name=name,
            subtype_name=subtype_name,
        )
    except (TypeError, ValueError, JSONDecodeError) as exc:
        raise ValidationError("Invalid properties payload") from exc

    conn.execute(
        """UPDATE accounts
           SET name=?, subtype_id=?, description=?, properties=?,
               initial_balance=?,
               updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (name, subtype_id, description, properties, initial_balance, account_id),
    )
    return get_account(conn, account_id)


def delete_account(conn, account_id: int):
    require_row(
        conn,
        "SELECT 1 FROM accounts WHERE id = ?",
        (account_id,),
        "Account not found",
        NotFoundError,
    )

    tx_count = conn.execute(
        """SELECT COUNT(*) AS tx_count FROM transactions
           WHERE debit_account = ? OR credit_account = ?""",
        (account_id, account_id),
    ).fetchone()["tx_count"]
    if tx_count:
        raise ConflictError(
            f"Cannot delete: account has {tx_count} transaction(s). Delete transactions first."
        )

    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
