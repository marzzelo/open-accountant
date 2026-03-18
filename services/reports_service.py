"""Report and analytics service functions."""

from typing import Optional

from database import balance_delta, compute_balance, compute_filtered_balance
from models import (
    BalanceGroup,
    BalanceLineItem,
    BalanceSheet,
    BalanceSubgroup,
    StatsData,
)

from services.errors import NotFoundError
from services.helpers import current_year_range as shared_current_year_range
from services.helpers import require_row, resolve_date_range


def current_year_range() -> tuple[str, str]:
    return shared_current_year_range()


def date_params(from_date: Optional[str], to_date: Optional[str]) -> tuple[str, str]:
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    return from_dt, to_dt


def get_balance(
    conn, from_date: Optional[str] = None, to_date: Optional[str] = None
) -> BalanceSheet:
    from_dt, to_dt, filtered = resolve_date_range(from_date, to_date)
    type_map: dict = {}

    rows = conn.execute(
        """SELECT a.id, a.name, a.type_id, a.subtype_id,
                  a.initial_balance,
                  t.name AS type_name,
                  COALESCE(s.name, 'Sin subtipo') AS subtype_name
           FROM accounts a
           JOIN types t ON a.type_id = t.id
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           ORDER BY a.type_id, s.name, a.name"""
    ).fetchall()

    for row in rows:
        balance = (
            compute_filtered_balance(
                conn, row["id"], row["type_id"], row["initial_balance"], from_dt, to_dt
            )
            if filtered
            else compute_balance(
                conn, row["id"], row["type_id"], row["initial_balance"]
            )
        )
        type_id = row["type_id"]
        if type_id not in type_map:
            type_map[type_id] = {"type_name": row["type_name"], "subtypes": {}}
        subtype_name = row["subtype_name"]
        type_map[type_id]["subtypes"].setdefault(subtype_name, []).append(
            BalanceLineItem(
                account_id=row["id"], account_name=row["name"], balance=balance
            )
        )

    groups = []
    totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
    for type_id in sorted(type_map.keys()):
        type_meta = type_map[type_id]
        subgroups = []
        type_total = 0.0
        for subtype_name, items in type_meta["subtypes"].items():
            subtotal = sum(item.balance for item in items)
            subgroups.append(
                BalanceSubgroup(
                    subtype_name=subtype_name, items=items, subtotal=subtotal
                )
            )
            type_total += subtotal
        groups.append(
            BalanceGroup(
                type_name=type_meta["type_name"],
                type_id=type_id,
                subgroups=subgroups,
                total=type_total,
            )
        )
        totals[type_id] = type_total

    result = totals[3] - totals[4]
    equation = totals[1] - (totals[2] + totals[5] + result)
    return BalanceSheet(
        period_from=from_dt[:10],
        period_to=to_dt[:10],
        groups=groups,
        total_activo=totals[1],
        total_pasivo=totals[2],
        total_patrimonio=totals[5],
        total_ingreso=totals[3],
        total_gasto=totals[4],
        resultado=result,
        equation_check=round(equation, 4),
    )


