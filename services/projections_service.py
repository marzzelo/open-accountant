"""Projections service: series CRUD + linear regression forecasting."""

from datetime import date
from typing import Optional

from database import (
    ci_order_sql,
    compute_balance,
    compute_filtered_balance,
    month_bucket_sql,
)
from models import ProjectionSeriesIn, ProjectionSeriesUpdate

from services.errors import NotFoundError
from services.helpers import (
    end_of_month_datetime,
    normalize_account_properties,
    require_row,
    serialize_temporal_value,
)


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


def _series_start_month(start_date) -> str:
    serialized = serialize_temporal_value(start_date)
    return str(serialized)[:7]


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


def _sparse_linear_regression(sparse: list) -> tuple[float, float]:
    """OLS on non-None entries using their actual indices. Returns (slope, intercept).

    Unlike running _linear_regression on a filled array, this avoids the distortion
    caused by _fill_by_regression clamping predicted negatives to 0 before re-fitting.
    The returned line is guaranteed to pass through the known data points when n=2.
    """
    known = [(i, float(v)) for i, v in enumerate(sparse) if v is not None]
    n = len(known)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, known[0][1]
    xs = [p[0] for p in known]
    ys = [p[1] for p in known]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
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

    income_map = {r["month"]: float(r["value"]) for r in income_rows}
    expense_map = {r["month"]: float(r["value"]) for r in expense_rows}
    return income_map, expense_map


def _get_monthly_balances(
    conn, from_date: str, to_date: str, type_id: int
) -> dict[str, float]:
    """
    Returns {YYYY-MM: balance} for accounts of the given type_id,
    computing cumulative balance up to the end of each month.
    """
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
    months = [r["month"] for r in months_rows]

    result: dict[str, float] = {}
    for month in months:
        month_end = end_of_month_datetime(month)
        total = 0.0
        for acc in asset_accounts:
            bal = compute_filtered_balance(
                conn,
                acc["id"],
                acc["type_id"],
                acc["initial_balance"],
                from_date,
                month_end,
            )
            total += bal
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


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if abs(float(denominator or 0)) < 0.0000001:
        return None
    return numerator / denominator


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None else None


# ── Investment helpers ─────────────────────────────────────────────────────────

_INVESTMENT_SUBTYPE_ID = 3  # Investments (Asset)
_DIVIDEND_SUBTYPE_ID = 10  # Dividends (Income)

_INVESTMENT_NAME_HINTS = (
    "investment",
    "investments",
    "brokerage",
    "portfolio",
    "etf",
    "mutual fund",
    "stock",
    "trading",
)
_DIVIDEND_NAME_HINTS = (
    "dividend",
    "dividends",
    "dividendo",
    "dividendos",
)


def _identify_investment_accounts(conn) -> list[dict]:
    """Return asset accounts classified as investments (subtype_id=3 or name hints)."""
    rows = conn.execute(
        """SELECT a.id, a.name, a.type_id, a.initial_balance, a.subtype_id,
                  COALESCE(s.name, '') AS subtype_name
           FROM accounts a
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           WHERE a.type_id = 1"""
    ).fetchall()
    result = []
    for r in rows:
        if r["subtype_id"] == _INVESTMENT_SUBTYPE_ID:
            result.append(dict(r))
            continue
        text = f"{r['name']} {r['subtype_name']}".lower()
        if any(h in text for h in _INVESTMENT_NAME_HINTS):
            result.append(dict(r))
    return result


def _identify_dividend_accounts(conn) -> list[dict]:
    """Return income accounts classified as dividends (subtype_id=10 or name hints)."""
    rows = conn.execute(
        """SELECT a.id, a.name, a.type_id, a.initial_balance, a.subtype_id,
                  COALESCE(s.name, '') AS subtype_name
           FROM accounts a
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           WHERE a.type_id = 3"""
    ).fetchall()
    result = []
    for r in rows:
        if r["subtype_id"] == _DIVIDEND_SUBTYPE_ID:
            result.append(dict(r))
            continue
        text = f"{r['name']} {r['subtype_name']}".lower()
        if any(h in text for h in _DIVIDEND_NAME_HINTS):
            result.append(dict(r))
    return result


