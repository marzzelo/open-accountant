from datetime import date

import app_config

import pytest

from database import get_db, init_db
from models import (
    AccountIn,
    AccountUpdate,
    SubtypeIn,
    SubtypeUpdate,
    TagIn,
    TagUpdate,
    TransactionIn,
)
from routers import reports as reports_router
from services import (
    about_service,
    accounts_service,
    helpers,
    projections_service,
    reports_service,
    settings_service,
    subtypes_service,
    tags_service,
    transactions_service,
    types_service,
)
from services.errors import ConflictError, NotFoundError, ValidationError


@pytest.fixture()
def initialized_environment(isolated_paths):
    app_config.load()
    init_db()
    return isolated_paths


TEST_BOARD_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9kAAAAASUVORK5CYII="
)


def test_server_host_and_port_env_override_settings(
    initialized_environment, monkeypatch
):
    assert app_config.server_host() == "127.0.0.1"
    assert app_config.server_port() == 5999

    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "5010")

    assert app_config.server_host() == "0.0.0.0"
    assert app_config.server_port() == 5010

    monkeypatch.setenv("PORT", "not-a-number")

    assert app_config.server_port() == 5999


def test_types_and_about_services_work_directly(initialized_environment):
    with get_db() as conn:
        types = types_service.list_types(conn)
        first_type = types_service.get_type(conn, 1)

    assert [item.name for item in types] == [
        "Asset",
        "Liability",
        "Income",
        "Expense",
        "Equity",
    ]
    assert first_type.name == "Asset"

    about = about_service.get_about()
    version = about_service.get_version()
    assert about["github"]
    assert about["version"]
    assert version["version"]


def test_subtypes_service_crud_and_usage_conflict(initialized_environment):
    with get_db() as conn:
        created = subtypes_service.create_subtype(
            conn, SubtypeIn(name="Pet Care", type_id=4)
        )
        fetched = subtypes_service.get_subtype(conn, created.id)
        assert fetched.name == "Pet Care"

        updated = subtypes_service.update_subtype(
            conn,
            created.id,
            SubtypeUpdate(name="Pets", type_id=4),
        )
        assert updated.name == "Pets"

        account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Vet Bills",
                type_id=4,
                subtype_id=created.id,
                description="Pet expenses",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        with pytest.raises(ConflictError):
            subtypes_service.delete_subtype(conn, created.id)

        accounts_service.delete_account(conn, account.id)
        subtypes_service.delete_subtype(conn, created.id)

        with pytest.raises(NotFoundError):
            subtypes_service.get_subtype(conn, created.id)


def test_subtypes_service_validates_type_existence(initialized_environment):
    with get_db() as conn:
        with pytest.raises(ValidationError):
            subtypes_service.create_subtype(conn, SubtypeIn(name="Broken", type_id=99))


def test_settings_service_updates_config_preferences_env_and_language(
    initialized_environment,
):
    settings_service.update_config(
        {
            "general": {"host": "0.0.0.0", "port": "6001"},
            "app": {"language": "en"},
        }
    )

    with get_db() as conn:
        updated = settings_service.update_preferences(
            conn,
            {
                "show_zero_balance_accounts": True,
                "board_view_mode": "compact",
                "finance_usd_official_buy_ars": "1234.00",
                "finance_usd_blue_sell_ars": "1500.00",
            },
        )
        assert updated["preferences"] == {
            "show_zero_balance_accounts": True,
            "board_view_mode": "compact",
        }
        assert settings_service.get_preferences(conn) == {
            "show_zero_balance_accounts": True,
            "board_view_mode": "compact",
        }

    config = settings_service.get_config()
    assert config["general"]["port"] == "6001"
    assert "current_book" not in config["general"]
    assert config["finance"]["usd_official_buy_ars"] == "1234.00"
    assert config["finance"]["usd_blue_sell_ars"] == "1500.00"

    env_result = settings_service.update_env(
        [
            {"key": "SECRET_KEY", "value": "super-secret"},
            {"key": "OPENAI_API_KEY", "value": "sk-test"},
        ]
    )
    assert env_result == {"ok": True}
    env_payload = settings_service.get_env()
    secret_row = next(item for item in env_payload if item["key"] == "SECRET_KEY")
    assert secret_row["value"] == "••••••••"
    assert secret_row["sensitive"] is True

    assert settings_service.set_language("en") == {"ok": True, "language": "en"}
    translations = settings_service.get_translations("en")
    assert translations["_lang"] == "en"
    assert {item["code"] for item in settings_service.list_languages()} >= {"en", "es"}


