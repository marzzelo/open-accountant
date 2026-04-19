"""Investment-specific projections helpers and statistical estimators."""

from typing import Optional

from database import compute_filtered_balance, month_bucket_sql

from services.helpers import end_of_month_datetime


_INTEREST_PERCENT_DIGITS = 6
_CONTRIBUTION_PERCENT_DIGITS = 4
_PROJECTED_INVESTMENT_DETAIL_DIGITS = 6


def _resolve_investment_projection_inputs(
    current_investment_balance: float,
    investment_model: dict,
    *,
    interest_pct_override: float | None = None,
    contribution_pct_override: float | None = None,
    interest_override: float | None = None,
    contribution_override: float | None = None,
) -> dict:
    interest_reference_base = float(
        investment_model.get("yield_reference_base")
        or current_investment_balance
        or 0.0
    )
    contribution_reference_income = float(
        investment_model.get("contribution_reference_income") or 0.0
    )
    default_interest_percent = round(
        investment_model.get("yield_rate", 0.0) * 100,
        _INTEREST_PERCENT_DIGITS,
    )
    default_contribution_percent = round(
        investment_model.get("contribution_rate", 0.0) * 100,
        _CONTRIBUTION_PERCENT_DIGITS,
    )
    default_interest_amount = round(
        investment_model.get(
            "interest_amount",
            default_interest_percent / 100.0 * interest_reference_base,
        ),
        4,
    )
    default_contribution_amount = round(
        investment_model.get(
            "contribution_amount",
            default_contribution_percent / 100.0 * contribution_reference_income,
        ),
        4,
    )

    if interest_pct_override is not None:
        applied_interest_percent = round(
            float(interest_pct_override), _INTEREST_PERCENT_DIGITS
        )
    elif interest_override is not None and abs(interest_reference_base) > 0.0000001:
        applied_interest_percent = round(
            float(interest_override) / interest_reference_base * 100.0,
            _INTEREST_PERCENT_DIGITS,
        )
    else:
        applied_interest_percent = default_interest_percent

    if (
        contribution_pct_override is not None
        and contribution_reference_income > 0.0000001
    ):
        applied_contribution_percent = round(
            float(contribution_pct_override), _CONTRIBUTION_PERCENT_DIGITS
        )
    elif (
        contribution_override is not None and contribution_reference_income > 0.0000001
    ):
        applied_contribution_percent = round(
            float(contribution_override) / contribution_reference_income * 100.0,
            _CONTRIBUTION_PERCENT_DIGITS,
        )
    else:
        applied_contribution_percent = default_contribution_percent

    applied_yield_rate = applied_interest_percent / 100.0
    applied_contribution_rate = applied_contribution_percent / 100.0
    applied_interest_amount = round(applied_yield_rate * interest_reference_base, 4)
    applied_contribution_amount = round(
        applied_contribution_rate * contribution_reference_income, 4
    )
    return {
        "default_interest_percent": default_interest_percent,
        "default_contribution_percent": default_contribution_percent,
        "default_interest_amount": default_interest_amount,
        "default_contribution_amount": default_contribution_amount,
        "applied_interest_percent": applied_interest_percent,
        "applied_contribution_percent": applied_contribution_percent,
        "applied_interest_amount": round(applied_interest_amount, 4),
        "applied_contribution_amount": round(applied_contribution_amount, 4),
        "applied_yield_rate": round(applied_yield_rate, 8),
        "applied_contribution_rate": round(applied_contribution_rate, 8),
        "interest_reference_base": round(interest_reference_base, 4),
        "contribution_reference_income": round(contribution_reference_income, 4),
        "has_overrides": (
            interest_pct_override is not None
            or contribution_pct_override is not None
            or interest_override is not None
            or contribution_override is not None
        ),
    }


_INVESTMENT_SUBTYPE_ID = 3
_DIVIDEND_SUBTYPE_ID = 10

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
    """Return asset accounts classified as investments."""
    rows = conn.execute(
        """SELECT a.id, a.name, a.type_id, a.initial_balance, a.subtype_id,
                  COALESCE(s.name, '') AS subtype_name
           FROM accounts a
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           WHERE a.type_id = 1"""
    ).fetchall()
    result = []
    for row in rows:
        if row["subtype_id"] == _INVESTMENT_SUBTYPE_ID:
            result.append(dict(row))
            continue
        text = f"{row['name']} {row['subtype_name']}".lower()
        if any(hint in text for hint in _INVESTMENT_NAME_HINTS):
            result.append(dict(row))
    return result


def _identify_dividend_accounts(conn) -> list[dict]:
    """Return income accounts classified as dividends."""
    rows = conn.execute(
        """SELECT a.id, a.name, a.type_id, a.initial_balance, a.subtype_id,
                  COALESCE(s.name, '') AS subtype_name
           FROM accounts a
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           WHERE a.type_id = 3"""
    ).fetchall()
    result = []
    for row in rows:
        if row["subtype_id"] == _DIVIDEND_SUBTYPE_ID:
            result.append(dict(row))
            continue
        text = f"{row['name']} {row['subtype_name']}".lower()
        if any(hint in text for hint in _DIVIDEND_NAME_HINTS):
            result.append(dict(row))
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
    months = [row["month"] for row in months_rows]

    result: dict[str, float] = {}
    for month in months:
        month_end = end_of_month_datetime(month)
        total = 0.0
        for account in accounts:
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


