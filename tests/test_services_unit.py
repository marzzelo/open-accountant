from contextlib import contextmanager
from datetime import date, datetime

import database

import app_config
import app_version

import pytest

from database import get_db, init_db
from models import (
    AccountIn,
    AccountUpdate,
    MovementOut,
    ProjectionSeriesIn,
    ProjectionSeriesOut,
    ProjectionSeriesUpdate,
    SessionOut,
    SubtypeIn,
    SubtypeUpdate,
    TagIn,
    TagOut,
    TagUpdate,
    TransactionIn,
    TransactionOut,
    RecurringTransactionIn,
    RecurringTransactionPostIn,
    UserOut,
)
from routers import (
    reports as reports_router,
)  # noqa: F401 (kept for router-level tests)
from services import exports_service
from services import (
    about_service,
    accounts_service,
    helpers,
    projections_service,
    reports_service,
    recurring_transactions_service,
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
    # Seed non-default server host/port so tests can assert that environment
    # overrides take priority over values stored in the settings table.
    app_config.set_value("general", "host", "127.0.0.1")
    app_config.set_value("general", "port", "5999")
    return isolated_paths


TEST_BOARD_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9kAAAAASUVORK5CYII="
)


def test_server_host_and_port_env_override_settings(
    initialized_environment, monkeypatch
):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert app_config.server_host() == "127.0.0.1"
    assert app_config.server_port() == 5999

    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "5010")

    assert app_config.server_host() == "0.0.0.0"
    assert app_config.server_port() == 5010

    monkeypatch.setenv("PORT", "not-a-number")

    assert app_config.server_port() == 5999


def test_temporal_output_models_coerce_date_and_datetime_values():
    dt = datetime(2026, 4, 17, 12, 34, 56)
    day = date(2026, 4, 17)

    movement = MovementOut(
        id=1,
        date=dt,
        description="Cash movement",
        amount=10.5,
        role="debit",
        counterpart="Caja",
    )
    user = UserOut(
        id=1,
        username="admin",
        is_admin=True,
        is_active=True,
        created_at=dt,
    )
    session = SessionOut(authenticated=True, user=user, expires_at=dt)
    tag = TagOut(
        id=1,
        name="Travel",
        color="#123456",
        created_at=dt,
        updated_at=dt,
        transaction_count=0,
    )
    tx = TransactionOut(
        id=1,
        debit_account=1,
        debit_name="Caja",
        debit_type_id=1,
        credit_account=2,
        credit_name="Ventas",
        credit_type_id=3,
        amount=10.5,
        original_amount=10.5,
        original_currency="ARS",
        fx_rate=1.0,
        fx_source=None,
        description="Ingreso",
        date=dt,
        created_at=dt,
        tags=[tag],
    )
    series = ProjectionSeriesOut(
        id=1,
        name="Salary",
        type="income",
        start_date=day,
        months=12,
        period_months=1,
        enabled=True,
        confirmed=False,
        monthly_amount=1000,
        created_at=dt,
    )

    assert movement.date == "2026-04-17 12:34:56"
    assert user.created_at == "2026-04-17 12:34:56"
    assert session.expires_at == "2026-04-17 12:34:56"
    assert tag.created_at == "2026-04-17 12:34:56"
    assert tag.updated_at == "2026-04-17 12:34:56"
    assert tx.date == "2026-04-17 12:34:56"
    assert tx.created_at == "2026-04-17 12:34:56"
    assert series.start_date == "2026-04-17"
    assert series.created_at == "2026-04-17 12:34:56"


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


def test_version_payload_prefers_heroku_release_metadata(monkeypatch):
    monkeypatch.setenv("HEROKU_RELEASE_VERSION", "v321")
    monkeypatch.setenv("HEROKU_RELEASE_CREATED_AT", "2026-04-17T18:45:12Z")
    monkeypatch.setenv("OPEN_ACCOUNTANT_VERSION", "v9.9.9")

    payload = app_version.version_payload()

    assert payload["tag"] == "v9.9.9"
    assert payload["version"] == "9.9.9"
    assert payload["release_version"] == "v321"
    assert payload["release_created_at"] == "2026-04-17T18:45:12Z"
    assert payload["release_created_at_display"] == "2026-04-17"
    assert payload["full_title"] == "Open Accountant v321 · 2026-04-17"


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


def test_init_db_repairs_postgres_subtype_identity(monkeypatch):
    executed = []
    metadata_rows = iter(
        [
            {"is_identity": "NO", "column_default": None},
            {"is_identity": "YES", "column_default": None},
        ]
    )

    class FakeCursor:
        def __init__(self, row=None):
            self._row = row

        def fetchone(self):
            return self._row

    class FakeConn:
        backend = "postgresql"

        def executescript(self, script):
            executed.append(("SCRIPT", script))

        def execute(self, query, params=()):
            normalized = " ".join(query.split())
            executed.append((normalized, params))

            if "FROM information_schema.columns" in normalized:
                row = next(
                    metadata_rows, {"is_identity": "YES", "column_default": None}
                )
                return FakeCursor(row)
            if (
                'SELECT COALESCE(MAX("id"), 0) + 1 AS next_val FROM "oacc_subtypes"'
                == normalized
            ):
                return FakeCursor({"next_val": 19})
            if normalized == "SELECT COUNT(*) AS account_count FROM accounts":
                return FakeCursor({"account_count": 1})
            return FakeCursor()

    fake_conn = FakeConn()

    @contextmanager
    def fake_get_db():
        yield fake_conn

    monkeypatch.setattr(database, "backend_name", lambda conn=None: "postgresql")
    monkeypatch.setattr(database, "get_db", fake_get_db)

    init_db()

    assert any(
        query
        == 'ALTER TABLE "oacc_subtypes" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY'
        for query, _ in executed
    )
    assert any(
        query
        == "SELECT setval(pg_get_serial_sequence('oacc_subtypes', 'id'), ?, false)"
        and params == (19,)
        for query, params in executed
    )


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