def _get_monthly_investment_balances(
    conn,
    investment_account_ids: list[int],
    from_date: str,
    to_date: str,
) -> dict[str, float]:
    """Return {YYYY-MM: total_balance} for the given investment accounts."""
    if not investment_account_ids:
        return {}

    accounts = conn.execute(
        f"""SELECT id, type_id, initial_balance FROM accounts
            WHERE id IN ({','.join('?' for _ in investment_account_ids)})""",
        tuple(investment_account_ids),
    ).fetchall()

    month_expr = month_bucket_sql(conn, "date")
    months_rows = conn.execute(
        f"""SELECT DISTINCT {month_expr} AS month FROM transactions
           WHERE date BETWEEN ? AND ? ORDER BY month""",
        (from_date, to_date),
    ).fetchall()
    months = [r["month"] for r in months_rows]

    result: dict[str, float] = {}
    for month in months:
        month_end = end_of_month_datetime(month)
        total = 0.0
        for acc in accounts:
            bal = compute_filtered_balance(
                conn,
                acc["id"],
                acc["type_id"],
                acc["initial_balance"],
                from_date,
                month_end,
            )
            total += bal
        result[month] = round(total, 4)
    return result


def _get_monthly_dividend_income(
    conn,
    dividend_account_ids: list[int],
    from_date: str,
    to_date: str,
) -> dict[str, float]:
    """Return {YYYY-MM: total_dividend_income} from dividend accounts.

    Dividend income = credit_amount - debit_amount on dividend accounts (type_id=3).
    """
    if not dividend_account_ids:
        return {}

    placeholders = ",".join("?" for _ in dividend_account_ids)
    month_expr = month_bucket_sql(conn, "t.date")
    rows = conn.execute(
        f"""WITH div_legs AS (
            SELECT {month_expr} AS month,
                   t.amount AS credit_amount,
                   0        AS debit_amount
            FROM transactions t
            WHERE t.credit_account IN ({placeholders})
              AND t.date BETWEEN ? AND ?

            UNION ALL

            SELECT {month_expr} AS month,
                   0        AS credit_amount,
                   t.amount AS debit_amount
            FROM transactions t
            WHERE t.debit_account IN ({placeholders})
              AND t.date BETWEEN ? AND ?
        )
        SELECT month, SUM(credit_amount - debit_amount) AS value
        FROM div_legs
        GROUP BY month
        HAVING SUM(credit_amount - debit_amount) > 0
        ORDER BY month""",
        (
            *dividend_account_ids,
            from_date,
            to_date,
            *dividend_account_ids,
            from_date,
            to_date,
        ),
    ).fetchall()
    return {r["month"]: float(r["value"]) for r in rows}


def _get_monthly_investment_contributions(
    conn,
    investment_account_ids: list[int],
    dividend_account_ids: list[int],
    from_date: str,
    to_date: str,
) -> dict[str, float]:
    """Return {YYYY-MM: net_manual_contribution} into investment accounts.

    Net manual contribution = money flowing into investment accounts from
    non-investment, non-dividend accounts minus money flowing out to them.
    Internal transfers between investment accounts are excluded.
    Dividend-sourced inflows are excluded.
    Equity (Capital) counterparties are excluded: initial balances booked
    against Capital represent the accumulated starting state, not individual
    monthly contributions.
    """
    if not investment_account_ids:
        return {}

    inv_set = set(investment_account_ids)
    div_set = set(dividend_account_ids)
    equity_ids = {
        r["id"]
        for r in conn.execute("SELECT id FROM accounts WHERE type_id = 5").fetchall()
    }
    exclude_set = inv_set | div_set | equity_ids

    inv_placeholders = ",".join("?" for _ in investment_account_ids)
    month_expr = month_bucket_sql(conn, "t.date")

    # Inflows: investment account is debited (asset debit-normal → balance increases)
    inflow_rows = conn.execute(
        f"""SELECT {month_expr} AS month,
                   t.credit_account AS counterpart,
                   SUM(t.amount) AS total
            FROM transactions t
            WHERE t.debit_account IN ({inv_placeholders})
              AND t.date BETWEEN ? AND ?
            GROUP BY month, t.credit_account
            ORDER BY month""",
        (*investment_account_ids, from_date, to_date),
    ).fetchall()

    # Outflows: investment account is credited (asset debit-normal → balance decreases)
    outflow_rows = conn.execute(
        f"""SELECT {month_expr} AS month,
                   t.debit_account AS counterpart,
                   SUM(t.amount) AS total
            FROM transactions t
            WHERE t.credit_account IN ({inv_placeholders})
              AND t.date BETWEEN ? AND ?
            GROUP BY month, t.debit_account
            ORDER BY month""",
        (*investment_account_ids, from_date, to_date),
    ).fetchall()

    result: dict[str, float] = {}
    for r in inflow_rows:
        if r["counterpart"] in exclude_set:
            continue
        result[r["month"]] = result.get(r["month"], 0.0) + float(r["total"])
    for r in outflow_rows:
        if r["counterpart"] in exclude_set:
            continue
        result[r["month"]] = result.get(r["month"], 0.0) - float(r["total"])

    return {m: round(v, 4) for m, v in result.items()}


