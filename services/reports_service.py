"""Report and analytics service functions."""

from datetime import datetime
from math import sqrt
from typing import Optional

from database import (
    balance_delta,
    ci_order_sql,
    compute_balance,
    compute_filtered_balance,
    month_bucket_sql,
)
from models import (
    BalanceGroup,
    BalanceLineItem,
    BalanceSheet,
    BalanceSubgroup,
    StatsData,
)

from services.errors import NotFoundError
from services.helpers import (
    current_month_range,
    current_year_range as shared_current_year_range,
    end_of_month_datetime,
    normalize_account_properties,
    require_row,
    resolve_date_range,
    serialize_temporal_value,
)
from services import tags_service


def current_year_range() -> tuple[str, str]:
    return shared_current_year_range()


def date_params(from_date: Optional[str], to_date: Optional[str]) -> tuple[str, str]:
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    return from_dt, to_dt


def _is_zero_balance(value: float) -> bool:
    return abs(float(value or 0)) < 0.005


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if abs(float(denominator or 0)) < 0.0000001:
        return None
    return numerator / denominator


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _month_start(month_str: str) -> str:
    return f"{month_str}-01 00:00:00"


def _month_sequence(start_month: str, end_month: str) -> list[str]:
    start_year, start_mon = map(int, start_month.split("-"))
    end_year, end_mon = map(int, end_month.split("-"))
    months: list[str] = []
    year = start_year
    month = start_mon
    while (year, month) <= (end_year, end_mon):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _median(sorted_values: list[float]) -> Optional[float]:
    if not sorted_values:
        return None
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0


def _percentile(sorted_values: list[float], percentile: float) -> Optional[float]:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _build_account_stats(
    conn,
    *,
    from_dt: str,
    to_dt: str,
    filtered: bool,
    tag_ids: Optional[list[int]],
    month_expr: str,
    tag_filter: str,
    tag_params: list[int],
) -> list[dict]:
    now = datetime.now()
    current_start_dt, current_end_dt = current_month_range(now)
    current_month = current_start_dt[:7]
    end_month = to_dt[:7] if filtered else current_month
    start_month = from_dt[:7]
    months = _month_sequence(start_month, end_month) if start_month <= end_month else []

    account_rows = conn.execute("""SELECT a.id, a.name, a.type_id, a.initial_balance,
                  t.name AS type_name,
                  COALESCE(s.name, '') AS subtype_name
           FROM accounts a
           JOIN types t ON a.type_id = t.id
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           WHERE a.type_id <> 5
             AND LOWER(TRIM(COALESCE(s.name, ''))) <> 'patrimonio'
           ORDER BY a.type_id, a.name""").fetchall()

    totals = conn.execute(
        f"""WITH month_legs AS (
               SELECT debit_account AS account_id,
                      {month_expr} AS month,
                      amount AS debit_amount,
                      0 AS credit_amount
               FROM transactions t
               WHERE t.date BETWEEN ? AND ?{tag_filter}

               UNION ALL

               SELECT credit_account AS account_id,
                      {month_expr} AS month,
                      0 AS debit_amount,
                      amount AS credit_amount
               FROM transactions t
               WHERE t.date BETWEEN ? AND ?{tag_filter}
           )
           SELECT account_id,
                  month,
                  COALESCE(SUM(debit_amount), 0) AS deb,
                  COALESCE(SUM(credit_amount), 0) AS cred
           FROM month_legs
           GROUP BY account_id, month""",
        (from_dt, to_dt, *tag_params, from_dt, to_dt, *tag_params),
    ).fetchall()

    totals_map: dict[tuple[int, str], tuple[float, float]] = {}
    for row in totals:
        totals_map[(row["account_id"], row["month"])] = (row["deb"], row["cred"])

    account_stats: list[dict] = []
    for row in account_rows:
        monthly_values: list[float] = []
        active_month_values: list[float] = []
        active_month_labels: list[str] = []
        for month in months:
            has_activity = (row["id"], month) in totals_map
            deb, cred = totals_map.get((row["id"], month), (0.0, 0.0))
            value = deb - cred if row["type_id"] in {1, 4} else cred - deb
            rounded_value = round(value, 4)
            monthly_values.append(rounded_value)
            if has_activity:
                active_month_values.append(rounded_value)
                active_month_labels.append(month)

        active_month_count = len(active_month_values)
        sorted_values = sorted(active_month_values)
        mean_value = (
            sum(active_month_values) / active_month_count
            if active_month_count > 0
            else None
        )
        median_value = _median(sorted_values)
        q1 = _percentile(sorted_values, 0.25)
        q3 = _percentile(sorted_values, 0.75)
        iqr = (q3 - q1) if q1 is not None and q3 is not None else None
        lower_bound = q1 - 1.5 * iqr if iqr is not None and q1 is not None else None
        upper_bound = q3 + 1.5 * iqr if iqr is not None and q3 is not None else None
        non_outliers = (
            [
                value
                for value in sorted_values
                if lower_bound is not None
                and upper_bound is not None
                and lower_bound <= value <= upper_bound
            ]
            if sorted_values and lower_bound is not None and upper_bound is not None
            else []
        )
        whisker_min = (
            non_outliers[0]
            if non_outliers
            else (sorted_values[0] if sorted_values else None)
        )
        whisker_max = (
            non_outliers[-1]
            if non_outliers
            else (sorted_values[-1] if sorted_values else None)
        )
        current_value = compute_filtered_balance(
            conn,
            row["id"],
            row["type_id"],
            0.0,
            current_start_dt,
            current_end_dt,
            tag_ids,
        )

        account_stats.append(
            {
                "account_id": row["id"],
                "account_name": row["name"],
                "type_id": row["type_id"],
                "type_name": row["type_name"],
                "subtype_name": row["subtype_name"],
                "current": _round_or_none(current_value),
                "mean": _round_or_none(mean_value),
                "median": _round_or_none(median_value),
                "stddev": _round_or_none(
                    _std_dev(active_month_values) if active_month_values else None
                ),
                "active_months": active_month_count,
                "months": active_month_labels,
                "values": [_round_or_none(value) for value in active_month_values],
                "boxplot": {
                    "k": 1.5,
                    "lower_bound": _round_or_none(lower_bound),
                    "upper_bound": _round_or_none(upper_bound),
                    "min": _round_or_none(whisker_min),
                    "q1": _round_or_none(q1),
                    "median": _round_or_none(median_value),
                    "q3": _round_or_none(q3),
                    "max": _round_or_none(whisker_max),
                    "mean": _round_or_none(mean_value),
                    "current": _round_or_none(current_value),
                },
            }
        )

    return account_stats