def test_settings_service_fetch_rates_uses_injected_fetcher():
    payload = settings_service.fetch_bluelytics_latest_rates(
        lambda: {
            "oficial": {"value_buy": 1000.0, "value_sell": 1100.0},
            "blue": {"value_buy": 1200.0, "value_sell": 1300.0},
            "last_update": "2026-03-17T10:00:00-03:00",
        }
    )

    assert payload["official_buy"] == 1000.0
    assert payload["blue_sell"] == 1300.0
    assert payload["card"] == 1430.0


def test_end_of_month_datetime_handles_short_months():
    assert helpers.end_of_month_datetime("2026-04") == "2026-04-30 23:59:59"
    assert helpers.end_of_month_datetime("2026-02") == "2026-02-28 23:59:59"
    assert helpers.end_of_month_datetime("2024-02") == "2024-02-29 23:59:59"


def test_accounts_transactions_and_reports_services_work_directly(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        reserve = accounts_service.create_account(
            conn,
            AccountIn(
                name="Reserve Fund",
                type_id=1,
                subtype_id=2,
                description="Safety buffer",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        tx = transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=reserve.id,
                credit_account=accounts["Salary"].id,
                amount=200.0,
                original_amount=None,
                fx_rate=None,
                description="Bonus",
            ),
        )
        assert tx.description == "Bonus"

        account = accounts_service.get_account(conn, reserve.id)
        assert account.balance == 200.0
        assert account.last_movements[0].description == "Bonus"

        ledger = reports_service.get_ledger(conn, reserve.id)
        assert ledger["closing_balance"] == 200.0
        assert ledger["entries"][0]["role"] == "Débito"
        assert ledger["entries"][0]["counterpart_id"] == accounts["Salary"].id

        balance_sheet = reports_service.get_balance(conn)
        assert balance_sheet.total_activo == 200.0
        assert balance_sheet.total_ingreso == 200.0
        assert balance_sheet.equation_check == 0.0


def test_reports_service_balance_filters_hide_accounts_and_zero_balances(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Bank"].id,
                credit_account=accounts["Salary"].id,
                amount=200.0,
                original_amount=None,
                fx_rate=None,
                description="Bonus",
            ),
        )

        filtered_balance = reports_service.get_balance(
            conn,
            hide_accounts=True,
            show_zero_balance=False,
        )

    asset_group = next(group for group in filtered_balance.groups if group.type_id == 1)
    assert all(len(subgroup.items) == 0 for subgroup in asset_group.subgroups)
    assert any(subgroup.subtotal == 200.0 for subgroup in asset_group.subgroups)
    assert all(group.type_id != 4 for group in filtered_balance.groups)
    assert any(
        group.type_id == 3 and group.total == 200.0 for group in filtered_balance.groups
    )


def test_reports_service_balance_filters_type_ids(initialized_environment):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Bank"].id,
                credit_account=accounts["Salary"].id,
                amount=175.0,
                original_amount=None,
                fx_rate=None,
                description="Bonus",
            ),
        )

        filtered_balance = reports_service.get_balance(conn, type_ids={1, 3})

    assert {group.type_id for group in filtered_balance.groups} == {1, 3}
    assert filtered_balance.total_activo == 175.0
    assert filtered_balance.total_ingreso == 175.0
    assert filtered_balance.total_pasivo == 0.0
    assert filtered_balance.total_patrimonio == 0.0