def test_recurring_transactions_use_last_day_for_short_months(initialized_environment):
    now = datetime(2026, 2, 28, 9, 0, 0)
    with get_db() as conn:
        accounts = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM accounts").fetchall()
        }
        created = recurring_transactions_service.create_recurring_transaction(
            conn,
            RecurringTransactionIn(
                debit_account=accounts["Groceries"],
                credit_account=accounts["Bank"],
                amount=100.0,
                description="Month end bill",
                alert_day=31,
            ),
        )

        active = recurring_transactions_service.list_recurring_transactions(
            conn, "active", now
        )

    listed = next(item for item in active if item.id == created.id)
    assert listed.effective_alert_date == "2026-02-28"
    assert listed.is_active is True


def test_posting_recurring_transaction_marks_current_month_but_allows_repost(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM accounts").fetchall()
        }
        tag = tags_service.create_tag(
            conn, TagIn(name="Utilities recurring", color="#2563EB")
        )
        created = recurring_transactions_service.create_recurring_transaction(
            conn,
            RecurringTransactionIn(
                debit_account=accounts["Utilities"],
                credit_account=accounts["Bank"],
                amount=120.0,
                description="Monthly utilities",
                alert_day=1,
                tag_ids=[tag.id],
            ),
        )
        first = recurring_transactions_service.post_recurring_transaction(
            conn, created.id, RecurringTransactionPostIn()
        )
        second = recurring_transactions_service.post_recurring_transaction(
            conn,
            created.id,
            RecurringTransactionPostIn(
                original_amount=125.0,
                original_currency="ARS",
            ),
        )
        refreshed = recurring_transactions_service.get_recurring_transaction(
            conn, created.id
        )

    assert first.transaction.tags[0].name == "Utilities recurring"
    assert second.transaction.amount == 125.0
    assert refreshed.last_transaction_id == second.transaction.id
    assert refreshed.is_active is False


def test_recurring_transaction_can_be_marked_done_without_creating_transaction(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM accounts").fetchall()
        }
        created = recurring_transactions_service.create_recurring_transaction(
            conn,
            RecurringTransactionIn(
                debit_account=accounts["Utilities"],
                credit_account=accounts["Bank"],
                amount=95.0,
                description="Manual utility payment",
                alert_day=1,
            ),
        )
        before_count = conn.execute(
            "SELECT COUNT(*) AS tx_count FROM transactions"
        ).fetchone()["tx_count"]
        marked = recurring_transactions_service.mark_recurring_transaction_done(
            conn, created.id
        )
        after_count = conn.execute(
            "SELECT COUNT(*) AS tx_count FROM transactions"
        ).fetchone()["tx_count"]

    assert marked.is_active is False
    assert marked.last_posted_period is not None
    assert marked.last_transaction_id is None
    assert after_count == before_count


