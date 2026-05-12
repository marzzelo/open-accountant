"""High-level projection report assembly."""

from datetime import date
from typing import Optional

from database import compute_balance, compute_filtered_balance

from services.helpers import end_of_month_datetime, normalize_account_properties
from services.projections.common import (
    _add_months,
    _build_slider_config,
    _fill_by_regression,
    _linear_regression,
    _month_str,
    _months_range,
    _project_flow_from_settings,
    _round_or_none,
    _safe_ratio,
    _slider_step,
    _sparse_linear_regression,
)
from services.projections.history import (
    _financial_rows,
    _get_monthly_balances,
    _get_monthly_cashflow,
)
from services.projections.investments import (
    _estimate_investment_model,
    _get_monthly_dividend_income,
    _get_monthly_investment_balances,
    _get_monthly_investment_contributions,
    _identify_dividend_accounts,
    _identify_investment_accounts,
    _normalize_investment_stat,
    _project_investments,
    _resolve_investment_projection_inputs,
)
from services.projections.series import (
    _compute_series_adjustments,
    _split_series_by_confirmation,
    list_series,
)


def build_projections(
    conn,
    horizon: int,
    history_months: int,
    *,
    today: date,
    income_trend_mode: str = "linear",
    income_trend_min: float | None = None,
    income_trend_max: float | None = None,
    income_inflation_base: float | None = None,
    income_inflation_rate: float | None = None,
    expense_trend_mode: str = "linear",
    expense_trend_min: float | None = None,
    expense_trend_max: float | None = None,
    expense_inflation_base: float | None = None,
    expense_inflation_rate: float | None = None,
    investment_lookback_months: int | None = None,
    investment_include_current_month: bool = False,
    investment_stat: str = "mean",
    investment_exclude_outliers: bool = True,
    investment_outlier_k: float = 1.5,
    investment_interest_pct_override: float | None = None,
    investment_contribution_pct_override: float | None = None,
    investment_interest_override: float | None = None,
    investment_contribution_override: float | None = None,
) -> dict:
    """Build the full projections payload returned by the HTTP endpoint."""
    investment_stat = _normalize_investment_stat(investment_stat)
    today_ym = _month_str(today.year, today.month)
    current_partial_end = f"{today_ym}-{today.day:02d} 23:59:59"

    hist_y, hist_m = _add_months(today.year, today.month, -history_months)
    history_start = _month_str(hist_y, hist_m) + "-01 00:00:00"
    history_end = end_of_month_datetime(today_ym)

    income_map, expense_map = _get_monthly_cashflow(conn, history_start, history_end)
    all_hist_months = _months_range(_month_str(hist_y, hist_m), history_months + 1)

    sparse_income = [income_map.get(month) for month in all_hist_months]
    sparse_expenses = [expense_map.get(month) for month in all_hist_months]

    hist_income = _fill_by_regression(sparse_income)
    hist_expenses = _fill_by_regression(sparse_expenses)
    hist_savings = [
        hist_income[index] - hist_expenses[index]
        for index in range(len(all_hist_months))
    ]

    asset_accounts = _financial_rows(conn, 1)
    liab_accounts = _financial_rows(conn, 2)
    expense_accounts = _financial_rows(conn, 4)
    asset_month_presence = _get_monthly_balances(
        conn, history_start, history_end, type_id=1
    )
    liab_bal_map = _get_monthly_balances(conn, history_start, history_end, type_id=2)
    hist_liabilities_sparse = [
        liab_bal_map.get(month, None) for month in all_hist_months
    ]
    hist_liabilities_filled = _fill_by_regression(hist_liabilities_sparse)
    current_assets = sum(
        compute_balance(
            conn, account["id"], account["type_id"], account["initial_balance"]
        )
        for account in asset_accounts
    )
    current_liabilities = sum(
        compute_balance(
            conn, account["id"], account["type_id"], account["initial_balance"]
        )
        for account in liab_accounts
    )

    current_assets_only = 0.0
    quick_assets = 0.0
    current_fixed_assets = 0.0
    current_liabilities_only = 0.0
    non_fixed_asset_accounts = []
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
        if props.get("liquidity_profile") == "fixed":
            current_fixed_assets += balance
        else:
            non_fixed_asset_accounts.append(account)
        if balance > 0 and props.get("liquidity_profile") in {"quick", "current"}:
            current_assets_only += balance
        if balance > 0 and props.get("liquidity_profile") == "quick":
            quick_assets += balance

    asset_bal_map: dict[str, float] = {}
    for month in all_hist_months:
        if month not in asset_month_presence:
            continue
        month_end = end_of_month_datetime(month)
        total = 0.0
        for account in non_fixed_asset_accounts:
            balance = compute_filtered_balance(
                conn,
                account["id"],
                account["type_id"],
                account["initial_balance"],
                history_start,
                month_end,
            )
            total += balance
        asset_bal_map[month] = round(total, 4)

    hist_assets_sparse = [asset_bal_map.get(month, None) for month in all_hist_months]
    hist_assets_filled = _fill_by_regression(hist_assets_sparse)

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

    inv_accounts = _identify_investment_accounts(conn)
    div_accounts = _identify_dividend_accounts(conn)
    inv_ids = [account["id"] for account in inv_accounts]
    div_ids = [account["id"] for account in div_accounts]

    current_investment_balance = 0.0
    for account in inv_accounts:
        current_investment_balance += compute_balance(
            conn, account["id"], account["type_id"], account["initial_balance"]
        )
    current_assets_excluding_fixed = current_assets - current_fixed_assets
    current_non_inv_assets = current_assets_excluding_fixed - current_investment_balance

    inv_lookback = investment_lookback_months or history_months
    inv_data_y, inv_data_m = _add_months(today.year, today.month, -inv_lookback)
    inv_data_start_month = _month_str(inv_data_y, inv_data_m)
    inv_data_start = inv_data_start_month + "-01 00:00:00"
    if investment_include_current_month:
        inv_model_y, inv_model_m = _add_months(
            today.year, today.month, -(inv_lookback - 1)
        )
    else:
        inv_model_y, inv_model_m = inv_data_y, inv_data_m
    inv_months = _months_range(_month_str(inv_model_y, inv_model_m), inv_lookback)
    detail_months = list(inv_months)
    if today_ym not in detail_months:
        detail_months.append(today_ym)

    inv_bal_map = _get_monthly_investment_balances(
        conn, inv_ids, inv_data_start, current_partial_end
    )
    div_map = _get_monthly_dividend_income(
        conn, div_ids, inv_data_start, current_partial_end
    )
    contrib_map = _get_monthly_investment_contributions(
        conn, inv_ids, div_ids, inv_data_start, current_partial_end
    )

    inv_income_map_full, inv_expense_map_full = _get_monthly_cashflow(
        conn, inv_data_start, current_partial_end
    )

    if inv_accounts:
        current_partial_balance = round(
            sum(
                compute_filtered_balance(
                    conn,
                    account["id"],
                    account["type_id"],
                    account["initial_balance"],
                    inv_data_start,
                    current_partial_end,
                )
                for account in inv_accounts
            ),
            4,
        )
        inv_bal_map[today_ym] = current_partial_balance

    model_months_set = set(inv_months)
    hist_inv_sparse = [
        inv_bal_map.get(month, None) if month in model_months_set else None
        for month in all_hist_months
    ]

    investment_model = _estimate_investment_model(
        inv_months,
        inv_bal_map,
        div_map,
        contrib_map,
        inv_income_map_full,
        expense_map=inv_expense_map_full,
        stat=investment_stat,
        exclude_outliers=investment_exclude_outliers,
        outlier_k=investment_outlier_k,
    )

    investment_projection_inputs = _resolve_investment_projection_inputs(
        current_investment_balance,
        investment_model,
        interest_pct_override=investment_interest_pct_override,
        contribution_pct_override=investment_contribution_pct_override,
        interest_override=investment_interest_override,
        contribution_override=investment_contribution_override,
    )
    interest_slider = _build_slider_config(
        investment_projection_inputs["default_interest_percent"],
        investment_model.get("yield_rate_samples_pct", []),
    )
    interest_slider["min"] = -50.0
    interest_slider["max"] = 50.0
    interest_slider["step"] = _slider_step(-50.0, 50.0)
    contribution_slider = _build_slider_config(
        investment_projection_inputs["default_contribution_percent"],
        investment_model.get("contribution_rate_samples_pct", []),
    )
    contribution_slider["min"] = 0.0
    contribution_slider["max"] = 100.0
    contribution_slider["step"] = _slider_step(0.0, 100.0)

    has_investments = len(inv_ids) > 0 and current_investment_balance > 0

    sparse_savings: list[float | None] = []
    for index in range(len(all_hist_months)):
        sparse_income_value, sparse_expense_value = (
            sparse_income[index],
            sparse_expenses[index],
        )
        sparse_savings.append(
            sparse_income_value - sparse_expense_value
            if sparse_income_value is not None and sparse_expense_value is not None
            else None
        )
    reg_income = _sparse_linear_regression(sparse_income)
    reg_expenses = _sparse_linear_regression(sparse_expenses)
    reg_savings = _sparse_linear_regression(sparse_savings)
    reg_assets = _linear_regression(hist_assets_filled)
    reg_liabilities = _linear_regression(hist_liabilities_filled)

    n_hist = len(all_hist_months)

    proj_y, proj_m = _add_months(today.year, today.month, 1)
    projected_months = _months_range(_month_str(proj_y, proj_m), horizon)

    baseline_income = _project_flow_from_settings(
        sparse_income,
        n_hist,
        horizon,
        mode=income_trend_mode,
        min_val=income_trend_min,
        max_val=income_trend_max,
        inflation_base=income_inflation_base,
        inflation_rate=income_inflation_rate,
    )
    baseline_expenses = _project_flow_from_settings(
        sparse_expenses,
        n_hist,
        horizon,
        mode=expense_trend_mode,
        min_val=expense_trend_min,
        max_val=expense_trend_max,
        inflation_base=expense_inflation_base,
        inflation_rate=expense_inflation_rate,
    )
    baseline_savings = [
        round(baseline_income[index] - baseline_expenses[index], 4)
        for index in range(horizon)
    ]

    series_list = list_series(conn)
    baseline_series, scenario_series = _split_series_by_confirmation(series_list)
    baseline_adj = _compute_series_adjustments(baseline_series, projected_months)
    adj = _compute_series_adjustments(scenario_series, projected_months)

    effective_baseline_income = [
        round(baseline_income[index] + baseline_adj["income"][index], 4)
        for index in range(horizon)
    ]
    effective_baseline_expenses = [
        round(baseline_expenses[index] + baseline_adj["expenses"][index], 4)
        for index in range(horizon)
    ]
    effective_baseline_savings = [
        round(
            effective_baseline_income[index] - effective_baseline_expenses[index],
            4,
        )
        for index in range(horizon)
    ]
    combined_investment_adj = [
        round(baseline_adj["investments"][index] + adj["investments"][index], 4)
        for index in range(horizon)
    ]

    scenario_income = [
        round(effective_baseline_income[index] + adj["income"][index], 4)
        for index in range(horizon)
    ]
    scenario_expenses = [
        round(effective_baseline_expenses[index] + adj["expenses"][index], 4)
        for index in range(horizon)
    ]
    scenario_savings = [
        round(scenario_income[index] - scenario_expenses[index], 4)
        for index in range(horizon)
    ]

    baseline_investments: list[float] = []
    baseline_non_inv_assets: list[float] = []
    baseline_detail: list[dict] = []
    scenario_investments: list[float] = []
    scenario_non_inv_assets: list[float] = []
    projected_detail: list[dict] = []
    if has_investments:
        baseline_investments, baseline_non_inv_assets, baseline_detail = (
            _project_investments(
                current_investment_balance,
                current_non_inv_assets,
                investment_projection_inputs["applied_yield_rate"],
                investment_projection_inputs["applied_contribution_rate"],
                effective_baseline_income,
                effective_baseline_expenses,
                effective_baseline_savings,
                horizon,
                investment_adj=baseline_adj["investments"],
            )
        )
        scenario_investments, scenario_non_inv_assets, projected_detail = (
            _project_investments(
                current_investment_balance,
                current_non_inv_assets,
                investment_projection_inputs["applied_yield_rate"],
                investment_projection_inputs["applied_contribution_rate"],
                scenario_income,
                scenario_expenses,
                scenario_savings,
                horizon,
                investment_adj=combined_investment_adj,
            )
        )
    else:
        baseline_investments = [round(current_investment_balance, 4)] * horizon
        scenario_investments = list(baseline_investments)
        baseline_non_inv_balance = current_non_inv_assets
        scenario_non_inv_balance = current_non_inv_assets
        for index in range(horizon):
            baseline_non_inv_balance = max(
                0.0,
                baseline_non_inv_balance + effective_baseline_savings[index],
            )
            baseline_non_inv_assets.append(round(baseline_non_inv_balance, 4))
            baseline_detail.append(
                {
                    "opening_investment_balance": round(current_investment_balance, 4),
                    "interest": 0.0,
                    "interest_total": 0.0,
                    "contribution": 0.0,
                    "projected_income": round(
                        (
                            effective_baseline_income[index]
                            if index < len(effective_baseline_income)
                            else 0.0
                        ),
                        4,
                    ),
                    "projected_expense": round(
                        (
                            effective_baseline_expenses[index]
                            if index < len(effective_baseline_expenses)
                            else 0.0
                        ),
                        4,
                    ),
                    "net_result": round(
                        max(0.0, effective_baseline_savings[index]),
                        4,
                    ),
                }
            )

            scenario_non_inv_balance = max(
                0.0,
                scenario_non_inv_balance + scenario_savings[index],
            )
            scenario_non_inv_assets.append(round(scenario_non_inv_balance, 4))
            projected_detail.append(
                {
                    "opening_investment_balance": round(current_investment_balance, 4),
                    "interest": 0.0,
                    "interest_total": 0.0,
                    "contribution": 0.0,
                    "projected_income": round(
                        scenario_income[index] if index < len(scenario_income) else 0.0,
                        4,
                    ),
                    "projected_expense": round(
                        (
                            scenario_expenses[index]
                            if index < len(scenario_expenses)
                            else 0.0
                        ),
                        4,
                    ),
                    "net_result": round(
                        max(0.0, scenario_savings[index]),
                        4,
                    ),
                }
            )

    baseline_assets = [
        round(baseline_non_inv_assets[index] + baseline_investments[index], 4)
        for index in range(horizon)
    ]

    baseline_liabilities = []
    for index in range(horizon):
        value = round(
            max(
                0.0,
                reg_liabilities[1]
                + reg_liabilities[0] * (n_hist + index)
                + baseline_adj["liabilities"][index],
            ),
            4,
        )
        baseline_liabilities.append(value)

    observed_hist_months = max(
        len(
            [
                month
                for month in all_hist_months
                if month in income_map or month in expense_map
            ]
        ),
        1,
    )
    essential_share = (
        (essential_expense_total / sum(expense_map.values()))
        if sum(expense_map.values()) > 0
        else 0.0
    )
    baseline_net_worth = [
        round(baseline_assets[index] - baseline_liabilities[index], 4)
        for index in range(horizon)
    ]
    scenario_assets = [
        round(scenario_non_inv_assets[index] + scenario_investments[index], 4)
        for index in range(horizon)
    ]
    adj["assets"] = [
        round(scenario_assets[index] - baseline_assets[index], 4)
        for index in range(horizon)
    ]
    scenario_liabilities = [
        round(baseline_liabilities[index] + adj["liabilities"][index], 4)
        for index in range(horizon)
    ]
    scenario_net_worth = [
        round(scenario_assets[index] - scenario_liabilities[index], 4)
        for index in range(horizon)
    ]
    current_liability_share = (
        current_liabilities_only / current_liabilities
        if current_liabilities > 0
        else 0.0
    )
    baseline_current_liabilities = [
        round(baseline_liabilities[index] * current_liability_share, 4)
        for index in range(horizon)
    ]
    scenario_current_liabilities = [
        round(scenario_liabilities[index] * current_liability_share, 4)
        for index in range(horizon)
    ]
    baseline_current_assets = [
        round(
            current_assets_only
            + max(0.0, baseline_non_inv_assets[index] - current_non_inv_assets),
            4,
        )
        for index in range(horizon)
    ]
    scenario_current_assets = [
        round(
            current_assets_only
            + max(0.0, baseline_non_inv_assets[index] - current_non_inv_assets),
            4,
        )
        for index in range(horizon)
    ]
    baseline_quick_assets = [
        round(
            quick_assets
            + max(0.0, baseline_non_inv_assets[index] - current_non_inv_assets),
            4,
        )
        for index in range(horizon)
    ]
    scenario_quick_assets = [
        round(
            quick_assets
            + max(0.0, baseline_non_inv_assets[index] - current_non_inv_assets),
            4,
        )
        for index in range(horizon)
    ]
    baseline_essential_expense = [
        round(max(0.0, effective_baseline_expenses[index] * essential_share), 4)
        for index in range(horizon)
    ]
    scenario_essential_expense = [
        round(max(0.0, scenario_expenses[index] * essential_share), 4)
        for index in range(horizon)
    ]

    def _health_point(
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
        today_ym,
        net_worth=current_assets_excluding_fixed - current_liabilities,
        current_assets_val=current_assets_only,
        quick_assets_val=quick_assets,
        current_liabilities_val=current_liabilities_only,
        essential_expense_val=current_monthly_essential_expense,
    )
    baseline_end = _health_point(
        projected_months[-1] if projected_months else today_ym,
        net_worth=(
            baseline_net_worth[-1] - current_fixed_assets
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
        projected_months[-1] if projected_months else today_ym,
        net_worth=(
            scenario_net_worth[-1] - current_fixed_assets
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

    investment_detail: list[dict] = []
    for month in detail_months:
        inv_balance = inv_bal_map.get(month)
        div_income = div_map.get(month, 0.0)
        contribution = contrib_map.get(month, 0.0)
        income_month = inv_income_map_full.get(month, 0.0)
        expense_month = inv_expense_map_full.get(month, 0.0)
        result_month = income_month - expense_month
        contribution_pct_income = (
            round(contribution / income_month * 100, 4)
            if income_month and income_month > 0
            else None
        )
        interest_pct_income = (
            round(div_income / income_month * 100, 4)
            if income_month and income_month > 0
            else None
        )
        investment_detail.append(
            {
                "month": month,
                "is_projected": False,
                "is_current_partial": month == today_ym,
                "investment_balance": (
                    round(inv_balance, 4) if inv_balance is not None else None
                ),
                "interest_total": round(div_income, 4),
                "interest_earned": round(div_income, 4),
                "interest_pct_investments": (
                    round(div_income / inv_balance * 100, 4)
                    if inv_balance and inv_balance > 0
                    else None
                ),
                "manual_contribution": round(contribution, 4),
                "contribution_pct_income": contribution_pct_income,
                "contribution_pct_result": (
                    round(contribution / result_month * 100, 4)
                    if result_month > 0
                    else None
                ),
                "total_income": round(income_month, 4),
                "total_expense": round(expense_month, 4),
                "net_result": round(result_month, 4),
                "interest_pct_income": interest_pct_income,
                "dividends": round(div_income, 4),
            }
        )
    for index, month in enumerate(projected_months):
        detail_row = projected_detail[index] if index < len(projected_detail) else {}
        projected_income_i = detail_row.get(
            "projected_income",
            scenario_income[index] if index < len(scenario_income) else 0,
        )
        projected_expense_i = detail_row.get(
            "projected_expense",
            scenario_expenses[index] if index < len(scenario_expenses) else 0,
        )
        net_result_i = detail_row.get(
            "net_result", max(0.0, projected_income_i - projected_expense_i)
        )
        interest_i = detail_row.get(
            "interest_exact",
            detail_row.get("interest_total", detail_row.get("interest", 0)),
        )
        contribution_i = detail_row.get(
            "contribution_exact", detail_row.get("contribution", 0)
        )
        series_transfer_i = detail_row.get(
            "series_transfer_exact", detail_row.get("series_transfer", 0)
        )
        opening_investment_balance = detail_row.get(
            "opening_investment_balance_exact",
            detail_row.get("opening_investment_balance", 0),
        )
        ending_investment_balance = detail_row.get(
            "ending_investment_balance_exact",
            scenario_investments[index] if index < len(scenario_investments) else None,
        )
        contribution_pct_income = (
            round(contribution_i / projected_income_i * 100, 4)
            if projected_income_i > 0
            else None
        )
        interest_pct_income = (
            round(interest_i / projected_income_i * 100, 4)
            if projected_income_i > 0
            else None
        )
        investment_detail.append(
            {
                "month": month,
                "is_projected": True,
                "investment_balance": (
                    round(ending_investment_balance, 6)
                    if ending_investment_balance is not None
                    else None
                ),
                "interest_total": round(interest_i, 6),
                "interest_earned": round(interest_i, 6),
                "interest_pct_investments": (
                    round(interest_i / opening_investment_balance * 100, 6)
                    if opening_investment_balance and opening_investment_balance > 0
                    else 0.0
                ),
                "manual_contribution": round(contribution_i, 4),
                "series_transfer": round(series_transfer_i, 4),
                "contribution_pct_income": contribution_pct_income,
                "contribution_pct_result": (
                    round(contribution_i / net_result_i * 100, 4)
                    if net_result_i > 0
                    else None
                ),
                "total_income": round(projected_income_i, 4),
                "total_expense": round(projected_expense_i, 4),
                "net_result": round(net_result_i, 4),
                "interest_pct_income": interest_pct_income,
                "dividends": round(interest_i, 6),
            }
        )

    return {
        "historical": {
            "income": [
                {
                    "month": all_hist_months[index],
                    "value": round(float(sparse_income[index]), 4),
                }
                for index in range(len(all_hist_months))
                if sparse_income[index] is not None
            ],
            "expenses": [
                {
                    "month": all_hist_months[index],
                    "value": round(float(sparse_expenses[index]), 4),
                }
                for index in range(len(all_hist_months))
                if sparse_expenses[index] is not None
            ],
            "savings": [
                {
                    "month": all_hist_months[index],
                    "value": round(
                        float(sparse_income[index]) - float(sparse_expenses[index]), 4
                    ),
                }
                for index in range(len(all_hist_months))
                if sparse_income[index] is not None
                and sparse_expenses[index] is not None
            ],
            "assets": [
                {"month": all_hist_months[index], "value": hist_assets_filled[index]}
                for index in range(len(all_hist_months))
                if hist_assets_sparse[index] is not None
            ],
            "liabilities": [
                {
                    "month": all_hist_months[index],
                    "value": hist_liabilities_filled[index],
                }
                for index in range(len(all_hist_months))
                if hist_liabilities_sparse[index] is not None
            ],
            "investments": [
                {"month": all_hist_months[index], "value": hist_inv_sparse[index]}
                for index in range(len(all_hist_months))
                if hist_inv_sparse[index] is not None
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
            "income": effective_baseline_income,
            "expenses": effective_baseline_expenses,
            "savings": effective_baseline_savings,
            "assets": baseline_assets,
            "liabilities": baseline_liabilities,
            "investments": baseline_investments,
            "returns": [
                round(row.get("interest_total", 0.0), 4)
                for row in (
                    baseline_detail
                    if has_investments
                    else [{"interest_total": 0.0}] * horizon
                )
            ],
        },
        "series_adjustment": adj,
        "current_balances": {
            "total_assets": round(current_assets, 4),
            "total_assets_excluding_fixed": round(current_assets_excluding_fixed, 4),
            "total_fixed_assets": round(current_fixed_assets, 4),
            "total_liabilities": round(current_liabilities, 4),
            "total_investments": round(current_investment_balance, 4),
        },
        "health": projected_health,
        "historical_months": all_hist_months,
        "investment_model": {
            "enabled": has_investments,
            "yield_rate": investment_model["yield_rate"],
            "contribution_rate": investment_model["contribution_rate"],
            "interest_amount": investment_model["interest_amount"],
            "contribution_amount": investment_model["contribution_amount"],
            "default_interest_percent": investment_projection_inputs[
                "default_interest_percent"
            ],
            "default_contribution_percent": investment_projection_inputs[
                "default_contribution_percent"
            ],
            "applied_interest_percent": investment_projection_inputs[
                "applied_interest_percent"
            ],
            "applied_contribution_percent": investment_projection_inputs[
                "applied_contribution_percent"
            ],
            "default_interest_amount": investment_projection_inputs[
                "default_interest_amount"
            ],
            "default_contribution_amount": investment_projection_inputs[
                "default_contribution_amount"
            ],
            "applied_interest_amount": investment_projection_inputs[
                "applied_interest_amount"
            ],
            "applied_contribution_amount": investment_projection_inputs[
                "applied_contribution_amount"
            ],
            "applied_yield_rate": investment_projection_inputs["applied_yield_rate"],
            "applied_contribution_rate": investment_projection_inputs[
                "applied_contribution_rate"
            ],
            "has_overrides": investment_projection_inputs["has_overrides"],
            "interest_slider": interest_slider,
            "contribution_slider": contribution_slider,
            "sample_count": investment_model["sample_count"],
            "contrib_sample_count": investment_model["contrib_sample_count"],
            "yield_excluded": investment_model["yield_excluded"],
            "contrib_excluded": investment_model["contrib_excluded"],
            "warnings": investment_model["warnings"],
            "stat": investment_stat,
            "include_current_month": investment_include_current_month,
            "exclude_outliers": investment_exclude_outliers,
            "outlier_k": investment_outlier_k,
            "lookback_months": inv_lookback,
        },
        "investment_detail": investment_detail,
    }


__all__ = ["build_projections"]
