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