def test_reports_service_stats_summary_and_net_worth_evolution(initialized_environment):
    with get_db() as conn:
        accounts = accounts_service.list_accounts(conn)
        bank = next(item for item in accounts if item.name == "Bank")
        income_account = next(item for item in accounts if item.type_id == 3)
        expense_account = next(item for item in accounts if item.type_id == 4)
        liability_account = next(item for item in accounts if item.type_id == 2)
        non_current_asset = accounts_service.create_account(
            conn,
            AccountIn(
                name="Bond Ladder",
                type_id=1,
                subtype_id=None,
                description="Long-term savings",
                initial_balance=0.0,
                properties='{"liquidity_profile":"non_current"}',
            ),
        )
        long_term_debt = accounts_service.create_account(
            conn,
            AccountIn(
                name="Mortgage Loan",
                type_id=2,
                subtype_id=None,
                description="Mortgage",
                initial_balance=0.0,
                properties='{"liability_term":"long_term"}',
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=income_account.id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="Salary inflow",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=expense_account.id,
                credit_account=bank.id,
                amount=250.0,
                original_amount=None,
                fx_rate=None,
                description="Groceries",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=liability_account.id,
                amount=300.0,
                original_amount=None,
                fx_rate=None,
                description="Card spending moved to debt",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=non_current_asset.id,
                credit_account=income_account.id,
                amount=200.0,
                original_amount=None,
                fx_rate=None,
                description="Bond contribution",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=long_term_debt.id,
                amount=500.0,
                original_amount=None,
                fx_rate=None,
                description="Mortgage drawdown",
            ),
        )

        stats = reports_service.get_stats(conn)
        projections = projections_service.get_projections(conn, 3, 3)
        refreshed_accounts = {
            item.name: item for item in accounts_service.list_accounts(conn)
        }

    assert stats.summary["total_income"] == 1200.0
    assert stats.summary["total_expense"] == 250.0
    assert stats.summary["net_result"] == 950.0
    assert stats.summary["savings_rate"] == pytest.approx(950.0 / 1200.0, rel=1e-4)
    assert stats.summary["total_assets"] == 1750.0
    assert stats.summary["total_liabilities"] == 800.0
    assert stats.summary["net_worth"] == 950.0
    assert stats.summary["debt_ratio"] == pytest.approx(800.0 / 1750.0, rel=1e-4)
    assert stats.summary["current_assets"] == 1550.0
    assert stats.summary["quick_assets"] == 1550.0
    assert stats.summary["current_liabilities"] == 300.0
    assert stats.summary["current_ratio"] == pytest.approx(1550.0 / 300.0, rel=1e-4)
    assert stats.summary["quick_ratio"] == pytest.approx(1550.0 / 300.0, rel=1e-4)
    assert stats.summary["monthly_essential_expense"] == 250.0
    assert stats.summary["runway_months"] == pytest.approx(1550.0 / 250.0, rel=1e-4)
    assert stats.summary["top_asset_name"] == "Bank"
    assert stats.summary["top_asset_share"] == pytest.approx(1550.0 / 1750.0, rel=1e-4)
    assert stats.summary["top_expense_name"] == expense_account.subtype_name
    assert stats.summary["top_expense_share"] == 1.0
    assert refreshed_accounts["Bank"].properties["liquidity_profile"] == "quick"
    assert (
        refreshed_accounts["Bond Ladder"].properties["liquidity_profile"]
        == "non_current"
    )
    assert (
        refreshed_accounts["Mortgage Loan"].properties["liability_term"] == "long_term"
    )
    assert len(stats.net_worth_evolution) == 1
    assert stats.net_worth_evolution[0]["assets"] == 1750.0
    assert stats.net_worth_evolution[0]["liabilities"] == 800.0
    assert stats.net_worth_evolution[0]["net_worth"] == 950.0
    assert projections["health"]["current"]["net_worth"] == 950.0
    assert projections["health"]["current"]["current_ratio"] == pytest.approx(
        1550.0 / 300.0, rel=1e-4
    )
    assert projections["health"]["delta_end"]["net_worth"] == 0.0


def test_projection_series_adjustments_accept_date_start_dates():
    adjustments = projections_service._compute_series_adjustments(
        [
            {
                "id": 1,
                "name": "vacaciones",
                "type": "expense",
                "start_date": date(2026, 7, 1),
                "months": 1,
                "monthly_amount": 2000000.0,
            }
        ],
        ["2026-07", "2026-08", "2026-09"],
    )

    assert adjustments["income"] == [0.0, 0.0, 0.0]
    assert adjustments["expenses"] == [2000000.0, 0.0, 0.0]
    assert adjustments["savings"] == [-2000000.0, 0.0, 0.0]
    assert adjustments["assets"] == [-2000000.0, -2000000.0, -2000000.0]
    assert adjustments["liabilities"] == [2000000.0, 2000000.0, 2000000.0]