def journal_data(conn, from_date=None, to_date=None, account_id=None, limit=1000):
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    conditions = ["t.date BETWEEN ? AND ?"]
    params: list = [from_dt, to_dt]
    if account_id:
        conditions.append("(t.debit_account = ? OR t.credit_account = ?)")
        params += [account_id, account_id]
    where = "WHERE " + " AND ".join(conditions)
    rows = conn.execute(
        f"""SELECT t.id, t.date, t.description, t.amount,
                   t.original_amount, t.original_currency, t.fx_rate, t.fx_source,
                   da.name AS debit_name, ca.name AS credit_name
            FROM transactions t
            JOIN accounts da ON t.debit_account  = da.id
            JOIN accounts ca ON t.credit_account = ca.id
            {where}
            ORDER BY t.date ASC, t.id ASC
            LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [
        {
            "id": row["id"],
            "date": row["date"],
            "debit_name": row["debit_name"],
            "credit_name": row["credit_name"],
            "amount": row["amount"],
            "original_amount": row["original_amount"],
            "original_currency": row["original_currency"],
            "fx_rate": row["fx_rate"],
            "fx_source": row["fx_source"],
            "description": row["description"],
        }
        for row in rows
    ]


def get_ledger(
    conn,
    account_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    account = require_row(
        conn,
        "SELECT id, name, type_id, initial_balance FROM accounts WHERE id = ?",
        (account_id,),
        "Account not found",
        NotFoundError,
    )

    rows = conn.execute(
        """SELECT t.id, t.date, t.description, t.amount,
                  t.original_amount, t.original_currency, t.fx_rate, t.fx_source,
                  t.debit_account, t.credit_account,
                  da.name AS debit_name, ca.name AS credit_name
           FROM transactions t
           JOIN accounts da ON t.debit_account  = da.id
           JOIN accounts ca ON t.credit_account = ca.id
           WHERE (t.debit_account = ? OR t.credit_account = ?)
             AND t.date BETWEEN ? AND ?
           ORDER BY t.date ASC, t.id ASC""",
        (account_id, account_id, from_dt, to_dt),
    ).fetchall()

    running = account["initial_balance"]
    entries = []
    for row in rows:
        if row["debit_account"] == account_id:
            role, counterpart, delta = (
                "Débito",
                row["credit_name"],
                balance_delta(account["type_id"], "debit", row["amount"]),
            )
        else:
            role, counterpart, delta = (
                "Crédito",
                row["debit_name"],
                balance_delta(account["type_id"], "credit", row["amount"]),
            )
        running += delta
        entries.append(
            {
                "id": row["id"],
                "date": row["date"],
                "description": row["description"] or counterpart,
                "counterpart": counterpart,
                "role": role,
                "debit": row["amount"] if role == "Débito" else None,
                "credit": row["amount"] if role == "Crédito" else None,
                "original_amount": row["original_amount"],
                "original_currency": row["original_currency"],
                "fx_rate": row["fx_rate"],
                "fx_source": row["fx_source"],
                "balance": round(running, 4),
            }
        )

    return {
        "account_id": account["id"],
        "account_name": account["name"],
        "period_from": from_dt[:10],
        "period_to": to_dt[:10],
        "opening_balance": account["initial_balance"],
        "closing_balance": round(running, 4),
        "entries": entries,
    }


def get_stats(
    conn, from_date: Optional[str] = None, to_date: Optional[str] = None
) -> StatsData:
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)

    cashflow_rows = conn.execute(
        """WITH tx_legs AS (
             SELECT strftime('%Y-%m', t.date) AS month,
                 da.type_id AS type_id,
                 t.amount AS debit_amount,
                 0 AS credit_amount
             FROM transactions t
             JOIN accounts da ON t.debit_account = da.id
             WHERE t.date BETWEEN ? AND ?

             UNION ALL

             SELECT strftime('%Y-%m', t.date) AS month,
                 ca.type_id AS type_id,
                 0 AS debit_amount,
                 t.amount AS credit_amount
             FROM transactions t
             JOIN accounts ca ON t.credit_account = ca.id
             WHERE t.date BETWEEN ? AND ?
         )
         SELECT month,
             SUM(CASE WHEN type_id = 3 THEN credit_amount - debit_amount ELSE 0 END) AS ingresos,
             SUM(CASE WHEN type_id = 4 THEN debit_amount - credit_amount ELSE 0 END) AS gastos
         FROM tx_legs
         GROUP BY month
         ORDER BY month""",
        (from_dt, to_dt, from_dt, to_dt),
    ).fetchall()
    monthly_cashflow = [
        {
            "month": row["month"],
            "ingresos": row["ingresos"],
            "gastos": row["gastos"],
            "neto": row["ingresos"] - row["gastos"],
        }
        for row in cashflow_rows
    ]

    exp_rows = conn.execute(
        """WITH subtype_legs AS (
         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.debit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 4 AND t.date BETWEEN ? AND ?

         UNION ALL

         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             -t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.credit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 4 AND t.date BETWEEN ? AND ?
     )
     SELECT subtype,
         SUM(signed_amount) AS amount
     FROM subtype_legs
     GROUP BY subtype
     HAVING SUM(signed_amount) > 0
     ORDER BY amount DESC""",
        (from_dt, to_dt, from_dt, to_dt),
    ).fetchall()
    expenses_by_subtype = [
        {"subtype": row["subtype"], "amount": row["amount"]} for row in exp_rows
    ]

    inc_rows = conn.execute(
        """WITH subtype_legs AS (
         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.credit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 3 AND t.date BETWEEN ? AND ?

         UNION ALL

         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             -t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.debit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 3 AND t.date BETWEEN ? AND ?
     )
     SELECT subtype,
         SUM(signed_amount) AS amount
     FROM subtype_legs
     GROUP BY subtype
     HAVING SUM(signed_amount) > 0
     ORDER BY amount DESC""",
        (from_dt, to_dt, from_dt, to_dt),
    ).fetchall()
    income_by_subtype = [
        {"subtype": row["subtype"], "amount": row["amount"]} for row in inc_rows
    ]

    asset_accounts = conn.execute(
        "SELECT id, name, type_id, initial_balance FROM accounts WHERE type_id = 1 ORDER BY name COLLATE NOCASE"
    ).fetchall()
    asset_composition = []
    for account in asset_accounts:
        balance = compute_filtered_balance(
            conn,
            account["id"],
            account["type_id"],
            account["initial_balance"],
            from_dt,
            to_dt,
        )
        if balance > 0:
            asset_composition.append(
                {
                    "account": account["name"],
                    "balance": round(balance, 4),
                }
            )

    top_rows = conn.execute(
        """SELECT a.name AS account,
                  SUM(t.amount) AS volume,
                  COUNT(*) AS tx_count
           FROM transactions t
           JOIN accounts a ON t.debit_account = a.id OR t.credit_account = a.id
           WHERE t.date BETWEEN ? AND ?
           GROUP BY a.id ORDER BY volume DESC LIMIT 10""",
        (from_dt, to_dt),
    ).fetchall()
    top_accounts = [
        {
            "account": row["account"],
            "volume": row["volume"],
            "tx_count": row["tx_count"],
        }
        for row in top_rows
    ]

    months_rows = conn.execute(
        """SELECT DISTINCT strftime('%Y-%m', date) AS month FROM transactions
           WHERE date BETWEEN ? AND ? ORDER BY month""",
        (from_dt, to_dt),
    ).fetchall()
    months = [row["month"] for row in months_rows]

    balance_evolution = []
    for account in asset_accounts:
        for month in months:
            month_end = month + "-31 23:59:59"
            balance = compute_filtered_balance(
                conn,
                account["id"],
                account["type_id"],
                account["initial_balance"],
                from_dt,
                month_end,
            )
            balance_evolution.append(
                {
                    "month": month,
                    "account_id": account["id"],
                    "account_name": account["name"],
                    "balance": balance,
                }
            )

    return StatsData(
        monthly_cashflow=monthly_cashflow,
        expenses_by_subtype=expenses_by_subtype,
        income_by_subtype=income_by_subtype,
        asset_composition=asset_composition,
        top_accounts=top_accounts,
        balance_evolution=balance_evolution,
    )