# ── Robust statistical estimation ─────────────────────────────────────────────


def _iqr_filter(values: list[float], k: float = 1.5) -> tuple[list[float], int]:
    """Apply IQR × k outlier filtering. Returns (filtered_values, excluded_count)."""
    if len(values) < 4:
        return list(values), 0
    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    filtered = [v for v in values if lower <= v <= upper]
    return filtered, len(values) - len(filtered)


def _aggregate(values: list[float], stat: str = "mean") -> float:
    """Compute mean or median of a list of floats."""
    if not values:
        return 0.0
    if stat == "median":
        s = sorted(values)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return sum(values) / len(values)


def _estimate_investment_model(
    all_months: list[str],
    inv_bal_map: dict[str, float],
    div_map: dict[str, float],
    contrib_map: dict[str, float],
    asset_bal_map: dict[str, float],
    *,
    stat: str = "mean",
    exclude_outliers: bool = True,
    outlier_k: float = 1.5,
) -> dict:
    """Estimate monthly yield rate and contribution rate from trailing data.

    contribution_rate is the ratio contrib / total_assets per period.
    Returns dict with: yield_rate, contribution_rate, sample_count, yield_excluded,
    contrib_excluded, warnings.
    """
    yields: list[float] = []
    contribution_rates: list[float] = []
    warnings: list[str] = []

    for i, m in enumerate(all_months):
        contrib_val = contrib_map.get(m)
        asset_val = asset_bal_map.get(m)
        if contrib_val is not None and asset_val is not None and asset_val > 0:
            contribution_rates.append(contrib_val / asset_val)

        div_val = div_map.get(m)
        if div_val is None or div_val <= 0:
            continue
        # Compute base as average of opening and closing balance for this month
        opening = None
        if i > 0:
            opening = inv_bal_map.get(all_months[i - 1])
        closing = inv_bal_map.get(m)
        if closing is not None and opening is not None:
            base = (opening + closing) / 2
        elif closing is not None:
            base = closing
        elif opening is not None:
            base = opening
        else:
            continue
        if base > 0:
            yields.append(div_val / base)

    yield_excluded = 0
    contrib_excluded = 0
    if exclude_outliers:
        if yields:
            yields, yield_excluded = _iqr_filter(yields, outlier_k)
        if contribution_rates:
            contribution_rates, contrib_excluded = _iqr_filter(
                contribution_rates, outlier_k
            )

    yield_rate = _aggregate(yields, stat)
    contribution_rate = _aggregate(contribution_rates, stat)

    # Warn if median zeroes out non-empty yield series
    if stat == "median" and yield_rate == 0 and len(yields) > 0:
        warnings.append("median_yield_zero")
    if stat == "median" and contribution_rate == 0 and len(contribution_rates) > 0:
        warnings.append("median_contribution_zero")

    return {
        "yield_rate": round(yield_rate, 8),
        "contribution_rate": round(contribution_rate, 8),
        "sample_count": len(yields),
        "contrib_sample_count": len(contribution_rates),
        "yield_excluded": yield_excluded,
        "contrib_excluded": contrib_excluded,
        "warnings": warnings,
    }


def _project_investments(
    current_investment_balance: float,
    current_non_inv_assets: float,
    yield_rate: float,
    contribution_rate: float,
    baseline_savings: list[float],
    horizon: int,
) -> tuple[list[float], list[float], list[dict]]:
    """Project investment and non-investment assets jointly.

    contribution_rate is the fraction of total assets contributed to
    investments each period.  Returns (investments, non_inv_assets, detail).
    """
    investments: list[float] = []
    non_inv_assets: list[float] = []
    detail: list[dict] = []
    inv_bal = current_investment_balance
    non_inv_bal = current_non_inv_assets
    for i in range(horizon):
        total_assets = non_inv_bal + inv_bal
        contribution = contribution_rate * total_assets
        interest = inv_bal * yield_rate
        inv_bal = max(0.0, inv_bal + interest + contribution)
        non_inv_savings = baseline_savings[i] - contribution
        non_inv_bal = max(0.0, non_inv_bal + non_inv_savings)
        investments.append(round(inv_bal, 4))
        non_inv_assets.append(round(non_inv_bal, 4))
        detail.append(
            {
                "interest": round(interest, 4),
                "contribution": round(contribution, 4),
                "total_assets": round(total_assets, 4),
            }
        )
    return investments, non_inv_assets, detail