def _tag_clause(tx_alias: str, tag_ids: Optional[list[int]]) -> tuple[str, list[int]]:
    clause, params = tags_service.build_transaction_tag_filter(tx_alias, tag_ids)
    if not clause:
        return "", []
    return f" AND {clause}", params


def _tag_csv(tags) -> str:
    return ", ".join(tag.name for tag in tags)


def _monthly_subtype_evolution(
    conn,
    *,
    type_id: int,
    from_dt: str,
    to_dt: str,
    tag_filter: str,
    tag_params: list[int],
    month_expr: str,
) -> list[dict]:
    if type_id == 3:
        debit_sign, credit_sign = -1, 1
    elif type_id == 4:
        debit_sign, credit_sign = 1, -1
    else:
        raise ValueError("Unsupported type_id for subtype evolution")

    rows = conn.execute(
        f"""WITH subtype_legs AS (
             SELECT {month_expr} AS month,
                    COALESCE(s.name, 'Sin subtipo') AS subtype,
                    ? * t.amount AS signed_amount
             FROM transactions t
             JOIN accounts a ON t.debit_account = a.id
             LEFT JOIN subtypes s ON a.subtype_id = s.id
             WHERE a.type_id = ? AND t.date BETWEEN ? AND ?{tag_filter}

             UNION ALL

             SELECT {month_expr} AS month,
                    COALESCE(s.name, 'Sin subtipo') AS subtype,
                    ? * t.amount AS signed_amount
             FROM transactions t
             JOIN accounts a ON t.credit_account = a.id
             LEFT JOIN subtypes s ON a.subtype_id = s.id
             WHERE a.type_id = ? AND t.date BETWEEN ? AND ?{tag_filter}
         )
         SELECT month,
                subtype,
                SUM(signed_amount) AS amount
         FROM subtype_legs
         GROUP BY month, subtype
          HAVING ABS(SUM(signed_amount)) >= 0.005
           ORDER BY month, ABS(SUM(signed_amount)) DESC, subtype""",
        (
            debit_sign,
            type_id,
            from_dt,
            to_dt,
            *tag_params,
            credit_sign,
            type_id,
            from_dt,
            to_dt,
            *tag_params,
        ),
    ).fetchall()
    return [
        {"month": row["month"], "subtype": row["subtype"], "amount": row["amount"]}
        for row in rows
    ]


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


