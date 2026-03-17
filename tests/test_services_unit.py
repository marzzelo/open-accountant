import app_config

import pytest

from database import get_db, init_db
from models import AccountIn, SubtypeIn, SubtypeUpdate, TransactionIn
from services import (
    about_service,
    accounts_service,
    books_service,
    reports_service,
    settings_service,
    subtypes_service,
    transactions_service,
    types_service,
)
from services.errors import ConflictError, NotFoundError, ValidationError


@pytest.fixture()
def initialized_environment(isolated_paths):
    app_config.load()
    init_db()
    return isolated_paths


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
                "finance_usd_official_buy_ars": "1234.00",
                "finance_usd_blue_sell_ars": "1500.00",
            },
        )
        assert updated["preferences"] == {"show_zero_balance_accounts": True}
        assert settings_service.get_preferences(conn) == {
            "show_zero_balance_accounts": True
        }

    config = settings_service.get_config()
    assert config["general"]["port"] == "6001"
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


def test_books_service_create_backup_import_select_rename_and_delete(
    initialized_environment,
):
    created = books_service.create_book("biz 2026", basic_seed=False)
    assert created == {"ok": True, "name": "biz2026"}

    backup = books_service.backup_book("home")
    assert "CREATE TABLE accounts" in backup

    imported = books_service.import_book_from_sql("clone", backup.encode("utf-8"))
    assert imported == {"ok": True, "name": "clone"}

    selected = books_service.select_book("biz2026")
    assert selected == {"ok": True, "current": "biz2026"}

    renamed = books_service.rename_book("clone", "archive")
    assert renamed == {"ok": True, "name": "archive"}

    assert books_service.delete_book("archive") == {"ok": True}
    books = books_service.list_books()
    assert any(item["name"] == "biz2026" and item["current"] for item in books)
    assert all(item["name"] != "archive" for item in books)


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

        balance_sheet = reports_service.get_balance(conn)
        assert balance_sheet.total_activo == 200.0
        assert balance_sheet.total_ingreso == 200.0
        assert balance_sheet.equation_check == 0.0


def test_types_service_get_type_raises_for_missing_id(initialized_environment):
    with get_db() as conn:
        with pytest.raises(NotFoundError):
            types_service.get_type(conn, 999)
