"""Projections service: series CRUD + linear regression forecasting."""

from datetime import date
from typing import Optional

from database import compute_balance, compute_filtered_balance
from models import ProjectionSeriesIn, ProjectionSeriesUpdate

from services.errors import NotFoundError
from services.helpers import require_row


# ── Month helpers ──────────────────────────────────────────────────────────────

def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Return (year, month) after adding delta months."""
    month += delta
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return year, month


def _month_str(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _parse_month(month_str: str) -> tuple[int, int]:
    return int(month_str[:4]), int(month_str[5:7])


def _month_to_index(month_str: str, base_month: str) -> int:
    """0-based index of month_str relative to base_month."""
    y1, m1 = _parse_month(base_month)
    y2, m2 = _parse_month(month_str)
    return (y2 - y1) * 12 + (m2 - m1)


def _months_range(start: str, count: int) -> list[str]:
    """List of 'count' month strings starting from 'start' (YYYY-MM)."""
    y, m = _parse_month(start)
    result = []
    for i in range(count):
        y2, m2 = _add_months(y, m, i)
        result.append(_month_str(y2, m2))
    return result


# ── Linear regression (pure Python, no numpy) ─────────────────────────────────

def _linear_regression(points: list[float]) -> tuple[float, float]:
    """OLS on y values where x = 0, 1, 2, ... Returns (slope, intercept)."""
    n = len(points)
    if n < 2:
        return 0.0, (points[0] if points else 0.0)
    x_mean = (n - 1) / 2.0
    y_mean = sum(points) / n
    num = sum((i - x_mean) * (points[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _fill_by_regression(sparse: list) -> list[float]:
    """
    Fill None entries in a sparse historical series by extrapolating with OLS
    on the available (non-None) data points.

    Rules:
    - 0 known points  → fill everything with 0.0
    - 1 known point   → fill everything with that value
    - 2+ known points → OLS regression on known indices; predict missing positions
                        (predictions clamped to 0 for flow metrics — callers decide)

    Known (non-None) positions are never overwritten.
    """
    n = len(sparse)
    known = [(i, float(v)) for i, v in enumerate(sparse) if v is not None]

    if len(known) == 0:
        return [0.0] * n

    if len(known) == 1:
        return [known[0][1]] * n

    # OLS on the subset of known positions (x = actual index in the full array)
    xs = [p[0] for p in known]
    ys = [p[1] for p in known]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(len(xs)))
    den = sum((xs[i] - x_mean) ** 2 for i in range(len(xs)))
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean

    result = []
    for i, v in enumerate(sparse):
        if v is not None:
            result.append(float(v))
        else:
            result.append(max(0.0, intercept + slope * i))
    return result


# ── Historical data helpers ───────────────────────────────────────────────────

def _get_monthly_cashflow(
    conn, from_date: str, to_date: str
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Returns (income_map, expense_map) where each maps YYYY-MM → value.
    Only months that actually have transactions for the respective account type
    appear in each map, so that months with no income/expense activity are
    correctly treated as missing data (None) by the caller.
    """
    legs_cte = """WITH tx_legs AS (
        SELECT strftime('%Y-%m', t.date) AS month,
               da.type_id AS type_id,
               t.amount    AS debit_amount,
               0           AS credit_amount
        FROM transactions t
        JOIN accounts da ON t.debit_account = da.id
        WHERE t.date BETWEEN ? AND ?

        UNION ALL

        SELECT strftime('%Y-%m', t.date) AS month,
               ca.type_id AS type_id,
               0           AS debit_amount,
               t.amount    AS credit_amount
        FROM transactions t
        JOIN accounts ca ON t.credit_account = ca.id
        WHERE t.date BETWEEN ? AND ?
    )"""

    income_rows = conn.execute(
        legs_cte + """
        SELECT month, SUM(credit_amount - debit_amount) AS value
        FROM tx_legs WHERE type_id = 3
        GROUP BY month ORDER BY month""",
        (from_date, to_date, from_date, to_date),
    ).fetchall()

    expense_rows = conn.execute(
        legs_cte + """
        SELECT month, SUM(debit_amount - credit_amount) AS value
        FROM tx_legs WHERE type_id = 4
        GROUP BY month ORDER BY month""",
        (from_date, to_date, from_date, to_date),
    ).fetchall()

    income_map  = {r["month"]: float(r["value"]) for r in income_rows}
    expense_map = {r["month"]: float(r["value"]) for r in expense_rows}
    return income_map, expense_map


def _get_monthly_balances(conn, from_date: str, to_date: str, type_id: int) -> dict[str, float]:
    """
    Returns {YYYY-MM: balance} for accounts of the given type_id,
    computing cumulative balance up to the end of each month.
    """
    asset_accounts = conn.execute(
        "SELECT id, type_id, initial_balance FROM accounts WHERE type_id = ?",
        (type_id,),
    ).fetchall()

    months_rows = conn.execute(
        """SELECT DISTINCT strftime('%Y-%m', date) AS month FROM transactions
           WHERE date BETWEEN ? AND ? ORDER BY month""",
        (from_date, to_date),
    ).fetchall()
    months = [r["month"] for r in months_rows]

    result: dict[str, float] = {}
    for month in months:
        month_end = month + "-31 23:59:59"
        total = 0.0
        for acc in asset_accounts:
            bal = compute_filtered_balance(
                conn, acc["id"], acc["type_id"], acc["initial_balance"],
                from_date, month_end,
            )
            total += bal
        result[month] = round(total, 4)
    return result