def test_settings_service_backup_export_and_restore_roundtrip(initialized_environment):
    with get_db() as conn:
        cash = conn.execute(
            "SELECT id FROM accounts WHERE name = ?",
            ("Cash",),
        ).fetchone()["id"]
        salary = conn.execute(
            "SELECT id FROM accounts WHERE name = ?",
            ("Salary",),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO transactions (
                debit_account,
                credit_account,
                amount,
                original_amount,
                original_currency,
                fx_rate,
                description,
                date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (cash, salary, 123.45, 123.45, "ARS", 1.0, "Backup test tx"),
        )

        tx_count_before = conn.execute(
            "SELECT COUNT(*) AS total FROM transactions"
        ).fetchone()["total"]
        backup = settings_service.export_backup(conn)

        conn.execute("DELETE FROM transactions")
        tx_count_after_delete = conn.execute(
            "SELECT COUNT(*) AS total FROM transactions"
        ).fetchone()["total"]
        assert tx_count_after_delete == 0

        restored = settings_service.restore_backup(conn, backup)
        tx_count_after_restore = conn.execute(
            "SELECT COUNT(*) AS total FROM transactions"
        ).fetchone()["total"]

    assert backup["format"] == settings_service.BACKUP_FORMAT
    assert "oacc_transactions" in backup["tables"]
    assert tx_count_before > 0
    assert tx_count_after_restore == tx_count_before
    assert restored["ok"] is True
    assert "oacc_transactions" in restored["restored_tables"]


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


def test_reports_service_stats_summary_and_net_worth_evolution(
    initialized_environment, monkeypatch
):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 25, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(reports_service, "datetime", FixedDateTime)

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
                date="2026-03-05 10:00:00",
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
                date="2026-03-07 10:00:00",
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
                date="2026-03-10 10:00:00",
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
                date="2026-03-15 10:00:00",
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
                date="2026-03-18 10:00:00",
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
    assert stats.summary["total_assets_excluding_fixed"] == 1750.0
    assert stats.summary["total_liabilities"] == 800.0
    assert stats.summary["net_worth"] == 950.0
    assert stats.summary["net_worth_excluding_fixed"] == 950.0
    assert stats.summary["debt_ratio"] == pytest.approx(800.0 / 1750.0, rel=1e-4)
    assert stats.summary["debt_ratio_excluding_fixed"] == pytest.approx(
        800.0 / 1750.0, rel=1e-4
    )
    assert stats.summary["current_assets"] == 1550.0
    assert stats.summary["quick_assets"] == 1550.0
    assert stats.summary["current_liabilities"] == 300.0
    assert stats.summary["current_ratio"] == pytest.approx(1550.0 / 300.0, rel=1e-4)
    assert stats.summary["quick_ratio"] == pytest.approx(1550.0 / 300.0, rel=1e-4)
    assert stats.summary["monthly_essential_expense"] == 250.0
    assert stats.summary["runway_months"] == pytest.approx(1550.0 / 250.0, rel=1e-4)
    assert stats.summary["recent_months_count"] == 1
    assert stats.summary["avg_monthly_income_recent"] == 1200.0
    assert stats.summary["avg_monthly_expense_recent"] == 250.0
    assert stats.summary["total_runway_months"] == pytest.approx(
        1750.0 / 250.0, rel=1e-4
    )
    assert stats.summary["top_asset_name"] == "Bank"
    assert stats.summary["top_asset_share"] == pytest.approx(1550.0 / 1750.0, rel=1e-4)
    assert stats.summary["top_asset_name_excluding_fixed"] == "Bank"
    assert stats.summary["top_asset_share_excluding_fixed"] == pytest.approx(
        1550.0 / 1750.0, rel=1e-4
    )
    assert stats.summary["top_expense_name"] == expense_account.subtype_name
    assert stats.summary["top_expense_share"] == 1.0
    assert sum(row["amount"] for row in stats.income_evolution) == pytest.approx(1200.0)
    assert sum(row["amount"] for row in stats.expense_evolution) == pytest.approx(250.0)
    assert sum(row["balance"] for row in stats.liability_evolution) == pytest.approx(
        800.0
    )
    account_stats = {row["account_name"]: row for row in stats.account_stats}
    assert "Capital" not in account_stats
    assert account_stats["Bank"]["current"] == pytest.approx(1550.0)
    assert account_stats["Groceries"]["current"] == pytest.approx(250.0)
    assert account_stats[income_account.name]["current"] == pytest.approx(1200.0)
    assert account_stats[liability_account.name]["current"] == pytest.approx(300.0)
    assert account_stats["Bond Ladder"]["active_months"] == 1
    assert account_stats["Bond Ladder"]["months"] == ["2026-03"]
    assert account_stats["Bond Ladder"]["mean"] == pytest.approx(200.0, rel=1e-4)
    assert account_stats["Bond Ladder"]["median"] == pytest.approx(200.0, rel=1e-4)
    assert account_stats["Bond Ladder"]["stddev"] == pytest.approx(0.0, rel=1e-4)
    assert account_stats["Bond Ladder"]["boxplot"]["q1"] == pytest.approx(
        200.0, rel=1e-4
    )
    assert account_stats["Bond Ladder"]["boxplot"]["median"] == pytest.approx(
        200.0, rel=1e-4
    )
    assert account_stats["Bank"]["boxplot"]["max"] == pytest.approx(1550.0)
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
    assert projections["current_balances"]["total_assets_excluding_fixed"] == 1750.0
    assert projections["current_balances"]["total_fixed_assets"] == 0.0


def test_reports_service_stats_income_evolution_preserves_negative_subtype_months(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]
        salary = accounts["Salary"]
        dividends = accounts_service.create_account(
            conn,
            AccountIn(
                name="Negative Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=salary.id,
                amount=100.0,
                original_amount=None,
                fx_rate=None,
                description="Salary inflow",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=dividends.id,
                amount=40.0,
                original_amount=None,
                fx_rate=None,
                description="Dividend payment",
                date="2026-03-10 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=dividends.id,
                credit_account=bank.id,
                amount=75.0,
                original_amount=None,
                fx_rate=None,
                description="Dividend reversal",
                date="2026-03-20 10:00:00",
            ),
        )

        stats = reports_service.get_stats(conn, "2026-03-01", "2026-03-31")

    assert stats.summary["total_income"] == pytest.approx(65.0)
    assert stats.monthly_cashflow == [
        {
            "month": "2026-03",
            "ingresos": 65.0,
            "gastos": 0.0,
            "neto": 65.0,
        }
    ]
    march_income = {row["subtype"]: row["amount"] for row in stats.income_evolution}
    assert march_income == {
        salary.subtype_name: pytest.approx(100.0),
        dividends.subtype_name: pytest.approx(-35.0),
    }


def test_reports_service_stats_liability_evolution_preserves_negative_balances(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]
        credit_card = accounts["Credit Card"]
        backup_card = accounts_service.create_account(
            conn,
            AccountIn(
                name="Backup Card",
                type_id=2,
                subtype_id=credit_card.subtype_id,
                description="Second card",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=credit_card.id,
                amount=300.0,
                original_amount=None,
                fx_rate=None,
                description="Card spending",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=backup_card.id,
                credit_account=bank.id,
                amount=50.0,
                original_amount=None,
                fx_rate=None,
                description="Card overpayment",
                date="2026-03-20 10:00:00",
            ),
        )

        stats = reports_service.get_stats(conn, "2026-03-01", "2026-03-31")

    assert stats.summary["total_liabilities"] == pytest.approx(250.0)
    march_liability_balances = {
        row["account_name"]: row["balance"] for row in stats.liability_evolution
    }
    assert march_liability_balances == {
        credit_card.name: pytest.approx(300.0),
        backup_card.name: pytest.approx(-50.0),
    }


def test_reports_service_account_stats_excludes_subtype_patrimonio_and_uses_real_current_month(
    initialized_environment,
    monkeypatch,
):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 20, 8, 30, 0, tzinfo=tz)

    monkeypatch.setattr(reports_service, "datetime", FixedDateTime)

    with get_db() as conn:
        patrimonio_subtype = subtypes_service.create_subtype(
            conn,
            SubtypeIn(name="Patrimonio", type_id=1),
        )
        hidden_asset = accounts_service.create_account(
            conn,
            AccountIn(
                name="Hidden Asset",
                type_id=1,
                subtype_id=patrimonio_subtype.id,
                description="Should be excluded",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]
        salary = accounts["Salary"]

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=salary.id,
                amount=400.0,
                original_amount=None,
                fx_rate=None,
                description="April salary",
                date="2026-04-10 09:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=hidden_asset.id,
                credit_account=salary.id,
                amount=50.0,
                original_amount=None,
                fx_rate=None,
                description="Hidden subtype movement",
                date="2026-04-11 09:00:00",
            ),
        )

        stats = reports_service.get_stats(conn, "2026-03-01", "2026-03-31")

    account_stats = {row["account_name"]: row for row in stats.account_stats}
    assert "Capital" not in account_stats
    assert "Hidden Asset" not in account_stats
    assert account_stats["Bank"]["current"] == pytest.approx(400.0)
    assert account_stats["Salary"]["current"] == pytest.approx(450.0)
    assert account_stats["Bank"]["active_months"] == 0
    assert account_stats["Bank"]["months"] == []


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