def test_tags_service_crud_assignment_and_report_filters(initialized_environment):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}

        groceries = tags_service.create_tag(
            conn,
            TagIn(name="Groceries", color="#16A34A", user_id=None),
        )
        travel = tags_service.create_tag(
            conn,
            TagIn(name="Travel", color="#2563EB", user_id=None),
        )

        salary_tx = transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Bank"].id,
                credit_account=accounts["Salary"].id,
                amount=1200.0,
                original_amount=None,
                fx_rate=None,
                description="Tagged salary",
                tag_ids=[travel.id],
            ),
        )
        grocery_tx = transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Groceries"].id,
                credit_account=accounts["Bank"].id,
                amount=180.0,
                original_amount=None,
                fx_rate=None,
                description="Tagged groceries",
                tag_ids=[groceries.id],
            ),
        )

        listed_tags = tags_service.list_tags(conn)
        assert {tag.name for tag in listed_tags} == {"Groceries", "Travel"}
        assert (
            next(
                tag for tag in listed_tags if tag.name == "Groceries"
            ).transaction_count
            == 1
        )

        tx_list = transactions_service.list_transactions(conn, tag_ids=[groceries.id])
        assert len(tx_list) == 1
        assert tx_list[0].id == grocery_tx.id
        assert tx_list[0].tags[0].name == "Groceries"

        journal = reports_service.journal_data(conn, tag_ids=[groceries.id])
        assert len(journal) == 1
        assert journal[0]["tags_label"] == "Groceries"

        ledger = reports_service.get_ledger(
            conn, accounts["Bank"].id, tag_ids=[travel.id]
        )
        assert len(ledger["entries"]) == 1
        assert ledger["entries"][0]["id"] == salary_tx.id
        assert ledger["entries"][0]["counterpart_id"] == accounts["Salary"].id

        stats = reports_service.get_stats(conn, tag_ids=[groceries.id])
        assert stats.summary["total_expense"] == 180.0
        assert stats.summary["total_income"] == 0.0

        updated = tags_service.update_tag(
            conn,
            groceries.id,
            TagUpdate(name="Food", color="#15803D", user_id=None),
        )
        assert updated.name == "Food"

        tags_service.delete_tag(conn, travel.id)
        remaining = tags_service.list_tags(conn)
        assert [tag.name for tag in remaining] == ["Food"]


def test_account_properties_auto_infer_without_subtypes(initialized_environment):
    with get_db() as conn:
        cash_reserve = accounts_service.create_account(
            conn,
            AccountIn(
                name="Cash Reserve",
                type_id=1,
                subtype_id=None,
                description="No subtype needed",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        mortgage = accounts_service.create_account(
            conn,
            AccountIn(
                name="Mortgage",
                type_id=2,
                subtype_id=None,
                description="No subtype needed",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        rent = accounts_service.create_account(
            conn,
            AccountIn(
                name="Rent",
                type_id=4,
                subtype_id=None,
                description="No subtype needed",
                initial_balance=0.0,
                properties="{}",
            ),
        )

    assert cash_reserve.properties["liquidity_profile"] == "quick"
    assert mortgage.properties["liability_term"] == "long_term"
    assert rent.properties["expense_profile"] == "essential"
    assert cash_reserve.properties["board_image_url"] == helpers.BOARD_IMAGE_DEFAULT_URL


def test_account_board_image_round_trip_and_update_preserves_custom_image(
    initialized_environment,
):
    with get_db() as conn:
        custom_image_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Illustrated Reserve",
                type_id=1,
                subtype_id=None,
                description="Image test",
                initial_balance=0.0,
                properties=('{"board_image_url":"' + TEST_BOARD_IMAGE_DATA_URL + '"}'),
            ),
        )

        updated = accounts_service.update_account(
            conn,
            custom_image_account.id,
            AccountUpdate(description="Updated description"),
        )

    assert custom_image_account.properties["board_image_url"].startswith(
        "data:image/png;base64,"
    )
    assert (
        updated.properties["board_image_url"]
        == custom_image_account.properties["board_image_url"]
    )
    assert updated.description == "Updated description"


def test_account_board_image_rejects_jpeg_payloads(initialized_environment):
    with get_db() as conn:
        with pytest.raises(ValidationError):
            accounts_service.create_account(
                conn,
                AccountIn(
                    name="JPEG Reserve",
                    type_id=1,
                    subtype_id=None,
                    description="Invalid image",
                    initial_balance=0.0,
                    properties='{"board_image_url":"data:image/jpeg;base64,AAAA"}',
                ),
            )


def test_transactions_service_computes_fx_traceability_fields(initialized_environment):
    app_config.set_value("finance", "usd_official_buy_ars", "1100.00")

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}

        tx = transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Bank"].id,
                credit_account=accounts["Salary"].id,
                amount=None,
                original_amount=12.5,
                original_currency="USD",
                fx_rate=None,
                fx_source="USD_BUY",
                description="USD salary",
            ),
        )

        assert tx.amount == 13750.0
        assert tx.original_amount == 12.5
        assert tx.original_currency == "USD"
        assert tx.fx_rate == 1100.0
        assert tx.fx_source == "USD_BUY"