# ── Series adjustments ────────────────────────────────────────────────────────

def _compute_series_adjustments(series_list: list[dict], projected_months: list[str]) -> dict:
    """
    For each projected month, sum income/expense from active series.
    A series is active in month M if start_date <= M-01 and month_index < series.months.
    Returns dict with keys: income, expenses, savings, assets, liabilities.
    Each value is a list aligned with projected_months.
    """
    n = len(projected_months)
    income_adj = [0.0] * n
    expense_adj = [0.0] * n

    for s in series_list:
        start_ym = s["start_date"][:7]  # "YYYY-MM"
        sy, sm = _parse_month(start_ym)
        for i, pm in enumerate(projected_months):
            py, pm_n = _parse_month(pm)
            month_idx = (py - sy) * 12 + (pm_n - sm)
            if 0 <= month_idx < s["months"]:
                if s["type"] == "income":
                    income_adj[i] += s["monthly_amount"]
                else:
                    expense_adj[i] += s["monthly_amount"]

    savings_adj = [income_adj[i] - expense_adj[i] for i in range(n)]

    # Cumulative asset adjustment = cumulative savings adjustment
    assets_adj = []
    cum = 0.0
    for i in range(n):
        cum += savings_adj[i]
        assets_adj.append(round(cum, 4))

    # Cumulative liability adjustment = cumulative expense series only
    liabilities_adj = []
    cum = 0.0
    for i in range(n):
        cum += expense_adj[i]
        liabilities_adj.append(round(cum, 4))

    return {
        "income": income_adj,
        "expenses": expense_adj,
        "savings": savings_adj,
        "assets": assets_adj,
        "liabilities": liabilities_adj,
    }


# ── Series CRUD ───────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "start_date": row["start_date"],
        "months": row["months"],
        "monthly_amount": row["monthly_amount"],
        "created_at": str(row["created_at"]),
    }