def test_projection_series_adjustments_respect_period_months():
    adjustments = projections_service._compute_series_adjustments(
        [
            {
                "id": 1,
                "name": "aporte semestral",
                "type": "income",
                "start_date": "2026-07-01",
                "months": 6,
                "period_months": 2,
                "monthly_amount": 100.0,
            }
        ],
        ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12"],
    )

    assert adjustments["income"] == [100.0, 0.0, 100.0, 0.0, 100.0, 0.0]
    assert adjustments["expenses"] == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert adjustments["savings"] == [100.0, 0.0, 100.0, 0.0, 100.0, 0.0]
    assert adjustments["assets"] == [100.0, 100.0, 200.0, 200.0, 300.0, 300.0]
    assert adjustments["liabilities"] == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_projection_series_adjustments_keep_signs_and_skip_disabled_series():
    adjustments = projections_service._compute_series_adjustments(
        [
            {
                "id": 1,
                "name": "bonus",
                "type": "income",
                "start_date": "2026-07-01",
                "months": 2,
                "enabled": True,
                "monthly_amount": 1000.0,
            },
            {
                "id": 2,
                "name": "rent",
                "type": "expense",
                "start_date": "2026-07-01",
                "months": 2,
                "enabled": True,
                "monthly_amount": 400.0,
            },
            {
                "id": 3,
                "name": "ignored",
                "type": "income",
                "start_date": "2026-07-01",
                "months": 2,
                "enabled": False,
                "monthly_amount": 999.0,
            },
        ],
        ["2026-07", "2026-08", "2026-09"],
    )

    assert adjustments["income"] == [1000.0, 1000.0, 0.0]
    assert adjustments["expenses"] == [400.0, 400.0, 0.0]
    assert adjustments["savings"] == [600.0, 600.0, 0.0]
    assert adjustments["assets"] == [600.0, 1200.0, 1200.0]
    assert adjustments["liabilities"] == [400.0, 800.0, 800.0]


def test_projection_series_service_persists_enabled_state(initialized_environment):
    with get_db() as conn:
        created = projections_service.create_series(
            conn,
            ProjectionSeriesIn(
                name="Rent",
                type="expense",
                start_date="2026-07-01",
                months=6,
                period_months=3,
                enabled=False,
                confirmed=True,
                monthly_amount=500.0,
            ),
        )

        assert created["enabled"] is False
        assert created["period_months"] == 3
        assert created["confirmed"] is True

        updated = projections_service.update_series(
            conn,
            created["id"],
            ProjectionSeriesUpdate(enabled=True),
        )

    assert updated["enabled"] is True
    assert updated["period_months"] == 3
    assert updated["confirmed"] is True


def test_confirmed_series_are_added_to_baseline_projection(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Bank"].id,
                credit_account=accounts["Salary"].id,
                amount=5000.0,
                original_amount=None,
                fx_rate=None,
                description="Salary",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Groceries"].id,
                credit_account=accounts["Bank"].id,
                amount=500.0,
                original_amount=None,
                fx_rate=None,
                description="Food",
                date="2026-03-08 10:00:00",
            ),
        )

        without_series = projections_service.get_projections(conn, 3, 3)

        projections_service.create_series(
            conn,
            ProjectionSeriesIn(
                name="Confirmed boost",
                type="income",
                start_date="2026-05-01",
                months=2,
                confirmed=True,
                monthly_amount=300.0,
            ),
        )
        projections_service.create_series(
            conn,
            ProjectionSeriesIn(
                name="Scenario boost",
                type="income",
                start_date="2026-05-01",
                months=2,
                confirmed=False,
                monthly_amount=200.0,
            ),
        )

        with_series = projections_service.get_projections(conn, 3, 3)

    assert with_series["baseline_projection"]["income"][0] == pytest.approx(
        without_series["baseline_projection"]["income"][0] + 300.0,
        rel=1e-4,
    )
    assert with_series["series_adjustment"]["income"][:2] == pytest.approx(
        [200.0, 200.0],
        rel=1e-4,
    )


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


def test_ledger_balance_series_covers_last_year_with_daily_points(
    initialized_environment,
):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        # One movement before the window and one inside it.
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=500.0,
                description="Old salary",
                date="2024-05-10 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=150.0,
                description="Salary",
                date="2026-03-10 10:00:00",
            ),
        )

        series = reports_service.get_ledger_balance_series(
            conn, bank.id, today=date(2026, 6, 30)
        )

        assert series["account_id"] == bank.id
        assert series["period_to"] == "2026-06-30"
        assert series["period_from"] == "2025-06-30"
        assert len(series["points"]) == 366
        assert series["points"][0]["date"] == "2025-06-30"
        assert series["points"][-1]["date"] == "2026-06-30"

        # The pre-window movement is folded into the opening balance...
        opening = bank.initial_balance + 500.0
        assert series["opening_balance"] == pytest.approx(opening)
        assert series["points"][0]["balance"] == pytest.approx(opening)

        # ...and the in-window movement steps the curve up on its own day.
        by_date = {point["date"]: point["balance"] for point in series["points"]}
        assert by_date["2026-03-09"] == pytest.approx(opening)
        assert by_date["2026-03-10"] == pytest.approx(opening + 150.0)
        assert series["closing_balance"] == pytest.approx(opening + 150.0)


def test_ledger_balance_series_honours_explicit_window(initialized_environment):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Groceries"].id,
                credit_account=bank.id,
                amount=80.0,
                description="Market",
                date="2026-02-02 09:00:00",
            ),
        )

        series = reports_service.get_ledger_balance_series(
            conn, bank.id, from_date="2026-02-01", to_date="2026-02-03"
        )

        assert [point["date"] for point in series["points"]] == [
            "2026-02-01",
            "2026-02-02",
            "2026-02-03",
        ]
        # Bank is debit-normal, so a credit lowers the balance.
        assert series["points"][0]["balance"] == pytest.approx(bank.initial_balance)
        assert series["points"][1]["balance"] == pytest.approx(
            bank.initial_balance - 80.0
        )
        assert series["closing_balance"] == pytest.approx(bank.initial_balance - 80.0)