# ── Series adjustments ────────────────────────────────────────────────────────


def _compute_series_adjustments(
    series_list: list[dict], projected_months: list[str]
) -> dict:
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
        start_ym = _series_start_month(s["start_date"])
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
        "start_date": str(serialize_temporal_value(row["start_date"])),
        "months": row["months"],
        "monthly_amount": row["monthly_amount"],
        "created_at": str(serialize_temporal_value(row["created_at"])),
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
    row = conn.execute(
        """INSERT INTO projection_series (name, type, start_date, months, monthly_amount)
           VALUES (?, ?, ?, ?, ?)
           RETURNING id""",
        (data.name, data.type, data.start_date, data.months, data.monthly_amount),
    )
    conn.commit()
    return get_series(conn, row.fetchone()["id"])


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
    conn.execute(f"UPDATE projection_series SET {set_clause} WHERE id = ?", values)
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


def get_projections(
    conn,
    horizon: int,
    history_months: int,
    *,
    investment_lookback_months: int | None = None,
    investment_stat: str = "mean",
    investment_exclude_outliers: bool = True,
    investment_outlier_k: float = 1.5,
) -> dict:
    """
    Compute financial projections using linear regression on historical data
    plus user-defined income/expense series.

    Returns a dict with: historical, regression, projected_months,
    baseline_projection, series_adjustment, current_balances, investment_model.
    """
    today = date.today()
    today_ym = _month_str(today.year, today.month)

    # History window: from (today - history_months) to today
    hist_y, hist_m = _add_months(today.year, today.month, -history_months)
    history_start = _month_str(hist_y, hist_m) + "-01 00:00:00"
    history_end = end_of_month_datetime(today_ym)

    # ── Historical cashflow ──
    income_map, expense_map = _get_monthly_cashflow(conn, history_start, history_end)

    # Build dense arrays covering all months in the window
    all_hist_months = _months_range(_month_str(hist_y, hist_m), history_months + 1)

    # Sparse arrays: None for months with no transactions for that metric.
    # Using separate maps ensures a month with only expenses shows None for
    # income (and vice-versa), so _fill_by_regression extrapolates correctly.
    sparse_income = [income_map.get(m) for m in all_hist_months]
    sparse_expenses = [expense_map.get(m) for m in all_hist_months]

    # Fill missing months by regression on known data points (or copy if only 1 known)
    hist_income = _fill_by_regression(sparse_income)
    hist_expenses = _fill_by_regression(sparse_expenses)
    hist_savings = [
        hist_income[i] - hist_expenses[i] for i in range(len(all_hist_months))
    ]

    # ── Historical asset/liability balances ──
    asset_bal_map = _get_monthly_balances(conn, history_start, history_end, type_id=1)
    liab_bal_map = _get_monthly_balances(conn, history_start, history_end, type_id=2)
    hist_assets_sparse = [asset_bal_map.get(m, None) for m in all_hist_months]
    hist_liabilities_sparse = [liab_bal_map.get(m, None) for m in all_hist_months]

    hist_assets_filled = _fill_by_regression(hist_assets_sparse)
    hist_liabilities_filled = _fill_by_regression(hist_liabilities_sparse)

    # ── Current balances ──
    asset_accounts = _financial_rows(conn, 1)
    liab_accounts = _financial_rows(conn, 2)
    expense_accounts = _financial_rows(conn, 4)
    current_assets = sum(
        compute_balance(conn, a["id"], a["type_id"], a["initial_balance"])
        for a in asset_accounts
    )
    current_liabilities = sum(
        compute_balance(conn, a["id"], a["type_id"], a["initial_balance"])
        for a in liab_accounts
    )

    current_assets_only = 0.0
    quick_assets = 0.0
    current_liabilities_only = 0.0
    for account in asset_accounts:
        balance = compute_balance(
            conn, account["id"], account["type_id"], account["initial_balance"]
        )
        props = normalize_account_properties(
            account["properties"],
            type_id=1,
            name=account["name"],
            subtype_name=account["subtype_name"],
        )
        if balance > 0 and props.get("liquidity_profile") in {"quick", "current"}:
            current_assets_only += balance
        if balance > 0 and props.get("liquidity_profile") == "quick":
            quick_assets += balance

    for account in liab_accounts:
        balance = compute_balance(
            conn, account["id"], account["type_id"], account["initial_balance"]
        )
        props = normalize_account_properties(
            account["properties"],
            type_id=2,
            name=account["name"],
            subtype_name=account["subtype_name"],
        )
        if balance > 0 and props.get("liability_term") == "current":
            current_liabilities_only += balance

    essential_expense_total = 0.0
    for account in expense_accounts:
        expense_total = compute_filtered_balance(
            conn,
            account["id"],
            account["type_id"],
            account["initial_balance"],
            history_start,
            history_end,
        )
        props = normalize_account_properties(
            account["properties"],
            type_id=4,
            name=account["name"],
            subtype_name=account["subtype_name"],
        )
        if expense_total > 0 and props.get("expense_profile") == "essential":
            essential_expense_total += expense_total

    # ── Investment data collection ──
    inv_accounts = _identify_investment_accounts(conn)
    div_accounts = _identify_dividend_accounts(conn)
    inv_ids = [a["id"] for a in inv_accounts]
    div_ids = [a["id"] for a in div_accounts]

    current_investment_balance = 0.0
    for a in inv_accounts:
        current_investment_balance += compute_balance(
            conn, a["id"], a["type_id"], a["initial_balance"]
        )
    current_non_inv_assets = current_assets - current_investment_balance

    inv_lookback = investment_lookback_months or history_months
    inv_y, inv_m = _add_months(today.year, today.month, -inv_lookback)
    inv_start = _month_str(inv_y, inv_m) + "-01 00:00:00"
    inv_months = _months_range(_month_str(inv_y, inv_m), inv_lookback + 1)

    inv_bal_map = _get_monthly_investment_balances(
        conn, inv_ids, inv_start, history_end
    )
    div_map = _get_monthly_dividend_income(conn, div_ids, inv_start, history_end)
    contrib_map = _get_monthly_investment_contributions(
        conn, inv_ids, div_ids, inv_start, history_end
    )

    # Total asset balances and income for the investment lookback period
    inv_total_asset_map = _get_monthly_balances(conn, inv_start, history_end, type_id=1)
    inv_income_map_full, _ = _get_monthly_cashflow(conn, inv_start, history_end)

    # Historical investment balance sparse aligned with all_hist_months
    hist_inv_sparse = [inv_bal_map.get(m, None) for m in all_hist_months]

    investment_model = _estimate_investment_model(
        inv_months,
        inv_bal_map,
        div_map,
        contrib_map,
        inv_total_asset_map,
        stat=investment_stat,
        exclude_outliers=investment_exclude_outliers,
        outlier_k=investment_outlier_k,
    )

    has_investments = len(inv_ids) > 0 and current_investment_balance > 0

    # Compute per-month dividend totals aligned to all_hist_months for
    # excluding from general income (avoid double-counting).
    div_income_aligned = {m: div_map.get(m, 0.0) for m in all_hist_months}

    # ── Regressions ──
    # Use sparse regression directly on known data points to avoid distortion:
    # _fill_by_regression clamps negative predictions to 0, so running
    # _linear_regression on the filled array produces a line that doesn't pass
    # through the original historical scatter points.
    sparse_savings: list[float | None] = []
    for i in range(len(all_hist_months)):
        si, se = sparse_income[i], sparse_expenses[i]
        sparse_savings.append(si - se if si is not None and se is not None else None)
    reg_income = _sparse_linear_regression(sparse_income)
    reg_expenses = _sparse_linear_regression(sparse_expenses)
    reg_savings = _sparse_linear_regression(sparse_savings)
    reg_assets = _linear_regression(hist_assets_filled)
    reg_liabilities = _linear_regression(hist_liabilities_filled)

    n_hist = len(all_hist_months)

    # ── Projected months ──
    proj_y, proj_m = _add_months(today.year, today.month, 1)
    projected_months = _months_range(_month_str(proj_y, proj_m), horizon)

    # ── Baseline projections ──
    def _project(slope, intercept, x_start, count):
        return [
            max(0.0, round(intercept + slope * (x_start + i), 4)) for i in range(count)
        ]

    baseline_income = _project(reg_income[0], reg_income[1], n_hist, horizon)
    baseline_expenses = _project(reg_expenses[0], reg_expenses[1], n_hist, horizon)
    baseline_savings = _project(reg_savings[0], reg_savings[1], n_hist, horizon)

    # ── Investment projection (joint iteration) ──
    baseline_investments: list[float] = []
    baseline_non_inv_assets: list[float] = []
    _proj_detail: list[dict] = []
    if has_investments:
        baseline_investments, baseline_non_inv_assets, _proj_detail = (
            _project_investments(
                current_investment_balance,
                current_non_inv_assets,
                investment_model["yield_rate"],
                investment_model["contribution_rate"],
                baseline_savings,
                horizon,
            )
        )
    else:
        baseline_investments = [round(current_investment_balance, 4)] * horizon
        cum_non_inv_savings = 0.0
        for i in range(horizon):
            cum_non_inv_savings += baseline_savings[i]
            val = max(0.0, current_non_inv_assets + cum_non_inv_savings)
            baseline_non_inv_assets.append(round(val, 4))
            _proj_detail.append(
                {
                    "interest": 0.0,
                    "contribution": 0.0,
                    "total_assets": round(val + current_investment_balance, 4),
                }
            )

    # Total assets = non-investment assets + projected investments
    baseline_assets = [
        round(baseline_non_inv_assets[i] + baseline_investments[i], 4)
        for i in range(horizon)
    ]

    # Liabilities: use regression trend from current balance
    baseline_liabilities = []
    for i in range(horizon):
        val = round(max(0.0, reg_liabilities[1] + reg_liabilities[0] * (n_hist + i)), 4)
        baseline_liabilities.append(val)

    # ── Series adjustments ──
    series_list = list_series(conn)
    adj = _compute_series_adjustments(series_list, projected_months)

    observed_hist_months = max(
        len([m for m in all_hist_months if m in income_map or m in expense_map]), 1
    )
    essential_share = (
        (essential_expense_total / sum(expense_map.values()))
        if sum(expense_map.values()) > 0
        else 0.0
    )
    baseline_net_worth = [
        round(baseline_assets[i] - baseline_liabilities[i], 4) for i in range(horizon)
    ]
    scenario_assets = [
        round(baseline_assets[i] + adj["assets"][i], 4) for i in range(horizon)
    ]
    scenario_liabilities = [
        round(baseline_liabilities[i] + adj["liabilities"][i], 4)
        for i in range(horizon)
    ]
    scenario_net_worth = [
        round(scenario_assets[i] - scenario_liabilities[i], 4) for i in range(horizon)
    ]
    current_liability_share = (
        current_liabilities_only / current_liabilities
        if current_liabilities > 0
        else 0.0
    )
    baseline_current_liabilities = [
        round(baseline_liabilities[i] * current_liability_share, 4)
        for i in range(horizon)
    ]
    scenario_current_liabilities = [
        round(scenario_liabilities[i] * current_liability_share, 4)
        for i in range(horizon)
    ]
    baseline_current_assets = [
        round(
            current_assets_only
            + max(0.0, baseline_non_inv_assets[i] - current_non_inv_assets),
            4,
        )
        for i in range(horizon)
    ]
    scenario_current_assets = [
        round(
            current_assets_only
            + max(0.0, baseline_non_inv_assets[i] - current_non_inv_assets)
            + adj["assets"][i],
            4,
        )
        for i in range(horizon)
    ]
    baseline_quick_assets = [
        round(
            quick_assets
            + max(0.0, baseline_non_inv_assets[i] - current_non_inv_assets),
            4,
        )
        for i in range(horizon)
    ]
    scenario_quick_assets = [
        round(
            quick_assets
            + max(0.0, baseline_non_inv_assets[i] - current_non_inv_assets)
            + adj["assets"][i],
            4,
        )
        for i in range(horizon)
    ]
    baseline_essential_expense = [
        round(max(0.0, baseline_expenses[i] * essential_share), 4)
        for i in range(horizon)
    ]
    scenario_essential_expense = [
        round(
            max(0.0, (baseline_expenses[i] + adj["expenses"][i]) * essential_share), 4
        )
        for i in range(horizon)
    ]

    def _health_point(
        month_index: int,
        month: str,
        *,
        net_worth: float,
        current_assets_val: float,
        quick_assets_val: float,
        current_liabilities_val: float,
        essential_expense_val: Optional[float],
    ) -> dict:
        current_ratio = _safe_ratio(current_assets_val, current_liabilities_val)
        quick_ratio = _safe_ratio(quick_assets_val, current_liabilities_val)
        runway_months = (
            _safe_ratio(quick_assets_val, essential_expense_val)
            if essential_expense_val
            else None
        )
        return {
            "month": month,
            "net_worth": round(net_worth, 4),
            "current_assets": round(current_assets_val, 4),
            "quick_assets": round(quick_assets_val, 4),
            "current_liabilities": round(current_liabilities_val, 4),
            "current_ratio": _round_or_none(current_ratio),
            "quick_ratio": _round_or_none(quick_ratio),
            "monthly_essential_expense": _round_or_none(essential_expense_val),
            "runway_months": _round_or_none(runway_months),
        }

    current_monthly_essential_expense = (
        essential_expense_total / observed_hist_months
        if essential_expense_total > 0
        else None
    )
    current_health = _health_point(
        -1,
        today_ym,
        net_worth=current_assets - current_liabilities,
        current_assets_val=current_assets_only,
        quick_assets_val=quick_assets,
        current_liabilities_val=current_liabilities_only,
        essential_expense_val=current_monthly_essential_expense,
    )
    baseline_end = _health_point(
        horizon - 1,
        projected_months[-1] if projected_months else today_ym,
        net_worth=(
            baseline_net_worth[-1]
            if baseline_net_worth
            else current_health["net_worth"]
        ),
        current_assets_val=(
            baseline_current_assets[-1]
            if baseline_current_assets
            else current_assets_only
        ),
        quick_assets_val=(
            baseline_quick_assets[-1] if baseline_quick_assets else quick_assets
        ),
        current_liabilities_val=(
            baseline_current_liabilities[-1]
            if baseline_current_liabilities
            else current_liabilities_only
        ),
        essential_expense_val=(
            baseline_essential_expense[-1]
            if baseline_essential_expense
            else current_monthly_essential_expense
        ),
    )
    scenario_end = _health_point(
        horizon - 1,
        projected_months[-1] if projected_months else today_ym,
        net_worth=(
            scenario_net_worth[-1]
            if scenario_net_worth
            else current_health["net_worth"]
        ),
        current_assets_val=(
            scenario_current_assets[-1]
            if scenario_current_assets
            else current_assets_only
        ),
        quick_assets_val=(
            scenario_quick_assets[-1] if scenario_quick_assets else quick_assets
        ),
        current_liabilities_val=(
            scenario_current_liabilities[-1]
            if scenario_current_liabilities
            else current_liabilities_only
        ),
        essential_expense_val=(
            scenario_essential_expense[-1]
            if scenario_essential_expense
            else current_monthly_essential_expense
        ),
    )
    projected_health = {
        "current": current_health,
        "baseline_end": baseline_end,
        "scenario_end": scenario_end,
        "delta_end": {
            "month": projected_months[-1] if projected_months else today_ym,
            "net_worth": round(
                scenario_end["net_worth"] - baseline_end["net_worth"], 4
            ),
            "runway_months": _round_or_none(
                (scenario_end["runway_months"] or 0)
                - (baseline_end["runway_months"] or 0)
                if scenario_end["runway_months"] is not None
                and baseline_end["runway_months"] is not None
                else None
            ),
            "current_ratio": _round_or_none(
                (scenario_end["current_ratio"] or 0)
                - (baseline_end["current_ratio"] or 0)
                if scenario_end["current_ratio"] is not None
                and baseline_end["current_ratio"] is not None
                else None
            ),
            "quick_ratio": _round_or_none(
                (scenario_end["quick_ratio"] or 0) - (baseline_end["quick_ratio"] or 0)
                if scenario_end["quick_ratio"] is not None
                and baseline_end["quick_ratio"] is not None
                else None
            ),
        },
        "assumptions": {
            "essential_expense_share": round(essential_share, 4),
            "current_liability_share": round(current_liability_share, 4),
        },
    }

    # ── Build investment detail table (historical + projected) ──
    _investment_detail: list[dict] = []
    for m in inv_months:
        inv_balance = inv_bal_map.get(m)
        div_income = div_map.get(m, 0.0)
        contrib = contrib_map.get(m, 0.0)
        total_assets_m = inv_total_asset_map.get(m)
        income_m = inv_income_map_full.get(m, 0.0)
        _investment_detail.append(
            {
                "month": m,
                "is_projected": False,
                "investment_balance": (
                    round(inv_balance, 4) if inv_balance is not None else None
                ),
                "interest_earned": round(div_income, 4),
                "manual_contribution": round(contrib, 4),
                "contribution_pct_assets": (
                    round(contrib / total_assets_m * 100, 4)
                    if total_assets_m and total_assets_m > 0
                    else None
                ),
                "total_income": round(income_m, 4),
                "interest_pct_income": (
                    round(div_income / income_m * 100, 4)
                    if income_m and income_m > 0
                    else None
                ),
            }
        )
    for i, m in enumerate(projected_months):
        detail_i = _proj_detail[i] if i < len(_proj_detail) else {}
        proj_income_i = baseline_income[i] if i < len(baseline_income) else 0
        interest_i = detail_i.get("interest", 0)
        contrib_i = detail_i.get("contribution", 0)
        total_assets_i = detail_i.get("total_assets", 0)
        _investment_detail.append(
            {
                "month": m,
                "is_projected": True,
                "investment_balance": (
                    baseline_investments[i] if i < len(baseline_investments) else None
                ),
                "interest_earned": round(interest_i, 4),
                "manual_contribution": round(contrib_i, 4),
                "contribution_pct_assets": (
                    round(contrib_i / total_assets_i * 100, 4)
                    if total_assets_i > 0
                    else None
                ),
                "total_income": round(proj_income_i, 4),
                "interest_pct_income": (
                    round(interest_i / proj_income_i * 100, 4)
                    if proj_income_i > 0
                    else None
                ),
            }
        )

    # ── Build historical output (only months with real data for scatter points) ──
    return {
        "historical": {
            "income": [
                {
                    "month": all_hist_months[i],
                    "value": round(float(sparse_income[i]), 4),
                }
                for i in range(len(all_hist_months))
                if sparse_income[i] is not None
            ],
            "expenses": [
                {
                    "month": all_hist_months[i],
                    "value": round(float(sparse_expenses[i]), 4),
                }
                for i in range(len(all_hist_months))
                if sparse_expenses[i] is not None
            ],
            "savings": [
                {
                    "month": all_hist_months[i],
                    "value": round(
                        float(sparse_income[i]) - float(sparse_expenses[i]), 4
                    ),
                }
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
            "investments": [
                {"month": all_hist_months[i], "value": hist_inv_sparse[i]}
                for i in range(len(all_hist_months))
                if hist_inv_sparse[i] is not None
            ],
        },
        "regression": {
            "income": {"slope": reg_income[0], "intercept": reg_income[1]},
            "expenses": {"slope": reg_expenses[0], "intercept": reg_expenses[1]},
            "savings": {"slope": reg_savings[0], "intercept": reg_savings[1]},
            "assets": {"slope": reg_assets[0], "intercept": reg_assets[1]},
            "liabilities": {
                "slope": reg_liabilities[0],
                "intercept": reg_liabilities[1],
            },
        },
        "projected_months": projected_months,
        "baseline_projection": {
            "income": baseline_income,
            "expenses": baseline_expenses,
            "savings": baseline_savings,
            "assets": baseline_assets,
            "liabilities": baseline_liabilities,
            "investments": baseline_investments,
        },
        "series_adjustment": adj,
        "current_balances": {
            "total_assets": round(current_assets, 4),
            "total_liabilities": round(current_liabilities, 4),
            "total_investments": round(current_investment_balance, 4),
        },
        "health": projected_health,
        "historical_months": all_hist_months,
        "investment_model": {
            "enabled": has_investments,
            "yield_rate": investment_model["yield_rate"],
            "contribution_rate": investment_model["contribution_rate"],
            "sample_count": investment_model["sample_count"],
            "contrib_sample_count": investment_model["contrib_sample_count"],
            "yield_excluded": investment_model["yield_excluded"],
            "contrib_excluded": investment_model["contrib_excluded"],
            "warnings": investment_model["warnings"],
            "stat": investment_stat,
            "exclude_outliers": investment_exclude_outliers,
            "outlier_k": investment_outlier_k,
            "lookback_months": inv_lookback,
        },
        "investment_detail": _investment_detail,
    }