def _get_monthly_dividend_income(
    conn,
    dividend_account_ids: list[int],
    from_date: str,
    to_date: str,
) -> dict[str, float]:
    """Return {YYYY-MM: signed_net_dividend_income} from dividend accounts."""
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
    return {row["month"]: float(row["value"]) for row in rows}


def _get_monthly_investment_contributions(
    conn,
    investment_account_ids: list[int],
    dividend_account_ids: list[int],
    from_date: str,
    to_date: str,
) -> dict[str, float]:
    """Return {YYYY-MM: net_manual_contribution} into investment accounts."""
    if not investment_account_ids:
        return {}

    inv_set = set(investment_account_ids)
    div_set = set(dividend_account_ids)
    equity_ids = {
        row["id"]
        for row in conn.execute("SELECT id FROM accounts WHERE type_id = 5").fetchall()
    }
    exclude_set = inv_set | div_set | equity_ids

    inv_placeholders = ",".join("?" for _ in investment_account_ids)
    month_expr = month_bucket_sql(conn, "t.date")

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
    for row in inflow_rows:
        if row["counterpart"] in exclude_set:
            continue
        result[row["month"]] = result.get(row["month"], 0.0) + float(row["total"])
    for row in outflow_rows:
        if row["counterpart"] in exclude_set:
            continue
        result[row["month"]] = result.get(row["month"], 0.0) - float(row["total"])

    return {month: round(value, 4) for month, value in result.items()}