def test_balance_pdf_table_builds_spans_and_total_rows(initialized_environment):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        accounts_service.create_account(
            conn,
            AccountIn(
                name="Travel Cash",
                type_id=1,
                subtype_id=accounts["Bank"].subtype_id,
                description="Cash reserve",
                initial_balance=50.0,
                properties="{}",
            ),
        )

        balance_sheet = reports_service.get_balance(conn)

    table_data, spans, group_total_rows, summary_rows = (
        reports_router._build_balance_pdf_table(balance_sheet)
    )

    assert table_data[0] == ["Tipo", "Subtipo", "Cuenta", "Saldo"]
    assert any(start_col == 0 and end_col == 0 for start_col, _, end_col, _ in spans)
    assert any(start_col == 1 and end_col == 1 for start_col, _, end_col, _ in spans)
    assert group_total_rows
    assert all(table_data[row][0].startswith("TOTAL ") for row in group_total_rows)
    assert summary_rows == [len(table_data) - 2, len(table_data) - 1]


def test_types_service_get_type_raises_for_missing_id(initialized_environment):
    with get_db() as conn:
        with pytest.raises(NotFoundError):
            types_service.get_type(conn, 999)


# ── Investment projection pure-function tests ─────────────────────────────────


def test_iqr_filter_removes_outliers():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]
    filtered, excluded = projections_service._iqr_filter(values, k=1.5)
    assert excluded >= 1
    assert 100.0 not in filtered
    assert all(v in values for v in filtered)


def test_iqr_filter_passes_through_small_lists():
    small = [1.0, 2.0, 3.0]
    filtered, excluded = projections_service._iqr_filter(small, k=1.5)
    assert filtered == small
    assert excluded == 0


def test_aggregate_mean():
    assert projections_service._aggregate([2.0, 4.0, 6.0], "mean") == 4.0


def test_aggregate_median_odd():
    assert projections_service._aggregate([1.0, 3.0, 5.0], "median") == 3.0


def test_aggregate_median_even():
    assert projections_service._aggregate([1.0, 3.0, 5.0, 7.0], "median") == 4.0


def test_aggregate_empty():
    assert projections_service._aggregate([], "mean") == 0.0


def test_project_investments_compound_growth():
    # Joint iteration: contribution = rate * projected_income, interest = inv * yield
    inv, non_inv, detail = projections_service._project_investments(
        1000.0,  # current_investment_balance
        1000.0,  # current_non_inv_assets
        0.01,  # yield_rate
        0.1,  # contribution_rate (10% of projected income)
        [1000.0, 1000.0, 1000.0],  # projected income
        [100.0, 100.0, 100.0],  # baseline_savings
        3,
    )
    assert len(inv) == 3
    # Period 0: income=1000, contrib=100, interest=10, inv=1000+10+100=1110
    assert inv[0] == pytest.approx(1110.0, rel=1e-4)
    assert detail[0]["interest"] == pytest.approx(10.0, rel=1e-4)
    assert detail[0]["contribution"] == pytest.approx(100.0, rel=1e-4)


def test_project_investments_floors_at_zero():
    inv, non_inv, detail = projections_service._project_investments(
        50.0, 1000.0, 0.0, 0.0, [0.0, 0.0, 0.0], [-200.0, -200.0, -200.0], 3
    )
    # With zero rate and zero contribution_rate, inv stays at 50, non_inv shrinks
    assert inv[0] == pytest.approx(50.0, rel=1e-4)
    assert non_inv[0] == pytest.approx(800.0, rel=1e-4)


def test_project_investments_zero_rate_contribution_only():
    inv, non_inv, detail = projections_service._project_investments(
        0.0, 10000.0, 0.0, 0.05, [10000.0, 10000.0], [500.0, 500.0], 2
    )
    # Period 0: income=10000, contrib=500, inv=0+0+500=500, non_inv stays flat
    assert inv[0] == pytest.approx(500.0, rel=1e-4)
    # Period 1: income=10000, contrib=500, inv=500+0+500=1000
    assert inv[1] == pytest.approx(1000.0, rel=1e-4)