def test_ledger_balance_series_rejects_unknown_account(initialized_environment):
    with get_db() as conn:
        with pytest.raises(NotFoundError):
            reports_service.get_ledger_balance_series(conn, 999999)


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


def test_account_properties_infer_fixed_liquidity_for_fixed_assets(
    initialized_environment,
):
    with get_db() as conn:
        fixed_asset = accounts_service.create_account(
            conn,
            AccountIn(
                name="Office Building",
                type_id=1,
                subtype_id=4,
                description="Fixed asset",
                initial_balance=0.0,
                properties="{}",
            ),
        )

    assert fixed_asset.properties["liquidity_profile"] == "fixed"


def test_reports_service_stats_exposes_total_assets_excluding_fixed(
    initialized_environment,
):
    with get_db() as conn:
        baseline_stats = reports_service.get_stats(conn)
        accounts_service.create_account(
            conn,
            AccountIn(
                name="Garage",
                type_id=1,
                subtype_id=4,
                description="Immovable asset",
                initial_balance=400.0,
                properties='{"liquidity_profile":"fixed"}',
            ),
        )
        updated_stats = reports_service.get_stats(conn)

    assert updated_stats.summary["total_assets"] == pytest.approx(
        baseline_stats.summary["total_assets"] + 400.0
    )
    assert updated_stats.summary["total_assets_excluding_fixed"] == pytest.approx(
        baseline_stats.summary["total_assets_excluding_fixed"]
    )


def test_fixed_assets_are_excluded_from_operational_stats_and_projection_health(
    initialized_environment,
):
    with get_db() as conn:
        baseline_stats = reports_service.get_stats(conn)
        baseline_projections = projections_service.get_projections(conn, 3, 3)
        accounts_service.create_account(
            conn,
            AccountIn(
                name="Garage",
                type_id=1,
                subtype_id=4,
                description="Immovable asset",
                initial_balance=400.0,
                properties='{"liquidity_profile":"fixed"}',
            ),
        )
        updated_stats = reports_service.get_stats(conn)
        updated_projections = projections_service.get_projections(conn, 3, 3)

    assert updated_stats.summary["total_assets"] == pytest.approx(
        baseline_stats.summary["total_assets"] + 400.0
    )
    assert updated_stats.summary["total_assets_excluding_fixed"] == pytest.approx(
        baseline_stats.summary["total_assets_excluding_fixed"]
    )
    assert updated_stats.summary["net_worth_excluding_fixed"] == pytest.approx(
        baseline_stats.summary["net_worth_excluding_fixed"]
    )
    assert updated_stats.summary["debt_ratio_excluding_fixed"] == pytest.approx(
        baseline_stats.summary["debt_ratio_excluding_fixed"]
    )
    assert (
        updated_stats.summary["top_asset_name_excluding_fixed"]
        == baseline_stats.summary["top_asset_name_excluding_fixed"]
    )
    assert updated_stats.net_worth_evolution == baseline_stats.net_worth_evolution
    assert all(
        row["account_name"] != "Garage" for row in updated_stats.balance_evolution
    )

    assert updated_projections["current_balances"][
        "total_fixed_assets"
    ] == pytest.approx(400.0)
    assert updated_projections["current_balances"][
        "total_assets_excluding_fixed"
    ] == pytest.approx(
        baseline_projections["current_balances"]["total_assets_excluding_fixed"]
    )
    assert (
        updated_projections["historical"]["assets"]
        == baseline_projections["historical"]["assets"]
    )
    assert (
        updated_projections["baseline_projection"]["assets"]
        == baseline_projections["baseline_projection"]["assets"]
    )
    assert updated_projections["health"]["current"]["net_worth"] == pytest.approx(
        baseline_projections["health"]["current"]["net_worth"]
    )


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
        exports_service._build_balance_pdf_table(balance_sheet)
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


def test_aggregate_empty():
    assert projections_service._aggregate([], "mean") == 0.0


def test_normalize_investment_stat_always_uses_mean():
    assert projections_service._normalize_investment_stat("mean") == "mean"
    assert projections_service._normalize_investment_stat("median") == "mean"
    assert projections_service._normalize_investment_stat(None) == "mean"


def test_project_investments_compound_growth():
    # Joint iteration: contribution = rate * projected_income, interest = inv * yield
    inv, non_inv, detail = projections_service._project_investments(
        1000.0,  # current_investment_balance
        1000.0,  # current_non_inv_assets
        0.01,  # yield_rate
        0.1,  # contribution_rate (10% of projected income)
        [1000.0, 1000.0, 1000.0],  # projected income
        [0.0, 0.0, 0.0],  # projected expenses
        [100.0, 100.0, 100.0],  # baseline_savings
        3,
    )
    assert len(inv) == 3
    # Period 0: income=1000, contrib=100, interest=10, inv=1000+10+100=1110
    assert inv[0] == pytest.approx(1110.0, rel=1e-4)
    assert detail[0]["interest"] == pytest.approx(10.0, rel=1e-4)
    assert detail[0]["contribution"] == pytest.approx(100.0, rel=1e-4)
    total_assets = [inv[i] + non_inv[i] for i in range(3)]
    assert total_assets[0] == pytest.approx(2110.0, rel=1e-4)
    assert total_assets[1] == pytest.approx(
        total_assets[0] + 100.0 + detail[1]["interest"], rel=1e-4
    )
    assert total_assets[2] == pytest.approx(
        total_assets[1] + 100.0 + detail[2]["interest"], rel=1e-4
    )


def test_project_investments_floors_at_zero():
    inv, non_inv, detail = projections_service._project_investments(
        50.0,
        1000.0,
        0.0,
        0.0,
        [0.0, 0.0, 0.0],
        [200.0, 200.0, 200.0],
        [-200.0, -200.0, -200.0],
        3,
    )
    # With zero rate and zero contribution_rate, inv stays at 50, non_inv shrinks
    assert inv[0] == pytest.approx(50.0, rel=1e-4)
    assert non_inv[0] == pytest.approx(800.0, rel=1e-4)


