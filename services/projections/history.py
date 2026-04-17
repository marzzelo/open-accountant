"""Historical projections data extraction helpers."""

from database import ci_order_sql, compute_filtered_balance, month_bucket_sql

from services.helpers import end_of_month_datetime


def _get_monthly_cashflow(
    conn, from_date: str, to_date: str
) -> tuple[dict[str, float], dict[str, float]]:
    """Return sparse income/expense maps keyed by month (YYYY-MM)."""
    month_expr = month_bucket_sql(conn, "t.date")
    legs_cte = """WITH tx_legs AS (
        SELECT {month_expr} AS month,
               da.type_id AS type_id,
               t.amount    AS debit_amount,
               0           AS credit_amount
        FROM transactions t
        JOIN accounts da ON t.debit_account = da.id
        WHERE t.date BETWEEN ? AND ?

        UNION ALL

        SELECT {month_expr} AS month,
               ca.type_id AS type_id,
               0           AS debit_amount,
               t.amount    AS credit_amount
        FROM transactions t
        JOIN accounts ca ON t.credit_account = ca.id
        WHERE t.date BETWEEN ? AND ?
    )""".format(
        month_expr=month_expr
    )

    income_rows = conn.execute(
        legs_cte
        + """
        SELECT month, SUM(credit_amount - debit_amount) AS value
        FROM tx_legs WHERE type_id = 3
        GROUP BY month ORDER BY month""",
        (from_date, to_date, from_date, to_date),
    ).fetchall()

    expense_rows = conn.execute(
        legs_cte
        + """
        SELECT month, SUM(debit_amount - credit_amount) AS value
        FROM tx_legs WHERE type_id = 4
        GROUP BY month ORDER BY month""",
        (from_date, to_date, from_date, to_date),
    ).fetchall()

    income_map = {row["month"]: float(row["value"]) for row in income_rows}
    expense_map = {row["month"]: float(row["value"]) for row in expense_rows}
    return income_map, expense_map


def _get_monthly_balances(
    conn, from_date: str, to_date: str, type_id: int
) -> dict[str, float]:
    """Return {YYYY-MM: balance} for accounts of the given type_id."""
    asset_accounts = conn.execute(
        "SELECT id, type_id, initial_balance FROM accounts WHERE type_id = ?",
        (type_id,),
    ).fetchall()

    month_expr = month_bucket_sql(conn, "date")
    months_rows = conn.execute(
        f"""SELECT DISTINCT {month_expr} AS month FROM transactions
           WHERE date BETWEEN ? AND ? ORDER BY month""",
        (from_date, to_date),
    ).fetchall()
    months = [row["month"] for row in months_rows]

    result: dict[str, float] = {}
    for month in months:
        month_end = end_of_month_datetime(month)
        total = 0.0
        for account in asset_accounts:
            balance = compute_filtered_balance(
                conn,
                account["id"],
                account["type_id"],
                account["initial_balance"],
                from_date,
                month_end,
            )
            total += balance
        result[month] = round(total, 4)
    return result


def _financial_rows(conn, type_id: int):
    order_sql = ci_order_sql(conn, "a.name")
    return conn.execute(
        f"""SELECT a.id, a.name, a.type_id, a.initial_balance, a.properties,
                  COALESCE(s.name, '') AS subtype_name
           FROM accounts a
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           WHERE a.type_id = ?
           ORDER BY {order_sql}""",
        (type_id,),
    ).fetchall()


__all__ = [
    "_financial_rows",
    "_get_monthly_balances",
    "_get_monthly_cashflow",
]