def _apply_balance_filters(
    groups: list[BalanceGroup],
    *,
    hide_accounts: bool = False,
    show_zero_balance: bool = True,
) -> list[BalanceGroup]:
    filtered_groups: list[BalanceGroup] = []

    for group in groups:
        next_subgroups: list[BalanceSubgroup] = []

        for subgroup in group.subgroups:
            if not show_zero_balance and _is_zero_balance(subgroup.subtotal):
                continue

            next_items = subgroup.items
            if not show_zero_balance:
                next_items = [
                    item for item in next_items if not _is_zero_balance(item.balance)
                ]
            if hide_accounts:
                next_items = []

            next_subgroups.append(
                BalanceSubgroup(
                    subtype_name=subgroup.subtype_name,
                    items=next_items,
                    subtotal=subgroup.subtotal,
                )
            )

        if next_subgroups or show_zero_balance or not _is_zero_balance(group.total):
            filtered_groups.append(
                BalanceGroup(
                    type_name=group.type_name,
                    type_id=group.type_id,
                    subgroups=next_subgroups,
                    total=group.total,
                )
            )

    return filtered_groups


def get_balance(
    conn,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    *,
    hide_accounts: bool = False,
    show_zero_balance: bool = True,
    type_ids: Optional[set[int]] = None,
    tag_ids: Optional[list[int]] = None,
) -> BalanceSheet:
    from_dt, to_dt, filtered = resolve_date_range(from_date, to_date)
    type_map: dict = {}

    rows = conn.execute("""SELECT a.id, a.name, a.type_id, a.subtype_id,
                  a.initial_balance,
                  t.name AS type_name,
                  COALESCE(s.name, 'Sin subtipo') AS subtype_name
           FROM accounts a
           JOIN types t ON a.type_id = t.id
           LEFT JOIN subtypes s ON a.subtype_id = s.id
           ORDER BY a.type_id, s.name, a.name""").fetchall()

    for row in rows:
        if type_ids is not None and row["type_id"] not in type_ids:
            continue

        balance = (
            compute_filtered_balance(
                conn,
                row["id"],
                row["type_id"],
                row["initial_balance"],
                from_dt,
                to_dt,
                tag_ids,
            )
            if filtered
            else compute_balance(
                conn, row["id"], row["type_id"], row["initial_balance"], tag_ids=tag_ids
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
        groups=_apply_balance_filters(
            groups,
            hide_accounts=hide_accounts,
            show_zero_balance=show_zero_balance,
        ),
        total_activo=totals[1],
        total_pasivo=totals[2],
        total_patrimonio=totals[5],
        total_ingreso=totals[3],
        total_gasto=totals[4],
        resultado=result,
        equation_check=round(equation, 4),
    )


def journal_data(
    conn,
    from_date=None,
    to_date=None,
    account_id=None,
    limit=1000,
    tag_ids: Optional[list[int]] = None,
):
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    conditions = ["t.date BETWEEN ? AND ?"]
    params: list = [from_dt, to_dt]
    if account_id:
        conditions.append("(t.debit_account = ? OR t.credit_account = ?)")
        params += [account_id, account_id]
    tag_filter, tag_params = tags_service.build_transaction_tag_filter("t", tag_ids)
    if tag_filter:
        conditions.append(tag_filter)
        params += tag_params
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
    tag_map = tags_service.get_transaction_tags_map(conn, [row["id"] for row in rows])
    return [
        {
            "id": row["id"],
            "date": serialize_temporal_value(row["date"]),
            "debit_name": row["debit_name"],
            "credit_name": row["credit_name"],
            "amount": row["amount"],
            "original_amount": row["original_amount"],
            "original_currency": row["original_currency"],
            "fx_rate": row["fx_rate"],
            "fx_source": row["fx_source"],
            "description": row["description"],
            "tags": [tag.model_dump() for tag in tag_map.get(row["id"], [])],
            "tags_label": _tag_csv(tag_map.get(row["id"], [])),
        }
        for row in rows
    ]


def get_ledger(
    conn,
    account_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    tag_ids: Optional[list[int]] = None,
):
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    account = require_row(
        conn,
        "SELECT id, name, type_id, initial_balance FROM accounts WHERE id = ?",
        (account_id,),
        "Account not found",
        NotFoundError,
    )

    tag_clause, tag_params = _tag_clause("t", tag_ids)
    rows = conn.execute(
        f"""SELECT t.id, t.date, t.description, t.amount,
                  t.original_amount, t.original_currency, t.fx_rate, t.fx_source,
                  t.debit_account, t.credit_account,
                  da.name AS debit_name, ca.name AS credit_name
           FROM transactions t
           JOIN accounts da ON t.debit_account  = da.id
           JOIN accounts ca ON t.credit_account = ca.id
           WHERE (t.debit_account = ? OR t.credit_account = ?)
             AND t.date BETWEEN ? AND ?
             {tag_clause}
           ORDER BY t.date ASC, t.id ASC""",
        (account_id, account_id, from_dt, to_dt, *tag_params),
    ).fetchall()

    running = account["initial_balance"]
    entries = []
    tag_map = tags_service.get_transaction_tags_map(conn, [row["id"] for row in rows])
    for row in rows:
        if row["debit_account"] == account_id:
            role, counterpart, counterpart_id, delta = (
                "Débito",
                row["credit_name"],
                row["credit_account"],
                balance_delta(account["type_id"], "debit", row["amount"]),
            )
        else:
            role, counterpart, counterpart_id, delta = (
                "Crédito",
                row["debit_name"],
                row["debit_account"],
                balance_delta(account["type_id"], "credit", row["amount"]),
            )
        running += delta
        entries.append(
            {
                "id": row["id"],
                "date": serialize_temporal_value(row["date"]),
                "description": row["description"] or counterpart,
                "counterpart": counterpart,
                "counterpart_id": counterpart_id,
                "role": role,
                "debit": row["amount"] if role == "Débito" else None,
                "credit": row["amount"] if role == "Crédito" else None,
                "original_amount": row["original_amount"],
                "original_currency": row["original_currency"],
                "fx_rate": row["fx_rate"],
                "fx_source": row["fx_source"],
                "balance": round(running, 4),
                "tags": [tag.model_dump() for tag in tag_map.get(row["id"], [])],
                "tags_label": _tag_csv(tag_map.get(row["id"], [])),
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
    conn,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    tag_ids: Optional[list[int]] = None,
) -> StatsData:
    from_dt, to_dt, _ = resolve_date_range(from_date, to_date)
    from_dt, to_dt, filtered = resolve_date_range(from_date, to_date)
    tag_filter, tag_params = _tag_clause("t", tag_ids)
    month_expr = month_bucket_sql(conn, "t.date")

    cashflow_rows = conn.execute(
        f"""WITH tx_legs AS (
             SELECT {month_expr} AS month,
                 da.type_id AS type_id,
                 t.amount AS debit_amount,
                 0 AS credit_amount
             FROM transactions t
             JOIN accounts da ON t.debit_account = da.id
             WHERE t.date BETWEEN ? AND ?{tag_filter}

             UNION ALL

             SELECT {month_expr} AS month,
                 ca.type_id AS type_id,
                 0 AS debit_amount,
                 t.amount AS credit_amount
             FROM transactions t
             JOIN accounts ca ON t.credit_account = ca.id
             WHERE t.date BETWEEN ? AND ?{tag_filter}
         )
         SELECT month,
             SUM(CASE WHEN type_id = 3 THEN credit_amount - debit_amount ELSE 0 END) AS ingresos,
             SUM(CASE WHEN type_id = 4 THEN debit_amount - credit_amount ELSE 0 END) AS gastos
         FROM tx_legs
         GROUP BY month
         ORDER BY month""",
        (from_dt, to_dt, *tag_params, from_dt, to_dt, *tag_params),
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
        f"""WITH subtype_legs AS (
         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.debit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 4 AND t.date BETWEEN ? AND ?{tag_filter}

         UNION ALL

         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             -t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.credit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 4 AND t.date BETWEEN ? AND ?{tag_filter}
     )
     SELECT subtype,
         SUM(signed_amount) AS amount
     FROM subtype_legs
     GROUP BY subtype
     HAVING SUM(signed_amount) > 0
     ORDER BY amount DESC""",
        (from_dt, to_dt, *tag_params, from_dt, to_dt, *tag_params),
    ).fetchall()
    expenses_by_subtype = [
        {"subtype": row["subtype"], "amount": row["amount"]} for row in exp_rows
    ]

    inc_rows = conn.execute(
        f"""WITH subtype_legs AS (
         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.credit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 3 AND t.date BETWEEN ? AND ?{tag_filter}

         UNION ALL

         SELECT COALESCE(s.name, 'Sin subtipo') AS subtype,
             -t.amount AS signed_amount
         FROM transactions t
         JOIN accounts a ON t.debit_account = a.id
         LEFT JOIN subtypes s ON a.subtype_id = s.id
         WHERE a.type_id = 3 AND t.date BETWEEN ? AND ?{tag_filter}
     )
     SELECT subtype,
         SUM(signed_amount) AS amount
     FROM subtype_legs
     GROUP BY subtype
     HAVING SUM(signed_amount) > 0
     ORDER BY amount DESC""",
        (from_dt, to_dt, *tag_params, from_dt, to_dt, *tag_params),
    ).fetchall()
    income_by_subtype = [
        {"subtype": row["subtype"], "amount": row["amount"]} for row in inc_rows
    ]
    income_evolution = _monthly_subtype_evolution(
        conn,
        type_id=3,
        from_dt=from_dt,
        to_dt=to_dt,
        tag_filter=tag_filter,
        tag_params=tag_params,
        month_expr=month_expr,
    )
    expense_evolution = _monthly_subtype_evolution(
        conn,
        type_id=4,
        from_dt=from_dt,
        to_dt=to_dt,
        tag_filter=tag_filter,
        tag_params=tag_params,
        month_expr=month_expr,
    )

    asset_accounts = _financial_rows(conn, 1)
    liability_accounts = _financial_rows(conn, 2)
    expense_accounts = _financial_rows(conn, 4)
    asset_composition = []
    asset_composition_excluding_fixed = []
    non_fixed_asset_ids = set()
    total_assets = 0.0
    total_assets_excluding_fixed = 0.0
    current_assets = 0.0
    quick_assets = 0.0
    for account in asset_accounts:
        balance = compute_filtered_balance(
            conn,
            account["id"],
            account["type_id"],
            account["initial_balance"],
            from_dt,
            to_dt,
            tag_ids,
        )
        asset_properties = normalize_account_properties(
            account["properties"],
            type_id=1,
            name=account["name"],
            subtype_name=account["subtype_name"],
        )
        liquidity_profile = asset_properties.get("liquidity_profile")
        total_assets += balance
        if liquidity_profile != "fixed":
            total_assets_excluding_fixed += balance
            non_fixed_asset_ids.add(account["id"])
        if balance > 0 and liquidity_profile in {"quick", "current"}:
            current_assets += balance
        if balance > 0 and liquidity_profile == "quick":
            quick_assets += balance
        if balance > 0:
            asset_composition.append(
                {
                    "account": account["name"],
                    "balance": round(balance, 4),
                }
            )
            if liquidity_profile != "fixed":
                asset_composition_excluding_fixed.append(
                    {
                        "account": account["name"],
                        "balance": round(balance, 4),
                    }
                )
    asset_composition.sort(key=lambda item: item["balance"], reverse=True)
    asset_composition_excluding_fixed.sort(
        key=lambda item: item["balance"], reverse=True
    )

    total_liabilities = 0.0
    current_liabilities = 0.0
    for account in liability_accounts:
        balance = compute_filtered_balance(
            conn,
            account["id"],
            account["type_id"],
            account["initial_balance"],
            from_dt,
            to_dt,
            tag_ids,
        )
        total_liabilities += balance
        liability_properties = normalize_account_properties(
            account["properties"],
            type_id=2,
            name=account["name"],
            subtype_name=account["subtype_name"],
        )
        if balance > 0 and liability_properties.get("liability_term") == "current":
            current_liabilities += balance

    essential_expense_total = 0.0
    for account in expense_accounts:
        expense_total = compute_filtered_balance(
            conn,
            account["id"],
            account["type_id"],
            account["initial_balance"],
            from_dt,
            to_dt,
            tag_ids,
        )
        expense_properties = normalize_account_properties(
            account["properties"],
            type_id=4,
            name=account["name"],
            subtype_name=account["subtype_name"],
        )
        if (
            expense_total > 0
            and expense_properties.get("expense_profile") == "essential"
        ):
            essential_expense_total += expense_total

    top_rows = conn.execute(
        f"""SELECT a.name AS account,
                  SUM(t.amount) AS volume,
                  COUNT(*) AS tx_count
           FROM transactions t
           JOIN accounts a ON t.debit_account = a.id OR t.credit_account = a.id
           WHERE t.date BETWEEN ? AND ?{tag_filter}
             AND LOWER(TRIM(a.name)) <> ?
           GROUP BY a.id ORDER BY volume DESC LIMIT 10""",
        (from_dt, to_dt, *tag_params, "capital"),
    ).fetchall()
    top_accounts = [
        {
            "account": row["account"],
            "volume": row["volume"],
            "tx_count": row["tx_count"],
        }
        for row in top_rows
    ]

    account_stats = _build_account_stats(
        conn,
        from_dt=from_dt,
        to_dt=to_dt,
        filtered=filtered,
        tag_ids=tag_ids,
        month_expr=month_expr,
        tag_filter=tag_filter,
        tag_params=tag_params,
    )

    months_rows = conn.execute(
        f"""SELECT DISTINCT {month_expr} AS month FROM transactions t
           WHERE date BETWEEN ? AND ?{tag_filter} ORDER BY month""",
        (from_dt, to_dt, *tag_params),
    ).fetchall()
    months = [row["month"] for row in months_rows]

    balance_evolution = []
    liability_evolution = []
    net_worth_evolution = []
    for month in months:
        month_end = end_of_month_datetime(month)
        month_assets = 0.0
        month_liabilities = 0.0

        for account in asset_accounts:
            balance = compute_filtered_balance(
                conn,
                account["id"],
                account["type_id"],
                account["initial_balance"],
                from_dt,
                month_end,
                tag_ids,
            )
            if account["id"] in non_fixed_asset_ids:
                month_assets += balance
                balance_evolution.append(
                    {
                        "month": month,
                        "account_id": account["id"],
                        "account_name": account["name"],
                        "subtype_name": account["subtype_name"],
                        "balance": balance,
                    }
                )

        for account in liability_accounts:
            balance = compute_filtered_balance(
                conn,
                account["id"],
                account["type_id"],
                account["initial_balance"],
                from_dt,
                month_end,
                tag_ids,
            )
            month_liabilities += balance
            liability_evolution.append(
                {
                    "month": month,
                    "account_id": account["id"],
                    "account_name": account["name"],
                    "subtype_name": account["subtype_name"],
                    "balance": balance,
                }
            )

        net_worth_evolution.append(
            {
                "month": month,
                "assets": round(month_assets, 4),
                "liabilities": round(month_liabilities, 4),
                "net_worth": round(month_assets - month_liabilities, 4),
            }
        )

    total_income = sum(row["ingresos"] for row in monthly_cashflow)
    total_expense = sum(row["gastos"] for row in monthly_cashflow)
    net_result = sum(row["neto"] for row in monthly_cashflow)
    monthly_nets = [row["neto"] for row in monthly_cashflow]
    top_asset = asset_composition[0] if asset_composition else None
    top_asset_excluding_fixed = (
        asset_composition_excluding_fixed[0]
        if asset_composition_excluding_fixed
        else None
    )
    top_expense = expenses_by_subtype[0] if expenses_by_subtype else None
    savings_rate = _safe_ratio(net_result, total_income)
    debt_ratio = _safe_ratio(total_liabilities, total_assets)
    debt_ratio_excluding_fixed = _safe_ratio(
        total_liabilities, total_assets_excluding_fixed
    )
    current_ratio = _safe_ratio(current_assets, current_liabilities)
    quick_ratio = _safe_ratio(quick_assets, current_liabilities)
    top_asset_share = (
        _safe_ratio(top_asset["balance"], total_assets) if top_asset else None
    )
    top_asset_share_excluding_fixed = (
        _safe_ratio(top_asset_excluding_fixed["balance"], total_assets_excluding_fixed)
        if top_asset_excluding_fixed
        else None
    )
    top_expense_share = (
        _safe_ratio(top_expense["amount"], total_expense) if top_expense else None
    )
    observed_months = max(len(monthly_cashflow), 1)
    recent_cashflow = monthly_cashflow[-6:]
    recent_months_count = len(recent_cashflow)
    avg_monthly_income_recent = (
        sum(row["ingresos"] for row in recent_cashflow) / recent_months_count
        if recent_months_count
        else None
    )
    avg_monthly_expense_recent = (
        sum(row["gastos"] for row in recent_cashflow) / recent_months_count
        if recent_months_count
        else None
    )
    runway_expense_basis = "essential" if essential_expense_total > 0 else "total"
    runway_expense_total = (
        essential_expense_total if essential_expense_total > 0 else total_expense
    )
    monthly_essential_expense = (
        runway_expense_total / observed_months if runway_expense_total > 0 else None
    )
    runway_months = (
        _safe_ratio(quick_assets, monthly_essential_expense)
        if monthly_essential_expense
        else None
    )
    total_runway_months = (
        _safe_ratio(total_assets, avg_monthly_expense_recent)
        if avg_monthly_expense_recent
        else None
    )

    summary = {
        "total_income": round(total_income, 4),
        "total_expense": round(total_expense, 4),
        "net_result": round(net_result, 4),
        "avg_monthly_net": (
            round(net_result / len(monthly_nets), 4) if monthly_nets else 0.0
        ),
        "monthly_volatility": round(_std_dev(monthly_nets), 4),
        "negative_months": len([value for value in monthly_nets if value < 0]),
        "savings_rate": _round_or_none(savings_rate),
        "recent_months_count": recent_months_count,
        "avg_monthly_income_recent": _round_or_none(avg_monthly_income_recent),
        "avg_monthly_expense_recent": _round_or_none(avg_monthly_expense_recent),
        "total_assets": round(total_assets, 4),
        "total_assets_excluding_fixed": round(total_assets_excluding_fixed, 4),
        "total_liabilities": round(total_liabilities, 4),
        "net_worth": round(total_assets - total_liabilities, 4),
        "net_worth_excluding_fixed": round(
            total_assets_excluding_fixed - total_liabilities, 4
        ),
        "current_assets": round(current_assets, 4),
        "quick_assets": round(quick_assets, 4),
        "current_liabilities": round(current_liabilities, 4),
        "debt_ratio": _round_or_none(debt_ratio),
        "debt_ratio_excluding_fixed": _round_or_none(debt_ratio_excluding_fixed),
        "current_ratio": _round_or_none(current_ratio),
        "quick_ratio": _round_or_none(quick_ratio),
        "monthly_essential_expense": _round_or_none(monthly_essential_expense),
        "runway_months": _round_or_none(runway_months),
        "total_runway_months": _round_or_none(total_runway_months),
        "runway_basis": runway_expense_basis,
        "top_asset_name": top_asset["account"] if top_asset else None,
        "top_asset_share": _round_or_none(top_asset_share),
        "top_asset_name_excluding_fixed": (
            top_asset_excluding_fixed["account"] if top_asset_excluding_fixed else None
        ),
        "top_asset_share_excluding_fixed": _round_or_none(
            top_asset_share_excluding_fixed
        ),
        "top_expense_name": top_expense["subtype"] if top_expense else None,
        "top_expense_share": _round_or_none(top_expense_share),
    }

    return StatsData(
        summary=summary,
        monthly_cashflow=monthly_cashflow,
        expenses_by_subtype=expenses_by_subtype,
        income_by_subtype=income_by_subtype,
        asset_composition=asset_composition,
        top_accounts=top_accounts,
        account_stats=account_stats,
        balance_evolution=balance_evolution,
        income_evolution=income_evolution,
        expense_evolution=expense_evolution,
        liability_evolution=liability_evolution,
        net_worth_evolution=net_worth_evolution,
    )