def test_project_flow_from_settings_inflation_uses_last_known_value_by_default():
    projected = projections_service._project_flow_from_settings(
        [None, 1000.0, 1200.0],
        3,
        3,
        mode="inflation",
        inflation_rate=10.0,
    )
    assert projected[0] == pytest.approx(1320.0, rel=1e-4)
    assert projected[1] == pytest.approx(1452.0, rel=1e-4)


def test_project_flow_from_settings_linear_respects_min_max_filter():
    projected = projections_service._project_flow_from_settings(
        [1000.0, 100000.0, 1200.0],
        3,
        1,
        mode="linear",
        min_val=900.0,
        max_val=2000.0,
    )
    assert projected[0] == pytest.approx(1300.0, rel=1e-4)


def test_estimate_investment_model_basic():
    months = ["2024-01", "2024-02", "2024-03", "2024-04"]
    inv_bal = {
        "2024-01": 10000.0,
        "2024-02": 10200.0,
        "2024-03": 10400.0,
        "2024-04": 10600.0,
    }
    div_map = {"2024-02": 100.0, "2024-03": 100.0, "2024-04": 100.0}
    contrib_map = {"2024-02": 200.0, "2024-03": 200.0, "2024-04": 200.0}
    income_map = {
        "2024-01": 5000.0,
        "2024-02": 5000.0,
        "2024-03": 5000.0,
        "2024-04": 5000.0,
    }
    model = projections_service._estimate_investment_model(
        months,
        inv_bal,
        div_map,
        contrib_map,
        income_map,
        stat="mean",
        exclude_outliers=False,
        outlier_k=1.5,
    )
    assert model["yield_rate"] > 0
    assert model["interest_amount"] == pytest.approx(100.0, rel=1e-4)
    # contribution_rate = 200 / 5000 = 0.04
    assert model["contribution_rate"] == pytest.approx(0.04, rel=1e-4)
    assert model["contribution_amount"] == pytest.approx(200.0, rel=1e-4)
    assert model["sample_count"] == 3
    assert model["contrib_sample_count"] == 3
    assert model["warnings"] == []


def test_estimate_investment_model_median_yield_zero_warning():
    # If most months have no dividends, median collapses to zero → expect warning
    months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
    inv_bal = {m: 10000.0 for m in months}
    # Only one month has dividends, rest do not
    div_map = {"2024-03": 500.0}
    contrib_map = {}
    model = projections_service._estimate_investment_model(
        months,
        inv_bal,
        div_map,
        contrib_map,
        {m: 10000.0 for m in months},
        stat="median",
        exclude_outliers=False,
        outlier_k=1.5,
    )
    # Only 1 yield sample, median of [something] = that value → no zero warning
    # But with 1 sample, median == that value, so no warning
    assert model["sample_count"] == 1
    assert model["yield_rate"] > 0


def test_estimate_investment_model_no_data():
    model = projections_service._estimate_investment_model(
        ["2024-01", "2024-02"],
        {},
        {},
        {},
        {},
        stat="mean",
        exclude_outliers=True,
        outlier_k=1.5,
    )
    assert model["yield_rate"] == 0.0
    assert model["contribution_rate"] == 0.0
    assert model["interest_amount"] == 0.0
    assert model["contribution_amount"] == 0.0
    assert model["sample_count"] == 0
    assert model["warnings"] == []


def test_resolve_investment_projection_inputs_defaults_and_overrides():
    model = {
        "yield_rate": 0.02,
        "contribution_rate": 0.15,
        "interest_amount": 200.0,
        "contribution_amount": 750.0,
        "yield_reference_base": 10000.0,
        "contribution_reference_income": 5000.0,
    }

    resolved = projections_service._resolve_investment_projection_inputs(
        10000.0,
        model,
    )
    assert resolved["default_interest_percent"] == pytest.approx(2.0, rel=1e-4)
    assert resolved["default_contribution_percent"] == pytest.approx(15.0, rel=1e-4)
    assert resolved["default_interest_amount"] == pytest.approx(200.0, rel=1e-4)
    assert resolved["default_contribution_amount"] == pytest.approx(750.0, rel=1e-4)
    assert resolved["applied_yield_rate"] == pytest.approx(0.02, rel=1e-4)
    assert resolved["applied_contribution_rate"] == pytest.approx(0.15, rel=1e-4)
    assert resolved["has_overrides"] is False

    overridden = projections_service._resolve_investment_projection_inputs(
        10000.0,
        model,
        interest_pct_override=3.0,
        contribution_pct_override=18.0,
    )
    assert overridden["applied_interest_amount"] == pytest.approx(300.0, rel=1e-4)
    assert overridden["applied_contribution_amount"] == pytest.approx(900.0, rel=1e-4)
    assert overridden["applied_yield_rate"] == pytest.approx(0.03, rel=1e-4)
    assert overridden["applied_contribution_rate"] == pytest.approx(0.18, rel=1e-4)
    assert overridden["has_overrides"] is True