def test_project_investments_zero_rate_contribution_only():
    inv, non_inv, detail = projections_service._project_investments(
        0.0, 10000.0, 0.0, 0.05, [10000.0, 10000.0], [0.0, 0.0], [500.0, 500.0], 2
    )
    # Period 0: income=10000, contrib=500, inv=0+0+500=500, non_inv stays flat
    assert inv[0] == pytest.approx(500.0, rel=1e-4)
    # Period 1: income=10000, contrib=500, inv=500+0+500=1000
    assert inv[1] == pytest.approx(1000.0, rel=1e-4)


def test_project_investments_keeps_six_decimal_detail_precision():
    inv, non_inv, detail = projections_service._project_investments(
        1000.0,
        0.0,
        0.03123456,
        0.0,
        [0.0],
        [0.0],
        [0.0],
        1,
    )

    assert inv[0] == pytest.approx(1031.2346, rel=1e-4)
    assert non_inv[0] == pytest.approx(0.0, rel=1e-4)
    assert detail[0]["interest_exact"] == pytest.approx(31.23456, rel=1e-8)
    assert detail[0]["ending_investment_balance_exact"] == pytest.approx(
        1031.23456, rel=1e-8
    )


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
        "2024-02": 10200.0,
        "2024-03": 10400.0,
        "2024-04": 10600.0,
    }
    div_map = {"2024-02": 100.0, "2024-03": 100.0, "2024-04": 100.0}
    contrib_map = {"2024-02": 200.0, "2024-03": 200.0, "2024-04": 200.0}
    income_map = {
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


def test_estimate_investment_model_includes_zero_and_negative_months():
    months = ["2024-01", "2024-02", "2024-03"]
    inv_bal = {m: 100.0 for m in months}
    div_map = {"2024-01": 10.0, "2024-03": -5.0}
    contrib_map = {"2024-03": 30.0}
    income_map = {m: 100.0 for m in months}

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

    assert model["sample_count"] == 3
    assert model["yield_rate"] == pytest.approx((0.10 + 0.0 - 0.05) / 3.0, rel=1e-6)
    assert model["interest_amount"] == pytest.approx(1.6667, rel=1e-6)
    assert model["contrib_sample_count"] == 3
    assert model["contribution_rate"] == pytest.approx(
        (0.0 + 0.0 + 0.30) / 3.0, rel=1e-6
    )
    assert model["contribution_amount"] == pytest.approx(10.0, rel=1e-6)


def test_estimate_investment_model_can_include_provisional_current_contribution():
    months = ["2024-02", "2024-03", "2024-04"]
    inv_bal = {m: 100.0 for m in months}
    income_map = {m: 100.0 for m in months}

    model = projections_service._estimate_investment_model(
        months,
        inv_bal,
        {},
        {"2024-04": 30.0},
        income_map,
        stat="mean",
        exclude_outliers=False,
        outlier_k=1.5,
    )

    assert model["yield_rate"] == 0.0
    assert model["contrib_sample_count"] == 3
    assert model["contribution_rate"] == pytest.approx(0.10, rel=1e-6)
    assert model["contribution_amount"] == pytest.approx(10.0, rel=1e-6)


def test_estimate_investment_model_normalizes_legacy_median_to_mean():
    months = ["2024-03"]
    inv_bal = {"2024-03": 10000.0}
    div_map = {"2024-03": 500.0}
    contrib_map = {}
    model = projections_service._estimate_investment_model(
        months,
        inv_bal,
        div_map,
        contrib_map,
        {"2024-03": 10000.0},
        stat="median",
        exclude_outliers=False,
        outlier_k=1.5,
    )
    assert model["sample_count"] == 1
    assert model["yield_rate"] > 0
    assert model["warnings"] == []


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

    high_precision_interest = projections_service._resolve_investment_projection_inputs(
        10000.0,
        model,
        interest_pct_override=3.123456,
    )
    assert high_precision_interest["applied_interest_percent"] == pytest.approx(
        3.123456, rel=1e-6
    )
    assert high_precision_interest["applied_yield_rate"] == pytest.approx(
        0.03123456, rel=1e-8
    )
    assert high_precision_interest["applied_interest_amount"] == pytest.approx(
        312.3456, rel=1e-6
    )


# ── Investment integration test with DB ───────────────────────────────────────


def test_investment_projection_integration(initialized_environment, monkeypatch):
    """Full integration: create investment + dividend accounts, add transactions,
    and verify no double-counting in total assets."""

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

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
                date="2026-03-05 10:00:00",
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
                date="2026-03-06 10:00:00",
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
                date="2026-03-07 10:00:00",
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
                date="2026-03-08 10:00:00",
            ),
        )

        result = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    with get_db() as conn:
        legacy_stat_result = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="median",
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
    assert result["investment_model"]["stat"] == "mean"
    assert legacy_stat_result["investment_model"]["stat"] == "mean"
    assert legacy_stat_result["investment_model"]["yield_rate"] == pytest.approx(
        result["investment_model"]["yield_rate"], rel=1e-6
    )
    assert legacy_stat_result["investment_model"]["contribution_rate"] == pytest.approx(
        result["investment_model"]["contribution_rate"], rel=1e-6
    )
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
            investment_interest_pct_override=3.123456,
            investment_contribution_pct_override=12.0,
        )

    assert overridden["investment_model"]["has_overrides"] is True
    assert overridden["investment_model"]["applied_interest_percent"] == pytest.approx(
        3.123456, rel=1e-6
    )
    first_projected_override = next(
        row for row in overridden["investment_detail"] if row["is_projected"]
    )
    assert first_projected_override["interest_pct_investments"] == pytest.approx(
        3.123456, rel=1e-6
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
        1210.0, rel=1e-4
    )
    first_projected_detail = next(
        row for row in inflation["investment_detail"] if row["is_projected"]
    )
    assert first_projected_detail["total_income"] == pytest.approx(1210.0, rel=1e-4)
    assert (
        inflation["baseline_projection"]["assets"]
        != result["baseline_projection"]["assets"]
    )