def list_series(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM projection_series ORDER BY start_date, name"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_series(conn, series_id: int) -> dict:
    row = require_row(
        conn,
        "SELECT * FROM projection_series WHERE id = ?",
        (series_id,),
        "Series not found",
        NotFoundError,
    )
    return _row_to_dict(row)


def create_series(conn, data: ProjectionSeriesIn) -> dict:
    cur = conn.execute(
        """INSERT INTO projection_series (name, type, start_date, months, monthly_amount)
           VALUES (?, ?, ?, ?, ?)""",
        (data.name, data.type, data.start_date, data.months, data.monthly_amount),
    )
    conn.commit()
    return get_series(conn, cur.lastrowid)


def update_series(conn, series_id: int, data: ProjectionSeriesUpdate) -> dict:
    row = require_row(
        conn,
        "SELECT * FROM projection_series WHERE id = ?",
        (series_id,),
        "Series not found",
        NotFoundError,
    )
    updates = data.model_dump(exclude_none=True)
    if not updates:
        return _row_to_dict(row)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [series_id]
    conn.execute(
        f"UPDATE projection_series SET {set_clause} WHERE id = ?", values
    )
    conn.commit()
    return get_series(conn, series_id)


def delete_series(conn, series_id: int) -> None:
    require_row(
        conn,
        "SELECT id FROM projection_series WHERE id = ?",
        (series_id,),
        "Series not found",
        NotFoundError,
    )
    conn.execute("DELETE FROM projection_series WHERE id = ?", (series_id,))
    conn.commit()


# ── Main projection function ──────────────────────────────────────────────────

def get_projections(conn, horizon: int, history_months: int) -> dict:
    """
    Compute financial projections using linear regression on historical data
    plus user-defined income/expense series.

    Returns a dict with: historical, regression, projected_months,
    baseline_projection, series_adjustment, current_balances.
    """
    today = date.today()
    today_ym = _month_str(today.year, today.month)

    # History window: from (today - history_months) to today
    hist_y, hist_m = _add_months(today.year, today.month, -history_months)
    history_start = _month_str(hist_y, hist_m) + "-01 00:00:00"
    history_end = today_ym + "-31 23:59:59"

    # ── Historical cashflow ──
    income_map, expense_map = _get_monthly_cashflow(conn, history_start, history_end)

    # Build dense arrays covering all months in the window
    all_hist_months = _months_range(_month_str(hist_y, hist_m), history_months + 1)

    # Sparse arrays: None for months with no transactions for that metric.
    # Using separate maps ensures a month with only expenses shows None for
    # income (and vice-versa), so _fill_by_regression extrapolates correctly.
    sparse_income   = [income_map.get(m)  for m in all_hist_months]
    sparse_expenses = [expense_map.get(m) for m in all_hist_months]

    # Fill missing months by regression on known data points (or copy if only 1 known)
    hist_income   = _fill_by_regression(sparse_income)
    hist_expenses = _fill_by_regression(sparse_expenses)
    hist_savings  = [hist_income[i] - hist_expenses[i] for i in range(len(all_hist_months))]

    # ── Historical asset/liability balances ──
    asset_bal_map = _get_monthly_balances(conn, history_start, history_end, type_id=1)
    liab_bal_map  = _get_monthly_balances(conn, history_start, history_end, type_id=2)
    hist_assets_sparse      = [asset_bal_map.get(m, None) for m in all_hist_months]
    hist_liabilities_sparse = [liab_bal_map.get(m,  None) for m in all_hist_months]

    hist_assets_filled      = _fill_by_regression(hist_assets_sparse)
    hist_liabilities_filled = _fill_by_regression(hist_liabilities_sparse)

    # ── Current balances ──
    asset_accounts = conn.execute(
        "SELECT id, type_id, initial_balance FROM accounts WHERE type_id = 1"
    ).fetchall()
    liab_accounts = conn.execute(
        "SELECT id, type_id, initial_balance FROM accounts WHERE type_id = 2"
    ).fetchall()
    current_assets = sum(
        compute_balance(conn, a["id"], a["type_id"], a["initial_balance"])
        for a in asset_accounts
    )
    current_liabilities = sum(
        compute_balance(conn, a["id"], a["type_id"], a["initial_balance"])
        for a in liab_accounts
    )

    # ── Regressions ──
    reg_income = _linear_regression(hist_income)
    reg_expenses = _linear_regression(hist_expenses)
    reg_savings = _linear_regression(hist_savings)
    reg_assets = _linear_regression(hist_assets_filled)
    reg_liabilities = _linear_regression(hist_liabilities_filled)

    n_hist = len(all_hist_months)

    # ── Projected months ──
    proj_y, proj_m = _add_months(today.year, today.month, 1)
    projected_months = _months_range(_month_str(proj_y, proj_m), horizon)

    # ── Baseline projections ──
    def _project(slope, intercept, x_start, count):
        return [max(0.0, round(intercept + slope * (x_start + i), 4)) for i in range(count)]

    baseline_income = _project(reg_income[0], reg_income[1], n_hist, horizon)
    baseline_expenses = _project(reg_expenses[0], reg_expenses[1], n_hist, horizon)
    baseline_savings = _project(reg_savings[0], reg_savings[1], n_hist, horizon)

    # Assets: current balance + cumulative projected savings
    baseline_assets = []
    cum_savings = 0.0
    for i in range(horizon):
        cum_savings += baseline_savings[i]
        baseline_assets.append(round(max(0.0, current_assets + cum_savings), 4))

    # Liabilities: use regression trend from current balance
    baseline_liabilities = []
    for i in range(horizon):
        val = round(max(0.0, reg_liabilities[1] + reg_liabilities[0] * (n_hist + i)), 4)
        baseline_liabilities.append(val)

    # ── Series adjustments ──
    series_list = list_series(conn)
    adj = _compute_series_adjustments(series_list, projected_months)

    # ── Build historical output (only months with real data for scatter points) ──
    return {
        "historical": {
            "income": [
                {"month": all_hist_months[i], "value": round(float(sparse_income[i]), 4)}
                for i in range(len(all_hist_months)) if sparse_income[i] is not None
            ],
            "expenses": [
                {"month": all_hist_months[i], "value": round(float(sparse_expenses[i]), 4)}
                for i in range(len(all_hist_months)) if sparse_expenses[i] is not None
            ],
            "savings": [
                {"month": all_hist_months[i],
                 "value": round(float(sparse_income[i]) - float(sparse_expenses[i]), 4)}
                for i in range(len(all_hist_months))
                if sparse_income[i] is not None and sparse_expenses[i] is not None
            ],
            "assets": [
                {"month": all_hist_months[i], "value": hist_assets_filled[i]}
                for i in range(len(all_hist_months))
                if hist_assets_sparse[i] is not None
            ],
            "liabilities": [
                {"month": all_hist_months[i], "value": hist_liabilities_filled[i]}
                for i in range(len(all_hist_months))
                if hist_liabilities_sparse[i] is not None
            ],
        },
        "regression": {
            "income":      {"slope": reg_income[0],      "intercept": reg_income[1]},
            "expenses":    {"slope": reg_expenses[0],    "intercept": reg_expenses[1]},
            "savings":     {"slope": reg_savings[0],     "intercept": reg_savings[1]},
            "assets":      {"slope": reg_assets[0],      "intercept": reg_assets[1]},
            "liabilities": {"slope": reg_liabilities[0], "intercept": reg_liabilities[1]},
        },
        "projected_months": projected_months,
        "baseline_projection": {
            "income":      baseline_income,
            "expenses":    baseline_expenses,
            "savings":     baseline_savings,
            "assets":      baseline_assets,
            "liabilities": baseline_liabilities,
        },
        "series_adjustment": adj,
        "current_balances": {
            "total_assets":      round(current_assets, 4),
            "total_liabilities": round(current_liabilities, 4),
        },
        "historical_months": all_hist_months,
    }