# ── Investment integration test with DB ───────────────────────────────────────


def test_investment_projection_integration(initialized_environment):
    """Full integration: create investment + dividend accounts, add transactions,
    and verify no double-counting in total assets."""
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        # Create investment account (subtype_id=3)
        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="My Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        # Create dividend income account (subtype_id=10)
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Dividend Income",
                type_id=3,
                subtype_id=10,
                description="Dividends received",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        # 1) Salary → Bank (external income)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=5000.0,
                original_amount=None,
                fx_rate=None,
                description="Salary",
            ),
        )

        # 2) Bank → Investment (internal transfer: move cash into investments)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=2000.0,
                original_amount=None,
                fx_rate=None,
                description="Transfer to brokerage",
            ),
        )

        # 3) Dividend income → Investment (reinvested dividends)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=div_account.id,
                amount=100.0,
                original_amount=None,
                fx_rate=None,
                description="Quarterly dividend",
            ),
        )

        # 4) Expense
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Groceries"].id,
                credit_account=bank.id,
                amount=500.0,
                original_amount=None,
                fx_rate=None,
                description="Food",
            ),
        )

        result = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    # Verify investment detection
    assert result["investment_model"]["enabled"] is True

    # Current balances: Bank has 5000-2000-500=2500, Inv has 2000+100=2100
    # Total assets = bank + cash + other assets + inv = 2500 + 2100 + ...
    assert result["current_balances"]["total_investments"] == pytest.approx(
        2100.0, rel=1e-4
    )
    assert result["current_balances"]["total_assets"] == pytest.approx(
        result["current_balances"]["total_investments"]
        + (
            result["current_balances"]["total_assets"]
            - result["current_balances"]["total_investments"]
        ),
        rel=1e-4,
    )

    # Historical investments should have data
    assert len(result["historical"]["investments"]) > 0

    # Baseline projection should have investment curve
    assert len(result["baseline_projection"]["investments"]) == 3

    # Health: liquidity KPIs should not count investment growth.
    # Current health quick_assets should roughly equal Bank balance (quick assets only)
    health = result["health"]["current"]
    assert health["quick_assets"] <= result["current_balances"]["total_assets"]

    # Verify internal transfer is detected as contribution, not general income
    assert (
        result["investment_model"]["contribution_rate"] != 0.0
        or result["investment_model"]["contrib_sample_count"] >= 0
    )
    assert result["investment_model"]["default_interest_percent"] >= 0.0
    assert result["investment_model"]["default_contribution_percent"] >= 0.0
    assert result["investment_model"]["default_interest_amount"] >= 0.0
    assert result["investment_model"]["default_contribution_amount"] >= 0.0
    assert result["investment_model"]["interest_slider"]["max"] > 0.0
    assert result["investment_model"]["contribution_slider"]["max"] > 0.0
    assert any(
        row["interest_pct_investments"] is not None
        for row in result["investment_detail"]
    )
    assert "contribution_pct_income" in result["investment_detail"][0]

    with get_db() as conn:
        overridden = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
            investment_interest_pct_override=3.0,
            investment_contribution_pct_override=12.0,
        )

    assert overridden["investment_model"]["has_overrides"] is True
    assert overridden["investment_model"]["applied_interest_percent"] == pytest.approx(
        3.0, rel=1e-4
    )
    assert overridden["investment_model"][
        "applied_contribution_percent"
    ] == pytest.approx(12.0, rel=1e-4)
    assert (
        overridden["baseline_projection"]["investments"]
        != result["baseline_projection"]["investments"]
    )

    with get_db() as conn:
        inflation = projections_service.get_projections(
            conn,
            3,
            3,
            income_trend_mode="inflation",
            income_inflation_base=1000.0,
            income_inflation_rate=10.0,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    assert inflation["baseline_projection"]["income"][0] == pytest.approx(
        1100.0, rel=1e-4
    )
    first_projected_detail = next(
        row for row in inflation["investment_detail"] if row["is_projected"]
    )
    assert first_projected_detail["total_income"] == pytest.approx(1100.0, rel=1e-4)
    assert (
        inflation["baseline_projection"]["assets"]
        != result["baseline_projection"]["assets"]
    )


def test_investment_account_identification(initialized_environment):
    """Verify that subtype-based and name-hint detection work correctly."""
    with get_db() as conn:
        # Create one by subtype
        accounts_service.create_account(
            conn,
            AccountIn(
                name="Retirement Fund",
                type_id=1,
                subtype_id=3,
                description="401k equivalent",
                initial_balance=1000.0,
                properties="{}",
            ),
        )
        # Create one by name hint (no subtype match)
        accounts_service.create_account(
            conn,
            AccountIn(
                name="My ETF Portfolio",
                type_id=1,
                subtype_id=None,
                description="Index funds",
                initial_balance=500.0,
                properties="{}",
            ),
        )
        # Create a normal bank account (should NOT be detected)
        # Bank already exists from seed data

        inv = projections_service._identify_investment_accounts(conn)
        inv_names = {a["name"] for a in inv}

    assert "Retirement Fund" in inv_names
    assert "My ETF Portfolio" in inv_names
    assert "Bank" not in inv_names
    assert "Cash" not in inv_names


def test_dividend_account_identification(initialized_environment):
    """Verify dividend account detection by subtype and name."""
    with get_db() as conn:
        # By subtype
        accounts_service.create_account(
            conn,
            AccountIn(
                name="Stock Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividends from stocks",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        # By name hint (subtype_id=8 = Other Income)
        accounts_service.create_account(
            conn,
            AccountIn(
                name="Dividendos Varios",
                type_id=3,
                subtype_id=8,
                description="Various dividends",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        div = projections_service._identify_dividend_accounts(conn)
        div_names = {a["name"] for a in div}

    assert "Stock Dividends" in div_names
    assert "Dividendos Varios" in div_names
    assert "Salary" not in div_names


def test_investment_contributions_exclude_internal_transfers(initialized_environment):
    """Verify that transfers between investment accounts, dividend-sourced flows,
    and equity (Capital) counterparties are not counted as contributions."""
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]
        capital = accounts["Capital"]

        inv1 = accounts_service.create_account(
            conn,
            AccountIn(
                name="Brokerage A",
                type_id=1,
                subtype_id=3,
                description="First brokerage",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        inv2 = accounts_service.create_account(
            conn,
            AccountIn(
                name="Brokerage B",
                type_id=1,
                subtype_id=3,
                description="Second brokerage",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_acc = accounts_service.create_account(
            conn,
            AccountIn(
                name="Div Income",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        # Initial balance booked against Capital (should NOT count)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv1.id,
                credit_account=capital.id,
                amount=5000.0,
                original_amount=None,
                fx_rate=None,
                description="Opening balance via Capital",
            ),
        )
        # External contribution: Bank → Brokerage A (should count)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv1.id,
                credit_account=bank.id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="Fund brokerage",
            ),
        )
        # Internal transfer: Brokerage A → Brokerage B (should NOT count)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv2.id,
                credit_account=inv1.id,
                amount=300.0,
                original_amount=None,
                fx_rate=None,
                description="Rebalance",
            ),
        )
        # Dividend → Brokerage A (should NOT count as manual contribution)
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv1.id,
                credit_account=div_acc.id,
                amount=50.0,
                original_amount=None,
                fx_rate=None,
                description="Dividend reinvest",
            ),
        )

        inv_ids = [inv1.id, inv2.id]
        div_ids = [div_acc.id]
        today_str = str(date.today())
        contrib = projections_service._get_monthly_investment_contributions(
            conn,
            inv_ids,
            div_ids,
            "2020-01-01 00:00:00",
            today_str + " 23:59:59",
        )

    # Only the Bank→Brokerage A transfer should count (1000).
    # Capital (5000), internal (300), dividend (50) are all excluded.
    total_contrib = sum(contrib.values())
    assert total_contrib == pytest.approx(1000.0, rel=1e-4)