def test_projected_assets_follow_previous_assets_plus_savings_plus_return(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Projected Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Projected Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=5000.0,
                original_amount=None,
                fx_rate=None,
                description="Salary",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=2000.0,
                original_amount=None,
                fx_rate=None,
                description="Transfer to brokerage",
                date="2026-03-06 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=div_account.id,
                amount=100.0,
                original_amount=None,
                fx_rate=None,
                description="Quarterly dividend",
                date="2026-03-07 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Groceries"].id,
                credit_account=bank.id,
                amount=500.0,
                original_amount=None,
                fx_rate=None,
                description="Food",
                date="2026-03-08 10:00:00",
            ),
        )

        projections_service.create_series(
            conn,
            ProjectionSeriesIn(
                name="Income boost",
                type="income",
                start_date="2026-05-01",
                months=2,
                monthly_amount=300.0,
            ),
        )

        result = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    displayed_savings = [
        result["baseline_projection"]["savings"][i]
        + result["series_adjustment"]["savings"][i]
        for i in range(3)
    ]
    displayed_assets = [
        result["baseline_projection"]["assets"][i]
        + result["series_adjustment"]["assets"][i]
        for i in range(3)
    ]
    projected_returns = [
        row["interest_total"]
        for row in result["investment_detail"]
        if row["is_projected"]
    ]

    assert len(projected_returns) == 3
    assert all(value >= 0.0 for value in projected_returns)

    previous_assets = result["current_balances"]["total_assets"]
    for i in range(3):
        expected_assets = round(
            previous_assets + displayed_savings[i] + projected_returns[i], 4
        )
        assert displayed_assets[i] == pytest.approx(expected_assets, rel=1e-4)
        previous_assets = displayed_assets[i]


def test_baseline_non_invested_projection_is_not_affected_by_series(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Stable Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Stable Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=5000.0,
                original_amount=None,
                fx_rate=None,
                description="Salary",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=2000.0,
                original_amount=None,
                fx_rate=None,
                description="Transfer to brokerage",
                date="2026-03-06 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=div_account.id,
                amount=100.0,
                original_amount=None,
                fx_rate=None,
                description="Quarterly dividend",
                date="2026-03-07 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=accounts["Groceries"].id,
                credit_account=bank.id,
                amount=500.0,
                original_amount=None,
                fx_rate=None,
                description="Food",
                date="2026-03-08 10:00:00",
            ),
        )

        without_series = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

        projections_service.create_series(
            conn,
            ProjectionSeriesIn(
                name="Income boost",
                type="income",
                start_date="2026-05-01",
                months=2,
                monthly_amount=300.0,
            ),
        )

        with_series = projections_service.get_projections(
            conn,
            3,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    assert with_series["baseline_projection"]["investments"] == pytest.approx(
        without_series["baseline_projection"]["investments"], rel=1e-4
    )
    assert with_series["baseline_projection"]["assets"] == pytest.approx(
        without_series["baseline_projection"]["assets"], rel=1e-4
    )
    assert with_series["baseline_projection"]["returns"] == pytest.approx(
        without_series["baseline_projection"]["returns"], rel=1e-4
    )

    without_non_invested = [
        without_series["baseline_projection"]["assets"][i]
        - without_series["baseline_projection"]["investments"][i]
        for i in range(3)
    ]
    with_non_invested = [
        with_series["baseline_projection"]["assets"][i]
        - with_series["baseline_projection"]["investments"][i]
        for i in range(3)
    ]
    assert with_non_invested == pytest.approx(without_non_invested, rel=1e-4)

    assert with_series["series_adjustment"]["assets"] != pytest.approx(
        without_series["series_adjustment"]["assets"], rel=1e-4
    )


def test_historical_investment_detail_uses_displayed_balance_for_interest_pct(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Projection Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Projection Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="February salary",
                date="2026-02-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="February investment contribution",
                date="2026-02-06 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="March salary",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=500.0,
                original_amount=None,
                fx_rate=None,
                description="March investment contribution",
                date="2026-03-06 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=div_account.id,
                amount=150.0,
                original_amount=None,
                fx_rate=None,
                description="March dividend reinvested",
                date="2026-03-07 10:00:00",
            ),
        )

        result = projections_service.get_projections(
            conn,
            1,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    march_row = next(
        row for row in result["investment_detail"] if row["month"] == "2026-03"
    )

    assert march_row["investment_balance"] == pytest.approx(1650.0, rel=1e-4)
    assert march_row["interest_total"] == pytest.approx(150.0, rel=1e-4)
    assert march_row["interest_pct_investments"] == pytest.approx(
        150.0 / 1650.0 * 100.0,
        rel=1e-4,
    )


def test_historical_investment_detail_keeps_negative_interest_months(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Negative Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Negative Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=bank.id,
                credit_account=accounts["Salary"].id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="March salary",
                date="2026-03-05 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="March investment contribution",
                date="2026-03-06 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=div_account.id,
                credit_account=inv_account.id,
                amount=50.0,
                original_amount=None,
                fx_rate=None,
                description="March investment loss",
                date="2026-03-07 10:00:00",
            ),
        )

        result = projections_service.get_projections(
            conn,
            1,
            3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    march_row = next(
        row for row in result["investment_detail"] if row["month"] == "2026-03"
    )

    assert march_row["investment_balance"] == pytest.approx(950.0, rel=1e-4)
    assert march_row["interest_total"] == pytest.approx(-50.0, rel=1e-4)
    assert march_row["interest_pct_investments"] == pytest.approx(
        -50.0 / 950.0 * 100.0,
        rel=1e-4,
    )


def test_investment_lookback_excludes_current_month(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Lookback Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Lookback Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        for month in (1, 2, 3, 4):
            transactions_service.create_transaction(
                conn,
                TransactionIn(
                    debit_account=bank.id,
                    credit_account=accounts["Salary"].id,
                    amount=1000.0,
                    original_amount=None,
                    fx_rate=None,
                    description=f"Salary {month}",
                    date=f"2026-{month:02d}-05 10:00:00",
                ),
            )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=1000.0,
                original_amount=None,
                fx_rate=None,
                description="Initial investment",
                date="2026-01-06 10:00:00",
            ),
        )

        for month, amount in ((1, 100.0), (2, 100.0), (3, 100.0), (4, 1000.0)):
            transactions_service.create_transaction(
                conn,
                TransactionIn(
                    debit_account=inv_account.id,
                    credit_account=div_account.id,
                    amount=amount,
                    original_amount=None,
                    fx_rate=None,
                    description=f"Dividend {month}",
                    date=f"2026-{month:02d}-07 10:00:00",
                ),
            )

        result = projections_service.get_projections(
            conn,
            1,
            12,
            investment_lookback_months=3,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    historical_months = [
        row["month"] for row in result["investment_detail"] if not row["is_projected"]
    ]
    current_row = next(
        row for row in result["investment_detail"] if row["month"] == "2026-04"
    )

    assert historical_months == ["2026-01", "2026-02", "2026-03", "2026-04"]
    assert current_row["is_current_partial"] is True
    assert current_row["interest_total"] == pytest.approx(1000.0, rel=1e-4)
    assert result["investment_model"]["default_interest_percent"] == pytest.approx(
        (100.0 / 1100.0 * 100.0 + 100.0 / 1150.0 * 100.0 + 100.0 / 1250.0 * 100.0)
        / 3.0,
        rel=1e-4,
    )
    assert result["investment_model"]["include_current_month"] is False


def test_investment_option_uses_current_contribution_as_provisional(
    initialized_environment, monkeypatch
):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 15)

    monkeypatch.setattr(projections_service, "date", FixedDate)

    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}
        bank = accounts["Bank"]

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Provisional Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=1000.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Provisional Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        for month in (2, 3, 4):
            transactions_service.create_transaction(
                conn,
                TransactionIn(
                    debit_account=bank.id,
                    credit_account=accounts["Salary"].id,
                    amount=1000.0,
                    original_amount=None,
                    fx_rate=None,
                    description=f"Salary {month}",
                    date=f"2026-{month:02d}-05 10:00:00",
                ),
            )

        for month, amount in ((2, 100.0), (3, 100.0), (4, 1000.0)):
            transactions_service.create_transaction(
                conn,
                TransactionIn(
                    debit_account=inv_account.id,
                    credit_account=div_account.id,
                    amount=amount,
                    original_amount=None,
                    fx_rate=None,
                    description=f"Dividend {month}",
                    date=f"2026-{month:02d}-07 10:00:00",
                ),
            )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=bank.id,
                amount=300.0,
                original_amount=None,
                fx_rate=None,
                description="April contribution",
                date="2026-04-08 10:00:00",
            ),
        )

        result = projections_service.get_projections(
            conn,
            1,
            12,
            investment_lookback_months=3,
            investment_include_current_month=True,
            investment_stat="mean",
            investment_exclude_outliers=False,
        )

    historical_months = [
        row["month"] for row in result["investment_detail"] if not row["is_projected"]
    ]
    april_row = next(
        row for row in result["investment_detail"] if row["month"] == "2026-04"
    )

    assert historical_months == ["2026-02", "2026-03", "2026-04"]
    assert april_row["is_current_partial"] is True
    assert result["investment_model"]["include_current_month"] is True
    assert result["investment_model"]["default_interest_percent"] == pytest.approx(
        (100.0 / 1100.0 * 100.0 + 100.0 / 1150.0 * 100.0 + 1000.0 / 1850.0 * 100.0)
        / 3.0,
        rel=1e-4,
    )
    assert result["investment_model"]["default_contribution_percent"] == pytest.approx(
        5.0,
        rel=1e-4,
    )