def _iqr_filter(values: list[float], k: float = 1.5) -> tuple[list[float], int]:
    """Apply IQR × k outlier filtering."""
    if len(values) < 4:
        return list(values), 0
    sorted_values = sorted(values)
    n = len(sorted_values)
    q1 = sorted_values[n // 4]
    q3 = sorted_values[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    filtered = [value for value in values if lower <= value <= upper]
    return filtered, len(values) - len(filtered)


def _iqr_filter_samples(
    samples: list[dict], value_key: str, k: float = 1.5
) -> tuple[list[dict], int]:
    """Apply IQR × k filtering to sample dicts using a numeric field."""
    if len(samples) < 4:
        return list(samples), 0
    values = [float(sample[value_key]) for sample in samples]
    sorted_values = sorted(values)
    n = len(sorted_values)
    q1 = sorted_values[n // 4]
    q3 = sorted_values[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    filtered = [
        sample for sample in samples if lower <= float(sample[value_key]) <= upper
    ]
    return filtered, len(samples) - len(filtered)


def _aggregate(values: list[float], stat: str = "mean") -> float:
    """Compute mean or median of a list of floats."""
    if not values:
        return 0.0
    if stat == "median":
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n % 2 == 1:
            return sorted_values[n // 2]
        return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    return sum(values) / len(values)


def _normalize_investment_stat(stat: str | None) -> str:
    """Investment projections always use the historical mean."""
    return "mean"


def _estimate_investment_model(
    all_months: list[str],
    inv_bal_map: dict[str, float],
    div_map: dict[str, float],
    contrib_map: dict[str, float],
    income_map: dict[str, float],
    *,
    expense_map: dict[str, float] | None = None,
    stat: str = "mean",
    exclude_outliers: bool = True,
    outlier_k: float = 1.5,
) -> dict:
    """Estimate monthly yield and contribution rates from trailing data."""
    if expense_map is None:
        expense_map = {}
    stat = _normalize_investment_stat(stat)
    interest_samples: list[dict] = []
    contribution_samples: list[dict] = []
    warnings: list[str] = []

    for index, month in enumerate(all_months):
        opening = inv_bal_map.get(all_months[index - 1]) if index > 0 else None
        closing = inv_bal_map.get(month)
        has_investment_context = opening is not None or closing is not None

        contrib_val = contrib_map.get(month, 0.0)
        income_val = income_map.get(month)
        expense_val = expense_map.get(month, 0.0)
        result_val = (income_val - expense_val) if income_val is not None else None
        if (
            result_val is not None
            and result_val > 0
            and (has_investment_context or month in contrib_map)
        ):
            contribution_samples.append(
                {
                    "amount": float(contrib_val),
                    "rate": float(contrib_val) / float(result_val),
                    "income": float(result_val),
                }
            )

        div_val = float(div_map.get(month, 0.0))
        if closing is not None and opening is not None:
            base = (opening + closing) / 2
        elif closing is not None:
            base = closing
        elif opening is not None:
            base = opening
        else:
            continue
        if base > 0:
            interest_samples.append(
                {
                    "amount": float(div_val),
                    "rate": float(div_val) / float(base),
                    "base": float(base),
                }
            )

    yield_excluded = 0
    contrib_excluded = 0
    filtered_interest_samples = list(interest_samples)
    filtered_contribution_samples = list(contribution_samples)
    if exclude_outliers:
        if filtered_interest_samples:
            filtered_interest_samples, yield_excluded = _iqr_filter_samples(
                filtered_interest_samples, "rate", outlier_k
            )
        if filtered_contribution_samples:
            filtered_contribution_samples, contrib_excluded = _iqr_filter_samples(
                filtered_contribution_samples, "rate", outlier_k
            )

    yields = [sample["rate"] for sample in filtered_interest_samples]
    contribution_rates = [sample["rate"] for sample in filtered_contribution_samples]
    interest_amounts = [sample["amount"] for sample in filtered_interest_samples]
    contribution_amounts = [
        sample["amount"] for sample in filtered_contribution_samples
    ]
    yield_bases = [sample["base"] for sample in filtered_interest_samples]
    contribution_incomes = [
        sample["income"] for sample in filtered_contribution_samples
    ]

    yield_rate = _aggregate(yields, stat)
    contribution_rate = _aggregate(contribution_rates, stat)
    interest_amount = _aggregate(interest_amounts, stat)
    contribution_amount = _aggregate(contribution_amounts, stat)
    yield_reference_base = _aggregate(yield_bases, stat)
    contribution_reference_income = _aggregate(contribution_incomes, stat)

    return {
        "yield_rate": round(yield_rate, 8),
        "contribution_rate": round(contribution_rate, 8),
        "interest_amount": round(interest_amount, 4),
        "contribution_amount": round(contribution_amount, 4),
        "yield_reference_base": round(yield_reference_base, 4),
        "contribution_reference_income": round(contribution_reference_income, 4),
        "yield_rate_samples_pct": [
            round(sample["rate"] * 100, 4) for sample in filtered_interest_samples
        ],
        "contribution_rate_samples_pct": [
            round(sample["rate"] * 100, 4) for sample in filtered_contribution_samples
        ],
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
    projected_income: list[float],
    projected_expenses: list[float],
    baseline_savings: list[float],
    horizon: int,
    investment_adj: list[float] | None = None,
) -> tuple[list[float], list[float], list[dict]]:
    """Project investment and non-investment assets jointly."""
    investments: list[float] = []
    non_inv_assets: list[float] = []
    detail: list[dict] = []
    inv_balance = current_investment_balance
    non_inv_balance = current_non_inv_assets
    normalized_adjustment = investment_adj or [0.0] * horizon
    for index in range(horizon):
        opening_investment_balance = inv_balance
        projected_income_i = max(
            0.0, projected_income[index] if index < len(projected_income) else 0.0
        )
        projected_expense_i = max(
            0.0,
            projected_expenses[index] if index < len(projected_expenses) else 0.0,
        )
        net_result_i = max(0.0, projected_income_i - projected_expense_i)
        contribution = contribution_rate * net_result_i
        interest = inv_balance * yield_rate

        raw_adjustment = (
            normalized_adjustment[index] if index < len(normalized_adjustment) else 0.0
        )
        if raw_adjustment > 0:
            available = max(
                0.0, non_inv_balance + baseline_savings[index] - contribution
            )
            series_transfer = min(raw_adjustment, available)
        elif raw_adjustment < 0:
            available_inv = max(0.0, inv_balance + interest + contribution)
            series_transfer = -min(-raw_adjustment, available_inv)
        else:
            series_transfer = 0.0

        inv_balance = max(0.0, inv_balance + interest + contribution + series_transfer)
        non_inv_savings = baseline_savings[index] - contribution - series_transfer
        non_inv_balance = max(0.0, non_inv_balance + non_inv_savings)
        investments.append(round(inv_balance, 4))
        non_inv_assets.append(round(non_inv_balance, 4))
        detail.append(
            {
                "opening_investment_balance": round(opening_investment_balance, 4),
                "interest": round(interest, 4),
                "interest_total": round(interest, 4),
                "contribution": round(contribution, 4),
                "series_transfer": round(series_transfer, 4),
                "projected_income": round(projected_income_i, 4),
                "projected_expense": round(projected_expense_i, 4),
                "net_result": round(net_result_i, 4),
                "opening_investment_balance_exact": round(
                    opening_investment_balance, _PROJECTED_INVESTMENT_DETAIL_DIGITS
                ),
                "ending_investment_balance_exact": round(
                    inv_balance, _PROJECTED_INVESTMENT_DETAIL_DIGITS
                ),
                "interest_exact": round(interest, _PROJECTED_INVESTMENT_DETAIL_DIGITS),
                "contribution_exact": round(
                    contribution, _PROJECTED_INVESTMENT_DETAIL_DIGITS
                ),
                "series_transfer_exact": round(
                    series_transfer, _PROJECTED_INVESTMENT_DETAIL_DIGITS
                ),
            }
        )
    return investments, non_inv_assets, detail


__all__ = [
    "_aggregate",
    "_estimate_investment_model",
    "_get_monthly_dividend_income",
    "_get_monthly_investment_balances",
    "_get_monthly_investment_contributions",
    "_identify_dividend_accounts",
    "_identify_investment_accounts",
    "_iqr_filter",
    "_iqr_filter_samples",
    "_normalize_investment_stat",
    "_project_investments",
    "_resolve_investment_projection_inputs",
]