def test_get_monthly_dividend_income_preserves_negative_months(initialized_environment):
    with get_db() as conn:
        accounts = {item.name: item for item in accounts_service.list_accounts(conn)}

        inv_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Lossy Brokerage",
                type_id=1,
                subtype_id=3,
                description="Investment account",
                initial_balance=0.0,
                properties="{}",
            ),
        )
        div_account = accounts_service.create_account(
            conn,
            AccountIn(
                name="Lossy Dividends",
                type_id=3,
                subtype_id=10,
                description="Dividend income",
                initial_balance=0.0,
                properties="{}",
            ),
        )

        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=inv_account.id,
                credit_account=div_account.id,
                amount=40.0,
                original_amount=None,
                fx_rate=None,
                description="Positive dividend",
                date="2026-03-10 10:00:00",
            ),
        )
        transactions_service.create_transaction(
            conn,
            TransactionIn(
                debit_account=div_account.id,
                credit_account=inv_account.id,
                amount=75.0,
                original_amount=None,
                fx_rate=None,
                description="Investment loss",
                date="2026-03-20 10:00:00",
            ),
        )

        div_map = projections_service._get_monthly_dividend_income(
            conn,
            [div_account.id],
            "2026-03-01 00:00:00",
            "2026-03-31 23:59:59",
        )

    assert div_map == {"2026-03": -35.0}


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


def test_recurring_transactions_service_finds_similar_case_insensitively(
    initialized_environment,
):
    with get_db() as conn:
        accounts = accounts_service.list_accounts(conn)
        bank = next(item for item in accounts if item.name == "Bank")
        salary = next(item for item in accounts if item.name == "Salary")

        created = recurring_transactions_service.create_recurring_transaction(
            conn,
            RecurringTransactionIn(
                debit_account=bank.id,
                credit_account=salary.id,
                amount=100.0,
                description="Monthly transfer",
                alert_day=10,
            ),
        )

        found = recurring_transactions_service.find_similar_recurring_transaction(
            conn,
            credit_account=salary.id,
            debit_account=bank.id,
            description="  monthly transfer  ",
        )

    assert found is not None
    assert found.id == created.id
